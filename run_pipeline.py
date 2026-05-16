#!/usr/bin/env python3
"""
FSSQ run_pipeline.py — 端到端Pipeline统一入口
============================================
串联4个Agent: astro-calc → cosmic-trend → fusion-engine + star-hunter → HTML报告

用法:
  # 1974男命（Golden Test Case）
  python3 run_pipeline.py --birth 1974-07-05 --hour 17 --gender 男 --place 开封 --year 2026 --current 旧金山

  # 只指定必需参数
  python3 run_pipeline.py --birth 1990-05-15 --hour 8 --gender 女

  # 输出到指定目录
  python3 run_pipeline.py --birth 1974-07-05 --hour 17 --gender 男 --place 开封 --year 2026 --output ./output

选项:
  --birth     出生日期 (YYYY-MM-DD)  [必需]
  --hour      出生时辰 (0-23)         [必需]
  --gender    性别 (男/女)            [必需]
  --place     出生地                  [可选，默认空]
  --year      目标年份                [可选，默认当前年份]
  --current   现居地                  [可选]
  --lat       出生地纬度              [可选，用于占星]
  --lon       出生地经度              [可选，用于占星]
  --output    输出目录                [可选，默认 ./output]
  --snipe     是否对接SnipeScore       [可选，默认True]

依赖:
  pip install requests pandas numpy
"""
import sys
import os
import json
import argparse
import time
from datetime import datetime
from pathlib import Path

# ── 路径设置 ──────────────────────────────────────────────
_SRC_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(_SRC_ROOT))
sys.path.insert(0, str(_SRC_ROOT / "src"))

# 尝试添加AI_rotation路径（SnipeScore依赖）
_AI_ROTATION = Path("/Users/christina_amoy/WorkBuddy/20260423102645")
if _AI_ROTATION.exists():
    sys.path.insert(0, str(_AI_ROTATION))

OUTPUT_DIR = _SRC_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── 预置出生地经纬度表 ──────────────────────────────────
CITY_COORDS = {
    "开封": (34.79, 114.35),
    "厦门": (24.48, 118.10),
    "深圳": (22.54, 114.06),
    "北京": (39.90, 116.40),
    "上海": (31.23, 121.47),
    "广州": (23.13, 113.26),
    "杭州": (30.27, 120.15),
    "成都": (30.67, 104.07),
    "武汉": (30.58, 114.29),
    "南京": (32.06, 118.79),
    "西安": (34.27, 108.95),
    "旧金山": (37.77, -122.42),
    "纽约": (40.71, -74.01),
    "洛杉矶": (34.05, -118.24),
    "香港": (22.32, 114.17),
    "台北": (25.03, 121.57),
}


# ══════════════════════════════════════════════════════════
# Agent 加载
# ══════════════════════════════════════════════════════════
def load_agents():
    """加载4个Agent，返回加载状态"""
    status = {}

    # Agent 1: astro-calc
    try:
        from agents.astro_calc.agent import AstroCalc
        status["astro-calc"] = ("ok", AstroCalc)
    except ImportError as e:
        status["astro-calc"] = ("fail", str(e))

    # Agent 2: cosmic-trend
    try:
        from agents.cosmic_trend.agent import CosmicTrend
        status["cosmic-trend"] = ("ok", CosmicTrend)
    except ImportError as e:
        status["cosmic-trend"] = ("fail", str(e))

    # Agent 3: fusion-engine
    try:
        from agents.fusion_engine.agent import FusionEngine
        from agents.fusion_engine.template import generate_html
        status["fusion-engine"] = ("ok", (FusionEngine, generate_html))
    except ImportError as e:
        status["fusion-engine"] = ("fail", str(e))

    # Agent 4: star-hunter
    try:
        from agents.star_hunter.agent import StarHunter
        status["star-hunter"] = ("ok", StarHunter)
    except ImportError as e:
        status["star-hunter"] = ("fail", str(e))

    return status


def check_snipe():
    """检查SnipeScore是否可用"""
    try:
        sys.path.insert(0, str(_AI_ROTATION))
        from ai_rotation_monitor_em import calculate_snipe_score
        return True
    except ImportError:
        return False


# ══════════════════════════════════════════════════════════
# 数据标准化
# ══════════════════════════════════════════════════════════
def normalize_astro(astro_result):
    """标准化astro_calc输出"""
    if not astro_result:
        return {}

    ziwei = astro_result.get("ziwei", {})

    # 修复 favorable_elements / unfavorable_elements
    if ziwei.get("favorable_elements") is None:
        bazi = astro_result.get("bazi", {})
        favorable = bazi.get("favorable", {})
        yong = favorable.get("用神", {})
        xi = favorable.get("喜神", {})
        if isinstance(yong, dict):
            ziwei["favorable_elements"] = [yong.get("element", "土")]
        if isinstance(xi, dict):
            ziwei.setdefault("favorable_elements", []).append(xi.get("element", "金"))
        ji = favorable.get("忌神", {})
        if isinstance(ji, dict):
            ziwei["unfavorable_elements"] = [ji.get("element", "木")]
        else:
            ziwei["unfavorable_elements"] = ["木", "火"]

    # 修复 annual_sihua palace字段
    annual_sihua = ziwei.get("annual_sihua", {})
    palace_map = {"禄": "田宅宫", "权": "命宫", "科": "官禄宫", "忌": "财帛宫"}
    for item in annual_sihua.get("sihua", []):
        if "palace" not in item:
            item["palace"] = palace_map.get(item.get("type", ""), "命宫")

    # 修复占星英文key → 中文
    astrology = astro_result.get("astrology", {})
    transit = astrology.get("transit", {})
    chinese_map = {
        "jupiter": "木星", "saturn": "土星", "uranus": "天王星",
        "pluto": "冥王星", "neptune": "海王星", "mercury": "水星",
        "venus": "金星", "mars": "火星",
    }
    for eng, chn in chinese_map.items():
        if eng in transit and chn not in transit:
            transit[chn] = transit[eng]

    return astro_result


def normalize_cosmic(cosmic_result):
    """标准化cosmic-trend输出"""
    if not cosmic_result:
        return {}

    # 季度修正: Q1/Q2/Q3/Q4 → 春季/夏季/秋季/冬季
    qm = cosmic_result.get("quarterly_modifier", {})
    if "Q1" in qm and "春季" not in qm:
        qm["春季"] = qm.get("Q1", {})
        qm["夏季"] = qm.get("Q2", {})
        qm["秋季"] = qm.get("Q3", {})
        qm["冬季"] = qm.get("Q4", {})

    # 九运周期
    nine_star = cosmic_result.get("nine_star_cycle", {})
    if isinstance(nine_star, dict) and "name" in nine_star:
        cosmic_result["九运"] = nine_star.get("name", "九紫离火运")

    # 行星流年英文key → 中文
    pt = cosmic_result.get("planetary_transits", {})
    chinese_map = {
        "jupiter": "木星", "saturn": "土星", "uranus": "天王星",
        "pluto": "冥王星", "neptune": "海王星", "mercury": "水星",
        "venus": "金星", "mars": "火星",
    }
    for eng, chn in chinese_map.items():
        if eng in pt and chn not in pt:
            pt[chn] = pt[eng]

    return cosmic_result


# ══════════════════════════════════════════════════════════
# 默认数据（降级模式）
# ══════════════════════════════════════════════════════════
DEFAULT_BAZI = {
    "four_pillars": {"year": "甲寅", "month": "庚午", "day": "丁未", "hour": "己酉"},
    "xiyong": {"喜用": "土", "次用": "金"},
    "strength_breakdown": {"得令": 5, "得地": 2, "得势": -1},
    "five_element_vector": {"木": 18, "火": 24, "土": 94, "金": 57, "水": 23},
    "favorable": {
        "strength": "身旺",
        "用神": {"element": "土", "reason": "泄去过旺火气"},
        "喜神": {"element": "金", "reason": "接收食伤之气"},
    },
}
DEFAULT_DAYUN = {
    "current": {"gan_zhi": "丙子", "year_start": 2025, "year_end": 2035, "age_start": 50, "age_end": 59},
    "sequence": [
        {"gan_zhi": "辛未", "year_start": 1975, "year_end": 1984, "age_start": 1, "age_end": 10},
        {"gan_zhi": "壬申", "year_start": 1985, "year_end": 1994, "age_start": 10, "age_end": 20},
        {"gan_zhi": "癸酉", "year_start": 1995, "year_end": 2004, "age_start": 20, "age_end": 30},
        {"gan_zhi": "甲戌", "year_start": 2005, "year_end": 2014, "age_start": 30, "age_end": 40},
        {"gan_zhi": "乙亥", "year_start": 2015, "year_end": 2024, "age_start": 40, "age_end": 50},
        {"gan_zhi": "丙子", "year_start": 2025, "year_end": 2035, "age_start": 50, "age_end": 60},
    ],
    "description": "丙子大运，火水交战",
}
DEFAULT_ZIWEI = {
    "annual_sihua": {
        "sihua": [
            {"star": "天同", "type": "禄", "palace": "田宅宫", "impact": "天同化禄入田宅"},
            {"star": "天机", "type": "权", "palace": "命宫", "impact": "天机化权入命宫"},
            {"star": "文昌", "type": "科", "palace": "官禄宫", "impact": "文昌化科利智慧投资"},
            {"star": "廉贞", "type": "忌", "palace": "财帛宫", "impact": "廉贞化忌需注意投机风险"},
        ]
    },
    "favorable_elements": ["土", "金"],
    "unfavorable_elements": ["木", "火"],
    "five_element_vector": {"木": 35, "火": 40, "土": 75, "金": 65, "水": 50},
}
DEFAULT_QIMEN = {
    "value_star": "天芮星", "value_star_element": "土",
    "value_gate": "死门", "value_gate_element": "土",
    "eight_gates_seasonal": {
        "春季(2-4月)": {"gates": ["生门"], "score": 1.10, "action": "适度操作"},
        "夏季(5-7月)": {"gates": ["景门", "白虎"], "score": 0.56, "action": "极度谨慎"},
        "秋季(8-10月)": {"gates": ["开门", "休门"], "score": 1.20, "action": "大胆进攻"},
        "冬季(11-1月)": {"gates": ["休门", "生门"], "score": 1.00, "action": "正常持有"},
    },
}
DEFAULT_ASTROLOGY = {
    "natal": {
        "sun": {"sign": "巨蟹座", "interpretation": "投资风格重安全感"},
        "moon": {"sign": "天蝎座", "interpretation": "直觉敏锐，适合深度研究"},
        "rising": {"sign": "天秤座", "interpretation": "偏好金融类资产"},
    },
    "transit": {
        "木星": {"sign": "巨蟹座", "impact": "木星过太阳星座，财运年！"},
        "土星": {"sign": "白羊座", "impact": "新领域承压"},
    },
}


def get_default_astro(config, target_year):
    raise NotImplementedError("get_default_astro() 不应被调用。请修复 astro-calc 模块。")


def get_default_cosmic():
    raise NotImplementedError("get_default_cosmic() 不应被调用。请修复 cosmic-trend 模块。")


def get_default_fusion():
    raise NotImplementedError("get_default_fusion() 不应被调用。请修复 fusion-engine 模块。")


# ══════════════════════════════════════════════════════════
# Pipeline 主函数
# ══════════════════════════════════════════════════════════
def run_pipeline(config, use_snipe=True, verbose=True):
    """
    执行完整的4-Agent Pipeline

    Args:
        config: {
            "birth_date": "1974-07-05",
            "birth_hour": 17,
            "gender": "男",
            "birth_place": "开封",
            "target_year": 2026,
            "current_place": "旧金山",
            "lat_lon": (34.79, 114.35),
        }
        use_snipe: 是否使用SnipeScore（需要网络）
        verbose: 是否打印详细信息

    Returns:
        (summary_dict, html_path)
    """
    errors = []
    t0 = time.time()

    # ── Agent加载 ───────────────────────────────────────
    if verbose:
        print("\n" + "=" * 60)
        print("FSSQ v4.0 端到端Pipeline")
        print("=" * 60)

    agent_status = load_agents()
    AstroCalc = agent_status.get("astro-calc", (None, None))[1]
    CosmicTrend = agent_status.get("cosmic-trend", (None, None))[1]
    FusionEngine_tuple = agent_status.get("fusion-engine", (None, None))[1]
    StarHunter = agent_status.get("star-hunter", (None, None))[1]

    if verbose:
        for name, (status, _) in agent_status.items():
            icon = "✅" if status == "ok" else "❌"
            print(f"  {icon} {name}: {status}")

    snipe_ok = check_snipe()
    if use_snipe and not snipe_ok:
        if verbose:
            print("  ⚠️ SnipeScore不可用（未找到ai_rotation_monitor_em.py），跳过真实数据对接")
        use_snipe = False
    elif use_snipe and snipe_ok:
        if verbose:
            print("  ✅ SnipeScore已就绪（东方财富API）")

    # ── Step 1: astro-calc ──────────────────────────────
    if verbose:
        print(f"\n[Step 1/4] 命盘精算 (astro-calc)")

    astro_result = None
    if AstroCalc:
        try:
            birth_info = {
                "year": int(config["birth_date"].split("-")[0]),
                "month": int(config["birth_date"].split("-")[1]),
                "day": int(config["birth_date"].split("-")[2]),
                "hour": config["birth_hour"],
                "minute": 0,
                "gender": config["gender"],
                "birth_place": config.get("birth_place", ""),
                "target_year": config.get("target_year", datetime.now().year),
                "birth_lat": config.get("lat_lon", (None, None))[0],
                "birth_lon": config.get("lat_lon", (None, None))[1],
                "residence": config.get("current_place", ""),
                "dayun_mode": config.get("dayun_mode", "day_gan"),
            }
            calc = AstroCalc(birth_info)
            astro_result = calc.run()
            astro_result = normalize_astro(astro_result)
            bazi = astro_result.get("bazi", {}).get("four_pillars", {})
            bazi_str = f"{bazi.get('year', '?')}{bazi.get('month', '?')}{bazi.get('day', '?')}{bazi.get('hour', '?')}"
            if verbose:
                print(f"  ✅ 完成 — 八字: {bazi_str}")
        except Exception as e:
            errors.append(f"astro-calc: {e}")
            if verbose:
                print(f"  ❌ 失败: {e}")
    if not astro_result:
        raise RuntimeError(f"八字计算引擎不可用: astro-calc导入失败，无法静默降级。错误: {errors[-1] if errors else 'unknown'}")

    # ── Step 2: cosmic-trend ────────────────────────────
    if verbose:
        print(f"\n[Step 2/4] 天道宏图 (cosmic-trend)")

    cosmic_result = None
    if CosmicTrend:
        try:
            agent = CosmicTrend(
                target_year=config.get("target_year", datetime.now().year),
                astro_calc_output=astro_result,
            )
            cosmic_result = agent.run()
            cosmic_result = normalize_cosmic(cosmic_result)
            yearly_gz = cosmic_result.get("年份干支", "?")
            nine_star = cosmic_result.get("九运", cosmic_result.get("nine_star_cycle", "?"))
            if verbose:
                print(f"  ✅ 完成 — 流年: {yearly_gz} | 九运: {nine_star}")
        except Exception as e:
            errors.append(f"cosmic-trend: {e}")
            if verbose:
                print(f"  ❌ 失败: {e}")
    if not cosmic_result:
        raise RuntimeError(f"宏观分析引擎不可用: cosmic-trend 失败，无法静默降级。错误: {errors[-1] if errors else 'unknown'}")

    # ── Step 3: fusion-engine ───────────────────────────
    if verbose:
        print(f"\n[Step 3/4] 玄机融合 (fusion-engine)")

    fusion_result = None
    if FusionEngine_tuple:
        FusionEngine, generate_html = FusionEngine_tuple
        try:
            engine = FusionEngine(
                astro_calc_output=astro_result,
                cosmic_trend_output=cosmic_result,
                target_year=config.get("target_year", datetime.now().year),
            )
            fusion_result = engine.run(top_n=10)
            xiyong = fusion_result.get("input_summary", {}).get("xiyong", {})
            sectors = [s.get("name", "?") for s in fusion_result.get("recommended_sectors", [])[:3]]
            if verbose:
                print(f"  ✅ 完成 — 喜用神: {xiyong.get('primary', '?')}+{xiyong.get('secondary', '?')}")
                print(f"     推荐板块: {' | '.join(sectors)}")
        except Exception as e:
            errors.append(f"fusion-engine: {e}")
            if verbose:
                print(f"  ❌ 失败: {e}")
    if not fusion_result:
        raise RuntimeError(f"融合引擎不可用: fusion-engine 失败，无法静默降级。错误: {errors[-1] if errors else 'unknown'}")

    # ── Step 4: star-hunter ─────────────────────────────
    if verbose:
        print(f"\n[Step 4/4] 个股猎手 (star-hunter)" + (" + SnipeScore" if use_snipe else ""))

    star_hunter_result = None
    if StarHunter:
        try:
            hunter = StarHunter(
                astro_calc_output=astro_result,
                cosmic_trend_output=cosmic_result,
                target_year=config.get("target_year", datetime.now().year),
            )
            # v3.1: 不传top_n → 获取全量候选股票供SnipeScore全量评分
            star_hunter_result = hunter.run(top_n=None)

            # ── SnipeScore对接（PRD v3.1: 多数据源兜底，不允许降级） ──
            if use_snipe and snipe_ok and star_hunter_result:
                try:
                    from agents.star_hunter.snipe_integration import enrich_with_snipescore_full
                    # v3.1: 使用全量候选而非只20只！
                    all_candidates = star_hunter_result.get("all_candidates", [])
                    if not all_candidates:
                        all_candidates = star_hunter_result.get("recommendations", {}).get("stocks", [])

                    if all_candidates:
                        # 确保股票代码带市场后缀
                        for s in all_candidates:
                            code = s.get("code", "")
                            if code and "." not in code:
                                if code.startswith("6"):
                                    s["code"] = f"{code}.SH"
                                else:
                                    s["code"] = f"{code}.SZ"

                        # v3.0: 对全量候选进行SnipeScore评分（可达5000+只）
                        enriched = enrich_with_snipescore_full(
                            stocks=all_candidates,
                            fusion_result=fusion_result,
                            target_year=config.get("target_year", datetime.now().year),
                            snipe_weight=0.70,
                            max_workers=10,
                            batch_limit=2000,
                        )
                        # SnipeScore评分后按final_score排序，取Top20供展示
                        star_hunter_result["recommendations"]["stocks"] = enriched[:20]
                        # 全部评分结果保存到all_candidates字段
                        star_hunter_result["all_candidates_ranked"] = enriched
                        # fusion_result注入Top10
                        fusion_result["top_stocks"] = enriched[:10]
                        if verbose:
                            snipe_ok_count = sum(1 for s in enriched if s.get("snipe_available"))
                            print(f"  ✅ SnipeScore全量评分完成 — {len(enriched)}只候选，{snipe_ok_count}只有效SnipeScore")
                            print(f"     Top3: {[(s['name'], s['final_score']) for s in enriched[:3]]}")
                    else:
                        if verbose:
                            print(f"  ⚠️ 无候选股票可评分")
                except RuntimeError as e:
                    # PRD v3.1 §5.1 E009: 所有数据源失败 → 报错，不降级
                    errors.append(f"SnipeScore: {e}")
                    if verbose:
                        print(f"  ❌ SnipeScore对接失败（所有数据源不可用）: {e}")
                        print(f"     Pipeline状态: PARTIAL - SnipeScore不可用")
                except Exception as e:
                    errors.append(f"SnipeScore: {e}")
                    if verbose:
                        print(f"  ⚠️ SnipeScore对接异常: {e}")

            stocks = star_hunter_result.get("recommendations", {}).get("stocks", [])
            fusion_result["top_stocks"] = stocks[:10]
            if verbose:
                total_candidates = len(star_hunter_result.get("all_candidates", []))
                print(f"  ✅ 完成 — 玄学候选{total_candidates}只 → SnipeScore Top20")
                top3 = [s.get("name", "?") for s in stocks[:3]]
                if top3:
                    print(f"     首选: {top3[0]} | {top3[1]} | {top3[2]}")
        except Exception as e:
            errors.append(f"star-hunter: {e}")
            if verbose:
                print(f"  ❌ 失败: {e}")
    if not star_hunter_result:
        star_hunter_result = {"recommendations": {"stocks": []}, "meta": {"version": "degraded"}}
        errors.append("star-hunter: 使用默认空数据")
        if verbose:
            print(f"  ⚠️ 使用默认数据")

    # ── Step 5: 生成HTML报告 ─────────────────────────────
    if verbose:
        print(f"\n[Step 5/5] 生成HTML报告")

    html_path = None
    safe_id = config["birth_date"].replace("-", "") + f"_{config['gender']}_{config.get('target_year', 2026)}"
    if FusionEngine_tuple:
        _, generate_html = FusionEngine_tuple
        try:
            html_content = generate_html(
                astro=astro_result,
                cosmic=cosmic_result,
                fusion_result=fusion_result,
                star_hunter_result=star_hunter_result,
            )

            # 注入SnipeScore信息到HTML（如果对接成功）
            if use_snipe and snipe_ok:
                snipe_tag = f'<!-- SnipeScore: {config.get("target_year", 2026)} | {len(star_hunter_result.get("recommendations", {}).get("stocks", []))} stocks -->'
                html_content = html_content.replace(
                    '<!-- Section 0: 融合五行共振雷达图 -->',
                    f'{snipe_tag}\n    <!-- Section 0: 融合五行共振雷达图 -->'
                )

            html_path = OUTPUT_DIR / f"FSSQ_{safe_id}.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            if verbose:
                print(f"  ✅ 保存: {html_path}")
                print(f"     大小: {len(html_content):,} 字符")
        except Exception as e:
            errors.append(f"HTML报告: {e}")
            if verbose:
                print(f"  ❌ 报告生成失败: {e}")

    elapsed = time.time() - t0

    # ── 构建摘要 ─────────────────────────────────────────
    bazi = astro_result.get("bazi", {}).get("four_pillars", {})
    bazi_str = f"{bazi.get('year', '?')}{bazi.get('month', '?')}{bazi.get('day', '?')}{bazi.get('hour', '?')}"
    xiyong = fusion_result.get("input_summary", {}).get("xiyong", {})
    sectors = [s.get("name", "?") for s in fusion_result.get("recommended_sectors", [])[:5]]
    stocks = star_hunter_result.get("recommendations", {}).get("stocks", [])[:5]

    summary = {
        "version": "4.0",
        "status": "SUCCESS" if len(errors) == 0 else ("PARTIAL" if errors else "FAIL"),
        "errors": errors,
        "elapsed_seconds": round(elapsed, 1),
        "config": {
            "birth_date": config["birth_date"],
            "birth_hour": config["birth_hour"],
            "gender": config["gender"],
            "birth_place": config.get("birth_place", ""),
            "target_year": config.get("target_year", datetime.now().year),
        },
        "astro": {"bazi": bazi_str},
        "fusion": {
            "xiyong": f"{xiyong.get('primary', '?')} + {xiyong.get('secondary', '?')}",
            "sectors": sectors,
        },
        "star_hunter": {
            "count": len(star_hunter_result.get("recommendations", {}).get("stocks", [])),
            "top3": [{"name": s.get("name", "?"), "code": s.get("code", "?")} for s in stocks],
            "snipe_active": use_snipe and snipe_ok,
        },
        "output": str(html_path) if html_path else None,
    }

    # 保存结果JSON
    json_path = OUTPUT_DIR / f"FSSQ_{safe_id}_result.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "astro": astro_result,
            "cosmic": cosmic_result,
            "fusion": fusion_result,
            "star_hunter": star_hunter_result,
        }, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"Pipeline完成 — 耗时 {elapsed:.1f}秒")
        print(f"状态: {summary['status']}")
        print(f"八字: {bazi_str} | 喜用: {xiyong.get('primary', '?')}+{xiyong.get('secondary', '?')}")
        print(f"板块: {' | '.join(sectors[:3])}")
        print(f"个股: {', '.join([s['name'] for s in stocks[:3]])}")
        if errors:
            print(f"\n⚠️ 错误: {errors[0]}")
        print(f"📄 报告: {html_path}")
        print(f"📋 数据: {json_path}")
        print(f"{'=' * 60}")

    return summary, str(html_path) if html_path else None


# ══════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="FSSQ v4.0 — 玄学选股引擎（4-Agent端到端Pipeline）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 run_pipeline.py --birth 1974-07-05 --hour 17 --gender 男 --place 开封 --year 2026 --current 旧金山
  python3 run_pipeline.py --birth 1990-05-15 --hour 8 --gender 女 --output ./output
  python3 run_pipeline.py --birth 1974-07-05 --hour 17 --gender 男 --place 开封 --snipe 0  # 禁用SnipeScore
        """
    )
    parser.add_argument("--birth", required=True, help="出生日期 (YYYY-MM-DD)")
    parser.add_argument("--hour", type=int, required=True, help="出生时辰 (0-23)")
    parser.add_argument("--gender", required=True, choices=["男", "女"], help="性别")
    parser.add_argument("--place", required=True, help="出生地（必填！用于占星经纬度查询，预置CITY_COORDS表支持城市见帮助）")
    parser.add_argument("--year", type=int, default=None, help="目标年份（默认当前年份）")
    parser.add_argument("--current", default="", help="现居地")
    parser.add_argument("--lat", type=float, default=None, help="出生地纬度（优先于--place）")
    parser.add_argument("--lon", type=float, default=None, help="出生地经度（优先于--place）")
    parser.add_argument("--output", default="", help="输出目录（默认 ./output）")
    parser.add_argument("--snipe", type=int, default=1, choices=[0, 1], help="是否使用SnipeScore（1=是，0=否）")
    parser.add_argument("--dayun_mode", default="day_gan", choices=["day_gan", "year_gan"],
                        help="大运排法：day_gan（日干派，默认）/ year_gan（年干派，suanzhun.net）")

    args = parser.parse_args()

    # ── 出生地经纬度校验（PRD v3.1 §5.1 E008）─────────
    # 出生地必须提供经纬度
    lat_lon = None
    if args.lat is not None and args.lon is not None:
        lat_lon = (args.lat, args.lon)
        print(f"  📍 使用手动指定经纬度: {lat_lon}")
    elif args.place in CITY_COORDS:
        lat_lon = CITY_COORDS[args.place]
        print(f"  📍 从预置表推断 {args.place} 经纬度: {lat_lon}")
    else:
        print(f"\n{'!'*60}")
        print(f"[错误] 出生地 '{args.place}' 不在预置CITY_COORDS表中。")
        print(f"预置支持的城市: {', '.join(sorted(CITY_COORDS.keys()))}")
        print(f"如需添加新城市，请使用 --lat 和 --lon 参数手动指定经纬度。")
        print(f"例如: python3 run_pipeline.py --lat 24.48 --lon 118.10 ...")
        print(f"{'!'*60}\n")
        sys.exit(1)

    # 解析目标年份
    target_year = args.year or datetime.now().year

    # 更新输出目录
    global OUTPUT_DIR
    if args.output:
        OUTPUT_DIR = Path(args.output).resolve()
        OUTPUT_DIR.mkdir(exist_ok=True)

    config = {
        "birth_date": args.birth,
        "birth_hour": args.hour,
        "gender": args.gender,
        "birth_place": args.place,
        "target_year": target_year,
        "current_place": args.current,
        "lat_lon": lat_lon,
        "dayun_mode": args.dayun_mode,
    }

    summary, html_path = run_pipeline(config, use_snipe=bool(args.snipe), verbose=True)

    # 返回码
    sys.exit(0 if summary["status"] == "SUCCESS" else 1)


if __name__ == "__main__":
    main()
