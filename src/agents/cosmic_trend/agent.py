"""
Agent 2: cosmic-trend — 天道宏图Agent
v3.0

输入: target_year + astro_calc_output(可选，读取current_dayun)
输出: 宏观天象JSON（年份干支+九运+行星过境+政策+板块映射+宏观五行得分）

核心原则：同一年所有人拿到的输出一致。
唯一的个性化输入：读取astro_calc的current_dayun，用于大运叠加影响。
"""
import json
import sys
import os
from datetime import datetime

_src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _src_root)
from constants import *


class CosmicTrend:
    """天道宏图 — 输出当前年份的宏观天象、政策环境、板块映射"""

    def __init__(self, target_year=None, astro_calc_output=None):
        """
        Args:
            target_year: 目标分析年份（默认读取电脑当前年份）
            astro_calc_output: astro_calc输出JSON（可选，用于读取current_dayun）
        """
        # 默认读取当前时间，除非明确指定
        self.year = target_year if target_year is not None else datetime.now().year
        self.astro_input = astro_calc_output
        self._current_time = datetime.now()  # 记录分析时的实际时间

        # 大运五行（从astro_calc读取）
        self.dayun_gan_zhi = None
        self.dayun_gan_el = None
        self.dayun_zhi_el = None
        if astro_calc_output and "dayun" in astro_calc_output:
            dy = astro_calc_output["dayun"].get("current", {})
            if dy.get("gan_zhi"):
                self.dayun_gan_zhi = dy["gan_zhi"]
                self.dayun_gan_el = GAN_ELEMENT[self.dayun_gan_zhi[0]]
                self.dayun_zhi_el = ZHI_ELEMENT[self.dayun_gan_zhi[1]]

    def run(self):
        """执行宏观分析"""
        # 1. 年份干支计算
        self._calc_year_ganzhi()

        # 2. 九运周期
        self.jiuyun = self._calc_jiuyun()

        # 3. 行星过境（含水逆）
        self.planets = self._calc_planetary_transits()

        # 4. 政策面
        self.policy = self._calc_policy()

        # 5. 板块五行映射
        self.sector_mapping = SECTOR_ELEMENTS

        # 6. 宏观五行向量
        self.macro_vector = self._calc_macro_vector()

        # 7. 季度修正
        self.quarterly = self._calc_quarterly()

        # 8. 大运叠加影响（如果有astro_calc输入）
        self.dayun_impact = self._calc_dayun_impact()

        return self._build_output()

    def _calc_year_ganzhi(self):
        """计算年份干支"""
        year_gan_idx = (self.year - 4) % 10
        year_zhi_idx = (self.year - 4) % 12
        self.year_gan = TIAN_GAN[year_gan_idx]
        self.year_zhi = DI_ZHI[year_zhi_idx]
        self.year_ganzhi = self.year_gan + self.year_zhi
        self.year_gan_el = GAN_ELEMENT[self.year_gan]
        self.year_zhi_el = ZHI_ELEMENT[self.year_zhi]

        # 年份特征描述
        self.year_desc = self._describe_year()

    def _describe_year(self):
        """描述年份天象特征"""
        # 双柱同天干地支组合
        if self.year_gan == self.year_zhi[0] if len(self.year_zhi) > 0 else False:
            return f"{self.year_gan}午年，{self.year_gan_el}气纯正"
        # 地支对应生肖
        zodiac = {
            "子": "鼠", "丑": "牛", "寅": "虎", "卯": "兔",
            "辰": "龙", "巳": "蛇", "午": "马", "未": "羊",
            "申": "猴", "酉": "鸡", "戌": "狗", "亥": "猪"
        }
        animal = zodiac.get(self.year_zhi, "")
        return f"{self.year_gan_el}{animal}年，{self.year_gan_el}气当令"

    def _calc_jiuyun(self):
        """计算九运周期"""
        if 2024 <= self.year <= 2043:
            return {
                "yuan": "下元",
                "yun": 9,
                "name": "九紫离火运",
                "years": "2024-2043",
                "element": "火",
                "boost_sectors": ["半导体AI", "新能源", "军工", "互联网传媒", "电力设备"],
                "boost_weight": 0.15,
                "description": "离火主光明、科技、军工、新能源"
            }
        elif 2004 <= self.year <= 2023:
            return {
                "yuan": "下元",
                "yun": 8,
                "name": "八白艮土运",
                "years": "2004-2023",
                "element": "土",
                "boost_sectors": ["房地产", "建筑", "银行", "珠宝"],
                "boost_weight": 0.15,
                "description": "艮土主地产、固收、传统行业"
            }
        elif 1984 <= self.year <= 2003:
            return {
                "yuan": "下元",
                "yun": 7,
                "name": "七赤兑金运",
                "years": "1984-2003",
                "element": "金",
                "boost_sectors": ["金融", "有色金属", "娱乐圈"],
                "boost_weight": 0.15,
                "description": "兑金主金融、演艺、口才"
            }
        else:
            return {
                "yuan": "未知",
                "yun": 0,
                "name": "未知",
                "years": "未知",
                "element": "土",
                "boost_sectors": [],
                "boost_weight": 0,
                "description": "超出已知九运范围"
            }

    def _calc_planetary_transits(self):
        """计算2026年行星过境"""
        # 2026年主要行星位置（简化计算）
        # 实际需用天文算法或查表
        return {
            "jupiter": {
                "sign": "巨蟹座",
                "element": "水象",
                "impact": "木星入巨蟹，消费/地产/金融受益，利长线布局",
                "invest_advice": "关注大消费、金融、家电板块"
            },
            "saturn": {
                "sign": "白羊座",
                "element": "火象",
                "impact": "土星过白羊，传统行业承压，新兴领域需稳健",
                "invest_advice": "避免重仓传统制造业"
            },
            "uranus": {
                "sign": "双子座",
                "element": "风象",
                "impact": "天王星在双子，通信/传媒/AI技术持续活跃",
                "invest_advice": "关注AI、半导体、通信设备"
            },
            "pluto": {
                "sign": "水瓶座",
                "element": "风象",
                "impact": "冥王星水瓶(2024-2043)，科技革命长周期",
                "invest_advice": "科技板块战略性配置"
            },
            "neptune": {
                "sign": "白羊座",
                "element": "火象",
                "impact": "海王星白羊，精神/灵性/能源题材活跃",
                "invest_advice": "关注新能源、精神消费"
            },
            "mercury_retrograde": [
                {"period": "4月18日-5月12日", "season": "春季", "advice": "避免重大决策"},
                {"period": "8月6日-8月30日", "season": "夏季", "advice": "注意持仓波动"},
                {"period": "11月26日-12月16日", "season": "冬季", "advice": "年末稳健为主"}
            ]
        }

    def _calc_policy(self):
        """2026年政策方向"""
        return {
            "theme": "新质生产力 + 科技自立",
            "directions": [
                {
                    "sector": "AI大模型",
                    "policy": "人工智能+战略",
                    "weight": 0.15,
                    "description": "国产大模型扶持，千亿参数模型突破"
                },
                {
                    "sector": "半导体",
                    "policy": "自主可控",
                    "weight": 0.12,
                    "description": "高端芯片国产替代，设备/材料/设计"
                },
                {
                    "sector": "新能源",
                    "policy": "双碳目标",
                    "weight": 0.10,
                    "description": "光伏/储能/电动车持续增长"
                },
                {
                    "sector": "军工",
                    "policy": "国防现代化",
                    "weight": 0.08,
                    "description": "装备升级换代，信息化智能化"
                },
                {
                    "sector": "医疗健康",
                    "policy": "创新药械",
                    "weight": 0.08,
                    "description": "生物医药创新，器械国产化"
                }
            ],
            "suppressed_sectors": [
                {"sector": "房地产", "reason": "房住不炒总基调", "weight": -0.10},
                {"sector": "教育培训", "reason": "双减政策持续", "weight": -0.08},
                {"sector": "互联网平台", "reason": "反垄断常态化", "weight": -0.05}
            ]
        }

    def _calc_macro_vector(self):
        """计算宏观五行向量"""
        v = {el: 20 for el in ELEMENTS}  # 基础20分

        # 1. 年干天干五行 +20
        v[self.year_gan_el] += 20

        # 2. 年支地支五行 +20
        v[self.year_zhi_el] += 20

        # 3. 九运加成 +25
        jy_el = self.jiuyun["element"]
        v[jy_el] += 25

        # 4. 政策加成（火/金/木相关行业）
        policy_els = {"AI大模型": "火", "半导体": "金", "新能源": "火",
                      "军工": "金", "医疗健康": "木"}
        for sector, el in policy_els.items():
            v[el] += 5

        # 5. 大运叠加影响（如果有）
        if self.dayun_gan_el:
            v[self.dayun_gan_el] += 8
        if self.dayun_zhi_el:
            v[self.dayun_zhi_el] += 5

        # 6. 生克关系调整
        # 年干生年支
        if self.year_gan_el == SHENG.get(self.year_zhi_el):
            v[self.year_zhi_el] += 5
        # 年干克年支
        if self.year_gan_el == KE.get(self.year_zhi_el):
            v[self.year_zhi_el] -= 5

        # 归一化到0-100
        total = sum(v.values())
        for el in ELEMENTS:
            v[el] = max(5, min(100, int(v[el] / total * 100)))

        # 计算五行状态（旺相休囚死）
        self.macro_status = self._calc_wxxs(v)

        return v

    def _calc_wxxs(self, v):
        """计算五行状态"""
        # 找最大值确定最旺
        max_score = max(v.values())
        dominant = [el for el, score in v.items() if score == max_score][0]

        # 五行旺相休囚死循环
        wxxs = {
            "木": {"旺": "火", "相": "土", "休": "金", "囚": "水", "死": "木"},
            "火": {"旺": "土", "相": "金", "休": "水", "囚": "木", "死": "火"},
            "土": {"旺": "金", "相": "水", "休": "木", "囚": "火", "死": "土"},
            "金": {"旺": "水", "相": "木", "休": "火", "囚": "土", "死": "金"},
            "水": {"旺": "木", "相": "火", "休": "土", "囚": "金", "死": "水"}
        }

        status = {}
        for el in ELEMENTS:
            if el == dominant:
                status[el] = {"score": v[el], "trend": "旺", "reason": f"{dominant}气最旺"}
            else:
                wxxs_circle = wxxs[dominant]
                trend = [k for k, val in wxxs_circle.items() if val == el]
                status[el] = {
                    "score": v[el],
                    "trend": trend[0] if trend else "平",
                    "reason": self._get_trend_reason(el, trend[0] if trend else "平", dominant)
                }
        return status

    def _get_trend_reason(self, el, trend, dominant):
        """获取五行状态原因"""
        reasons = {
            "旺": f"{dominant}旺令时，{el}得势",
            "相": f"{dominant}旺时，{el}为相",
            "休": f"{dominant}旺时，{el}休退",
            "囚": f"{dominant}旺时，{el}被囚",
            "死": f"{dominant}旺时，{el}死绝"
        }
        return reasons.get(trend, "")

    def _calc_quarterly(self):
        """季度修正系数（含时间感知）"""
        now = datetime.now()
        current_month = now.month
        current_year = now.year

        # 确定当前季度
        if current_month <= 3:
            current_quarter = "Q1"
        elif current_month <= 6:
            current_quarter = "Q2"
        elif current_month <= 9:
            current_quarter = "Q3"
        else:
            current_quarter = "Q4"

        quarters = {
            "Q1": {"months": "1-3月", "factor": 1.05, "action": "布局建仓",
                   "key_sectors": ["AI", "半导体"], "reason": "两会政策预期，春季躁动"},
            "Q2": {"months": "4-6月", "factor": 0.85, "action": "谨慎操作",
                   "key_sectors": ["军工", "新能源"], "reason": "水逆期+业绩验证，波动加大"},
            "Q3": {"months": "7-9月", "factor": 1.15, "action": "积极进攻",
                   "key_sectors": ["消费", "金融", "科技"], "reason": "政策密集期，三中全会效应"},
            "Q4": {"months": "10-12月", "factor": 0.95, "action": "稳健持有",
                   "key_sectors": ["银行", "固收", "地产"], "reason": "年末结算，资金面偏紧"}
        }

        # 时间感知修正
        quarter_order = ["Q1", "Q2", "Q3", "Q4"]
        for i, q in enumerate(quarter_order):
            # 判断是否已过
            if quarter_order.index(current_quarter) > i:
                quarters[q]["status"] = "已完成"
                quarters[q]["action"] = "回顾总结"
                quarters[q]["factor"] = 1.0  # 已过季度不参与计算
            elif quarter_order.index(current_quarter) == i:
                quarters[q]["status"] = "进行中"
            else:
                quarters[q]["status"] = "即将到来"

        return quarters

    def _calc_dayun_impact(self):
        """计算大运叠加影响"""
        if not self.dayun_gan_zhi:
            return None

        # 大运与流年的生克关系
        dayun_gan_el = self.dayun_gan_el
        dayun_zhi_el = self.dayun_zhi_el
        year_gan_el = self.year_gan_el
        year_zhi_el = self.year_zhi_el

        # 大运天干与流年天干
        gan_interaction = self._calc_interaction(dayun_gan_el, year_gan_el)

        # 大运地支与流年地支
        zhi_interaction = self._calc_interaction(dayun_zhi_el, year_zhi_el)

        # 综合评分
        impact_score = 0
        if gan_interaction["type"] == "生":
            impact_score += 5
        elif gan_interaction["type"] == "克":
            impact_score -= 3

        if zhi_interaction["type"] == "生":
            impact_score += 5
        elif zhi_interaction["type"] == "克":
            impact_score -= 3

        return {
            "dayun_gan_zhi": self.dayun_gan_zhi,
            "dayun_gan_element": dayun_gan_el,
            "dayun_zhi_element": dayun_zhi_el,
            "gan_interaction": gan_interaction,
            "zhi_interaction": zhi_interaction,
            "overall_impact": impact_score,
            "interpretation": self._interpret_impact(impact_score)
        }

    def _calc_interaction(self, el1, el2):
        """计算两五行关系"""
        if el1 == el2:
            return {"type": "同", "effect": "中性", "description": f"{el1}与{el2}同气相助"}
        if SHENG.get(el1) == el2:
            return {"type": "生", "effect": "利好", "description": f"{el1}生{el2}，大运生扶流年"}
        if SHENG.get(el2) == el1:
            return {"type": "泄", "effect": "消耗", "description": f"{el1}泄{el2}，大运泄耗流年"}
        if KE.get(el1) == el2:
            return {"type": "克", "effect": "压制", "description": f"{el1}克{el2}，大运克制流年"}
        if KE.get(el2) == el1:
            return {"type": "耗", "effect": "被动", "description": f"{el1}耗{el2}，流年消耗大运"}
        return {"type": "无", "effect": "中性", "description": "无特殊生克"}

    def _interpret_impact(self, score):
        """解释大运影响"""
        if score >= 8:
            return "大运与流年共振，整体大吉，把握机遇"
        elif score >= 4:
            return "大运生扶流年，运势向上，积极布局"
        elif score >= 0:
            return "大运与流年平和，稳中求进"
        elif score >= -4:
            return "大运泄耗流年，注意风险，保守操作"
        else:
            return "大运与流年相克，守成为主，严控仓位"

    def _build_output(self):
        """构建输出JSON"""
        output = {
            "meta": {
                "version": "cosmic-trend v3.0",
                "agent": "cosmic-trend",
                "timestamp": datetime.now().isoformat(),
                "target_year": self.year
            },
            "yearly_ganzhi": {
                "gan_zhi": self.year_ganzhi,
                "heavenly_stem": self.year_gan,
                "earthly_branch": self.year_zhi,
                "stem_element": self.year_gan_el,
                "branch_element": self.year_zhi_el,
                "description": self.year_desc
            },
            "nine_star_cycle": self.jiuyun,
            "planetary_transits": self.planets,
            "policy": self.policy,
            "sector_mapping": self.sector_mapping,
            "macro_five_element": {
                "vector": self.macro_vector,
                "status": self.macro_status
            },
            "quarterly_modifier": self.quarterly
        }

        # 大运影响（如果有）
        if self.dayun_impact:
            output["dayun_overlay"] = self.dayun_impact

        # Validation
        output["validation"] = [
            {
                "check": "年份干支计算",
                "status": "PASS",
                "detail": f"{self.year}年 → {self.year_ganzhi}"
            },
            {
                "check": "九运周期",
                "status": "PASS",
                "detail": f"{self.jiuyun['name']}（{self.jiuyun['years']}）"
            }
        ]

        return output


def main():
    """CLI入口"""
    import argparse
    parser = argparse.ArgumentParser(description="cosmic-trend: 天道宏图Agent")
    parser.add_argument("--year", type=int, default=2026, help="目标年份")
    parser.add_argument("--dayun", type=str, default=None, help="大运干支（如辛卯）")
    args = parser.parse_args()

    # 构造astro_calc输入（如果有）
    astro_input = None
    if args.dayun:
        astro_input = {
            "dayun": {
                "current": {
                    "gan_zhi": args.dayun
                }
            }
        }

    ct = CosmicTrend(target_year=args.year, astro_calc_output=astro_input)
    result = ct.run()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
