"""
FSSQ Orchestrator — 编排器
串联4个Agent: astro-calc → cosmic-trend → star-hunter → fusion-engine → HTML报告

用法:
  python src/orchestrator/pipeline.py --input input.json
  python src/orchestrator/pipeline.py  # 默认1974男命
"""
import json
import sys
import os
import argparse
from datetime import datetime

# 确保src目录在path中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.astro_calc.agent import AstroCalc
from agents.cosmic_trend.agent import CosmicTrend
from agents.star_hunter.agent import StarHunter
from agents.fusion_engine.agent import FusionEngine
from agents.fusion_engine.template import generate_html


def run_pipeline(birth_info, output_dir=None):
    """
    执行完整4-Agent流水线

    Args:
        birth_info: 出生信息dict
        output_dir: 输出目录（默认项目output/）

    Returns:
        (html_path, result_dict) 元组
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(output_dir, exist_ok=True)

    target_year = birth_info.get("target_year", 2026)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    print("=" * 60)
    print(f"风生水起（FSSQ）v3.0 Pipeline")
    print(f"目标: {birth_info['year']}年{birth_info['gender']}命 → {target_year}年投资指南")
    print("=" * 60)

    # ---- Step 1: astro-calc ----
    print("\n[1/4] 🧮 astro-calc 命盘精算...")
    try:
        astro = AstroCalc(birth_info).run()
        print(f"  ✅ 完成 | 校验: {astro['meta']['validation']}")
        print(f"  四柱: {astro['bazi']['four_pillars']['year']} {astro['bazi']['four_pillars']['month']} {astro['bazi']['four_pillars']['day']} {astro['bazi']['four_pillars']['hour']}")
        print(f"  日主: {astro['bazi']['day_master']}({astro['bazi']['day_master_element']}) {astro['bazi']['strength']}")
        print(f"  用神: {astro['bazi']['yong_shen']} | 喜神: {astro['bazi']['xi_shen']} | 忌神: {astro['bazi']['ji_shen']}")
        print(f"  大运: {astro['dayun']['current']['gan_zhi']} ({astro['dayun']['current']['year_start']}-{astro['dayun']['current']['year_end']})")
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return None, None

    if astro["meta"]["validation"] != "PASS":
        print(f"  ⚠️ 校验未完全通过，继续执行但结果可能不准确")

    # ---- Step 2: cosmic-trend ----
    print("\n[2/4] 🌌 cosmic-trend 天道宏图...")
    cosmic = CosmicTrend(target_year=target_year, astro_calc_output=astro).run()
    yearly_gz = cosmic.get("yearly_ganzhi", {})
    nine_star = cosmic.get("nine_star_cycle", {})
    macro_vec = cosmic.get("macro_five_element", {}).get("vector", {})
    print(f"  ✅ 完成 | 干支: {yearly_gz.get('gan_zhi', '?')} | 九运: {nine_star.get('name', '?')}")
    print(f"  大势五行: " + " ".join(f"{e}{macro_vec.get(e, 0)}" for e in ["木","火","土","金","水"]))

    # ---- Step 3: fusion-engine ----
    print("\n[3/4] 🔮 fusion-engine 融合计算...")
    try:
        fe = FusionEngine(astro_calc_output=astro, cosmic_trend_output=cosmic, target_year=target_year)
        fusion_result = fe.run()
        fusion_vector = fusion_result.get("fused_five_element", {}).get("vector", fusion_result.get("fusion_vector", {}))
        recommended = fusion_result.get("recommended_sectors", [])
        print(f"  ✅ 融合完成")
        print(f"  融合向量: " + " ".join(f"{e}{fusion_vector.get(e, 0)}" for e in ["木","火","土","金","水"]))
        print(f"  推荐Top5: {[s['name'] for s in recommended[:5]]}")
    except Exception as e:
        print(f"  ❌ 融合失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None

    # ---- Step 4: star-hunter ----
    # v3.1: 不传top_n限制，获取全量候选股票供SnipeScore全量评分
    print("\n[4/4] 🎯 star-hunter 个股猎手（全量候选）...")
    try:
        sh = StarHunter(astro_calc_output=astro, cosmic_trend_output=cosmic, target_year=target_year)
        # 不设top_n → 返回全量候选（供SnipeScore评分）
        star_result = sh.run(top_n=None)
        all_candidates = star_result.get("all_candidates", [])
        top_stocks_from_meta = star_result.get("recommendations", {}).get("stocks", [])[:20]
        print(f"  ✅ 完成 | 玄学候选{len(all_candidates)}只（板块全量）")
        print(f"  Top5玄学候选: {[(s.get('name','?'), s.get('match_score', s.get('current_score','?'))) for s in top_stocks_from_meta[:5]]}")
    except Exception as e:
        print(f"  ❌ star-hunter失败: {e}")
        import traceback
        traceback.print_exc()
        all_candidates = []
        top_stocks_from_meta = []
        star_result = {}

    # ---- 整合个股到fusion_result ----
    # v3.1: all_candidates包含全量候选，top_stocks_from_meta是玄学Top20
    fusion_result["top_stocks"] = top_stocks_from_meta

    # ---- 生成HTML报告 ----
    print("\n📄 生成HTML报告...")
    html = generate_html(astro, cosmic, fusion_result)

    # 文件名
    desc = f"{birth_info['year']}{'年'}{birth_info['gender']}命"
    html_filename = f"{desc}_{target_year}_风生水起_客户版.html"
    html_path = os.path.join(output_dir, html_filename)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ HTML已保存: {html_path}")

    # 保存中间JSON
    json_path = os.path.join(output_dir, f"{desc}_{target_year}_pipeline.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "astro": astro,
            "cosmic": cosmic,
            "fusion": fusion_result,
            "star": star_result,
        }, f, ensure_ascii=False, indent=2)
    print(f"  ✅ JSON已保存: {json_path}")

    print("\n" + "=" * 60)
    print("Pipeline 完成！")
    print(f"推荐板块: {[s['name'] for s in recommended]}")
    print(f"禁忌板块: {[s['name'] for s in fusion_result['forbidden_sectors']]}")
    print(f"个股Top5: {[(s.get('name','?'), s.get('current_score', s.get('match_score', s.get('final_score','?')))) for s in top_stocks[:5]]}")
    print("=" * 60)

    return html_path, fusion_result


# ============================================================
# 默认测试输入
# ============================================================
DEFAULT_INPUT = {
    "year": 1974, "month": 7, "day": 5, "hour": 17, "minute": 30,
    "gender": "男", "birth_place": "开封", "birth_lat": 34.79, "birth_lon": 114.35,
    "residence": "旧金山", "target_year": 2026
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FSSQ v3.0 编排器 Pipeline")
    parser.add_argument("--input", type=str, help="出生信息JSON文件路径")
    parser.add_argument("--output-dir", type=str, help="输出目录")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            birth_info = json.load(f)
    else:
        birth_info = DEFAULT_INPUT

    html_path, result = run_pipeline(birth_info, args.output_dir)
    if html_path:
        print(f"\n报告: {html_path}")
