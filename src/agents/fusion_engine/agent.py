"""
Agent 4: fusion-engine — 玄机融合Agent
v3.0

输入:
  - astro_calc_output: astro-calc输出JSON
  - cosmic_trend_output: cosmic-trend输出JSON
  - target_year: 目标年份（默认当前年份）

核心流程:
  1. 输入校验（守门员）
  2. 加权融合五行向量
  3. 板块打分（余弦相似度 + 忌神惩罚）
  4. 置信度评级
  5. 输出板块推荐

输出:
  - 推荐板块列表（含分数和置信度）
  - 禁忌板块列表
"""
import json
import sys
import os
from datetime import datetime

_src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _src_root)
from constants import *

# 导入子模块
from .input_validator import validate_inputs, can_degrade
from .weighted import WeightedFusion
from .resonance import ResonanceScorer, get_all_sectors
from .confidence import ConfidenceRater, get_confidence_label


class FusionEngine:
    """玄机融合引擎 — 投资顾问"""

    def __init__(self, astro_calc_output=None, cosmic_trend_output=None, target_year=None):
        """
        Args:
            astro_calc_output: astro-calc输出JSON
            cosmic_trend_output: cosmic-trend输出JSON
            target_year: 目标年份（默认读取当前时间）
        """
        self.astro = astro_calc_output
        self.cosmic = cosmic_trend_output
        self.year = target_year if target_year else datetime.now().year

        # 校验结果
        self.validation = None

        # 喜用神和忌神
        self.xiyong = self._extract_xiyong()
        self.ji = self._extract_avoid()

        # 数据来源信息
        self.sources = {
            "astro": bool(astro_calc_output),
            "cosmic": bool(cosmic_trend_output),
            "ziwei": bool(astro_calc_output and astro_calc_output.get("ziwei")),
            "qimen": bool(astro_calc_output and astro_calc_output.get("qimen")),
            "astrography": bool(astro_calc_output and astro_calc_output.get("astrology"))
        }

    def _extract_xiyong(self):
        """提取喜用神"""
        if not self.astro:
            return {"primary": "木", "secondary": "水"}

        bazi = self.astro.get("bazi", {})

        # 优先从 yong_shen（用神）和 xi_shen（喜神）读取
        yong = bazi.get("yong_shen")
        xi = bazi.get("xi_shen")

        # 兼容旧格式 xiyong
        if not yong:
            xiyong = bazi.get("xiyong", {})
            if isinstance(xiyong, dict):
                yong = xiyong.get("喜用", xiyong.get("primary", "木"))
                xi = xiyong.get("次用", xiyong.get("secondary", "水"))
            elif isinstance(xiyong, list) and len(xiyong) >= 2:
                yong = xiyong[0]
                xi = xiyong[1]

        return {
            "primary": yong or "木",
            "secondary": xi or "水"
        }

    def _extract_avoid(self):
        """提取忌神"""
        if not self.astro:
            # 默认忌神
            return ["金"] if self.xiyong["primary"] == "木" else ["木"]

        bazi = self.astro.get("bazi", {})

        # 优先从 ji_shen（忌神列表）读取
        ji = bazi.get("ji_shen", [])
        if ji:
            return ji if isinstance(ji, list) else [ji]

        # 兼容旧格式 avoid
        avoid = bazi.get("avoid", [])
        if avoid:
            return avoid if isinstance(avoid, list) else [avoid]

        # 根据喜用神推断忌神
        xi = self.xiyong["primary"]
        avoid_map = {"木": "金", "火": "水", "土": "木", "金": "火", "水": "土"}
        return [avoid_map.get(xi, "金")]

    def run(self, top_n=10, forbid_bottom=3):
        """
        执行融合分析

        Args:
            top_n: 返回前N个推荐板块
            forbid_bottom: 禁止板块数量（最低分的N个）

        Returns:
            dict: 融合结果
        """
        # 1. 输入校验
        self.validation = validate_inputs(self.astro, self.cosmic, self.year)

        # 如果校验失败，检查是否可以降级
        if not self.validation["valid"]:
            if can_degrade(self.validation):
                print(f"⚠ 检测到{len(self.validation['warnings'])}个警告，降级运行")
            else:
                return self._build_error_output()

        # 2. 加权融合（八字40%+紫微30%+奇门20%+占星10%）
        fusion = WeightedFusion(weights=WeightedFusion.FUSION_WEIGHTS)
        fused_vector = fusion.fuse(self.astro, cosmic_json=self.cosmic, avoid_elements=self.ji)
        fusion_explain = fusion.explain_fusion(self.astro, self.cosmic, fused_vector)

        # 3. 板块打分
        scorer = ResonanceScorer(fused_vector, avoid_elements=self.ji)
        all_sectors = get_all_sectors()
        sector_scores = scorer.rank_sectors(all_sectors)

        # 4. 置信度评级
        rater = ConfidenceRater(fused_vector, self.sources)
        confidence = rater.rate(sector_scores)

        # 5. 构建输出
        return self._build_output(
            fused_vector,
            fusion_explain,
            sector_scores,
            confidence,
            top_n,
            forbid_bottom
        )

    def _build_output(self, fused_vector, fusion_explain, sector_scores, confidence, top_n, forbid_bottom):
        """构建输出JSON"""
        # 推荐板块
        recommended = sector_scores[:top_n]

        # 禁忌板块
        forbidden = sector_scores[-forbid_bottom:] if forbid_bottom > 0 else []

        # 流月分析
        monthly = self._calc_monthly_analysis(fused_vector)

        output = {
            "meta": {
                "version": "fusion-engine v3.0",
                "agent": "fusion-engine",
                "timestamp": datetime.now().isoformat(),
                "target_year": self.year,
                "validation": {
                    "status": "PASS" if self.validation["valid"] else "WARN",
                    "errors": self.validation.get("errors", []),
                    "warnings": self.validation.get("warnings", [])
                }
            },
            "input_summary": {
                "xiyong": self.xiyong,
                "avoid": self.ji,
                "sources": self.sources,
                "fusion_explain": fusion_explain
            },
            "fused_five_element": {
                "vector": fused_vector,
                "dominant": max(fused_vector, key=fused_vector.get),
                "explain": fusion_explain
            },
            "recommended_sectors": [
                {
                    "rank": i + 1,
                    "name": s["name"],
                    "score": s["score"],
                    "cosine_sim": s["cosine_sim"],
                    "avoid_penalty": s["avoid_penalty"],
                    "reason": s["reason"]
                }
                for i, s in enumerate(recommended)
            ],
            "forbidden_sectors": [
                {
                    "name": s["name"],
                    "score": s["score"],
                    "reason": "忌神五行占比高，命中命主忌神"
                }
                for s in forbidden
            ],
            "confidence": confidence,
            "monthly_analysis": monthly,
            "all_sector_scores": [
                {"rank": s["rank"], "name": s["name"], "score": s["score"]}
                for s in sector_scores
            ]
        }

        return output

    def _build_error_output(self):
        """构建错误输出"""
        return {
            "meta": {
                "version": "fusion-engine v3.0",
                "agent": "fusion-engine",
                "timestamp": datetime.now().isoformat(),
                "target_year": self.year,
                "validation": {
                    "status": "FAIL",
                    "errors": self.validation.get("errors", []),
                    "error_report": self.validation.get("error_report", "校验失败")
                }
            },
            "output": None,
            "message": "上游数据校验失败，拒绝融合。请修复astro-calc或cosmic-trend后重试。"
        }

    def _calc_monthly_analysis(self, fused_vector):
        """计算流月分析"""
        # 流年干支
        year_gan_idx = (self.year - 4) % 10
        year_zhi_idx = (self.year - 4) % 12
        year_gan = TIAN_GAN[year_gan_idx]
        year_zhi = DI_ZHI[year_zhi_idx]

        # 月支序列
        month_zhi_list = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]

        # 五虎遁
        gan_start = {
            "甲": 2, "己": 2, "乙": 4, "庚": 4, "丙": 6, "辛": 6, "丁": 8, "壬": 8, "戊": 0, "癸": 0
        }
        gan_idx = gan_start.get(year_gan, 0)

        monthly = []
        for i, zhi in enumerate(month_zhi_list):
            month_gan_idx = (gan_idx + i) % 10
            month_gan = TIAN_GAN[month_gan_idx]
            month_gan_el = GAN_ELEMENT[month_gan]
            month_zhi_el = ZHI_ELEMENT[zhi]

            # 当月最旺五行
            month_score = {el: 0 for el in ELEMENTS}
            month_score[month_gan_el] += 1
            month_score[month_zhi_el] += 2  # 月令权重更高

            dominant = max(month_score, key=month_score.get)

            # 与喜用神关系
            xi = self.xiyong["primary"]
            if dominant == xi:
                action = "🟢 积极"
                timing = "buy"
            elif dominant == self.xiyong["secondary"]:
                action = "🔵 稳健"
                timing = "hold"
            elif dominant in self.ji:
                action = "⚫ 回避"
                timing = "avoid"
            else:
                action = "🔵 观察"
                timing = "hold"

            monthly.append({
                "month": i + 1,
                "gan_zhi": month_gan + zhi,
                "dominant_element": dominant,
                "action": action,
                "timing": timing
            })

        return monthly


def main():
    """CLI入口"""
    import argparse
    parser = argparse.ArgumentParser(description="fusion-engine: 玄机融合Agent")
    parser.add_argument("--xiyong", type=str, default="木,水", help="喜用神（如木,水）")
    parser.add_argument("--avoid", type=str, default="金", help="忌神（如金）")
    parser.add_argument("--year", type=int, default=None, help="目标年份")
    parser.add_argument("--top", type=int, default=10, help="返回前N个板块")
    args = parser.parse_args()

    # 构造astro_calc输入（简化版）
    xi_parts = args.xiyong.split(",")
    avoid_parts = args.avoid.split(",")

    astro_input = {
        "bazi": {
            "xiyong": {"喜用": xi_parts[0], "次用": xi_parts[1] if len(xi_parts) > 1 else "金"},
            "avoid": avoid_parts,
            "elements": {"木": 40, "火": 20, "土": 10, "金": 10, "水": 20}
        }
    }

    # 构造cosmic输入（简化版）
    cosmic_input = {
        "meta": {"target_year": args.year or datetime.now().year},
        "macro_five_element": {
            "vector": {"木": 13, "火": 50, "土": 10, "金": 15, "水": 10}
        }
    }

    fe = FusionEngine(
        astro_calc_output=astro_input,
        cosmic_trend_output=cosmic_input,
        target_year=args.year or datetime.now().year
    )

    result = fe.run(top_n=args.top)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
