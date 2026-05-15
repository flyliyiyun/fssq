# FSSQ - 玄学选股引擎

**风生水起玄学选股系统** — 个人命盘 × 大势环境 → A股题材推荐

基于八字、紫微斗数、奇门遁甲、西方占星四大体系，融合 SnipeScore 量化选股系统，为投资者提供五行喜忌 + 行业板块共振的选股辅助决策。

## 技术架构

```
用户输入（生辰 / 性别 / 出生地经纬度）
    ↓
Layer 1 — 输入校验
    ↓
Layer 2 — 四柱八字引擎（40%）+ 紫微斗数（30%）+ 奇门遁甲（20%）+ 西方占星（10%）
    ↓
Layer 3 — 五行行业映射
    ↓
Layer 4 — 宏观大势（干支 / 九星 / 占星行运 / A股政策面）
    ↓
Layer 5 — 融合共振打分引擎
    ↓
Layer 6 — 四级输出（年度 / 季度 / 月度 / 置信度评级）
```

## 目录结构

```
src/
├── orchestrator.py           # 主入口，流水线编排
├── constants.py              # 五行/天干/地支常量
├── orchestrator/
│   └── pipeline.py           # 4-Agent 流水线
├── agents/
│   ├── astro_calc/           # 占星排盘 Agent（pyswisseph）
│   ├── cosmic_trend/         # 大势分析 Agent（宏观 + 政策）
│   ├── fusion_engine/        # 融合引擎
│   │   ├── agent.py         # 融合主逻辑
│   │   ├── confidence.py    # 置信度评级
│   │   ├── input_validator.py
│   │   ├── resonance.py     # 共振计算
│   │   ├── template.py      # 10段式报告模板
│   │   └── weighted.py      # 加权融合
│   └── star_hunter/          # SnipeScore 选股集成
├── api/
│   └── main.py               # FastAPI Web 服务（支持上传星座图）
├── frontend/
│   └── index.html            # 前端界面
└── data/
    └── A股所有股票板块分类_含五行属性.csv  # 4636只A股五行数据

docs/
├── dayun_rules.md             # 大运计算规则文档
└── futu_trading_design.md    # 富途实盘交易设计方案

PRD_v4.md                      # 产品需求文档 v4.2
run_pipeline.py                # CLI 入口脚本
requirements.txt               # Python 依赖
Dockerfile                     # Docker 镜像
docker-compose.yml             # Docker Compose
```

## 快速开始

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# CLI 运行（输出 JSON + HTML 报告）
python run_pipeline.py --name "测试" --birth "1974-07-05" --hour 17 --gender male --output ./output
```

### Docker 运行

```bash
docker-compose up --build
# 服务地址：http://localhost:8080
# API 文档：http://localhost:8080/docs
```

### Web 服务

```bash
cd src/api
uvicorn main:app --host 0.0.0.0 --port 8080
```

## 核心参数

| 参数 | 说明 |
|------|------|
| 大运计算 | 支持双模式：`dayun_mode="day_gan"`（默认，日干派）/`"year_gan"`（年干派）|
| 喜用神 | 权重打分法，非单一规则 |
| 日柱/月柱 | 查万年历表，不推算 |
| 时柱 | 五鼠遁口诀公式 |
| 占星排盘 | 需要出生地经纬度（可选，缺省跳过占星部分）|
| 融合权重 | SnipeScore 70% + 玄学 30% × 1.5 放大 |
| 股票池 | 4636只正常A股（.NQ/.BJ 自动过滤）|

## 注意事项

- 本系统为**辅助决策工具**，不构成投资建议
- 所有玄学推演结果仅供参考，请以 SnipeScore 量化评分为准
- 投资有风险，入市需谨慎

## 许可证

MIT License
