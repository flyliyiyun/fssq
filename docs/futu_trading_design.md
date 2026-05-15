# 富途OpenD实盘对接设计文档

> **版本**：v1.0（设计阶段）
> **日期**：2026-05-14
> **前置条件**：FSSQ Pipeline正常运行 + SnipeScore 8维评分可用

---

## 一、架构总览

```
FSSQ Pipeline输出
    │
    ▼
┌──────────────────┐
│  信号决策引擎     │ ← 新增模块
│  SignalEngine    │
└────────┬─────────┘
         │ 买入/卖出/持仓信号
         ▼
┌──────────────────┐
│  风控引擎         │ ← 新增模块
│  RiskController  │
└────────┬─────────┘
         │ 通过风控的交易指令
         ▼
┌──────────────────┐
│  富途API适配层    │ ← 新增模块
│  FutuAdapter     │ → futu-api → OpenD → 交易所
└──────────────────┘
         │
         ▼
    实盘成交回报
```

---

## 二、信号决策引擎 (SignalEngine)

### 2.1 信号来源

| 信号 | 来源 | 触发条件 |
|------|------|----------|
| **BUY** | FSSQ报告 + SnipeScore | 板块五行匹配≥70分 + SnipeScore≥75 + 四级时效=buy + RSI<65 |
| **SELL** | FSSQ报告时效降级 | 四级时效从buy/hold→sell/empty |
| **STOP_LOSS** | 风控引擎 | 个股亏损>8% |
| **TAKE_PROFIT** | 风控引擎 | 个股盈利>20% |
| **REBALANCE** | 月度/季度 | FSSQ报告更新后板块权重变化>15% |

### 2.2 信号结构

```python
@dataclass
class TradeSignal:
    signal_id: str          # UUID
    timestamp: datetime     # 信号产生时间
    action: str             # BUY / SELL / HOLD
    stock_code: str         # "SH.600000" / "SZ.000001"
    stock_name: str         # "浦发银行"
    reason: str             # 原因描述
    confidence: float       # 0-1，信号置信度
    source: str             # "FSSQ_BUY" / "RISK_STOP_LOSS" / "FSSQ_SELL"

    # 数量建议
    suggested_amount: float # 金额（CNY）
    suggested_price: float  # 建议价格（市价/限价）
    order_type: str         # MARKET / LIMIT

    # 元数据
    snipe_score: float      # SnipeScore原始分
    wx_element_score: float # 玄学匹配分
    timing_level: str       # buy/hold/sell/empty
    sector: str             # 所属板块
```

### 2.3 信号生成逻辑

```
每月初（或报告更新时）：
1. 运行FSSQ Pipeline获取最新报告
2. 筛选 timing_level == "buy" 的个股
3. 按最终得分排序（SnipeScore×0.7 + 玄学×0.45）
4. Top N（默认5只）生成BUY信号
5. 已持仓且 timing_level 变为 "sell/empty" → 生成SELL信号
```

---

## 三、风控引擎 (RiskController)

### 3.1 风控规则

| 规则 | 参数 | 动作 |
|------|------|------|
| **单股止损** | 亏损>8% | 市价卖出 |
| **单股止盈** | 盈利>25% | 减半仓（部分止盈） |
| **单股止盈全出** | 盈利>40% | 全部卖出 |
| **总仓位上限** | 总市值/总资金<80% | 拒绝新BUY |
| **单股仓位上限** | 单股/总资金<15% | BUY金额截断 |
| **板块集中度** | 同板块/总资金<30% | 拒绝超限BUY |
| **日亏损上限** | 日亏损>3% | 当日暂停交易 |
| **周亏损上限** | 周亏损>6% | 本周暂停交易 |
| **最大持仓数** | ≤10只 | 满仓后只允许换股 |

### 3.2 风控检查流程

```python
def check_risk(signal: TradeSignal, portfolio: Portfolio) -> RiskDecision:
    # 1. 日/周亏损检查
    if daily_loss > 0.03 or weekly_loss > 0.06:
        return RiskDecision.REJECT("触发日/周亏损限制")

    # 2. 仓位检查
    if signal.action == "BUY":
        if portfolio.total_position_ratio > 0.80:
            return RiskDecision.REJECT("总仓位超80%")
        if portfolio.stock_ratio(signal.stock_code) > 0.15:
            return RiskDecision.REDUCE("单股仓位超15%", max_ratio=0.15)
        if portfolio.sector_ratio(signal.sector) > 0.30:
            return RiskDecision.REJECT("板块集中度超30%")
        if len(portfolio.holdings) >= 10:
            return RiskDecision.REJECT("持仓数已达上限")

    return RiskDecision.APPROVE()
```

### 3.3 止损止盈监控

```
每30秒检查一次持仓盈亏：
  for stock in portfolio.holdings:
      pnl_pct = (current_price - avg_cost) / avg_cost
      if pnl_pct < -0.08: → 止损卖出
      elif pnl_pct > 0.25: → 减半
      elif pnl_pct > 0.40: → 全出
```

---

## 四、富途API适配层 (FutuAdapter)

### 4.1 依赖

```python
from futu import *
# OpenQuoteContext — 行情订阅
# OpenSecTradeContext — A股/港股/美股交易
# TRX_ENV  — 交易环境（真实/模拟）
```

### 4.2 OpenD配置

```python
FUTU_CONFIG = {
    "host": "127.0.0.1",
    "port": 11111,
    "trade_pwd_md5": "<encrypted>",  # 交易密码MD5
    "security_firm": "FUTUSECURITIES",
    "env": TrdEnv.REAL,  # TrdEnv.SIMULATE for 模拟盘
}
```

### 4.3 核心方法

```python
class FutuAdapter:
    def __init__(self, config: dict):
        self.quote_ctx = OpenQuoteContext(host=config["host"], port=config["port"])
        self.trade_ctx = None  # 按需建立

    def connect(self) -> bool:
        """建立连接，订阅行情"""
        ret, _ = self.quote_ctx.get_global_state()
        return ret == RET_OK

    def subscribe(self, stock_codes: list):
        """订阅股票行情"""
        self.quote_ctx.subscribe(stock_codes, [SubType.QUOTE, SubType.K_DAY])

    def get_realtime_price(self, stock_code: str) -> dict:
        """获取实时价格"""
        ret, data = self.quote_ctx.get_stock_quote([stock_code])
        if ret == RET_OK:
            return data.iloc[0].to_dict()
        return {}

    def place_order(self, signal: TradeSignal) -> dict:
        """下单"""
        if not self.trade_ctx:
            self._unlock_trade()

        if signal.action == "BUY":
            ret, order_id = self.trade_ctx.place_order(
                price=signal.suggested_price,
                qty=signal.quantity,
                code=signal.stock_code,
                trd_side=TrdSide.BUY,
                order_type=OrderType.MARKET if signal.order_type == "MARKET" else OrderType.NORMAL,
                trd_env=TrdEnv.REAL
            )
        elif signal.action == "SELL":
            ret, order_id = self.trade_ctx.place_order(
                price=signal.suggested_price,
                qty=signal.quantity,
                code=signal.stock_code,
                trd_side=TrdSide.SELL,
                order_type=OrderType.MARKET if signal.order_type == "MARKET" else OrderType.NORMAL,
                trd_env=TrdEnv.REAL
            )
        return {"ret": ret, "order_id": order_id}

    def get_positions(self) -> list:
        """获取当前持仓"""
        ret, data = self.trade_ctx.position_list_query()
        return data.to_dict('records') if ret == RET_OK else []

    def get_account_balance(self) -> dict:
        """获取账户资金"""
        ret, data = self.trade_ctx.accinfo_query()
        return data.iloc[0].to_dict() if ret == RET_OK else {}
```

### 4.4 A股交易注意事项

| 事项 | 说明 |
|------|------|
| 交易时间 | 周一至周五 9:30-11:30, 13:00-15:00 |
| 涨跌停 | ±10%（ST ±5%），市价单在涨跌停时可能无法成交 |
| T+1 | 当日买入次日才可卖出 |
| 最小单位 | 100股（1手） |
| 手续费 | 佣金（万2.5）+ 印花税（卖出千1）+ 过户费 |

---

## 五、执行流程

### 5.1 月度执行（主力策略）

```
每月1日 9:15（开盘前）:
  1. 运行FSSQ Pipeline（target_year=当前年，含当月时效）
  2. SignalEngine解析报告，生成BUY/SELL信号
  3. RiskController风控检查
  4. FutuAdapter执行：
     a. 先SELL信号（清仓时效降级的）
     b. 后BUY信号（建仓新推荐的）
  5. 记录交易日志
  6. 推送执行结果（飞书/微信）
```

### 5.2 日内风控（被动执行）

```
交易日 9:35 - 15:00 每30秒:
  1. 获取持仓实时价格
  2. 计算各股盈亏百分比
  3. 触发止损/止盈 → 立即执行
  4. 记录+推送
```

### 5.3 手动审批模式（初期）

```
初期不自动执行，仅生成信号+推送：
  1. 信号生成 → 推送到飞书/微信
  2. Christina人工确认 → 回复"执行"/"跳过"
  3. 确认后执行
  4. 运行稳定3个月后切换为半自动（止损自动，买入手动）
  5. 运行稳定6个月后切换为全自动
```

---

## 六、数据模型

### 6.1 交易日志

```python
@dataclass
class TradeLog:
    log_id: str
    timestamp: datetime
    signal_id: str
    stock_code: str
    stock_name: str
    action: str          # BUY / SELL
    order_id: str        # 富途订单号
    price: float         # 成交价
    quantity: int        # 成交量
    amount: float        # 成交金额
    commission: float    # 手续费
    status: str          # FILLED / PARTIAL / FAILED
    source: str          # 信号来源
    notes: str           # 备注
```

### 6.2 持仓状态

```python
@dataclass
class Holding:
    stock_code: str
    stock_name: str
    sector: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    pnl_amount: float
    pnl_pct: float
    buy_date: datetime
    buy_signal_id: str
    timing_level: str    # 当初买入时的时效级别
    snipe_score: float
```

### 6.3 账户快照

```python
@dataclass
class AccountSnapshot:
    timestamp: datetime
    total_assets: float
    cash: float
    market_value: float
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    num_holdings: int
    sector_distribution: dict  # {板块: 占比}
```

---

## 七、文件结构（Phase 4新增）

```
src/
├── trading/                    # 新增交易模块
│   ├── __init__.py
│   ├── signal_engine.py        # 信号决策引擎
│   ├── risk_controller.py      # 风控引擎
│   ├── futu_adapter.py         # 富途API适配层
│   ├── models.py               # 数据模型（TradeSignal, Holding等）
│   ├── scheduler.py            # 定时任务调度
│   └── notifier.py             # 推送通知（飞书/微信）
├── data/
│   └── trade_logs/             # 交易日志存储
│       └── {YYYY-MM-DD}.json
└── config/
    └── trading_config.json     # 交易配置（风控参数、富途连接等）
```

---

## 八、实施步骤

### Step 1：环境搭建（1天）
1. 安装富途OpenD（Docker或本地）
2. 安装futu-api：`pip install futu-api`
3. 配置模拟盘连接
4. 验证行情订阅+查询

### Step 2：FutuAdapter开发（1天）
1. 实现connect/subscribe/get_price
2. 实现place_order（先模拟盘）
3. 实现get_positions/get_balance
4. 单元测试

### Step 3：RiskController开发（0.5天）
1. 实现风控规则检查
2. 实现止盈止损监控
3. 单元测试

### Step 4：SignalEngine开发（1天）
1. 解析FSSQ报告输出
2. 生成标准化TradeSignal
3. 月度/触发式信号生成

### Step 5：集成测试（1天）
1. 端到端：FSSQ报告→信号→风控→下单
2. 模拟盘验证
3. 通知推送验证

### Step 6：上线策略
1. **第1个月**：信号推送+手动执行
2. **第2-3个月**：止损自动+买入手动
3. **第4个月起**：全自动化（风控兜底）

---

## 九、安全与合规

1. **交易密码**：通过环境变量注入，不写入代码/配置文件
2. **操作日志**：所有交易操作记录JSON日志，可追溯
3. **模拟盘先行**：先在模拟盘运行至少1个月，验证策略稳定性
4. **人工审批**：初期所有交易需人工确认，防止策略bug导致资金损失
5. **仓位控制**：初始资金建议不超过总资产10%，逐步加仓
