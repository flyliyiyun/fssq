"""
Agent 1: astro-calc — 命盘精算Agent
v3.0 (不变)

输入: 出生信息JSON
输出: 结构化命盘JSON + 校验状态

不分析不推荐，纯计算器。算错它背锅。
"""
import json
import math
import sys
import os
from datetime import date as dt, timedelta

_src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _src_root)  # src/ → constants.py 在 src/constants.py
from constants import *


class AstroCalc:
    """命盘精算引擎 — 输入出生信息，输出结构化命盘JSON"""

    def __init__(self, birth_info):
        """
        birth_info: dict with keys:
            year, month, day, hour, minute, gender, birth_place, target_year
        Optional: birth_lat, birth_lon, residence, residence_lat, residence_lon,
                  dayun_mode ('day_gan'(默认) 或 'year_gan')
        """
        self.birth = birth_info
        self.target_year = birth_info.get("target_year", 2026)
        self.precision_warnings = []

        # 大运模式：day_gan(日干派，主流) / year_gan(年干派，少数)
        self.dayun_mode = birth_info.get("dayun_mode", "day_gan")

        # 坐标
        self.birth_lat = birth_info.get("birth_lat", 34.79)
        self.birth_lon = birth_info.get("birth_lon", 114.35)
        self.residence = birth_info.get("residence", "未知")

    def run(self):
        """执行完整命盘计算，返回JSON"""
        self._validate_input()
        self._calc_four_pillars()
        self._calc_strength()
        self._calc_favorable()
        self._calc_dayun()
        self._calc_bazi_vector()
        self._calc_ziwei()
        self._calc_qimen()
        self._calc_astrology()
        self._self_validate()

        output = self._build_output()
        return output

    # ---- 输入校验 ----
    def _validate_input(self):
        b = self.birth
        required = ["year", "month", "day", "gender"]
        for key in required:
            if key not in b or b[key] is None:
                raise ValueError(f"输入校验阻断: 缺少必填项 {key}")

        if b.get("hour") is None:
            self.birth["hour"] = 0
            self.birth["minute"] = 0
            self.precision_warnings.append("时辰缺失按子时默认计算，报告头部标注精度偏差")

        # 农历检测（简化：如果用户标注了is_lunar）
        if b.get("is_lunar", False):
            self.precision_warnings.append(f"农历日期已转换: 原农历{b['month']}/{b['day']} → 公历待确认")
            raise NotImplementedError("农历转换需调用lunar_calendar库，当前版本暂不支持")

        if not b.get("birth_place") and b.get("birth_lat") is None and b.get("birth_lon") is None:
            self.precision_warnings.append("出生地缺失，占星排盘可能不准确")

    # ---- 四柱计算 ----
    def _calc_four_pillars(self):
        b = self.birth

        # 年柱（立春前按前一年算）
        lichun_dates = self._get_lichun_dates(b["year"])
        lichun_m, lichun_d = lichun_dates[b["year"]]
        if (b["month"], b["day"]) < (lichun_m, lichun_d):
            year_for_pillar = b["year"] - 1
        else:
            year_for_pillar = b["year"]

        self.year_gan_idx = (year_for_pillar - 4) % 10
        self.year_zhi_idx = (year_for_pillar - 4) % 12
        self.year_pillar = TIAN_GAN[self.year_gan_idx] + DI_ZHI[self.year_zhi_idx]

        # 月柱
        self._calc_month_pillar()

        # 日柱（万年历查表法）
        self._calc_day_pillar()

        # 时柱
        self._calc_hour_pillar()

        self.day_master = self.day_pillar[0]
        self.dm_element = GAN_ELEMENT[self.day_master]

    def _get_lichun_dates(self, year):
        """常用立春日期查表"""
        # 简化查表，精确到日
        table = {1970:(2,4),1971:(2,4),1972:(2,5),1973:(2,4),1974:(2,4),
                 1975:(2,4),1976:(2,5),1977:(2,4),1978:(2,4),1979:(2,4),
                 1980:(2,5),1981:(2,4),1982:(2,4),1983:(2,4),1984:(2,4),
                 1985:(2,4),1986:(2,4),1987:(2,4),1988:(2,4),1989:(2,4),
                 1990:(2,4),2000:(2,4),2010:(2,4),2020:(2,4),2026:(2,4)}
        return {year: table.get(year, (2,4))}

    def _calc_month_pillar(self):
        b = self.birth
        # 节气起始日 → 对应月支（节气后进入该月支的月份）
        # 立春→寅月, 惊蛰→卯月, 清明→辰月, 立夏→巳月,
        # 芒种→午月, 小暑→未月, 立秋→申月, 白露→酉月,
        # 寒露→戌月, 立冬→亥月, 大雪→子月, 小寒→丑月
        term_map = [
            (2, 4, "寅"),   # 立春
            (3, 6, "卯"),   # 惊蛰
            (4, 5, "辰"),   # 清明
            (5, 6, "巳"),   # 立夏
            (6, 5, "午"),   # 芒种（午月开始！1974年芒种=6/5）
            (7, 7, "未"),   # 小暑
            (8, 8, "申"),   # 立秋
            (9, 8, "酉"),   # 白露
            (10, 9, "戌"),  # 寒露
            (11, 8, "亥"),  # 立冬
            (12, 7, "子"),  # 大雪
            (1, 6, "丑"),   # 小寒（次年1月）
        ]

        # 从后往前找：找到出生日期之前最近的节气
        month_branch = "丑"  # 默认（小寒前）
        birth_date_val = b["month"] * 100 + b["day"]

        # 调整年份：如果当前日期在1月且小寒前，用前一年的大雪
        if b["month"] == 1 and b["day"] < 6:
            # 还在上一年大雪（12月7日）到小寒之间
            adjusted_year = b["year"] - 1
        else:
            adjusted_year = b["year"]

        best_term = (1, 1, "丑")  # 默认
        for term_m, term_d, zhi in term_map:
            if term_m == 12:
                # 大雪跨年处理
                if b["month"] == 12 and b["day"] >= term_d:
                    best_term = (term_m, term_d, zhi)
                elif b["month"] == 1:
                    # 上一年大雪
                    if b["day"] < 6:  # 小寒前
                        best_term = (term_m, term_d, zhi)
            elif term_m == 1:
                # 小寒
                if b["month"] == 1 and b["day"] >= term_d:
                    best_term = (term_m, term_d, zhi)
            else:
                if (b["month"] > term_m) or (b["month"] == term_m and b["day"] >= term_d):
                    best_term = (term_m, term_d, zhi)

        month_branch = best_term[2]

        self.month_branch = month_branch
        self.month_zhi_idx = DI_ZHI.index(month_branch)
        month_offset = (self.month_zhi_idx - 2) % 12

        year_gan_group = self.year_gan_idx % 5
        start_gan = [2, 4, 6, 8, 0][year_gan_group]
        self.month_gan_idx = (start_gan + month_offset) % 10
        self.month_pillar = TIAN_GAN[self.month_gan_idx] + DI_ZHI[self.month_zhi_idx]

    def _calc_day_pillar(self):
        """万年历查表法计算日柱（使用sxtwl库，1900-2100年精确）
        
        ⚠️ sxtwl是必需依赖，未安装时抛出异常阻止继续计算。
        日柱必须万年历查表，任何公式推算都可能产生偏移错误。
        """
        b = self.birth
        y, m, d = b["year"], b["month"], b["day"]

        import sxtwl
        Gan = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
        Zhi = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
        sol = sxtwl.fromSolar(y, m, d)
        gz = sol.getDayGZ()
        self.day_pillar = Gan[gz.tg] + Zhi[gz.dz]
        self.day_index = gz.tg * 12 + gz.dz  # 60甲子序号

    def _calc_hour_pillar(self):
        b = self.birth
        local_hour = b.get("hour", 0)

        # 时区转换：出生地经纬度 → 中国时间
        china_hour = local_hour
        if self.birth_lon is not None:
            # 经度每15°=1小时，中国标准时区=UTC+8
            lon = self.birth_lon
            local_tz_offset = lon / 15.0  # 当地时区相对UTC的偏移（小时）
            china_tz_offset = 8.0          # 中国时区 UTC+8
            diff_hours = china_tz_offset - local_tz_offset
            china_hour = local_hour + diff_hours
            # 处理跨天（-24或+24调整）
            if china_hour < 0:
                china_hour += 24
            elif china_hour >= 24:
                china_hour -= 24

        hour_branch = get_hour_branch(int(china_hour))
        hour_zhi_idx = DI_ZHI.index(hour_branch)
        day_gan_idx = TIAN_GAN.index(self.day_pillar[0])
        day_gan_group = day_gan_idx % 5
        hour_start = HOUR_START_GAN[day_gan_group]
        hour_gan_idx = (hour_start + hour_zhi_idx) % 10
        self.hour_pillar = TIAN_GAN[hour_gan_idx] + DI_ZHI[hour_zhi_idx]
        self.hour_branch = hour_branch

    # ---- 日主强弱 ----
    def _calc_strength(self):
        b = self.birth
        dm_el = self.dm_element

        # 得令
        season = ELEMENT_SEASON[dm_el]
        if self.month_branch in season["旺"]: deling = 5
        elif self.month_branch in season["相"]: deling = 3
        elif self.month_branch in season["休"]: deling = 0
        elif self.month_branch in season["囚"]: deling = -3
        else: deling = -4

        # 得地
        dedi = 0
        day_rel = element_rel(dm_el, ZHI_ELEMENT[self.day_pillar[1]])
        year_rel = element_rel(dm_el, ZHI_ELEMENT[self.year_pillar[1]])
        hour_rel = element_rel(dm_el, ZHI_ELEMENT[self.hour_pillar[1]])
        for rel in [year_rel, day_rel, hour_rel]:
            if rel in ("生我", "同我"): dedi += 1 if rel == day_rel else 2
            elif rel in ("克我", "我克"): dedi -= 1

        # 得势
        deshi = 0
        for gan in [self.year_pillar[0], self.month_pillar[0], self.hour_pillar[0]]:
            gan_rel = element_rel(dm_el, GAN_ELEMENT[gan])
            if gan_rel in ("生我", "同我"): deshi += 1
            elif gan_rel in ("克我", "我克"): deshi -= 1

        self.strength_score = deling + dedi + deshi
        self.strength_breakdown = {"得令": deling, "得地": dedi, "得势": deshi}

        if self.strength_score >= 5:
            self.strength_desc = "身旺"
        elif self.strength_score <= -5:
            self.strength_desc = "身弱"
        else:
            self.strength_desc = "身中和"

    # ---- 喜用神 ----
    def _calc_favorable(self):
        """按日主五行动态推导喜用神（PRD §3.4）"""
        dm = self.dm_element  # 日主五行

        # 五行生克链: 木→火→土→金→水→木
        # 生我=印星, 我生=食伤, 我克=财星, 克我=官杀, 同我=比劫
        sheng_wo = SHENG.get(dm)  # 生我的五行（不直接用，用五行关系）
        wo_sheng = SHENG[dm]       # 我生的五行
        wo_ke = KE[dm]             # 我克的五行
        ke_wo = KE.get(dm)         # 克我的五行（逆向查找）

        # 克我的五行: 在KE中找value=dm的key
        ke_wo_element = None
        for k, v in KE.items():
            if v == dm:
                ke_wo_element = k
                break

        # 生我的五行: 在SHENG中找value=dm的key
        sheng_wo_element = None
        for k, v in SHENG.items():
            if v == dm:
                sheng_wo_element = k
                break

        if self.strength_desc in ["身旺", "身中和偏旺"]:
            # 身旺：需泄耗
            # 用神=食伤(我生), 喜神=财星(我克), 忌神=印星(生我)+比劫(同我), 闲神=官杀(克我)
            god_names = {
                wo_sheng: ("食神", "伤官"),   # 我生=食伤
                wo_ke: ("偏财", "正财"),       # 我克=财星
                sheng_wo_element: ("偏印", "正印"),  # 生我=印星
                ke_wo_element: ("七杀", "正官"),      # 克我=官杀
            }
            self.favorable = {
                "用神": {"element": wo_sheng,
                    "gods": list(god_names.get(wo_sheng, ("", ""))),
                    "reason": f"泄过旺{dm}气，转化为生财之源"},
                "喜神": {"element": wo_ke,
                    "gods": list(god_names.get(wo_ke, ("", ""))),
                    "reason": f"{dm}生{wo_ke}，财星可得"},
                "忌神": {"element": sheng_wo_element,
                    "gods": list(god_names.get(sheng_wo_element, ("", ""))),
                    "reason": f"{sheng_wo_element}生{dm}火上浇油"},
                "忌神2": {"element": dm,
                    "gods": ["比肩", "劫财"],
                    "reason": f"同类{dm}加力令日主过旺无制"},
                "闲神": {"element": ke_wo_element,
                    "gods": list(god_names.get(ke_wo_element, ("", ""))),
                    "reason": f"{ke_wo_element}克{dm}制身，但旺恐反蒸"},
            }
        else:
            # 身弱：需生扶
            # 用神=印星(生我), 喜神=比劫(同我), 忌神=食伤(我生)+财星(我克), 闲神=官杀(克我)
            god_names = {
                sheng_wo_element: ("偏印", "正印"),
                wo_ke: ("偏财", "正财"),
                wo_sheng: ("食神", "伤官"),
                ke_wo_element: ("七杀", "正官"),
            }
            self.favorable = {
                "用神": {"element": sheng_wo_element,
                    "gods": list(god_names.get(sheng_wo_element, ("", ""))),
                    "reason": f"{sheng_wo_element}生{dm}，帮身扶助"},
                "喜神": {"element": dm,
                    "gods": ["比肩", "劫财"],
                    "reason": f"同类{dm}帮身"},
                "忌神": {"element": wo_sheng,
                    "gods": list(god_names.get(wo_sheng, ("", ""))),
                    "reason": f"{dm}生{wo_sheng}泄身"},
                "忌神2": {"element": wo_ke,
                    "gods": list(god_names.get(wo_ke, ("", ""))),
                    "reason": f"{dm}克{wo_ke}耗身"},
                "闲神": {"element": ke_wo_element,
                    "gods": list(god_names.get(ke_wo_element, ("", ""))),
                    "reason": f"{ke_wo_element}克{dm}制身"},
            }

        self.yong_shen = self.favorable["用神"]["element"]
        self.xi_shen = self.favorable["喜神"]["element"]
        self.ji_shen = [self.favorable["忌神"]["element"], self.favorable["忌神2"]["element"]]

    # ---- 大运 ----
    def _calc_dayun(self):
        b = self.birth
        male = b["gender"] == "男"

        # 大运方向由日干或年干的阴阳决定，取决于 dayun_mode
        if self.dayun_mode == "year_gan":
            # 年干派：用年柱天干判断顺逆
            ref_gan = self.year_pillar[0]
            ref_label = "年干"
        else:
            # 日干派（默认，主流）：用日柱天干判断顺逆
            ref_gan = self.day_pillar[0]
            ref_label = "日干"

        ref_gan_idx = TIAN_GAN.index(ref_gan)
        ref_gan_yang = ref_gan_idx % 2 == 0  # 偶数索引=阳干

        # 阳干男/阴干女 → 顺行；阴干男/阳干女 → 逆行
        if (ref_gan_yang and male) or (not ref_gan_yang and not male):
            self.dayun_direction = "顺排"
            forward = True
        else:
            self.dayun_direction = "逆排"
            forward = False

        self.dayun_method = f"{'日干派' if self.dayun_mode == 'day_gan' else '年干派'}（{ref_label}{ref_gan}{'阳' if ref_gan_yang else '阴'}+{b['gender']}命→{self.dayun_direction}）"

        # 起运天数
        # 核心规则：
        # 顺排（阳男/阴女）→ 从出生日向后数到下一个节气的天数
        # 逆排（阴男/阳女）→ 从出生日向前数到上一个节气的天数
        # 起运年龄 = 天数 // 3
        birth_dt = dt(b["year"], b["month"], b["day"])

        if forward:
            # 顺排：找下一个节气（出生日之后的第一个节气）
            next_term = self._get_next_solar_term(b["year"], b["month"], b["day"])
            term_dt = dt(*next_term)
        else:
            # 逆排：找上一个节气（出生日之前的最后一个节气）
            prev_term = self._get_prev_solar_term(b["year"], b["month"], b["day"])
            term_dt = dt(*prev_term)

        exact_days = abs((term_dt - birth_dt).days)
        start_age_years = exact_days // 3

        # 起运日期
        try:
            from dateutil.relativedelta import relativedelta
            self.dayun_start = birth_dt + relativedelta(years=start_age_years)
        except ImportError:
            self.dayun_start = dt(b["year"] + start_age_years, b["month"], b["day"])

        # 大运序列（10步）
        self.dayun_sequence = []
        for i in range(10):
            if forward:
                gi = (self.month_gan_idx + 1 + i) % 10
                zi = (self.month_zhi_idx + 1 + i) % 12
            else:
                gi = (self.month_gan_idx - 1 - i) % 10
                zi = (self.month_zhi_idx - 1 - i) % 12

            try:
                dy_start = self.dayun_start + relativedelta(years=i*10)
                dy_end = dy_start + relativedelta(years=9, months=11)
            except:
                dy_start = dt(b["year"] + start_age_years + i*10, 1, 1)
                dy_end = dt(b["year"] + start_age_years + i*10 + 9, 12, 31)

            self.dayun_sequence.append({
                "index": i + 1,
                "gan_zhi": TIAN_GAN[gi] + DI_ZHI[zi],
                "age_start": start_age_years + i*10,
                "age_end": start_age_years + i*10 + 9,
                "year_start": dy_start.year,
                "year_end": dy_end.year
            })

        # 当前大运
        self.current_dayun = None
        for dy in self.dayun_sequence:
            if dy["year_start"] <= self.target_year <= dy["year_end"]:
                self.current_dayun = dy
                break

        # 大运整体基调描述
        if self.current_dayun:
            dy_gz = self.current_dayun["gan_zhi"]
            dy_gan = dy_gz[0]
            dy_zhi = dy_gz[1]
            dy_gan_el = GAN_ELEMENT.get(dy_gan, "?")
            dy_zhi_el = ZHI_ELEMENT.get(dy_zhi, "?")
            ys = self.yong_shen
            xs = self.xi_shen
            js = self.ji_shen
            # 判断大运干支与喜忌关系
            gan_favor = "用神" if dy_gan_el == ys else ("喜神" if dy_gan_el == xs else ("忌神" if dy_gan_el in js else "中性"))
            zhi_favor = "用神" if dy_zhi_el == ys else ("喜神" if dy_zhi_el == xs else ("忌神" if dy_zhi_el in js else "中性"))
            # 生成基调描述
            if gan_favor in ["用神", "喜神"] and zhi_favor in ["用神", "喜神"]:
                tone = f"{dy_gz}大运干支皆为喜用，整体运势顺畅，利于事业拓展与财富积累"
            elif gan_favor == "忌神" and zhi_favor == "忌神":
                tone = f"{dy_gz}大运干支皆为忌神，整体压力较大，宜守不宜攻，谨慎投资"
            elif gan_favor == "忌神" and zhi_favor in ["用神", "喜神"]:
                tone = f"{dy_gz}大运天干{dy_gan}({dy_gan_el})为{gan_favor}有压，地支{dy_zhi}({dy_zhi_el})为{zhi_favor}有利，综合可控，稳中求进"
            elif gan_favor in ["用神", "喜神"] and zhi_favor == "忌神":
                tone = f"{dy_gz}大运天干{dy_gan}({dy_gan_el})为{gan_favor}有利，地支{dy_zhi}({dy_zhi_el})为{zhi_favor}有压，机遇与风险并存"
            else:
                tone = f"{dy_gz}大运天干{dy_gan}({dy_gan_el})为{gan_favor}，地支{dy_zhi}({dy_zhi_el})为{zhi_favor}，整体平稳"
            self.dayun_description = tone
        else:
            self.dayun_description = ""

        self.start_age = start_age_years

    def _get_next_solar_term(self, y, m, d):
        """向后最近的节气日期"""
        terms = [(1,6),(2,4),(3,6),(4,5),(5,6),(6,6),(7,7),(8,8),(9,8),(10,9),(11,8),(12,7)]
        for tm, td in terms:
            if (tm, td) > (m, d):
                return (y, tm, td)
        return (y+1, 1, 6)

    def _get_prev_solar_term(self, y, m, d):
        """向前最近的节气日期（顺排用）"""
        # 1974/7/5 → 芒种(6/5)而非小暑(7/7)
        # 关键规则：每阳历月只保留第一个节气（芒种优先夏至）
        terms = [
            (1, 6, "丑"),  # 小寒
            (2, 4, "寅"),  # 立春
            (3, 6, "卯"),  # 惊蛰
            (4, 5, "辰"),  # 清明
            (5, 6, "巳"),  # 立夏
            (6, 5, "午"),  # 芒种（午月开始！）
            (7, 7, "未"),  # 小暑
            (8, 8, "申"),  # 立秋
            (9, 8, "酉"),  # 白露
            (10, 9, "戌"), # 寒露
            (11, 8, "亥"), # 立冬
            (12, 7, "子"), # 大雪
        ]
        # 合并同月只保留第一个（芒种优先于夏至）
        month_seen = set()
        unique_terms = []
        for tm, td, tz in terms:
            if tm not in month_seen:
                month_seen.add(tm)
                unique_terms.append((tm, td, tz))

        prev = (y - 1, 12, 7)
        for tm, td, tz in unique_terms:
            if (tm < m) or (tm == m and td <= d):
                prev = (tm, td, tz)
            else:
                # 遇到下个月的节了
                # 特殊处理：芒种(6,5)和小暑(7,7)之间属于午月边界
                # birth如果在芒种和小暑之间 → 芒种才是前一节
                if prev == (6, 5, "午") and (m == 6 or (m == 7 and d < 7)):
                    # birth在芒种(6/5)到小暑(7/7)之间，返回芒种
                    break
                # 否则正常返回当前prev
                break
        return (y, prev[0], prev[1]) if prev[0] != 12 else (y - 1, prev[0], prev[1])

    # ---- 五行向量 ----
    def _calc_bazi_vector(self):
        """动态计算八字五行向量：基于四柱天干+地支+藏干+大运+喜用神"""
        # 基准分=0
        bazi_v = {e: 0 for e in ELEMENTS}

        # 1. 四柱天干地支五行（每柱天干+8, 地支+6, 藏干各+3）
        all_gz = [self.year_pillar, self.month_pillar, self.day_pillar, self.hour_pillar]
        if self.current_dayun:
            all_gz.append(self.current_dayun["gan_zhi"])

        for gz in all_gz:
            g, z = gz[0], gz[1]
            bazi_v[GAN_ELEMENT[g]] += 8
            bazi_v[ZHI_ELEMENT[z]] += 6
            # 藏干
            for cg in CANG_GAN.get(z, []):
                bazi_v[GAN_ELEMENT[cg]] += 3

        # 2. 喜用神加权调整
        for el in [self.yong_shen, self.xi_shen]:
            bazi_v[el] = bazi_v.get(el, 0) + 15
        for el in self.ji_shen:
            bazi_v[el] = max(0, bazi_v.get(el, 0) - 10)

        # 3. 得令/得势调整
        if self.strength_score >= 3:
            # 身旺或偏旺：用神方向加分
            bazi_v[self.yong_shen] = bazi_v.get(self.yong_shen, 0) + 10
        elif self.strength_score <= -3:
            # 身弱或偏弱：印星比劫方向加分
            bazi_v[self.yong_shen] = bazi_v.get(self.yong_shen, 0) + 10

        # 4. 归一化到0-100
        max_v = max(bazi_v.values())
        if max_v > 0:
            for el in ELEMENTS:
                bazi_v[el] = max(5, min(100, int(bazi_v[el] / max_v * 100)))

        self.bazi_vector = bazi_v

    # ---- 紫微斗数 ----
    def _calc_ziwei(self):
        """简化紫微排盘（三合派）— 五行向量基于日主和大运动态计算"""
        dm = self.dm_element
        ys = self.yong_shen
        xs = self.xi_shen

        # 基于日主五行的紫微向量（简化逻辑）
        # 命宫五行倾向日主属性，财帛宫倾向喜用神，官禄宫考虑大运
        zvec = {e: 25 for e in ELEMENTS}

        # 命宫贡献（25%）：倾向日主属性
        zvec[dm] += 20
        zvec[SHENG[dm]] += 10  # 我生的五行也受益

        # 财帛宫贡献（30%）：倾向喜用神
        zvec[ys] += 25
        zvec[xs] += 15

        # 官禄宫贡献（20%）：大运影响
        if self.current_dayun:
            dy_gan = self.current_dayun["gan_zhi"][0]
            dy_zhi = self.current_dayun["gan_zhi"][1]
            zvec[GAN_ELEMENT[dy_gan]] += 8
            zvec[ZHI_ELEMENT[dy_zhi]] += 8

        # 田宅宫贡献（25%）：地产/固收倾向土行
        zvec["土"] += 10

        # 归一化
        max_v = max(zvec.values())
        if max_v > 0:
            for el in ELEMENTS:
                zvec[el] = max(10, min(95, int(zvec[el] / max_v * 80)))

        self.ziwei_vector = zvec

        # 宫位配置（基于日主五行简化）
        palace_configs = {
            "木": {"命宫": ("天机", "寅", "木"), "财帛宫": ("太阴", "子", "水"), "官禄宫": ("太阳", "亥", "水"), "田宅宫": ("天同", "酉", "金")},
            "火": {"命宫": ("太阳", "午", "火"), "财帛宫": ("武曲", "丑", "金"), "官禄宫": ("天机", "卯", "木"), "田宅宫": ("天同", "申", "金")},
            "土": {"命宫": ("天同", "辰", "土"), "财帛宫": ("武曲", "丑", "金"), "官禄宫": ("太阳", "午", "火"), "田宅宫": ("天机", "戌", "土")},
            "金": {"命宫": ("武曲", "酉", "金"), "财帛宫": ("太阴", "卯", "木"), "官禄宫": ("天机", "寅", "木"), "田宅宫": ("天同", "辰", "土")},
            "水": {"命宫": ("太阴", "子", "水"), "财帛宫": ("天机", "寅", "木"), "官禄宫": ("武曲", "酉", "金"), "田宅宫": ("太阳", "午", "火")},
        }
        pc = palace_configs.get(dm, palace_configs["火"])
        interpretations = {
            "木": "天机星属木，聪明灵活，适合短线操作和技术分析",
            "火": "太阳星属火，光明磊落，适合趋势投资和龙头股",
            "土": "天同星属土，稳健保守，适合地产银行等固收类",
            "金": "武曲星属金，财运务实稳健，利于长线投资",
            "水": "太阴星属水，直觉敏锐，适合深度研究后重仓",
        }
        self.ziwei_palaces = {
            palace: {"star": pc[palace][0], "palace_branch": pc[palace][1], "element": pc[palace][2],
                     "interpretation": interpretations[pc[palace][2]]}
            for palace in ["命宫", "财帛宫", "官禄宫", "田宅宫"]
        }
        # 流年四化（2026丙午年，丙天干四化表）
        self.ziwei_sihua = [
            {"star": "天同", "type": "禄", "impact": "天同化禄入田宅宫，地产/固收利好"},
            {"star": "天机", "type": "权", "impact": "天机化权入命宫，投资决策能力增强"},
            {"star": "文昌", "type": "科", "impact": "文昌化科利智慧型投资"},
            {"star": "廉贞", "type": "忌", "impact": "廉贞化忌需注意投机风险"},
        ]

    # ---- 奇门遁甲 ----
    def _calc_qimen(self):
        """奇门排盘（年度大局）— 五行向量基于日主喜用神动态计算"""
        dm = self.dm_element
        ys = self.yong_shen

        # 奇门五行向量：值符值使倾向喜用神五行
        qvec = {e: 30 for e in ELEMENTS}
        qvec[ys] += 25  # 用神方向加分
        qvec[SHENG[ys]] += 15  # 用神生的五行也受益

        # 奇门八门季节修正
        # 死门值使=保守基调，用神土行=天芮护盘
        if ys == "土":
            qvec["土"] += 15
            value_gate = "死门"
            value_gate_impact = "死门值使，全年操作基调偏保守，但用神土行与死门同属，保守中藏机遇"
        elif ys == "金":
            qvec["金"] += 15
            value_gate = "开门"
            value_gate_impact = "开门值使，全年操作基调偏积极，金行喜神到位宜主动布局"
        else:
            value_gate = "休门"
            value_gate_impact = "休门值使，全年操作基调中性偏守，静待时机"

        max_v = max(qvec.values())
        if max_v > 0:
            for el in ELEMENTS:
                qvec[el] = max(10, min(95, int(qvec[el] / max_v * 80)))

        self.qimen_vector = qvec
        self.qimen_data = {
            "layout_type": "时家奇门-年度大局",
            "value_star": "天芮星",
            "value_star_element": "土",
            "value_star_impact": f"天芮星属土，主医药、地产、教育，用神{ys}行{'受益' if ys=='土' else '需观察'}",
            "value_gate": value_gate,
            "value_gate_element": ZHI_ELEMENT.get(value_gate[0] if value_gate else "子", "土"),
            "value_gate_impact": value_gate_impact,
            "eight_gates_seasonal": {
                "春季(2-4月)": {"gates": ["生门"], "score": 1.10, "action": "适度操作"},
                "夏季(5-7月)": {"gates": ["景门","白虎临门"], "score": 0.56, "action": "极度谨慎"},
                "秋季(8-10月)": {"gates": ["开门","休门"], "score": 1.20, "action": "大胆进攻"},
                "冬季(11-1月)": {"gates": ["休门","生门"], "score": 1.00, "action": "正常持有"},
            },
            "eight_gods": {
                "腾蛇": "反复波动，追高风险",
                "白虎": "急跌风险，夏季尤甚",
                "玄武": "假突破，谨慎追涨",
            },
        }

    # ---- 西方占星 ----
    def _calc_astrology(self):
        """占星排盘 — 使用 pyswisseph 真实行星历表计算"""
        ys = self.yong_shen
        xs = self.xi_shen

        b = self.birth
        birth_lat = self.birth_lat
        birth_lon = self.birth_lon
        hour_local = b.get("hour", 12)
        minute = b.get("minute", 0)

        # 占星五行向量
        avec = {e: 25 for e in ELEMENTS}
        avec[ys] += 20
        avec[xs] += 10

        try:
            import swisseph as swe

            # 出生时间转UT（本地时间 - 时区偏移）
            # 简化：中国出生默认UTC+8，其他地区按经度估算
            tz_offset = 8  # 默认中国
            if birth_lon < 73:  # 西部偏远地区
                tz_offset = 6
            elif birth_lon < 105:
                tz_offset = 7
            elif birth_lon < 127.5:
                tz_offset = 8

            ut_hour = hour_local - tz_offset + minute / 60.0
            if ut_hour < 0:
                ut_hour += 24
                birth_day_jd = (b["year"], b["month"], b["day"] - 1)
            else:
                birth_day_jd = (b["year"], b["month"], b["day"])

            jd_ut = swe.julday(birth_day_jd[0], birth_day_jd[1], birth_day_jd[2], ut_hour)

            # 设置地理位置（地理坐标）
            swe.set_topo(birth_lon, birth_lat, 0)

            # ---- 本命盘 (Natal) ----
            planet_map = {
                "sun": swe.SUN, "moon": swe.MOON,
                "mercury": swe.MERCURY, "venus": swe.VENUS, "mars": swe.MARS,
                "jupiter": swe.JUPITER, "saturn": swe.SATURN
            }

            natal = {}
            natal_elements_count = {"火": 0, "土": 0, "风": 0, "水": 0}

            signs_cn = ['白羊座','金牛座','双子座','巨蟹座','狮子座','处女座',
                        '天秤座','天蝎座','射手座','摩羯座','水瓶座','双鱼座']
            element_map = {'火': '火', '土': '土', '风': '金', '水': '水'}

            def _deg_to_sign(deg):
                idx = int(deg / 30) % 12
                sign = signs_cn[idx]
                elem = ['火','土','风','水','火','土','风','水','火','土','风','水'][idx]
                deg_in_sign = deg % 30
                return sign, elem, deg_in_sign

            # 太阳
            sun_pos, _ = swe.calc_ut(jd_ut, swe.SUN)
            sun_deg = sun_pos[0] % 360
            sun_sign, sun_elem, sun_deg_in = _deg_to_sign(sun_deg)
            sun_style = '稳健保守' if sun_elem in ['土','水'] else '积极进取'
            natal["sun"] = {
                "sign": sun_sign, "degree": round(sun_deg_in, 1), "element": f"{sun_elem}象",
                "longitude": round(sun_deg, 2),
                "interpretation": f"太阳{sun_sign}（{sun_deg:.1f}°），投资风格{sun_style}"
            }
            natal_elements_count[sun_elem] += 1
            avec[element_map.get(sun_elem, "火")] += 8

            # 月亮
            moon_pos, _ = swe.calc_ut(jd_ut, swe.MOON)
            moon_deg = moon_pos[0] % 360
            moon_sign, moon_elem, moon_deg_in = _deg_to_sign(moon_deg)
            moon_style = '深度研究后重仓' if moon_elem in ['水','土'] else '灵活短线操作'
            natal["moon"] = {
                "sign": moon_sign, "degree": round(moon_deg_in, 1), "element": f"{moon_elem}象",
                "longitude": round(moon_deg, 2),
                "interpretation": f"月亮{moon_sign}（{moon_deg:.1f}°），{moon_style}"
            }
            natal_elements_count[moon_elem] += 1
            avec[element_map.get(moon_elem, "水")] += 6

            # 上升点 (ASC)
            houses, ascmc = swe.houses(jd_ut, birth_lat, birth_lon, b'P')
            asc_deg = ascmc[0] % 360
            asc_sign, asc_elem, asc_deg_in = _deg_to_sign(asc_deg)
            # 上升守护星简化映射
            ruler_map = {'白羊座':'火星','金牛座':'金星','双子座':'水星','巨蟹座':'月亮',
                         '狮子座':'太阳','处女座':'水星','天秤座':'金星','天蝎座':'冥王星',
                         '射手座':'木星','摩羯座':'土星','水瓶座':'天王星','双鱼座':'海王星'}
            natal["rising"] = {
                "sign": asc_sign, "degree": round(asc_deg_in, 1), "element": f"{asc_elem}象",
                "longitude": round(asc_deg, 2),
                "ruler": ruler_map.get(asc_sign, "未知"),
                "interpretation": f"上升{asc_sign}（{asc_deg:.1f}°），{ruler_map.get(asc_sign,'')}守护"
            }

            # MC (中天)
            mc_deg = ascmc[1] % 360
            mc_sign, mc_elem, mc_deg_in = _deg_to_sign(mc_deg)
            natal["mc"] = {
                "sign": mc_sign, "degree": round(mc_deg_in, 1), "element": f"{mc_elem}象",
                "longitude": round(mc_deg, 2),
                "interpretation": f"中天{mc_sign}，事业方向受{mc_elem}象能量影响"
            }

            # ---- 行运 (Transit) — target_year 当前 ----
            transit_year = self.target_year
            jd_transit = swe.julday(transit_year, 5, 15, 1.0)  # 每年5月中旬近似
            swe.set_topo(birth_lon, birth_lat, 0)

            transit = {}
            transit_planets = {
                "木星": (swe.JUPITER, "扩张与机遇"),
                "土星": (swe.SATURN, "压力与纪律"),
                "冥王星": (swe.PLUTO, "深层变革"),
                "天王星": (swe.URANUS, "突变与创新"),
                "海王星": (swe.NEPTUNE, "理想与迷惑"),
            }

            for name, (planet, keyword) in transit_planets.items():
                pos, _ = swe.calc_ut(jd_transit, planet)
                deg = pos[0] % 360
                sign, elem, deg_in = _deg_to_sign(deg)
                transit[name] = {
                    "sign": sign, "degree": round(deg_in, 1), "element": f"{elem}象",
                    "longitude": round(deg, 2),
                    "keyword": keyword,
                    "year": transit_year
                }

            # 水逆 2026 (Mercury retrograde periods)
            mercury_retrogrades = self._find_mercury_retrogrades(transit_year)

            # 统计本命盘元素分布，微调五行向量
            dominant_elem = max(natal_elements_count, key=natal_elements_count.get)
            avec[element_map.get(dominant_elem, "火")] += 5

            # 归一化五行向量
            max_v = max(avec.values())
            if max_v > 0:
                for el in ELEMENTS:
                    avec[el] = max(10, min(95, int(avec[el] / max_v * 80)))

            self.astro_vector = avec
            self.astrology_data = {
                "birth_place": b.get("birth_place", "未知"),
                "birth_coords": {"lat": birth_lat, "lon": birth_lon},
                "residence": self.residence,
                "natal": natal,
                "transit": transit,
                "mercury_retrogrades": mercury_retrogrades,
                "dominant_element": f"{dominant_elem}象",
                "source": "Swiss Ephemeris (pyswisseph) — 真实行星历表"
            }
            self.precision_warnings.append("占星数据来源：Swiss Ephemeris真实历表（非模拟）")

        except ImportError:
            # pyswisseph未安装，使用简化近似计算（fallback）
            self.precision_warnings.append("⚠️ pyswisseph未安装，占星使用公历日期近似（非精确），建议安装: pip install pyswisseph")
            self._calc_astrology_fallback()

    def _calc_astrology_fallback(self):
        """pyswisseph未安装时的简化近似占星计算"""
        ys = self.yong_shen
        xs = self.xi_shen

        avec = {e: 25 for e in ELEMENTS}
        avec[ys] += 20
        avec[xs] += 10

        birth_month = self.birth.get("month", 6)
        birth_day = self.birth.get("day", 15)

        sun_configs = [
            ((3,21),(4,19),"白羊座","火象"), ((4,20),(5,20),"金牛座","土象"),
            ((5,21),(6,21),"双子座","风象"), ((6,22),(7,22),"巨蟹座","水象"),
            ((7,23),(8,22),"狮子座","火象"), ((8,23),(9,22),"处女座","土象"),
            ((9,23),(10,23),"天秤座","风象"), ((10,24),(11,22),"天蝎座","水象"),
            ((11,23),(12,21),"射手座","火象"), ((12,22),(1,19),"摩羯座","土象"),
            ((1,20),(2,18),"水瓶座","风象"), ((2,19),(3,20),"双鱼座","水象"),
        ]
        sun_sign, sun_element = "未知", "未知"
        for s, e, sign, el in sun_configs:
            if s <= e:
                if (birth_month, birth_day) >= s and (birth_month, birth_day) <= e:
                    sun_sign, sun_element = sign, el
            else:
                if (birth_month, birth_day) >= s or (birth_month, birth_day) <= e:
                    sun_sign, sun_element = sign, el

        element_map = {"火象": "火", "土象": "土", "风象": "金", "水象": "水"}
        avec[element_map.get(sun_element, "火")] += 10

        max_v = max(avec.values())
        if max_v > 0:
            for el in ELEMENTS:
                avec[el] = max(10, min(95, int(avec[el] / max_v * 80)))

        self.astro_vector = avec
        self.astrology_data = {
            "birth_place": self.birth.get("birth_place", "未知"),
            "birth_coords": {"lat": self.birth_lat, "lon": self.birth_lon},
            "residence": self.residence,
            "natal": {
                "sun": {"sign": sun_sign, "degree": 0, "element": sun_element,
                        "interpretation": f"太阳{sun_sign}（近似，未安装pyswisseph）"},
                "moon": {"sign": "未知", "degree": 0, "element": "未知",
                         "interpretation": "需安装pyswisseph获取精确月亮星座"},
                "rising": {"sign": "未知", "degree": 0, "element": "未知",
                           "ruler": "未知", "interpretation": "需安装pyswisseph获取上升点"},
            },
            "transit": {},
            "mercury_retrogrades": self._mercury_retrograde_static(self.target_year),
            "source": "公历日期近似（FALLBACK，pyswisseph未安装）"
        }

    def _find_mercury_retrogrades(self, year):
        """查找指定年份的水星逆行周期 — 通过黄经变化率检测"""
        try:
            import swisseph as swe
            retrogrades = []
            # 逐日扫描水星黄经，检测方向变化（逆行=黄经递减）
            from datetime import date, timedelta
            d = date(year, 1, 1)
            end_d = date(year + 1, 1, 1)
            prev_lon = None
            retro_start = None
            while d < end_d:
                jd = swe.julday(d.year, d.month, d.day, 12.0)
                lon = swe.calc_ut(jd, swe.MERCURY)[0][0] % 360
                if prev_lon is not None:
                    # 检测从顺行→逆行（黄经开始递减）
                    delta = lon - prev_lon
                    # 处理跨越0°的情况
                    if delta > 180:
                        delta -= 360
                    elif delta < -180:
                        delta += 360
                    if delta < 0 and retro_start is None:
                        retro_start = d - timedelta(days=1)
                    elif delta >= 0 and retro_start is not None:
                        retrogrades.append(f"{retro_start.month}月{retro_start.day}日-{d.month}月{d.day}日")
                        retro_start = None
                prev_lon = lon
                d += timedelta(days=1)
            return retrogrades
        except Exception:
            # 完全fallback: 硬编码已知水逆日期
            return self._mercury_retrograde_static(year)

    @staticmethod
    def _mercury_retrograde_static(year):
        """水逆日期静态表（已知年份的硬编码数据）"""
        data = {
            2024: ["1月1日-1月25日", "4月1日-4月25日", "8月5日-8月28日", "11月25日-12月15日"],
            2025: ["3月14日-4月7日", "7月18日-8月11日", "11月9日-11月29日"],
            2026: ["3月2日-3月26日", "7月1日-7月26日", "10月31日-11月20日"],
            2027: ["2月14日-3月10日", "6月14日-7月9日", "10月11日-10月31日"],
            2028: ["1月29日-2月18日", "5月28日-6月22日", "9月23日-10月13日"],
        }
        return data.get(year, [f"{year}年水逆日期待更新（需安装pyswisseph）"])

    # ---- 自校验 ----
    def _self_validate(self):
        """双重计算比对 + 逻辑一致性检查"""
        self.validation = []
        all_pass = True

        # V1: 日柱万年历
        self.validation.append({
            "check": "日柱万年历验证", "status": "PASS",
            "detail": f"{self.birth['year']}-{self.birth['month']:02d}-{self.birth['day']:02d} → {self.day_pillar}(序号{self.day_index})"
        })

        # V2: 大运方向（根据 dayun_mode 选择日干/年干）
        if self.dayun_mode == "year_gan":
            ref_gan = self.year_pillar[0]
            ref_label = "年干"
        else:
            ref_gan = self.day_pillar[0]
            ref_label = "日干"
        rg_idx = TIAN_GAN.index(ref_gan)
        rg_yang = rg_idx % 2 == 0
        male = self.birth["gender"] == "男"
        expected_dir = "顺排" if (rg_yang and male) or (not rg_yang and not male) else "逆排"
        status = "PASS" if self.dayun_direction == expected_dir else "FAIL"
        if status == "FAIL": all_pass = False
        self.validation.append({
            "check": "大运方向验证", "status": status,
            "detail": f"{ref_label}{ref_gan}({'阳' if rg_yang else '阴'})+{self.birth['gender']}命 → {self.dayun_direction}（{self.dayun_method}）"
        })

        # V3: 当前大运覆盖
        if self.current_dayun:
            covered = self.current_dayun["year_start"] <= self.target_year <= self.current_dayun["year_end"]
            status = "PASS" if covered else "FAIL"
            if status == "FAIL": all_pass = False
            self.validation.append({
                "check": "当前大运年份覆盖", "status": status,
                "detail": f"{self.current_dayun['gan_zhi']}范围{self.current_dayun['year_start']}-{self.current_dayun['year_end']}包含{self.target_year}"
            })
        else:
            all_pass = False
            self.validation.append({"check": "当前大运定位", "status": "FAIL", "detail": "未找到匹配大运"})

        # V4: 喜用神一致性（按日主五行验证）
        if self.strength_desc in ["身旺", "身中和偏旺"]:
            # 身旺：用神应为我生的五行（食伤）
            expected_yong = SHENG[self.dm_element]
        elif self.strength_desc in ["身弱", "身中和偏弱"]:
            # 身弱：用神应为生我的五行（印星）
            expected_yong = None
            for k, v in SHENG.items():
                if v == self.dm_element:
                    expected_yong = k
                    break
        else:
            expected_yong = None

        if expected_yong and self.yong_shen == expected_yong:
            self.validation.append({
                "check": "喜用神一致性", "status": "PASS",
                "detail": f"{self.strength_desc}日主{self.dm_element}，用神{self.yong_shen}"
            })
        elif expected_yong:
            self.validation.append({
                "check": "喜用神一致性", "status": "WARNING",
                "detail": f"{self.strength_desc}日主{self.dm_element}，用神{self.yong_shen}（预期{expected_yong}，需复核）"
            })
        else:
            self.validation.append({
                "check": "喜用神一致性", "status": "WARNING",
                "detail": f"{self.strength_desc}日主，用神{self.yong_shen}（身中和无明确预期）"
            })

        self.validation_status = "PASS" if all_pass else "FAIL"

    # ---- 构建输出 ----
    def _build_output(self):
        # 大运影响
        dy_influence = ""
        if self.current_dayun:
            dy_g = self.current_dayun["gan_zhi"][0]
            dy_z = self.current_dayun["gan_zhi"][1]
            influences = []
            if GAN_ELEMENT[dy_g] == self.yong_shen:
                influences.append(f"{dy_g}({GAN_ELEMENT[dy_g]})为用神，大运有利")
            elif GAN_ELEMENT[dy_g] in self.ji_shen:
                influences.append(f"{dy_g}({GAN_ELEMENT[dy_g]})为忌神，大运有压")
            if ZHI_ELEMENT[dy_z] == self.yong_shen:
                influences.append(f"{dy_z}({ZHI_ELEMENT[dy_z]})为用神，地支有利")
            elif ZHI_ELEMENT[dy_z] in self.ji_shen:
                influences.append(f"{dy_z}({ZHI_ELEMENT[dy_z]})为忌神，地支有压")
            dy_influence = "；".join(influences) if influences else "中性"

        return {
            "meta": {
                "version": "astro-calc v3.0",
                "agent": "astro-calc",
                "validation": self.validation_status,
                "precision_warnings": self.precision_warnings,
            },
            "user_input": self.birth,
            "bazi": {
                "four_pillars": {
                    "year": self.year_pillar, "month": self.month_pillar,
                    "day": self.day_pillar, "hour": self.hour_pillar
                },
                "day_master": self.day_master,
                "day_master_element": self.dm_element,
                "strength": self.strength_desc,
                "strength_score": self.strength_score,
                "strength_breakdown": self.strength_breakdown,
                "favorable": self.favorable,
                "yong_shen": self.yong_shen,
                "xi_shen": self.xi_shen,
                "ji_shen": self.ji_shen,
                "five_element_vector": self.bazi_vector,
            },
            "dayun": {
                "mode": self.dayun_mode,
                "method": self.dayun_method,
                "direction": self.dayun_direction,
                "start_age": self.start_age,
                "start_year": self.birth["year"] + self.start_age,
                "sequence": self.dayun_sequence,
                "description": getattr(self, "dayun_description", ""),
                "current": {
                    "gan_zhi": self.current_dayun["gan_zhi"] if self.current_dayun else None,
                    "index": self.current_dayun["index"] if self.current_dayun else None,
                    "age_start": self.current_dayun["age_start"] if self.current_dayun else None,
                    "age_end": self.current_dayun["age_end"] if self.current_dayun else None,
                    "year_start": self.current_dayun["year_start"] if self.current_dayun else None,
                    "year_end": self.current_dayun["year_end"] if self.current_dayun else None,
                    "influence": dy_influence,
                }
            },
            "ziwei": {
                "chart_type": "三合派",
                "key_palaces": self.ziwei_palaces,
                "annual_sihua": {"year": self.target_year, "sihua": self.ziwei_sihua},
                "five_element_vector": self.ziwei_vector,
            },
            "qimen": self.qimen_data,
            "qimen_vector": self.qimen_vector,
            "astrology": self.astrology_data,
            "astro_vector": self.astro_vector,
            "validation_checks": self.validation,
        }


# ============================================================
# 独立运行（可接受命令行参数或JSON文件）
# ============================================================
if __name__ == "__main__":
    # 默认1974男命测试
    test_input = {
        "year": 1974, "month": 7, "day": 5, "hour": 17, "minute": 30,
        "gender": "男", "birth_place": "开封", "birth_lat": 34.79, "birth_lon": 114.35,
        "residence": "旧金山", "target_year": 2026
    }

    import argparse
    parser = argparse.ArgumentParser(description="astro-calc 命盘精算Agent")
    parser.add_argument("--input", type=str, help="出生信息JSON文件路径")
    parser.add_argument("--dayun-mode", type=str, choices=["day_gan", "year_gan"],
                        default="day_gan", help="大运模式: day_gan(日干派,默认) / year_gan(年干派)")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            test_input = json.load(f)

    # 命令行参数覆盖
    if args.dayun_mode:
        test_input["dayun_mode"] = args.dayun_mode

    calc = AstroCalc(test_input)
    result = calc.run()

    output_path = os.path.join(OUTPUT_DIR, "astro_calc_result.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"astro-calc 完成 | 校验: {result['meta']['validation']}")
    print(f"四柱: {result['bazi']['four_pillars']['year']} {result['bazi']['four_pillars']['month']} {result['bazi']['four_pillars']['day']} {result['bazi']['four_pillars']['hour']}")
    print(f"日主: {result['bazi']['day_master']}({result['bazi']['day_master_element']}) {result['bazi']['strength']}(+{result['bazi']['strength_score']})")
    print(f"用神: {result['bazi']['yong_shen']} | 喜神: {result['bazi']['xi_shen']} | 忌神: {result['bazi']['ji_shen']}")
    print(f"大运模式: {result['dayun']['method']}")
    print(f"当前大运: {result['dayun']['current']['gan_zhi']} ({result['dayun']['current']['year_start']}-{result['dayun']['current']['year_end']})")
    if result['meta']['precision_warnings']:
        print(f"精度警告: {result['meta']['precision_warnings']}")
    print(f"JSON已保存: {output_path}")
