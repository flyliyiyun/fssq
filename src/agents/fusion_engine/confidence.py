"""
fusion-engine: confidence — 置信度评级
v3.0

根据融合结果的稳定性和数据完整性，给出置信度评级。
"""
import sys
import os
from datetime import datetime

_src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _src_root)
from constants import *


class ConfidenceRater:
    """置信度评级引擎"""

    def __init__(self, fused_vector, input_sources):
        """
        Args:
            fused_vector: 融合后的五行向量
            input_sources: 数据来源信息 {"astro": bool, "cosmic": bool, "ziwei": bool, ...}
        """
        self.fused = fused_vector
        self.sources = input_sources

    def rate(self, resonance_scores):
        """
        评级

        Args:
            resonance_scores: 板块打分结果

        Returns:
            dict: 置信度信息 {level, stars, confidence_score, factors}
        """
        # 计算置信度得分
        score = self._calc_confidence_score(resonance_scores)

        # 星级
        if score >= 85:
            stars = "★★★★★"
            level = "极高"
        elif score >= 70:
            stars = "★★★★☆"
            level = "高"
        elif score >= 55:
            stars = "★★★☆☆"
            level = "中"
        elif score >= 40:
            stars = "★★☆☆☆"
            level = "低"
        else:
            stars = "★☆☆☆☆"
            level = "极低"

        # 影响因素
        factors = self._analyze_factors(resonance_scores)

        return {
            "level": level,
            "stars": stars,
            "confidence_score": round(score, 1),
            "factors": factors,
            "timestamp": datetime.now().isoformat()
        }

    def _calc_confidence_score(self, resonance_scores):
        """计算置信度得分（0-100）"""
        score = 50  # 基础分

        # 1. 数据来源完整性（最高+20）
        source_bonus = 0
        if self.sources.get("astro"):
            source_bonus += 10
        if self.sources.get("cosmic"):
            source_bonus += 10
        if self.sources.get("ziwei"):
            source_bonus += 5
        if self.sources.get("qimen"):
            source_bonus += 3
        if self.sources.get("astrography"):
            source_bonus += 2
        score += min(source_bonus, 20)

        # 2. 打分差异度（最高+15）
        # 差异度越高，说明分析越有区分度
        if resonance_scores:
            scores = [s["score"] for s in resonance_scores[:5]]  # TOP5
            if scores:
                avg = sum(scores) / len(scores)
                max_score = max(scores)
                min_score = min(scores)
                spread = max_score - min_score

                # 差异度适中最好（30-50分差异最佳）
                if 30 <= spread <= 50:
                    score += 15
                elif spread > 50:
                    score += 10
                elif spread > 20:
                    score += 8
                else:
                    score += 5

        # 3. TOP1得分（最高+10）
        if resonance_scores and resonance_scores[0]["score"] >= 70:
            score += 10
        elif resonance_scores and resonance_scores[0]["score"] >= 60:
            score += 7
        elif resonance_scores and resonance_scores[0]["score"] >= 50:
            score += 4

        # 4. 五行向量均衡度（最高+5）
        values = list(self.fused.values())
        if values:
            max_val = max(values)
            min_val = min(values)
            ratio = min_val / max_val if max_val > 0 else 0

            # 如果太偏科，说明数据可能有偏
            if 0.3 <= ratio <= 0.7:
                score += 5
            elif ratio >= 0.2:
                score += 3

        return min(100, max(0, score))

    def _analyze_factors(self, resonance_scores):
        """分析影响因素"""
        factors = []

        # 数据来源
        if self.sources.get("astro"):
            factors.append("✓ 八字数据完整")
        if self.sources.get("cosmic"):
            factors.append("✓ 宏观数据完整")

        # TOP1得分
        if resonance_scores and resonance_scores[0]["score"] >= 70:
            factors.append("✓ 板块推荐明确")
        elif resonance_scores and resonance_scores[0]["score"] < 40:
            factors.append("⚠ 板块推荐模糊")

        # 忌神影响
        avoid_penalties = [s["avoid_penalty"] for s in resonance_scores]
        if any(p > 15 for p in avoid_penalties):
            factors.append("⚠ 部分忌神影响较大")

        return factors


def get_confidence_label(score):
    """获取置信度标签"""
    if score >= 85:
        return "极高可信"
    elif score >= 70:
        return "较高可信"
    elif score >= 55:
        return "中等可信"
    elif score >= 40:
        return "较低可信"
    else:
        return "可信度不足"
