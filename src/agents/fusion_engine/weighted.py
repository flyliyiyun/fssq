"""
fusion-engine: weighted — 加权融合算法
v3.0

根据PRD v2 §5.4，融合公式：
融合五行向量[element] = bazi_vector × 0.40 + ziwei_vector × 0.30
                      + qimen_vector × 0.20 + astro_vector × 0.10

Phase 2权重（无紫微/奇门/占星时）：
  八字 40% + 宏观 60%
"""
import sys
import os

_src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _src_root)
from constants import *


class WeightedFusion:
    """加权融合引擎"""

    # Phase 3权重（八字40%+紫微30%+奇门20%+占星10%）
    # PRD v2 §5.4 融合公式
    FUSION_WEIGHTS = {
        "bazi": 0.40,      # 八字命盘（核心）
        "ziwei": 0.30,     # 紫微斗数
        "qimen": 0.20,     # 奇门遁甲
        "astro": 0.10,     # 西方占星
    }

    def __init__(self, weights=None):
        self.weights = weights or self.FUSION_WEIGHTS

    def fuse(self, astro_json, cosmic_json=None, avoid_elements=None):
        """
        执行加权融合

        PRD v2 §5.4 融合公式：
        融合五行向量 = bazi_vector × 0.40 + ziwei_vector × 0.30
                      + qimen_vector × 0.20 + astro_vector × 0.10

        注意：cosmic-trend不参与融合，仅提供外部天象参考

        Args:
            astro_json: astro-calc输出JSON（包含八字、紫微、奇门、占星五行向量）
            cosmic_json: cosmic-trend输出JSON（当前版本不参与融合，仅提供板块映射参考）
            avoid_elements: 忌神列表，用于排除板块中的忌神五行

        Returns:
            dict: 融合后的五行向量 {"木": xx, "火": xx, "土": xx, "金": xx, "水": xx}
        """
        # 初始化融合向量
        fused = {el: 0.0 for el in ELEMENTS}
        total_weight = 0

        # 1. 八字向量 (权重40%)
        bazi_vector = self._extract_bazi_vector(astro_json)
        if bazi_vector:
            weight = self.weights.get("bazi", 0)
            for el in ELEMENTS:
                fused[el] += bazi_vector.get(el, 0) * weight
            total_weight += weight

        # 2. 紫微斗数向量 (权重30%)
        ziwei_vector = self._extract_ziwei_vector(astro_json)
        if ziwei_vector:
            weight = self.weights.get("ziwei", 0)
            for el in ELEMENTS:
                fused[el] += ziwei_vector.get(el, 0) * weight
            total_weight += weight

        # 3. 奇门遁甲向量 (权重20%)
        qimen_vector = self._extract_qimen_vector(astro_json)
        if qimen_vector:
            weight = self.weights.get("qimen", 0)
            for el in ELEMENTS:
                fused[el] += qimen_vector.get(el, 0) * weight
            total_weight += weight

        # 4. 西方占星向量 (权重10%)
        astro_vector = self._extract_astro_vector(astro_json)
        if astro_vector:
            weight = self.weights.get("astro", 0)
            for el in ELEMENTS:
                fused[el] += astro_vector.get(el, 0) * weight
            total_weight += weight

        # 归一化
        if total_weight > 0:
            max_val = max(fused.values()) if max(fused.values()) > 0 else 1
            for el in ELEMENTS:
                fused[el] = fused[el] / max_val * 100 if max_val > 0 else 50

        # 确保至少有一些分数
        for el in ELEMENTS:
            if fused[el] < 5:
                fused[el] = 5

        # 转为整数
        fused = {el: int(fused[el]) for el in ELEMENTS}

        return fused

    def _extract_bazi_vector(self, astro_json):
        """从astro_calc提取八字五行向量"""
        if not astro_json:
            return None
        bazi = astro_json.get("bazi", {})
        elements = bazi.get("five_element_vector") or bazi.get("elements", {})
        return elements if elements else None

    def _extract_ziwei_vector(self, astro_json):
        """从astro_calc提取紫微斗数五行向量"""
        if not astro_json:
            return None
        ziwei = astro_json.get("ziwei", {})
        return ziwei.get("five_element_vector", {})

    def _extract_qimen_vector(self, astro_json):
        """从astro_calc提取奇门遁甲五行向量
        兼容两种格式：
        1. astro_json["qimen"]["five_element_vector"] 或 ["qimen_vector"]
        2. astro_json["qimen_vector"] (顶层key)
        """
        if not astro_json:
            return None
        # 优先从顶层读取（astro_calc输出格式）
        top_vec = astro_json.get("qimen_vector")
        if top_vec and isinstance(top_vec, dict) and any(v > 0 for v in top_vec.values()):
            return top_vec
        # 从qimen对象内部读取
        qimen = astro_json.get("qimen", {})
        if isinstance(qimen, dict):
            inner_vec = qimen.get("five_element_vector") or qimen.get("qimen_vector", {})
            if inner_vec and isinstance(inner_vec, dict) and any(v > 0 for v in inner_vec.values()):
                return inner_vec
        return {}

    def _extract_astro_vector(self, astro_json):
        """从astro_calc提取西方占星五行向量"""
        if not astro_json:
            return None
        astrology = astro_json.get("astrology", {})
        if isinstance(astrology, dict):
            return astrology.get("five_element_vector", {})
        return {}

    def _default_bazi_vector(self, astro_json):
        """从八字提取五行向量"""
        bazi = astro_json.get("bazi", {})

        # 尝试从elements字段读取
        elements = bazi.get("elements", {})
        if elements:
            return elements

        # 尝试从四柱计算
        four_pillars = bazi.get("four_pillars", {})
        vector = {el: 0 for el in ELEMENTS}

        for pillar_name, pillar_value in four_pillars.items():
            if isinstance(pillar_value, str) and len(pillar_value) == 2:
                gan = pillar_value[0]
                zhi = pillar_value[1]
                vector[GAN_ELEMENT.get(gan, "土")] += 1
                vector[ZHI_ELEMENT.get(zhi, "土")] += 1

        # 归一化
        total = sum(vector.values()) or 1
        return {el: vector[el] / total * 100 for el in ELEMENTS}

    def get_weights_used(self):
        """返回使用的权重"""
        return self.weights

    def explain_fusion(self, astro_json, cosmic_json, fused_vector):
        """生成融合解释"""
        explanations = []

        # 八字贡献
        if astro_json and "bazi" in astro_json:
            bazi = astro_json["bazi"]
            # 优先从 yong_shen/xi_shen 读取
            yong = bazi.get("yong_shen")
            xi = bazi.get("xi_shen")
            # 兼容 xiyong 格式
            if not yong:
                xiyong = bazi.get("xiyong", {})
                if isinstance(xiyong, dict):
                    yong = xiyong.get("喜用", xiyong.get("primary", "木"))
                    xi = xiyong.get("次用", xiyong.get("secondary", "水"))
                elif isinstance(xiyong, list) and len(xiyong) >= 2:
                    yong = xiyong[0]
                    xi = xiyong[1]
            weight = self.weights.get("bazi", 0)
            explanations.append(f"八字×{weight:.0%}：命主用神{yong or '木'}、喜神{xi or '水'}，影响偏向")

        # 宏观贡献
        if cosmic_json and "macro_five_element" in cosmic_json:
            macro = cosmic_json["macro_five_element"]
            status = macro.get("status", {})
            dominant = max(status.items(), key=lambda x: x[1].get("score", 0) if isinstance(x[1], dict) else 0)[0] if status else "火"
            explanations.append(f"宏观天象：{dominant}气当令")

        return " | ".join(explanations)
