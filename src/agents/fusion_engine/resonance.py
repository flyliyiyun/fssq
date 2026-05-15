"""
fusion-engine: resonance — 共振打分引擎
v3.0

板块打分七步流程（PRD v2 §5.4）：
1. 各术数独立计算五行需求向量
2. 加权融合五行向量
3. 板块五行向量映射
4. 余弦相似度计算
5. 忌神惩罚（多源校验）
6. 奇门季节修正
7. 置信度评级
"""
import sys
import os
from math import sqrt

_src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _src_root)
from constants import *


class ResonanceScorer:
    """共振打分引擎"""

    def __init__(self, fused_vector, avoid_elements=None):
        """
        Args:
            fused_vector: 融合后的五行向量
            avoid_elements: 忌神列表（从八字读取）
        """
        self.fused = fused_vector
        self.avoid = avoid_elements or []

    def score_sector(self, sector_name, sector_elements):
        """
        计算板块得分

        Args:
            sector_name: 板块名称
            sector_elements: 板块五行向量（如 {"木": 0.1, "火": 0.6, ...}）

        Returns:
            dict: {score, cosine_sim, avoid_penalty, seasonal_bonus, reason}
        """
        # 1. 归一化板块向量
        sector_norm = self._normalize_sector(sector_name, sector_elements)

        # 2. 余弦相似度
        cosine_sim = self._cosine_similarity(self.fused, sector_norm)

        # 3. 忌神惩罚
        avoid_penalty = self._calc_avoid_penalty(sector_elements)

        # 4. 季节修正（简化为月度）
        seasonal_bonus = self._calc_seasonal_bonus(sector_name)

        # 5. 综合得分
        # 基础分 = 余弦相似度 × 100
        base_score = cosine_sim * 100

        # 最终分 = 基础分 - 忌神惩罚 + 季节修正
        final_score = base_score - avoid_penalty + seasonal_bonus

        # 限制在0-100
        final_score = max(0, min(100, final_score))

        # 6. 生成原因说明
        reason = self._explain_score(
            sector_elements,
            cosine_sim,
            avoid_penalty,
            seasonal_bonus
        )

        return {
            "score": round(final_score, 1),
            "cosine_sim": round(cosine_sim, 3),
            "avoid_penalty": round(avoid_penalty, 1),
            "seasonal_bonus": round(seasonal_bonus, 1),
            "reason": reason
        }

    def _normalize_sector(self, sector_name, sector_elements):
        """归一化板块向量"""
        # 从SECTOR_ELEMENTS获取标准映射
        for sector, elements in SECTOR_ELEMENTS.items():
            if sector in sector_name or sector_name in sector:
                return elements

        # 如果没找到，使用传入的elements
        if isinstance(sector_elements, dict):
            total = sum(sector_elements.values()) or 1
            return {el: sector_elements.get(el, 0) / total * 100 for el in ELEMENTS}

        return {el: 20 for el in ELEMENTS}

    def _cosine_similarity(self, vec1, vec2):
        """计算余弦相似度"""
        # 点积
        dot = sum(vec1.get(el, 0) * vec2.get(el, 0) for el in ELEMENTS)

        # 模长
        norm1 = sqrt(sum(vec1.get(el, 0) ** 2 for el in ELEMENTS))
        norm2 = sqrt(sum(vec2.get(el, 0) ** 2 for el in ELEMENTS))

        if norm1 == 0 or norm2 == 0:
            return 0.5

        return dot / (norm1 * norm2)

    def _calc_avoid_penalty(self, sector_elements):
        """计算忌神惩罚"""
        if not self.avoid:
            return 0

        penalty = 0
        for avoid_el in self.avoid:
            # 板块中忌神占比越高，惩罚越大
            if isinstance(sector_elements, dict):
                sector_ratio = sector_elements.get(avoid_el, 0)
                penalty += sector_ratio * 30  # 最高惩罚30分

        return min(penalty, 30)  # 最高惩罚30分

    def _calc_seasonal_bonus(self, sector_name):
        """计算季节修正（简化版）"""
        # 九运加成（2024-2043火运）
        fire_sectors = ["半导体", "军工", "新能源", "互联网", "电力"]
        for fs in fire_sectors:
            if fs in sector_name:
                return 5

        return 0

    def _explain_score(self, sector_elements, cosine_sim, avoid_penalty, seasonal_bonus):
        """生成得分解释"""
        reasons = []

        # 余弦相似度说明
        if cosine_sim >= 0.9:
            reasons.append("五行高度匹配")
        elif cosine_sim >= 0.7:
            reasons.append("五行较好匹配")
        elif cosine_sim >= 0.5:
            reasons.append("五行一般匹配")

        # 忌神说明
        if avoid_penalty > 0:
            reasons.append(f"忌神惩罚-{avoid_penalty:.0f}分")

        # 季节说明
        if seasonal_bonus > 0:
            reasons.append("九紫离火运加持")

        return "，".join(reasons) if reasons else "中性匹配"

    def rank_sectors(self, sectors):
        """
        对板块列表打分排序

        Args:
            sectors: 板块名称列表

        Returns:
            list: 排序后的板块列表 [{name, score, ...}, ...]
        """
        scored = []
        for sector in sectors:
            # 获取板块标准五行
            sector_elements = SECTOR_ELEMENTS.get(sector, {el: 20 for el in ELEMENTS})

            result = self.score_sector(sector, sector_elements)
            scored.append({
                "name": sector,
                "score": result["score"],
                "cosine_sim": result["cosine_sim"],
                "avoid_penalty": result["avoid_penalty"],
                "seasonal_bonus": result["seasonal_bonus"],
                "reason": result["reason"]
            })

        # 按得分降序排列
        scored.sort(key=lambda x: x["score"], reverse=True)

        # 添加排名
        for i, s in enumerate(scored):
            s["rank"] = i + 1

        return scored


def get_all_sectors():
    """获取所有可用板块"""
    return list(SECTOR_ELEMENTS.keys())
