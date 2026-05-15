"""
snipe_integration.py — SnipeScore对接模块 v3.1
===============================================
对玄学推荐板块的全量候选股票进行SnipeScore评分，
通过腾讯行情API批量获取实时数据，并发计算8维评分，
融合玄学+量化输出最终Top推荐。

核心公式（PRD v3.1 §5.1 E009）:
  最终得分 = SnipeScore × 0.70 + 玄学微调分 × 0.30 × 1.5

关键设计（v3.0 vs v2.0）:
  - v2.0: 只对20只龙头股评分（A_SHARE_LEADERS）
  - v3.0: 对板块全量候选股票评分（可达2000只）
  - v3.1: 腾讯行情批量查询为主力数据源（比AKShare更稳定）
  - 数据源: 腾讯行情 → AKShare补充 → 并发K线

多数据源兜底链（PRD v3.1 §5.2 防错机制）:
  腾讯行情批量 → AKShare实时 → 东方财富K线 → 新浪日K
  所有数据源失败 → 报错，不允许降级玄学模式
"""
import os
import sys
import time
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# 绕过系统代理
for _k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY']:
    os.environ.pop(_k, None)

# ── 加载SnipeScore核心（东方财富8维评分）─────────────────
_SNIPE_PATH = Path("/Users/christina_amoy/WorkBuddy/20260423102645")
if _SNIPE_PATH.exists() and str(_SNIPE_PATH) not in sys.path:
    sys.path.insert(0, str(_SNIPE_PATH))

try:
    from ai_rotation_monitor_em import (
        calculate_snipe_score,
        fetch_em_batch_quotes,
        fetch_em_kline,
        code_to_em_secid,
        safe_float,
        normalize_change,
        calculate_rsi,
        SNIPE_WEIGHTS,
        _http_session,
    )
    _SNIPE_OK = True
except ImportError as e:
    _SNIPE_OK = False
    _IMPORT_ERROR = str(e)

# ── 日志 ────────────────────────────────────────────────
_log = logging.getLogger("snipe_integration")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
_log.addHandler(_handler)
_log.setLevel(logging.INFO)

# ── A股板块龙头股池（兜底补充：当候选股票行情数据缺失时补充）──────────
A_SHARE_LEADERS: List[Tuple[str, str, str, str]] = [
    # 房地产
    ("000002.SZ", "房地产", "万科A", "a_share"),
    ("600048.SH", "房地产", "保利发展", "a_share"),
    ("600266.SH", "房地产", "城建发展", "a_share"),
    ("600383.SH", "房地产", "金地集团", "a_share"),
    ("001979.SZ", "房地产", "招商蛇口", "a_share"),
    # 建筑建材
    ("600585.SH", "建筑建材", "海螺水泥", "a_share"),
    ("601668.SH", "建筑建材", "中国建筑", "a_share"),
    ("601390.SH", "建筑建材", "中国中铁", "a_share"),
    ("601186.SH", "建筑建材", "中国铁建", "a_share"),
    ("002271.SZ", "建筑建材", "东方雨虹", "a_share"),
    # 银行
    ("601398.SH", "银行", "工商银行", "a_share"),
    ("601939.SH", "银行", "建设银行", "a_share"),
    ("600036.SH", "银行", "招商银行", "a_share"),
    ("601166.SH", "银行", "兴业银行", "a_share"),
    ("600000.SH", "银行", "浦发银行", "a_share"),
    # 保险
    ("601318.SH", "保险", "中国平安", "a_share"),
    ("601601.SH", "保险", "中国太保", "a_share"),
    ("601628.SH", "保险", "中国人寿", "a_share"),
    # 有色金属
    ("601899.SH", "有色金属", "紫金矿业", "a_share"),
    ("603993.SH", "有色金属", "洛阳钼业", "a_share"),
    ("000060.SZ", "有色金属", "中金岭南", "a_share"),
    ("000630.SZ", "有色金属", "铜陵有色", "a_share"),
    # 白酒
    ("000858.SZ", "白酒", "五粮液", "a_share"),
    ("600519.SH", "白酒", "贵州茅台", "a_share"),
    ("000568.SZ", "白酒", "泸州老窖", "a_share"),
    # 食品饮料
    ("600887.SH", "食品饮料", "伊利股份", "a_share"),
    ("002714.SZ", "食品饮料", "牧原股份", "a_share"),
    # 医药
    ("600276.SH", "医药", "恒瑞医药", "a_share"),
    ("000538.SZ", "医药", "云南白药", "a_share"),
    ("603259.SH", "医药", "药明康德", "a_share"),
    # 券商
    ("600030.SH", "券商", "中信证券", "a_share"),
    ("000776.SZ", "券商", "广发证券", "a_share"),
    ("601211.SH", "券商", "国泰君安", "a_share"),
    # 军工
    ("601989.SH", "军工", "中国重工", "a_share"),
    ("000733.SZ", "军工", "振华科技", "a_share"),
    # 半导体/AI
    ("688256.SH", "半导体AI", "寒武纪", "a_share"),
    ("688981.SH", "半导体AI", "中芯国际", "a_share"),
    ("603986.SH", "半导体AI", "兆易创新", "a_share"),
    ("002371.SZ", "半导体AI", "北方华创", "a_share"),
    ("688012.SH", "半导体AI", "中微公司", "a_share"),
    # 新能源
    ("600438.SH", "新能源", "通威股份", "a_share"),
    ("002594.SZ", "新能源", "比亚迪", "a_share"),
    ("300750.SZ", "新能源", "宁德时代", "a_share"),
    # 通信
    ("600050.SH", "通信", "中国联通", "a_share"),
    ("601728.SH", "通信", "中国电信", "a_share"),
    # 互联网传媒
    ("300058.SZ", "互联网传媒", "蓝色光标", "a_share"),
    ("603444.SH", "互联网传媒", "吉比特", "a_share"),
]


# ══════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════

def _normalize_meta_score(score: float) -> float:
    return max(0.0, min(100.0, float(score)))


def _code_to_tx(code: str) -> str:
    """标准代码 → 腾讯行情代码"""
    if code.endswith(".SZ"):
        return f"sz{code.replace('.SZ', '')}"
    elif code.endswith(".SH"):
        return f"sh{code.replace('.SH', '')}"
    elif code.endswith(".BJ"):
        return f"bj{code.replace('.BJ', '')}"
    return code


def _code_from_tx(tx_code: str) -> str:
    """腾讯行情代码 → 标准代码"""
    if tx_code.startswith('sz'):
        return f"{tx_code[2:]}.SZ"
    elif tx_code.startswith('sh'):
        return f"{tx_code[2:]}.SH"
    elif tx_code.startswith('bj'):
        return f"{tx_code[2:]}.BJ"
    return tx_code


def _fetch_kline_for_stock(code: str) -> Optional[Dict]:
    """
    通过东方财富K线API获取单只股票K线数据
    （sandbox环境下东方财富API不可用，返回None由AKShare兜底）

    Args:
        code: 标准格式股票代码 ["000002.SZ", "600048.SH", "830779.BJ"]

    Returns:
        {week_change_pct, volume_ratio, rsi_14d, sma20} 或 None
    """
    # 判断市场
    if code.endswith(".BJ"):
        # 北交所：东方财富不支持，跳过
        return None
    elif code.endswith(".SH") or code.endswith(".SZ"):
        market = "a_share"
    else:
        return None

    try:
        # 转换代码为东方财富secid格式
        secid = code_to_em_secid(code, market)
        df = fetch_em_kline(secid, lmt=30)
        if df is None or len(df) < 10:
            return None

        closes = df['close'].astype(float)
        volumes = df['volume'].astype(float)

        # 5日涨幅
        week_ago = float(closes.iloc[-6]) if len(closes) >= 6 else float(closes.iloc[0])
        week_chg = (float(closes.iloc[-1]) / week_ago - 1) * 100 if week_ago > 0 else 0.0

        # 量比（今日成交量/前5日均量）
        avg_vol = float(volumes.iloc[-6:-1].mean()) if len(volumes) >= 6 else float(volumes.mean())
        today_vol = float(volumes.iloc[-1])
        vol_ratio = today_vol / avg_vol if avg_vol > 0 else 1.0

        # RSI(14)
        rsi = calculate_rsi(closes, period=14)

        # SMA20
        sma20 = float(closes.iloc[-20:].mean()) if len(closes) >= 20 else float(closes.mean())

        return {
            "week_change_pct": week_chg,
            "volume_ratio": vol_ratio,
            "rsi_14d": rsi,
            "sma20": sma20,
            "_kline_source": "em_kline",
        }
    except Exception:
        return None


# ══════════════════════════════════════════════════════════
# v3.1 核心：腾讯行情批量查询（主力数据源）
# ══════════════════════════════════════════════════════════

def _fetch_batch_via_tx(codes: List[str], batch_size: int = 50) -> Dict[str, Dict]:
    """
    通过腾讯行情API批量获取股票实时数据（v3.1主力数据源）

    腾讯API一次最多查询约50只股票，分批并发请求，
    比AKShare更稳定，比东方财富更快。

    Args:
        codes: 标准格式股票代码列表 ["000002.SZ", "600048.SH", ...]
        batch_size: 每批数量

    Returns:
        {标准代码: {name, current_price, day_change_pct, yesterday_close, ...}}
    """
    import requests

    _log.info(f"  📡 [主力] 腾讯行情批量查询 ({len(codes)}只)...")

    result = {}
    all_tx_codes = [_code_to_tx(c) for c in codes]

    # 分批处理
    for i in range(0, len(all_tx_codes), batch_size):
        batch = all_tx_codes[i:i+batch_size]
        batch_codes_std = codes[i:i+batch_size]
        tx_param = ','.join(batch)

        try:
            url = f"https://qt.gtimg.cn/q={tx_param}"
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                _log.warning(f"     腾讯批次{i//batch_size+1} HTTP {resp.status_code}")
                continue

            lines = resp.text.strip().split('\n')
            for line in lines:
                # 解析: v_sz000002="51~名称~代码~现价~..."
                m = re.search(r'v_(\w+)="([^"]+)"', line)
                if not m:
                    continue
                tx_code = m.group(1)
                parts = m.group(2).split('~')
                if len(parts) < 50:
                    continue
                try:
                    std_code = _code_from_tx(tx_code)
                    current_price = float(parts[3]) if parts[3] else 0
                    yesterday_close = float(parts[4]) if parts[4] else 0
                    today_open = float(parts[5]) if parts[5] else 0
                    day_change_pct = float(parts[32]) if parts[32] else 0
                    high = float(parts[33]) if parts[33] else 0
                    low = float(parts[34]) if parts[34] else 0
                    volume = float(parts[36]) if parts[36] else 0
                    amount = float(parts[37]) if parts[37] else 0
                    pe_ratio = float(parts[39]) if parts[39] else 0

                    result[std_code] = {
                        "name": parts[1].strip(),
                        "current_price": current_price,
                        "yesterday_close": yesterday_close,
                        "today_open": today_open,
                        "day_change_pct": day_change_pct,
                        "high": high,
                        "low": low,
                        "volume": volume,
                        "amount": amount,
                        "pe_ratio": pe_ratio,
                        "_quote_source": "tx_batch",
                    }
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            _log.warning(f"     腾讯批次{i//batch_size+1}异常: {e}")
            continue

    _log.info(f"     腾讯行情: {len(result)}/{len(codes)}成功 ✅")
    return result


# ══════════════════════════════════════════════════════════
# AKShare补充数据源（腾讯失败时使用）
# ══════════════════════════════════════════════════════════

def _fetch_via_akshare(codes: List[str]) -> Dict[str, Dict]:
    """
    通过AKShare获取候选股票实时行情（腾讯失败时兜底）
    注意：AKShare的stock_zh_a_spot()数据不完整，仅作补充使用
    """
    try:
        import akshare as ak

        _log.info(f"  📡 [备选] AKShare实时行情...")
        df = ak.stock_zh_a_spot()

        # 提取相关代码
        code_raw_list = set()
        for code in codes:
            code_raw = code.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
            code_raw_list.add(code_raw.upper())

        result = {}
        for _, row in df.iterrows():
            code_raw = str(row.get('代码', '')).strip().upper()
            if code_raw not in code_raw_list:
                continue
            try:
                # 找到对应标准代码
                std_code = None
                for c in codes:
                    if c.replace('.SZ', '').replace('.SH', '').replace('.BJ', '') == code_raw:
                        std_code = c
                        break
                if not std_code:
                    continue

                current_price = float(row.get('最新价', 0) or 0)
                yesterday_close = float(row.get('昨收', 0) or 0)
                day_change_pct = float(row.get('涨跌幅', 0) or 0)
                today_open = float(row.get('今开', 0) or 0)
                high = float(row.get('最高', 0) or 0)
                low = float(row.get('最低', 0) or 0)
                volume = float(row.get('成交量', 0) or 0)
                amount = float(row.get('成交额', 0) or 0)

                result[std_code] = {
                    "name": str(row.get('名称', '')).strip(),
                    "current_price": current_price,
                    "yesterday_close": yesterday_close,
                    "today_open": today_open,
                    "day_change_pct": day_change_pct,
                    "high": high,
                    "low": low,
                    "volume": volume,
                    "amount": amount,
                    "pe_ratio": 0,
                    "_quote_source": "akshare",
                }
            except (ValueError, KeyError):
                continue

        if result:
            _log.info(f"     AKShare补充: {len(result)}只 ✅")
        return result
    except Exception as e:
        _log.warning(f"     AKShare备选失败: {e}")
        return {}


# ══════════════════════════════════════════════════════════
# K线数据获取（并发）
# ══════════════════════════════════════════════════════════

def _fetch_akshare_daykline(code: str) -> Optional[Dict]:
    """
    通过AKShare获取单只股票日K线数据
    （东方财富K线不可用时的替代方案）
    """
    try:
        import akshare as ak
        import pandas as pd

        # 转换代码格式
        raw = code.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
        if code.startswith('6') or code.startswith('688'):
            ak_symbol = f"sh{raw}"
        else:
            ak_symbol = f"sz{raw}"

        df = ak.stock_zh_a_daily(symbol=ak_symbol, adjust="qfq")
        if df is None or len(df) < 10:
            return None

        df = df.tail(30)
        closes = df['close'].astype(float)
        volumes = df['volume'].astype(float)

        # 5日涨幅
        week_ago = float(closes.iloc[-6]) if len(closes) >= 6 else float(closes.iloc[0])
        week_chg = (float(closes.iloc[-1]) / week_ago - 1) * 100 if week_ago > 0 else 0.0

        # 量比
        avg_vol = float(volumes.iloc[-6:-1].mean()) if len(volumes) >= 6 else float(volumes.mean())
        today_vol = float(volumes.iloc[-1])
        vol_ratio = today_vol / avg_vol if avg_vol > 0 else 1.0

        # RSI
        rsi = calculate_rsi(closes, period=14)

        # SMA20
        sma20 = float(closes.iloc[-20:].mean()) if len(closes) >= 20 else float(closes.mean())

        return {
            "week_change_pct": week_chg,
            "volume_ratio": vol_ratio,
            "rsi_14d": rsi,
            "sma20": sma20,
            "_kline_source": "akshare_daykline",
        }
    except Exception:
        return None


def _enrich_single_stock_concurrent(
    code: str,
    stock_info: Dict,
    snipe_weight: float = 0.70,
    spot_data: Optional[Dict] = None,
) -> Optional[Dict]:
    """
    并发处理单只股票：获取K线数据 → 计算SnipeScore → 融合评分

    K线获取优先级：
      1. 东方财富K线（最快，但sandbox环境不可用）
      2. AKShare日K线（较慢，但sandbox可用）

    Args:
        code: 股票代码
        stock_info: star-hunter传来的股票信息
        snipe_weight: SnipeScore权重
        spot_data: 腾讯实时行情数据（已在主线程获取）

    Returns:
        增强后的股票dict，或None（无有效数据时）
    """
    meta_score = stock_info.get("match_score", stock_info.get("current_score", 50))
    quote = dict(spot_data) if spot_data else {}

    # 尝试东方财富K线（sandbox通常不可用）
    kline_data = None
    if _SNIPE_OK and spot_data and spot_data.get("current_price", 0) > 0:
        kline_data = _fetch_kline_for_stock(code)
        if kline_data:
            quote.update(kline_data)
            time.sleep(0.1)

    # 东方财富不可用时，尝试AKShare日K线（sandbox可用）
    # 但注意：AKShare日K较慢，不在并发中使用，仅对Top候选使用
    # 这里的并发函数不获取AKShare（会太慢）
    # AKShare K线在主线程对Top20补充获取

    if not quote:
        return None

    # 计算SnipeScore
    if _SNIPE_OK and quote.get("current_price", 0) > 0:
        try:
            snipe_result = calculate_snipe_score(quote)
        except Exception:
            snipe_result = None
    else:
        snipe_result = None

    return _enrich_stock(stock_info, snipe_result, snipe_weight, quote)


def _enrich_stock(
    stock: Dict,
    snipe_result: Optional[Dict],
    snipe_weight: float,
    raw_data: Optional[Dict] = None,
) -> Dict:
    """为单只股票注入SnipeScore数据"""
    meta_score = stock.get("match_score", stock.get("current_score", 50))

    if snipe_result is None:
        result = dict(stock)
        result.update({
            "snipe_score": 0,
            "snipe_available": False,
            "final_score": round(_normalize_meta_score(meta_score) * 0.30 * 1.5, 1),
            "snipe_detail": None,
            "_no_snipe": True,
            "_quote_source": raw_data.get("_quote_source", "unknown") if raw_data else "none",
        })
        return result

    final = calculate_final_score(
        snipe_score=snipe_result["snipe_score"],
        meta_score=meta_score,
        snipe_weight=snipe_weight,
    )

    result = dict(stock)
    result.update({
        "current_price": raw_data.get("current_price", 0) if raw_data else 0,
        "day_change_pct": raw_data.get("day_change_pct", 0) if raw_data else 0,
        "week_change_pct": raw_data.get("week_change_pct", 0) if raw_data else 0,
        "rsi_14d": raw_data.get("rsi_14d", 50) if raw_data else 50,
        "volume_ratio": raw_data.get("volume_ratio", 1) if raw_data else 1,
        "snipe_score": final["snipe_score"],
        "snipe_available": True,
        "final_score": final["final_score"],
        "snipe_contribution": final["snipe_contribution"],
        "meta_contribution": final["meta_contribution"],
        "_quote_source": raw_data.get("_quote_source", "unknown") if raw_data else "unknown",
        "_kline_source": raw_data.get("_kline_source", "none") if raw_data else "none",
        "snipe_detail": {
            "动量分": snipe_result["scores"].get("动量分", 0),
            "RSI分": snipe_result["scores"].get("RSI分", 0),
            "量比分": snipe_result["scores"].get("量比分", 0),
            "趋势分": snipe_result["scores"].get("趋势分", 0),
            "资金分": snipe_result["scores"].get("资金分", 0),
            "滞涨分": snipe_result["scores"].get("滞涨分", 0),
            "估值分": snipe_result["scores"].get("估值分", 0),
            "催化剂分": snipe_result["scores"].get("催化剂分", 0),
        },
        "_no_snipe": False,
    })
    return result


def calculate_final_score(
    snipe_score: float,
    meta_score: float,
    snipe_weight: float = 0.70,
) -> Dict[str, Any]:
    """计算最终综合得分"""
    meta_contribution = _normalize_meta_score(meta_score) * 0.30 * 1.5
    snipe_contribution = float(snipe_score) * snipe_weight
    final_score = min(100.0, snipe_contribution + meta_contribution)
    return {
        "snipe_score": round(float(snipe_score), 1),
        "meta_score": round(_normalize_meta_score(meta_score), 1),
        "final_score": round(final_score, 1),
        "snipe_contribution": round(snipe_contribution, 1),
        "meta_contribution": round(meta_contribution, 1),
        "snipe_weight": snipe_weight,
    }


# ══════════════════════════════════════════════════════════
# v3.1 核心：全量股票SnipeScore评分
# ══════════════════════════════════════════════════════════

def enrich_with_snipescore_full(
    stocks: List[Dict],
    fusion_result: Optional[Dict] = None,
    target_year: int = 2026,
    snipe_weight: float = 0.70,
    max_workers: int = 10,
    batch_limit: int = 2000,
) -> List[Dict]:
    """
    v3.1 核心：对全量候选股票进行SnipeScore评分

    数据获取流程（v3.1优先级）：
      1. 腾讯行情批量查询（主力，最稳定）
      2. AKShare补充（腾讯失败时）
      3. 东方财富K线并发获取（RSI/动量/量比）
      4. 所有数据源失败 → RuntimeError

    Args:
        stocks: star-hunter输出的全量候选股票列表
        fusion_result: fusion-engine输出
        target_year: 目标年份
        snipe_weight: SnipeScore权重
        max_workers: 并发线程数
        batch_limit: 最大处理股票数

    Returns:
        增强后的Top股票列表（按final_score排序）

    Raises:
        RuntimeError: 所有数据源均不可用时
    """
    if not stocks:
        return []

    if not _SNIPE_OK:
        raise RuntimeError(
            "[SnipeScore] 无法加载SnipeScore核心模块。\n"
            "请确保 /Users/christina_amoy/WorkBuddy/20260423102645/ai_rotation_monitor_em.py 存在。"
        )

    if len(stocks) > batch_limit:
        _log.warning(f"  ⚠️ 候选股票{len(stocks)}只超过批次限制{batch_limit}，自动截断")
        stocks = stocks[:batch_limit]

    total_input = len(stocks)
    _log.info(f"\n{'='*50}")
    _log.info(f"SnipeScore全量评分 v3.1")
    _log.info(f"  候选股票: {total_input}只（玄学候选池）")
    _log.info(f"  SnipeScore权重: {snipe_weight:.0%}")
    _log.info(f"{'='*50}")

    # Step 1: 构建代码→股票信息映射
    code_to_stock = {}
    for s in stocks:
        code = s.get("code", "")
        if code:
            code_to_stock[code] = s

    # Step 2: 补充板块龙头
    board_leaders = {}
    for scode, sector, name, _mkt in A_SHARE_LEADERS:
        if sector not in board_leaders:
            board_leaders[sector] = (scode, name)

    added = 0
    for s in stocks:
        board = s.get("board", "")
        for sector, (scode, name) in board_leaders.items():
            if sector in board and scode not in code_to_stock:
                code_to_stock[scode] = {
                    "code": scode, "name": name, "board": sector,
                    "match_score": s.get("match_score", 50),
                    "current_score": s.get("current_score", 50),
                    "_from_leader": True,
                }
                added += 1

    if added > 0:
        _log.info(f"  补充板块龙头: {added}只")

    all_codes = list(code_to_stock.keys())
    _log.info(f"  待评分股票总数: {len(all_codes)}只")

    # Step 3: 腾讯行情批量获取（主力数据源）
    spot_data = _fetch_batch_via_tx(all_codes, batch_size=50)

    # Step 4: AKShare补充（腾讯不足时）
    if len(spot_data) < len(all_codes) * 0.5:
        ak_data = _fetch_via_akshare(all_codes)
        for code, data in ak_data.items():
            if code not in spot_data:
                spot_data[code] = data

    # Step 5: 所有数据源失败 → 报错
    if not spot_data:
        error_msg = (
            f"[SnipeScore v3.1] 所有数据源均不可用：\n"
            f"  1. 腾讯行情 (qt.gtimg.cn)\n"
            f"  2. AKShare (stock_zh_a_spot)\n"
            f"候选股票: {all_codes[:5]}... (共{len(all_codes)}只)\n"
            f"请检查网络连接或稍后重试。"
        )
        _log.error(error_msg)
        raise RuntimeError(error_msg)

    _log.info(f"  实时行情匹配: {len(spot_data)}/{len(all_codes)}只 ({len(spot_data)*100//len(all_codes)}%)")

    # Step 6: 并发获取K线数据（RSI/动量/量比）
    _log.info(f"  📡 并发获取K线数据（RSI/动量/量比）...")
    kline_start = time.time()

    enriched = []
    done_count = 0

    def _process_code(code):
        stock_info = code_to_stock[code]
        quote = spot_data.get(code, {})

        # 尝试K线获取
        kline_data = None
        if _SNIPE_OK and code in spot_data:
            kline_data = _fetch_kline_for_stock(code)
            if kline_data:
                quote = dict(quote)
                quote.update(kline_data)
                time.sleep(0.1)

        # 如果没有实时行情且没有K线 → 跳过
        if not quote:
            return None

        # 计算SnipeScore
        snipe_result = None
        if _SNIPE_OK and quote.get("current_price", 0) > 0:
            try:
                snipe_result = calculate_snipe_score(quote)
            except Exception:
                pass

        return _enrich_stock(stock_info, snipe_result, snipe_weight, quote)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_code, code): code for code in all_codes}
        for future in as_completed(futures):
            done_count += 1
            if done_count % 300 == 0:
                _log.info(f"     进度: {done_count}/{len(all_codes)} ({done_count*100//len(all_codes)}%)")
            try:
                result = future.result(timeout=20)
                if result is not None:
                    enriched.append(result)
            except Exception as e:
                code = futures[future]
                _log.debug(f"     {code} 处理异常: {e}")

    kline_elapsed = time.time() - kline_start

    # Step 7: 对Top30补充AKShare日K线（sandbox环境下东方财富K线不可用，用AKShare替代）
    # 仅对最终Top30补充详细K线指标（耗时可控：30×0.6s≈18秒）
    if len(enriched) >= 20:
        _log.info(f"  📡 补充Top30的AKShare日K线（RSI/动量/量比）...")
        kline_start2 = time.time()
        top30_codes = [s["code"] for s in enriched[:30]]
        ak_kline_ok = 0
        for i, code in enumerate(top30_codes):
            # 找enriched中的索引
            for j, s in enumerate(enriched[:30]):
                if s["code"] == code:
                    if not s.get("snipe_available"):
                        continue
                    kline = _fetch_akshare_daykline(code)
                    if kline:
                        # 更新quote和snipe_result
                        enriched[j]["rsi_14d"] = kline["rsi_14d"]
                        enriched[j]["week_change_pct"] = kline["week_change_pct"]
                        enriched[j]["volume_ratio"] = kline["volume_ratio"]
                        enriched[j]["_kline_source"] = "akshare_daykline"

                        # 重新计算SnipeScore
                        quote_for_rescore = {
                            "symbol": code,
                            "name": s.get("name", ""),
                            "current_price": s.get("current_price", 0),
                            "yesterday_close": s.get("yesterday_close", 0),
                            "day_change_pct": s.get("day_change_pct", 0),
                            "high": s.get("high", 0),
                            "low": s.get("low", 0),
                            "today_open": s.get("today_open", 0),
                            "volume": s.get("volume", 0),
                            "amount": s.get("amount", 0),
                            "pe_ratio": s.get("pe_ratio", 0),
                            "week_change_pct": kline["week_change_pct"],
                            "rsi_14d": kline["rsi_14d"],
                            "volume_ratio": kline["volume_ratio"],
                            "sma20": kline["sma20"],
                        }
                        if _SNIPE_OK:
                            try:
                                new_snipe = calculate_snipe_score(quote_for_rescore)
                                meta = s.get("match_score", 50)
                                new_final = calculate_final_score(
                                    new_snipe["snipe_score"], meta, snipe_weight
                                )
                                enriched[j]["snipe_score"] = new_final["snipe_score"]
                                enriched[j]["final_score"] = new_final["final_score"]
                                enriched[j]["snipe_contribution"] = new_final["snipe_contribution"]
                                enriched[j]["snipe_detail"] = {
                                    "动量分": new_snipe["scores"].get("动量分", 0),
                                    "RSI分": new_snipe["scores"].get("RSI分", 0),
                                    "量比分": new_snipe["scores"].get("量比分", 0),
                                    "趋势分": new_snipe["scores"].get("趋势分", 0),
                                    "资金分": new_snipe["scores"].get("资金分", 0),
                                    "滞涨分": new_snipe["scores"].get("滞涨分", 0),
                                    "估值分": new_snipe["scores"].get("估值分", 0),
                                    "催化剂分": new_snipe["scores"].get("催化剂分", 0),
                                }
                                ak_kline_ok += 1
                            except Exception:
                                pass
                    break
            if (i + 1) % 10 == 0:
                _log.info(f"     AKShare K线进度: {i+1}/30")

        # 重新排序（按更新后的final_score）
        enriched.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        for i, s in enumerate(enriched):
            s["rank"] = i + 1
        kline_elapsed2 = time.time() - kline_start2
        _log.info(f"     AKShare K线: {ak_kline_ok}/30成功，额外耗时{kline_elapsed2:.1f}秒")

    # 统计
    enriched.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    for i, s in enumerate(enriched):
        s["rank"] = i + 1

    valid_count = sum(1 for s in enriched if s.get("snipe_available"))
    zero_count = len(enriched) - valid_count

    _log.info(f"\n{'='*50}")
    _log.info(f"SnipeScore全量评分完成")
    _log.info(f"  有效SnipeScore: {valid_count}只 ✅")
    _log.info(f"  无行情数据: {zero_count}只 ⚠️")
    _log.info(f"  最终Top5推荐:")
    for i, s in enumerate(enriched[:5]):
        src = s.get('_quote_source', '')[:6]
        ksrc = s.get('_kline_source', '')[:6]
        _log.info(f"    {i+1}. {s['name']}({s['code']}) "
                  f"玄学{s.get('match_score','?')} + SnipeScore{s.get('snipe_score','?')} "
                  f"→ 最终{s.get('final_score','?')} [{src}/{ksrc}]")

    return enriched


# ── 兼容层（v2.0签名）─────────────────────────────
def enrich_with_snipescore(
    stocks: List[Dict],
    fusion_result: Optional[Dict] = None,
    target_year: int = 2026,
    snipe_weight: float = 0.70,
) -> List[Dict]:
    return enrich_with_snipescore_full(
        stocks=stocks, fusion_result=fusion_result,
        target_year=target_year, snipe_weight=snipe_weight,
    )


# ══════════════════════════════════════════════════════════
# CLI测试
# ══════════════════════════════════════════════════════════
def main():
    print("\n" + "=" * 60)
    print("SnipeScore全量评分测试 (v3.1 - 腾讯行情为主力)")
    print("=" * 60)

    if not _SNIPE_OK:
        print(f"❌ 无法加载SnipeScore核心: {_IMPORT_ERROR}")
        return

    # 模拟玄学候选：推荐板块内每板块取50只
    sys.path.insert(0, "/Users/christina_amoy/WorkBuddy/玄学合集/src")
    from constants import load_stock_pool

    pool = load_stock_pool()
    board_samples = defaultdict(list)
    for s in pool:
        if s["board"]:
            board_samples[s["board"]].append(s)

    test_stocks = []
    for board, stocks in list(board_samples.items())[:10]:
        test_stocks.extend(stocks[:50])

    print(f"\n测试候选: {len(test_stocks)}只")
    print()

    try:
        start = time.time()
        enriched = enrich_with_snipescore_full(test_stocks, {}, target_year=2026)
        elapsed = time.time() - start

        print(f"\n{'='*60}")
        print(f"Top20 SnipeScore排名:")
        print(f"{'#':<4} {'代码':<12} {'名称':<8} {'玄学':<5} {'Snipe':<5} {'最终':<5} {'RSI':<5} {'涨跌幅':<7} {'来源'}")
        print(f"{'-'*60}")
        for s in enriched[:20]:
            src = s.get('_quote_source', '')[:6]
            print(f"{s['rank']:<4} {s['code']:<12} {s['name']:<8} "
                  f"{s.get('match_score', 0):<5.0f} {s.get('snipe_score', 0):<5.0f} "
                  f"{s.get('final_score', 0):<5.1f} {s.get('rsi_14d', 0):<5.0f} "
                  f"{s.get('day_change_pct', 0):<7.2f} {src}")

        print(f"\n✅ 全量评分: {len(enriched)}只，耗时{elapsed:.1f}秒")
    except RuntimeError as e:
        print(f"\n❌ 失败: {e}")


if __name__ == "__main__":
    main()
