"""
Orchestrator: 4-Agent串联编排器
v1.0

串联流程:
  astro-calc → cosmic-trend → fusion-engine + star-hunter → template

用法:
  python orchestrator.py --birth "1974-07-05" --hour 17 --gender 男 --place "开封" --year 2026
"""
import sys
import os
import json
import argparse
from datetime import datetime

# 设置路径
_src_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _src_root)

# ============================================================
# Step 1: 导入4个Agent
# ============================================================
print("=" * 60)
print("FSSQ v4.0 玄学选股引擎 — 4-Agent串联")
print("=" * 60)

# Agent 1: astro-calc (命盘精算)
print("\n[1/4] 加载 astro-calc (命盘精算)...")
try:
    from agents.astro_calc.agent import AstroCalc
    print("  ✅ astro-calc loaded")
except ImportError as e:
    print(f"  ❌ astro-calc import error: {e}")
    AstroCalc = None

# Agent 2: cosmic-trend (天道宏图)
print("[2/4] 加载 cosmic-trend (天道宏图)...")
try:
    from agents.cosmic_trend.agent import CosmicTrend
    print("  ✅ cosmic-trend loaded")
except ImportError as e:
    print(f"  ❌ cosmic-trend import error: {e}")
    CosmicTrend = None

# Agent 3: fusion-engine (玄机融合)
print("[3/4] 加载 fusion-engine (玄机融合)...")
try:
    from agents.fusion_engine.agent import FusionEngine
    from agents.fusion_engine.template import generate_html
    print("  ✅ fusion-engine loaded")
except ImportError as e:
    print(f"  ❌ fusion-engine import error: {e}")
    FusionEngine = None
    generate_html = None

# Agent 4: star-hunter (个股猎手)
print("[4/4] 加载 star-hunter (个股猎手)...")
try:
    from agents.star_hunter.agent import StarHunter
    from agents.star_hunter.snipe_integration import enrich_with_snipescore_full
    print("  ✅ star-hunter loaded")
    print("  ✅ snipe_integration loaded")
except ImportError as e:
    print(f"  ❌ star-hunter import error: {e}")
    StarHunter = None
    enrich_with_snipescore_full = None


# ============================================================
# Step 2: 定义Orchestrator类
# ============================================================
class FSSQOrchestrator:
    """4-Agent串联编排器"""

    def __init__(self, config):
        """
        config: {
            "birth_date": "1974-07-05",
            "birth_hour": 17,
            "gender": "男",
            "birth_place": "开封",
            "target_year": 2026,
            "lat_lon": (34.79, 114.35),  # 出生地经纬度 (可选)
            "current_place": "深圳"       # 现居地 (可选)
        }
        """
        self.config = config
        self.birth_date = config["birth_date"]
        self.birth_hour = config["birth_hour"]
        self.gender = config["gender"]
        self.birth_place = config.get("birth_place", "")
        self.target_year = config.get("target_year", datetime.now().year)
        self.lat_lon = config.get("lat_lon")
        self.current_place = config.get("current_place", "")

        # 输出结果
        self.astro_result = None
        self.cosmic_result = None
        self.fusion_result = None
        self.star_hunter_result = None
        self.html_report = None

        # 错误记录
        self.errors = []

    def run(self):
        """执行完整的4-Agent流程"""
        print(f"\n{'='*60}")
        print(f"开始生成 {self.target_year} 年投资报告")
        print(f"命主: {self.birth_date} {self.birth_hour}时 {self.gender} {self.birth_place}")
        print(f"{'='*60}")

        # Step 1: astro-calc (命盘精算)
        self._run_astro_calc()

        # Step 2: cosmic-trend (天道宏图)
        self._run_cosmic_trend()

        # Step 3: fusion-engine (玄机融合)
        self._run_fusion_engine()

        # Step 4: star-hunter (个股猎手)
        self._run_star_hunter()

        # Step 5: 生成HTML报告
        self._generate_report()

        return self._build_summary()

    def _run_astro_calc(self):
        """Step 1: 执行astro-calc"""
        print("\n📊 Step 1: 命盘精算 (astro-calc)")

        try:
            if AstroCalc is None:
                raise ImportError("AstroCalc not available")

            # 构造birth_info
            birth_info = {
                "year": int(self.birth_date.split("-")[0]),
                "month": int(self.birth_date.split("-")[1]),
                "day": int(self.birth_date.split("-")[2]),
                "hour": self.birth_hour,
                "minute": 0,
                "gender": self.gender,
                "birth_place": self.birth_place,
                "target_year": self.target_year,
                "birth_lat": self.lat_lon[0] if self.lat_lon else None,
                "birth_lon": self.lat_lon[1] if self.lat_lon else None,
                "residence": self.current_place
            }

            calc = AstroCalc(birth_info)
            self.astro_result = calc.run()

            # 数据标准化：修复astro-calc格式差异
            self._normalize_astro_data()

            print(f"  ✅ 命盘计算完成")
            print(f"     八字: {self._extract_bazi()}")

        except Exception as e:
            print(f"  ⚠️ astro-calc 失败: {e}")
            import traceback
            traceback.print_exc()
            self.errors.append(f"astro-calc: {e}")
            # 使用默认结构
            self.astro_result = self._get_default_astro()

    def _run_cosmic_trend(self):
        """Step 2: 执行cosmic-trend"""
        print("\n🌌 Step 2: 天道宏图 (cosmic-trend)")

        try:
            if CosmicTrend is None:
                raise ImportError("CosmicTrend not available")

            agent = CosmicTrend(
                target_year=self.target_year,
                astro_calc_output=self.astro_result
            )
            self.cosmic_result = agent.run()

            # 把yearly_ganzhi转换为兼容格式
            yearly_ganzhi = self.cosmic_result.get('yearly_ganzhi', {})
            if isinstance(yearly_ganzhi, dict):
                self.cosmic_result['年份干支'] = yearly_ganzhi.get('gan_zhi', '丙午')
            else:
                self.cosmic_result['年份干支'] = str(yearly_ganzhi) if yearly_ganzhi else '丙午'

            # 数据标准化：修复cosmic-trend格式差异
            self._normalize_cosmic_data()

            print(f"  ✅ 宏观分析完成")
            print(f"     年份干支: {self.cosmic_result.get('年份干支', '?')}")

        except Exception as e:
            print(f"  ⚠️ cosmic-trend 失败: {e}")
            import traceback
            traceback.print_exc()
            self.errors.append(f"cosmic-trend: {e}")
            # 使用默认结构
            self.cosmic_result = self._get_default_cosmic()

    def _normalize_astro_data(self):
        """标准化astro_calc输出，修复格式差异"""
        if not self.astro_result:
            return

        # 1. 修复 ziwei.favorable_elements 和 unfavorable_elements (None → 从喜用神推断)
        ziwei = self.astro_result.get('ziwei', {})
        if ziwei.get('favorable_elements') is None:
            bazi = self.astro_result.get('bazi', {})
            favorable = bazi.get('favorable', {})
            # 从favorable中提取喜用神
            yong = favorable.get('用神', {})
            xi = favorable.get('喜神', {})
            if isinstance(yong, dict):
                ziwei['favorable_elements'] = [yong.get('element', '土')]
            if isinstance(xi, dict) and ziwei.get('favorable_elements'):
                ziwei['favorable_elements'].append(xi.get('element', '金'))
            elif isinstance(xi, dict):
                ziwei['favorable_elements'] = [xi.get('element', '金')]

            # 提取忌神
            ji_list = bazi.get('ji_shen', [])
            if isinstance(ji_list, list) and ji_list:
                ziwei['unfavorable_elements'] = ji_list[:2]
            else:
                ji = favorable.get('忌神', {})
                if isinstance(ji, dict):
                    ziwei['unfavorable_elements'] = [ji.get('element', '木')]
                else:
                    ziwei['unfavorable_elements'] = ['木', '火']

        # 2. 修复 ziwei.annual_sihua 缺少 palace 字段
        annual_sihua = ziwei.get('annual_sihua', {})
        if 'sihua' in annual_sihua:
            palace_map = {
                '禄': '田宅宫',
                '权': '命宫',
                '科': '官禄宫',
                '忌': '财帛宫'
            }
            for item in annual_sihua['sihua']:
                if 'palace' not in item:
                    item['palace'] = palace_map.get(item.get('type', ''), '命宫')

        # 3. 修复 astology.transit 英文key → 中文
        astrology = self.astro_result.get('astrology', {})
        transit = astrology.get('transit', {})
        chinese_map = {
            'jupiter': '木星', 'saturn': '土星', 'uranus': '天王星',
            'pluto': '冥王星', 'neptune': '海王星', 'mercury': '水星',
            'venus': '金星', 'mars': '火星', 'sun': '太阳', 'moon': '月亮'
        }
        for eng, chn in chinese_map.items():
            if eng in transit and chn not in transit:
                transit[chn] = transit[eng]

        print(f"  🔧 数据标准化完成")

    def _normalize_cosmic_data(self):
        """标准化cosmic-trend输出，修复格式差异"""
        if not self.cosmic_result:
            return

        # 1. 修复 quarterly_modifier: Q1/Q2/Q3/Q4 → 春季/夏季/秋季/冬季
        qm = self.cosmic_result.get('quarterly_modifier', {})
        if 'Q1' in qm and '春季' not in qm:
            qm['春季'] = qm.get('Q1', {})
            qm['夏季'] = qm.get('Q2', {})
            qm['秋季'] = qm.get('Q3', {})
            qm['冬季'] = qm.get('Q4', {})

        # 2. 修复 nine_star_cycle: 嵌套dict → 字符串
        nine_star = self.cosmic_result.get('nine_star_cycle', {})
        if isinstance(nine_star, dict) and 'name' in nine_star:
            self.cosmic_result['九运'] = nine_star.get('name', '九紫离火运')

        # 3. 修复 planetary_transits: 英文key → 中文
        pt = self.cosmic_result.get('planetary_transits', {})
        chinese_map = {
            'jupiter': '木星', 'saturn': '土星', 'uranus': '天王星',
            'pluto': '冥王星', 'neptune': '海王星', 'mercury': '水星',
            'venus': '金星', 'mars': '火星'
        }
        for eng, chn in chinese_map.items():
            if eng in pt and chn not in pt:
                pt[chn] = pt[eng]

        print(f"  🔧 数据标准化完成")

    def _run_fusion_engine(self):
        """Step 3: 执行fusion-engine"""
        print("\n⚡ Step 3: 玄机融合 (fusion-engine)")

        try:
            if FusionEngine is None:
                raise ImportError("FusionEngine not available")

            engine = FusionEngine(
                astro_calc_output=self.astro_result,
                cosmic_trend_output=self.cosmic_result,
                target_year=self.target_year
            )

            self.fusion_result = engine.run(top_n=10)

            # 提取喜用神
            xiyong = self.fusion_result.get("input_summary", {}).get("xiyong", {})
            print(f"  ✅ 融合完成")
            print(f"     喜用神: {xiyong.get('primary', '?')} + {xiyong.get('secondary', '?')}")

            # 提取top_stocks (如果fusion-engine有)
            if "top_stocks" not in self.fusion_result:
                self.fusion_result["top_stocks"] = []

        except Exception as e:
            print(f"  ⚠️ fusion-engine 失败: {e}")
            self.errors.append(f"fusion-engine: {e}")
            self.fusion_result = self._get_default_fusion()

    def _run_star_hunter(self):
        """Step 4: 执行star-hunter + SnipeScore评分"""
        print("\n🎯 Step 4: 个股猎手 (star-hunter)")

        try:
            if StarHunter is None:
                raise ImportError("StarHunter not available")

            hunter = StarHunter(
                astro_calc_output=self.astro_result,
                cosmic_trend_output=self.cosmic_result,
                target_year=self.target_year
            )

            # Step 4a: 获取玄学候选（全量，不限top_n）
            raw_result = hunter.run(top_n=20)  # top_n仅限制返回数量，不限制候选池

            # Step 4b: 获取全量候选股票供SnipeScore评分
            all_candidates = raw_result.get("all_candidates", [])
            if not all_candidates:
                stocks = raw_result.get("recommendations", {}).get("stocks", [])
                all_candidates = stocks

            print(f"  ✅ 玄学候选股票: {len(all_candidates)}只")

            # Step 4c: SnipeScore全量评分（含腾讯行情+并发8维评分+AKShare K线补充）
            if all_candidates and enrich_with_snipescore_full is not None:
                print(f"  📊 开始SnipeScore全量评分...")
                try:
                    enriched = enrich_with_snipescore_full(
                        stocks=all_candidates,
                        fusion_result=self.fusion_result,
                        target_year=self.target_year,
                        snipe_weight=0.70,
                        max_workers=10,
                    )
                    print(f"  ✅ SnipeScore评分完成: {len(enriched)}只")
                except Exception as snipe_err:
                    print(f"  ⚠️ SnipeScore评分失败（玄学模式）: {snipe_err}")
                    enriched = all_candidates
            else:
                enriched = all_candidates

            # 把top_stocks注入fusion_result（用于HTML报告）
            if enriched:
                self.fusion_result["top_stocks"] = enriched[:10]
                print(f"     精选个股: {len(enriched)}只")
                if enriched:
                    print(f"     首选: {enriched[0].get('name', '?')} ({enriched[0].get('code', '?')})")
                    snipe_avail = '✅' if enriched[0].get('snipe_available') else '⚠️'
                    print(f"     SnipeScore: {enriched[0].get('snipe_score', 0):.1f} {snipe_avail}")

            # 重新构建star_hunter_result（保持原结构，替换stocks为enriched）
            raw_result["recommendations"]["stocks"] = enriched[:20]
            self.star_hunter_result = raw_result

        except Exception as e:
            print(f"  ⚠️ star-hunter 失败: {e}")
            self.errors.append(f"star-hunter: {e}")
            self.star_hunter_result = {"recommendations": {"stocks": []}}
    def _generate_report(self):
        """Step 5: 生成HTML报告"""
        print("\n📄 Step 5: 生成HTML报告")

        try:
            if generate_html is None:
                raise ImportError("generate_html not available")

            self.html_report = generate_html(
                astro=self.astro_result,
                cosmic=self.cosmic_result,
                fusion_result=self.fusion_result,
                star_hunter_result=self.star_hunter_result
            )

            # 保存报告
            safe_name = f"{self.birth_date.replace('-', '')}_{self.gender}_{self.target_year}"
            output_path = os.path.join(
                _src_root, "output", f"FSSQ_{safe_name}.html"
            )

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(self.html_report)

            print(f"  ✅ 报告已保存: {output_path}")
            print(f"     文件大小: {len(self.html_report):,} 字符")

            return output_path

        except Exception as e:
            print(f"  ❌ 报告生成失败: {e}")
            self.errors.append(f"template: {e}")
            return None

    def _build_summary(self):
        """构建执行摘要"""
        summary = {
            "status": "SUCCESS" if not self.errors else "PARTIAL",
            "errors": self.errors,
            "astro_status": bool(self.astro_result),
            "cosmic_status": bool(self.cosmic_result),
            "fusion_status": bool(self.fusion_result),
            "star_hunter_status": bool(self.star_hunter_result),
            "bazi": self._extract_bazi(),
            "xiyong": self._extract_xiyong(),
            "top_sectors": self._extract_top_sectors(),
            "top_stocks": self._extract_top_stocks()
        }
        return summary

    def _extract_bazi(self):
        """提取八字"""
        try:
            bazi = self.astro_result.get("bazi", {})
            fp = bazi.get("four_pillars", {})
            return f"{fp.get('year', '?')}{fp.get('month', '?')}{fp.get('day', '?')}{fp.get('hour', '?')}"
        except:
            return "?"

    def _extract_xiyong(self):
        """提取喜用神"""
        try:
            xiyong = self.fusion_result.get("input_summary", {}).get("xiyong", {})
            return f"{xiyong.get('primary', '?')} + {xiyong.get('secondary', '?')}"
        except:
            return "?"

    def _extract_top_sectors(self):
        """提取推荐板块"""
        try:
            sectors = self.fusion_result.get("recommended_sectors", [])[:3]
            return [s.get("name", "?") for s in sectors]
        except:
            return []

    def _extract_top_stocks(self):
        """提取推荐个股"""
        try:
            stocks = self.star_hunter_result.get("recommendations", {}).get("stocks", [])[:5]
            return [{"name": s.get("name", "?"), "code": s.get("code", "?")} for s in stocks]
        except:
            return []

    def _get_default_astro(self):
        """获取默认astro结构"""
        return {
            "user_input": self.config,
            "bazi": {
                "four_pillars": {"year": "甲寅", "month": "庚午", "day": "丁未", "hour": "己酉"},
                "xiyong": {"喜用": "土", "次用": "金"},
                "strength_breakdown": {"得令": 5, "得地": 2, "得势": -1},
                "five_element_vector": {"木": 18, "火": 24, "土": 94, "金": 57, "水": 23},
                "favorable": {
                    "strength": "身旺",
                    "用神": {"element": "土", "reason": "泄去过旺火气"},
                    "喜神": {"element": "金", "reason": "接收食伤之气"}
                }
            },
            "dayun": {
                "current": {"gan_zhi": "丙子", "year_start": 2025, "year_end": 2035, "age_start": 50, "age_end": 60},
                "sequence": [
                    {"gan_zhi": "辛未", "year_start": 1975, "year_end": 1984, "age_start": 1, "age_end": 10},
                    {"gan_zhi": "壬申", "year_start": 1985, "year_end": 1994, "age_start": 10, "age_end": 20},
                    {"gan_zhi": "癸酉", "year_start": 1995, "year_end": 2004, "age_start": 20, "age_end": 30},
                    {"gan_zhi": "甲戌", "year_start": 2005, "year_end": 2014, "age_start": 30, "age_end": 40},
                    {"gan_zhi": "乙亥", "year_start": 2015, "year_end": 2024, "age_start": 40, "age_end": 50},
                    {"gan_zhi": "丙子", "year_start": 2025, "year_end": 2035, "age_start": 50, "age_end": 60},
                ],
                "description": "丙子大运，火水交战"
            },
            "ziwei": {
                "annual_sihua": {
                    "sihua": [
                        {"star": "天同", "type": "禄", "palace": "田宅宫", "impact": "天同化禄入田宅"},
                        {"star": "天机", "type": "权", "palace": "命宫", "impact": "天机化权入命宫"},
                        {"star": "文昌", "type": "科", "palace": "官禄宫", "impact": "文昌化科利智慧投资"},
                        {"star": "廉贞", "type": "忌", "palace": "财帛宫", "impact": "廉贞化忌需注意投机风险"}
                    ]
                },
                "favorable_elements": ["土", "金"],
                "unfavorable_elements": ["木", "火"],
                "key_palaces": {
                    "命宫": {"star": "天机", "element": "木", "interpretation": "天机星聪明灵活"},
                    "财帛宫": {"star": "武曲", "element": "金", "interpretation": "武曲星财运务实稳健"}
                },
                "five_element_vector": {"木": 35, "火": 40, "土": 75, "金": 65, "水": 50}
            },
            "qimen": {
                "value_star": "天芮星",
                "value_star_element": "土",
                "value_star_impact": "主医药、地产、教育",
                "value_gate": "死门",
                "value_gate_element": "土",
                "value_gate_impact": "死门值使，全年偏保守",
                "eight_gates_seasonal": {
                    "春季(2-4月)": {"gates": ["生门"], "score": 1.10, "action": "适度操作"},
                    "夏季(5-7月)": {"gates": ["景门", "白虎"], "score": 0.56, "action": "极度谨慎"},
                    "秋季(8-10月)": {"gates": ["开门", "休门"], "score": 1.20, "action": "大胆进攻"},
                    "冬季(11-1月)": {"gates": ["休门", "生门"], "score": 1.00, "action": "正常持有"}
                }
            },
            "astrology": {
                "natal": {
                    "sun": {"sign": "巨蟹座", "interpretation": "投资风格重安全感"},
                    "moon": {"sign": "天蝎座", "interpretation": "直觉敏锐，适合深度研究"},
                    "rising": {"sign": "天秤座", "interpretation": "审美偏好金融类资产"}
                },
                "transit": {
                    "木星": {"sign": "巨蟹座", "impact": "木星过太阳星座，财运年！"},
                    "土星": {"sign": "白羊座", "impact": "新领域承压"}
                }
            },
            "astro_vector": {"木": 25, "火": 30, "土": 80, "金": 60, "水": 55}
        }

    def _get_default_cosmic(self):
        """获取默认cosmic结构"""
        return {
            "年份干支": "丙午",
            "yearly_ganzhi": "丙午",
            "九运": "九紫离火运(2024-2043)",
            "nine_star_cycle": "九紫离火运",
            "macro_five_element": {"vector": {"木": 23, "火": 95, "土": 75, "金": 30, "水": 20}},
            "planetary_transits": {
                "mercury_retrograde": [
                    {"period": "4月18日-5月12日", "season": "春季", "advice": "水逆影响思考"}
                ]
            },
            "quarterly_modifier": {
                "春季": {"action": "稳健布局", "factor": 1.10},
                "夏季": {"action": "极度谨慎", "factor": 0.56},
                "秋季": {"action": "大胆进攻", "factor": 1.20},
                "冬季": {"action": "正常持有", "factor": 1.00}
            }
        }

    def _get_default_fusion(self):
        """获取默认fusion结构"""
        return {
            "fused_five_element": {
                "vector": {"木": 20, "火": 25, "土": 25, "金": 20, "水": 10},
                "dominant": "土"
            },
            "recommended_sectors": [
                {"rank": 1, "name": "房地产", "score": 78.5, "reason": "土金属性"},
                {"rank": 2, "name": "建筑建材", "score": 75.2, "reason": "土金共振"},
                {"rank": 3, "name": "银行", "score": 72.0, "reason": "土金双属性"}
            ],
            "forbidden_sectors": [
                {"name": "军工", "score": 25.0, "reason": "火行忌神主导"},
                {"name": "半导体AI", "score": 28.0, "reason": "忌神年"}
            ],
            "monthly_analysis": [
                {"month": 1, "gan_zhi": "己丑", "dominant_element": "土", "action": "🟢 积极买入", "timing": "buy"},
                {"month": 2, "gan_zhi": "庚寅", "dominant_element": "金", "action": "🟢 稳健布局", "timing": "hold"},
                {"month": 3, "gan_zhi": "辛卯", "dominant_element": "金", "action": "🟢 稳健布局", "timing": "hold"},
                {"month": 4, "gan_zhi": "壬辰", "dominant_element": "水", "action": "🔵 持有观望", "timing": "hold"},
                {"month": 5, "gan_zhi": "癸巳", "dominant_element": "火", "action": "⚫ 回避空仓", "timing": "avoid"},
                {"month": 6, "gan_zhi": "甲午", "dominant_element": "火", "action": "⚫ 回避空仓", "timing": "avoid"},
                {"month": 7, "gan_zhi": "乙未", "dominant_element": "火", "action": "⚫ 回避空仓", "timing": "avoid"},
                {"month": 8, "gan_zhi": "丙申", "dominant_element": "金", "action": "🟢 积极买入", "timing": "buy"},
                {"month": 9, "gan_zhi": "丁酉", "dominant_element": "金", "action": "🟢 积极买入", "timing": "buy"},
                {"month": 10, "gan_zhi": "戊戌", "dominant_element": "土", "action": "🟢 积极买入", "timing": "buy"},
                {"month": 11, "gan_zhi": "己亥", "dominant_element": "水", "action": "🔵 持有观望", "timing": "hold"},
                {"month": 12, "gan_zhi": "庚子", "dominant_element": "金", "action": "🟢 稳健布局", "timing": "hold"}
            ],
            "input_summary": {
                "xiyong": {"primary": "土", "secondary": "金"},
                "avoid": ["木", "火"]
            },
            "top_stocks": []
        }


# ============================================================
# Step 3: CLI入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="FSSQ 4-Agent串联编排器")
    parser.add_argument("--birth", required=True, help="出生日期 (YYYY-MM-DD)")
    parser.add_argument("--hour", type=int, required=True, help="出生时辰 (0-23)")
    parser.add_argument("--gender", required=True, choices=["男", "女"], help="性别")
    parser.add_argument("--place", default="", help="出生地")
    parser.add_argument("--year", type=int, default=None, help="目标年份")
    parser.add_argument("--lat", type=float, default=None, help="出生地纬度")
    parser.add_argument("--lon", type=float, default=None, help="出生地经度")
    parser.add_argument("--current", default="", help="现居地")
    parser.add_argument("--output", default="", help="输出路径")

    args = parser.parse_args()

    config = {
        "birth_date": args.birth,
        "birth_hour": args.hour,
        "gender": args.gender,
        "birth_place": args.place,
        "target_year": args.year or datetime.now().year,
        "current_place": args.current,
        "lat_lon": (args.lat, args.lon) if args.lat and args.lon else None
    }

    # 执行编排
    orchestrator = FSSQOrchestrator(config)
    summary = orchestrator.run()

    # 输出摘要
    print("\n" + "=" * 60)
    print("执行摘要")
    print("=" * 60)
    print(f"状态: {summary['status']}")
    print(f"八字: {summary['bazi']}")
    print(f"喜用神: {summary['xiyong']}")
    print(f"推荐板块: {', '.join(summary['top_sectors']) if summary['top_sectors'] else '无'}")
    print(f"精选个股: {', '.join([s['name'] for s in summary['top_stocks']]) if summary['top_stocks'] else '无'}")

    if summary['errors']:
        print(f"\n⚠️ 错误记录:")
        for err in summary['errors']:
            print(f"  - {err}")

    # 保存结果JSON
    if args.output:
        result_path = os.path.join(args.output, "orchestrator_result.json")
    else:
        result_path = os.path.join(_src_root, "output", "orchestrator_result.json")

    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "astro": orchestrator.astro_result,
            "cosmic": orchestrator.cosmic_result,
            "fusion": orchestrator.fusion_result,
            "star_hunter": orchestrator.star_hunter_result
        }, f, ensure_ascii=False, indent=2)

    print(f"\n💾 结果已保存: {result_path}")


if __name__ == "__main__":
    main()
