"""
Agent 3: star-hunter — 星座猎手Agent
v3.0

输入:
  - astro_calc_output: 八字命盘（包含喜用神）
  - cosmic_trend_output: 宏观天象（包含宏观五行向量、季度修正）
  - target_year: 目标年份（默认当前年份）

输出:
  - 推荐板块 + 推荐个股
  - 每只股票的月度操作时效（买入/持有/卖出/空仓）

核心原则：
  喜用神五行 × 宏观五行向量 → 五行匹配度 → 选股
  流月五行 × 喜用神 → 月度操作时效
"""
import json
import sys
import os
from datetime import datetime
from math import cos

_src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _src_root)
from constants import *


class StarHunter:
    """星座猎手 — 根据命主喜用神 + 宏观天象，筛选A股个股"""

    def __init__(self, astro_calc_output, cosmic_trend_output=None, target_year=None):
        """
        Args:
            astro_calc_output: astro-calc输出JSON（必须，包含喜用神）
            cosmic_trend_output: cosmic-trend输出JSON（可选，用于宏观五行向量）
            target_year: 目标分析年份（默认读取当前时间）
        """
        self.astro = astro_calc_output
        self.cosmic = cosmic_trend_output
        self.year = target_year if target_year else datetime.now().year
        self._current_month = datetime.now().month

        # 加载股票池
        self.stock_pool = load_stock_pool()

        # 喜用神（从astro_calc读取）
        self.xiyong = self._extract_xiyong()

        # 流年干支（从astro_calc或计算）
        self.year_ganzhi = self._extract_year_ganzhi()

        # 流年五行（从astro_calc读取，或计算）
        self.year_elements = self._extract_year_elements()

        # 流月数据（12个月）
        self.monthly_flow = self._calc_monthly_flow()

    def _extract_xiyong(self):
        """从astro_calc提取喜用神（兼容多种格式）"""
        if not self.astro:
            return {"primary": "木", "secondary": "水"}

        # 尝试从bazi读取喜用神
        bazi = self.astro.get("bazi", {})

        # 优先从 yong_shen（用神）和 xi_shen（喜神）读取
        yong = bazi.get("yong_shen")
        xi = bazi.get("xi_shen")

        # 兼容旧格式 xiyong
        if not yong:
            xiyong = bazi.get("xiyong", {})
            if isinstance(xiyong, dict):
                yong = xiyong.get("喜用", xiyong.get("primary", ""))
                xi = xiyong.get("次用", xiyong.get("secondary", ""))
            elif isinstance(xiyong, list) and len(xiyong) >= 2:
                yong = xiyong[0]
                xi = xiyong[1]

        # 兼容 favorable 格式（用神/喜神/忌神结构）
        if not yong:
            favorable = bazi.get("favorable", {})
            if isinstance(favorable, dict):
                # 用神 = primary
                yong_info = favorable.get("用神", favorable.get("yong_shen", {}))
                if isinstance(yong_info, dict):
                    yong = yong_info.get("element", yong_info.get("五行", ""))
                elif isinstance(yong_info, str):
                    yong = yong_info

                # 喜神 = secondary
                xi_info = favorable.get("喜神", favorable.get("xi_shen", {}))
                if isinstance(xi_info, dict):
                    xi = xi_info.get("element", xi_info.get("五行", ""))
                elif isinstance(xi_info, str):
                    xi = xi_info

        return {
            "primary": yong or "木",
            "secondary": xi or "水"
        }

    def _extract_year_ganzhi(self):
        """提取流年干支"""
        if self.astro and "dayun" in self.astro:
            # 尝试从dayun读取当前流年
            dayun = self.astro.get("dayun", {})
            current = dayun.get("current", {})
            liunian = current.get("liunian", {})
            return liunian.get("gan_zhi", self._calc_year_ganzhi())

        return self._calc_year_ganzhi()

    def _calc_year_ganzhi(self):
        """计算年份干支"""
        year_gan_idx = (self.year - 4) % 10
        year_zhi_idx = (self.year - 4) % 12
        return TIAN_GAN[year_gan_idx] + DI_ZHI[year_zhi_idx]

    def _extract_year_elements(self):
        """提取流年五行"""
        if self.astro and "bazi" in self.astro:
            bazi = self.astro.get("bazi", {})
            elements = bazi.get("elements", {})
            if elements:
                return elements

        # 默认：年干+年支
        gan = GAN_ELEMENT.get(self.year_ganzhi[0], "土")
        zhi = ZHI_ELEMENT.get(self.year_ganzhi[1], "土")
        return {gan: 2, zhi: 2}

    def _calc_monthly_flow(self):
        """计算流年12个月的五行能量"""
        monthly = []

        # 流年天干地支五行
        year_gan_el = GAN_ELEMENT.get(self.year_ganzhi[0], "土")
        year_zhi_el = ZHI_ELEMENT.get(self.year_ganzhi[1], "土")

        # 月支序列（节令月开始）
        month_zhi = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]

        for i, zhi in enumerate(month_zhi):
            month_num = i + 1
            zhi_el = ZHI_ELEMENT.get(zhi, "土")

            # 月干计算（五虎遁简化）
            # 年干对应月干起点：甲己→丙，乙庚→戊，丙辛→庚，丁壬→壬，戊癸→甲
            gan_start = {
                "甲": 2, "己": 2,  # 丙
                "乙": 4, "庚": 4,  # 戊
                "丙": 6, "辛": 6,  # 庚
                "丁": 8, "壬": 8,  # 壬
                "戊": 0, "癸": 0   # 甲
            }
            gan_idx = gan_start.get(self.year_ganzhi[0], 0)
            month_gan_idx = (gan_idx + i) % 10
            month_gan_el = GAN_ELEMENT.get(TIAN_GAN[month_gan_idx], "火")

            # 综合月五行（年干+月干+月支加权）
            scores = {el: 0 for el in ELEMENTS}
            scores[year_gan_el] += 1
            scores[month_gan_el] += 2  # 月令权重最高
            scores[zhi_el] += 1

            # 时间感知：当前月份标记
            status = "future"
            if month_num < self._current_month:
                status = "past"
            elif month_num == self._current_month:
                status = "current"

            monthly.append({
                "month": month_num,
                "gan_zhi": TIAN_GAN[month_gan_idx] + zhi,
                "gan_element": month_gan_el,
                "zhi_element": zhi_el,
                "scores": scores,
                "dominant": max(scores, key=scores.get),
                "status": status
            })

        return monthly

    def _calc_element_match(self, stock_element, target_elements):
        """
        计算股票五行与目标五行的匹配度

        核心原则：喜用神优先 > 宏观五行加持 > 其他

        Args:
            stock_element: 股票的五行属性（木/火/土/金/水）
            target_elements: 目标五行向量（如 {"木": 13, "火": 50, ...}）

        Returns:
            match_score: 0-100的匹配度分数
        """
        xi = self.xiyong.get("primary", "")
        ci = self.xiyong.get("secondary", "")

        # 喜用神加成
        base_score = 50

        if stock_element == xi:
            # 正合喜用神 → 最高分
            # 加成：看宏观向量中该五行是否也强
            macro_ratio = target_elements.get(xi, 0) / sum(target_elements.values()) if target_elements else 0
            return min(100, int(80 + macro_ratio * 20))
        elif stock_element == ci:
            # 次用神 → 次高
            macro_ratio = target_elements.get(ci, 0) / sum(target_elements.values()) if target_elements else 0
            return min(100, int(65 + macro_ratio * 15))
        elif SHENG.get(stock_element) == xi:
            # 股票五行生喜用神 → 中高分
            return min(100, int(55 + target_elements.get(stock_element, 20) / 10))
        elif KE.get(xi) == stock_element:
            # 喜用神克股票五行 → 扣分
            return max(0, int(40 - target_elements.get(stock_element, 20) / 5))
        elif stock_element == KE.get(xi):
            # 股票五行克喜用神 → 大幅扣分
            return max(0, int(30 - target_elements.get(stock_element, 20) / 3))
        else:
            # 中性 → 基础分
            return int(45 + target_elements.get(stock_element, 20) / 5)

    def _calc_timing(self, stock_element):
        """
        计算个股月度操作时效（v3.0完整版）

        Returns:
            dict: {
                month: "buy"/"hold"/"sell"/"empty",
                sell_months: [...],
                empty_months: [...],
                sell_triggers: [...],  # SnipeScore技术指标触发
                stop_loss: "..."
            }
        """
        timing = {}
        buy_months = []
        hold_months = []
        sell_months = []
        empty_months = []

        xi = self.xiyong.get("primary", "")
        ci = self.xiyong.get("secondary", "")
        ji = self._get_avoid_element()

        for month_data in self.monthly_flow:
            m = month_data["month"]
            dominant = month_data["dominant"]
            gan_zhi = month_data["gan_zhi"]

            # 时效判断
            if dominant == xi or dominant == ci:
                timing[m] = "buy"
                buy_months.append(f"{m}月")
            elif dominant in [SHENG.get(xi), SHENG.get(ci)]:
                timing[m] = "hold"
                hold_months.append(f"{m}月")
            elif dominant == ji:
                timing[m] = "empty"
                empty_months.append(f"{m}月")
            elif KE.get(dominant) == xi:
                timing[m] = "sell"
                sell_months.append(f"{m}月")
            else:
                timing[m] = "hold"
                hold_months.append(f"{m}月")

        # 生成SnipeScore卖出触发条件
        sell_triggers = self._generate_snipe_triggers(stock_element, timing, sell_months)

        # 生成止损规则
        stop_loss = self._generate_stop_loss(stock_element)

        return {
            "monthly": timing,
            "buy_months": buy_months,
            "hold_months": hold_months,
            "sell_months": sell_months,
            "empty_months": empty_months,
            "sell_triggers": sell_triggers,
            "stop_loss": stop_loss
        }

    def _generate_snipe_triggers(self, stock_element, timing, sell_months):
        """
        根据SnipeScore 8维指标生成卖出触发条件
        SnipeScore 8维权重：动量15%+资金15%+滞涨15%+催化剂15%+RSI10%+量比10%+趋势10%+估值10%

        Args:
            stock_element: 股票五行
            timing: 月度时效字典
            sell_months: 卖出月份列表

        Returns:
            list: 卖出触发条件列表
        """
        xi = self.xiyong.get("primary", "")
        triggers = []

        # 玄学时机触发（基于流月五行）
        if sell_months:
            # 主要卖出触发：忌神旺月
            trigger_1 = {
                "trigger_type": "玄学_忌神旺月",
                "condition": f"流月{stock_element}气主导 + SnipeScore动量<40",
                "action": "减仓50%",
                "severity": "high",
                "snipe_metrics": ["动量", "RSI"]
            }
            triggers.append(trigger_1)

            # 卖出触发：资金流出
            trigger_2 = {
                "trigger_type": "资金面_净流出",
                "condition": "连续3日主力资金净流出 > 5% + SnipeScore资金<35",
                "action": "减仓至30%底仓",
                "severity": "high",
                "snipe_metrics": ["资金", "量比"]
            }
            triggers.append(trigger_2)

        # 技术面触发（通用）
        # RSI超买
        trigger_rsi = {
            "trigger_type": "技术面_RSI超买",
            "condition": "RSI(14) > 80 + 流月忌神当令",
            "action": "分批减仓，保留1/3底仓",
            "severity": "medium",
            "snipe_metrics": ["RSI", "动量"]
        }
        triggers.append(trigger_rsi)

        # 放量滞涨
        trigger_volume = {
            "trigger_type": "技术面_滞涨",
            "condition": "量比 > 2.0 + 涨幅 < 1% (3日内) + SnipeScore滞涨>70",
            "action": "减仓50%",
            "severity": "medium",
            "snipe_metrics": ["量比", "滞涨", "催化剂"]
        }
        triggers.append(trigger_volume)

        # 趋势破位
        trigger_trend = {
            "trigger_type": "趋势破位",
            "condition": "收盘价 < 20日均线 + SnipeScore趋势<40",
            "action": "减仓50%，跌破60日均线清仓",
            "severity": "high",
            "snipe_metrics": ["趋势", "动量"]
        }
        triggers.append(trigger_trend)

        # 估值泡沫（针对成长股）
        if stock_element in ["木", "火"]:
            trigger_pe = {
                "trigger_type": "估值泡沫",
                "condition": "PE > 行业均值3倍 + SnipeScore估值>80",
                "action": "止盈离场，不追高",
                "severity": "low",
                "snipe_metrics": ["估值"]
            }
            triggers.append(trigger_pe)

        # 催化剂消失
        trigger_catalyst = {
            "trigger_type": "催化剂消退",
            "condition": "SnipeScore催化剂<30 (连续5日无利好) + 流月忌神",
            "action": "清仓该股，转入防御板块",
            "severity": "medium",
            "snipe_metrics": ["催化剂"]
        }
        triggers.append(trigger_catalyst)

        return triggers

    def _generate_stop_loss(self, stock_element):
        """
        生成止损规则

        Args:
            stock_element: 股票五行

        Returns:
            dict: 止损规则
        """
        xi = self.xiyong.get("primary", "")
        ji = self._get_avoid_element()

        # 根据五行属性和忌神关系设置止损
        if stock_element == xi:
            # 正合喜用神：宽松止损
            return {
                "level_1": {
                    "condition": "跌破10日均线",
                    "action": "减仓1/3",
                    "price_drop": "-5%"
                },
                "level_2": {
                    "condition": "跌破20日均线",
                    "action": "减仓50%",
                    "price_drop": "-10%"
                },
                "level_3": {
                    "condition": "跌破60日均线",
                    "action": "清仓",
                    "price_drop": "-20%"
                },
                "note": "喜用神共振，止损可适当放宽"
            }
        elif stock_element == SHENG.get(xi):
            # 生喜用神：中等止损
            return {
                "level_1": {
                    "condition": "跌破8日均线",
                    "action": "减仓1/3",
                    "price_drop": "-3%"
                },
                "level_2": {
                    "condition": "跌破15日均线",
                    "action": "减仓50%",
                    "price_drop": "-8%"
                },
                "level_3": {
                    "condition": "跌破30日均线",
                    "action": "清仓",
                    "price_drop": "-15%"
                },
                "note": "标准止损，趋势破坏即离场"
            }
        else:
            # 其他五行：严格止损
            return {
                "level_1": {
                    "condition": "跌破5日均线",
                    "action": "减仓1/3",
                    "price_drop": "-2%"
                },
                "level_2": {
                    "condition": "跌破10日均线",
                    "action": "减仓50%",
                    "price_drop": "-5%"
                },
                "level_3": {
                    "condition": "跌破20日均线",
                    "action": "清仓",
                    "price_drop": "-10%"
                },
                "note": "非核心持仓，严格止损"
            }

    def _get_avoid_element(self):
        """获取忌神五行（兼容多种格式）"""
        if self.astro and "bazi" in self.astro:
            bazi = self.astro.get("bazi", {})

            # 优先从 ji_shen（忌神列表）读取
            ji = bazi.get("ji_shen", [])
            if ji:
                avoid = ji[0] if isinstance(ji, list) else ji
                return avoid

            # 兼容 avoid 格式
            avoid_list = bazi.get("avoid", [])
            if avoid_list:
                avoid = avoid_list[0] if isinstance(avoid_list, list) else avoid_list
                return avoid

            # 兼容 favorable 格式
            favorable = bazi.get("favorable", {})
            if isinstance(favorable, dict):
                ji_info = favorable.get("忌神", favorable.get("ji_shen", {}))
                if isinstance(ji_info, dict):
                    avoid = ji_info.get("element", ji_info.get("五行", ""))
                    if avoid:
                        return avoid
                elif isinstance(ji_info, str) and ji_info:
                    return ji_info

        # 默认忌神：喜用神的克星
        xi = self.xiyong.get("primary", "木")
        return KE.get(xi, "金")

    def _apply_quarterly_modifier(self, score, month):
        """应用季度修正系数"""
        if not self.cosmic or "quarterly_modifier" not in self.cosmic:
            return score

        qm = self.cosmic["quarterly_modifier"]
        if month <= 3:
            factor = qm.get("Q1", {}).get("factor", 1.0)
        elif month <= 6:
            factor = qm.get("Q2", {}).get("factor", 1.0)
        elif month <= 9:
            factor = qm.get("Q3", {}).get("factor", 1.0)
        else:
            factor = qm.get("Q4", {}).get("factor", 1.0)

        return int(score * factor)

    def run(self, top_n=None):
        """
        执行选股

        Args:
            top_n: 返回前N只股票（仅用于最终输出限制，不限制候选池）
                   默认None=返回全量候选股票，供SnipeScore全量评分

        Returns:
            dict: 推荐股票列表 + 板块推荐 + 全量候选（供SnipeScore用）
        """
        # 获取宏观五行向量
        macro_vector = {}
        if self.cosmic and "macro_five_element" in self.cosmic:
            macro_vector = self.cosmic["macro_five_element"].get("vector", {})

        # 筛选股票（全量候选，不设上限）
        candidates = []
        for stock in self.stock_pool:
            stock_el = stock.get("element", "")
            if not stock_el:
                continue

            # 计算五行匹配度
            match_score = self._calc_element_match(stock_el, macro_vector)

            # 计算月度时效（v3.0完整版，含sell_triggers和stop_loss）
            timing = self._calc_timing(stock_el)

            # 当前月份的应用季度修正
            current_score = self._apply_quarterly_modifier(match_score, self._current_month)

            # 当前月份的时效
            current_timing = timing["monthly"].get(self._current_month, "hold")

            candidates.append({
                "code": stock["code"],
                "name": stock["name"],
                "board": stock["board"],
                "element": stock_el,
                "match_score": match_score,
                "current_score": current_score,
                "current_timing": current_timing,
                "timing": timing,  # v3.0完整timing对象
                "reason": self._explain_match(stock_el, match_score)
            })

        # 按当前得分排序
        candidates.sort(key=lambda x: x["current_score"], reverse=True)

        # 仅在最终输出时限制数量（不影响SnipeScore候选池）
        # 注意：pipeline传给snipe_integration时使用 all_candidates 而非 limited_stocks
        if top_n is not None:
            top_stocks = candidates[:top_n]
        else:
            top_stocks = candidates  # 全量输出（供SnipeScore评分）

        # 按板块聚合
        board_scores = {}
        for stock in candidates:
            board = stock["board"]
            if board not in board_scores:
                board_scores[board] = []
            board_scores[board].append(stock["current_score"])

        board_recommendations = []
        for board, scores in board_scores.items():
            avg_score = sum(scores) / len(scores)
            board_el = self._get_board_element(board)
            board_recommendations.append({
                "board": board,
                "avg_score": round(avg_score, 1),
                "element": board_el,
                "stock_count": len(scores),
                "recommendation": self._get_board_recommendation(avg_score, board_el)
            })

        board_recommendations.sort(key=lambda x: x["avg_score"], reverse=True)

        return self._build_output(top_stocks, board_recommendations)

    def _get_board_element(self, board):
        """获取板块的五行属性（简化：用SECTOR_ELEMENTS映射）"""
        for sector, elements in SECTOR_ELEMENTS.items():
            if sector in board or board in sector:
                dominant = max(elements, key=elements.get)
                return dominant
        return "土"  # 默认

    def _get_board_recommendation(self, avg_score, board_el):
        """判断板块推荐等级"""
        xi = self.xiyong.get("primary", "")

        if board_el == xi and avg_score >= 60:
            return "强烈推荐"
        elif board_el == self.xiyong.get("secondary", "") and avg_score >= 50:
            return "推荐"
        elif avg_score >= 40:
            return "中性"
        else:
            return "回避"

    def _explain_match(self, stock_el, score):
        """解释匹配原因"""
        xi = self.xiyong.get("primary", "")
        ci = self.xiyong.get("secondary", "")

        if stock_el == xi:
            return f"股票属{stock_el}，正合命主喜用神{xi}，五行共振"
        elif stock_el == ci:
            return f"股票属{stock_el}，助命主次用神{ci}"
        elif SHENG.get(stock_el) == xi:
            return f"股票属{stock_el}，生扶喜用神{xi}"
        elif KE.get(stock_el) == xi:
            return f"股票属{stock_el}，克伐喜用神{xi}，需谨慎"
        else:
            return f"股票属{stock_el}，与命主喜用神无直接关系"

    def _build_output(self, stocks, boards):
        """构建输出JSON（v3.0完整版）

        输出结构（新增all_candidates供SnipeScore全量评分）:
          - top_stocks: 最终推荐Top20（供展示）
          - all_candidates: 全量候选股票（供SnipeScore评分，不设上限）
          - recommended_boards: 板块推荐（含全量候选数）
        """
        # 时效图标映射
        TIMING_ICON = {
            "buy": "🟢",
            "hold": "🔵",
            "sell": "🟠",
            "empty": "⚫"
        }

        def _format_stock(s):
            """格式化单只股票"""
            # 生成12月时效日历
            timing_calendar = ""
            monthly_timing = s["timing"]["monthly"]
            for m in range(1, 13):
                icon = TIMING_ICON.get(monthly_timing.get(m, "hold"), "🔵")
                timing_calendar += icon

            # 格式化sell_triggers
            sell_triggers = []
            for t in s["timing"]["sell_triggers"]:
                severity_icon = "🔴" if t["severity"] == "high" else ("🟡" if t["severity"] == "medium" else "🟢")
                sell_triggers.append({
                    "severity": severity_icon,
                    "type": t["trigger_type"],
                    "condition": t["condition"],
                    "action": t["action"],
                    "metrics": t["snipe_metrics"]
                })

            # 格式化stop_loss
            sl = s["timing"]["stop_loss"]
            stop_loss_text = (
                f"{sl['level_1']['condition']}→{sl['level_1']['action']}({sl['level_1']['price_drop']}) | "
                f"{sl['level_2']['condition']}→{sl['level_2']['action']}({sl['level_2']['price_drop']}) | "
                f"{sl['level_3']['condition']}→{sl['level_3']['action']}({sl['level_3']['price_drop']})"
            )

            return {
                "rank": 0,  # SnipeScore排序后填充
                "code": s["code"],
                "name": s["name"],
                "board": s["board"],
                "element": s["element"],
                "match_score": s["match_score"],
                "current_score": s["current_score"],
                "current_timing": TIMING_ICON.get(s["current_timing"], "🔵") + self._timing_label(s["current_timing"]),
                "timing_calendar": timing_calendar,
                "buy_months": s["timing"]["buy_months"],
                "hold_months": s["timing"]["hold_months"],
                "sell_months": s["timing"]["sell_months"],
                "empty_months": s["timing"]["empty_months"],
                "sell_triggers": sell_triggers,
                "stop_loss": stop_loss_text,
                "stop_loss_detail": sl,
                "reason": s["reason"]
            }

        # 格式化推荐Top股票（供展示）
        formatted_stocks = [_format_stock(s) for s in stocks]

        # 格式化全量候选股票（供SnipeScore评分）
        formatted_all = [_format_stock(s) for s in stocks]  # 先用完整列表，snipe_integration会重排

        # 板块全量候选数统计
        board_candidates_count = {}
        for s in stocks:
            board = s["board"]
            board_candidates_count[board] = board_candidates_count.get(board, 0) + 1

        formatted_boards = []
        for b in boards[:10]:
            b_dict = dict(b)
            b_dict["candidate_count"] = board_candidates_count.get(b["board"], 0)
            formatted_boards.append(b_dict)

        output = {
            "meta": {
                "version": "star-hunter v3.1",
                "agent": "star-hunter",
                "timestamp": datetime.now().isoformat(),
                "target_year": self.year,
                "xiyong": self.xiyong,
                "year_ganzhi": self.year_ganzhi,
                "total_candidates": len(stocks),  # 全量候选数
            },
            "recommendations": {
                "stocks": formatted_stocks[:20],  # 展示Top20
                "boards": formatted_boards
            },
            # v3.1 新增：全量候选供SnipeScore评分
            "all_candidates": formatted_all,  # 全量候选（不含rank，由snipe_integration填充）
            "recommended_boards": formatted_boards,
            "monthly_flow": [
                {
                    "month": m["month"],
                    "gan_zhi": m["gan_zhi"],
                    "dominant_element": m["dominant"],
                    "status": m["status"]
                }
                for m in self.monthly_flow
            ],
            "validation": [
                {
                    "check": "喜用神",
                    "status": "PASS" if self.xiyong.get("primary") else "WARN",
                    "detail": f"主用:{self.xiyong.get('primary')} 次用:{self.xiyong.get('secondary')}"
                },
                {
                    "check": "股票池",
                    "status": "PASS" if len(self.stock_pool) > 100 else "WARN",
                    "detail": f"共{len(self.stock_pool)}只股票"
                },
                {
                    "check": "全量候选",
                    "status": "PASS" if len(stocks) > 100 else "WARN",
                    "detail": f"玄学候选{len(stocks)}只，供SnipeScore全量评分"
                }
            ]
        }

        return output

    def _timing_label(self, timing):
        """时效标签"""
        labels = {
            "buy": "买入",
            "hold": "持有",
            "sell": "卖出",
            "empty": "空仓"
        }
        return labels.get(timing, "持有")


def main():
    """CLI入口"""
    import argparse
    parser = argparse.ArgumentParser(description="star-hunter: 星座猎手Agent")
    parser.add_argument("--xiyong", type=str, default="木,水", help="喜用神（如木,水）")
    parser.add_argument("--year", type=int, default=None, help="目标年份")
    parser.add_argument("--top", type=int, default=20, help="返回前N只股票")
    args = parser.parse_args()

    # 构造astro_calc输入（简化版）
    xi_parts = args.xiyong.split(",")
    astro_input = {
        "bazi": {
            "xiyong": {"喜用": xi_parts[0], "次用": xi_parts[1] if len(xi_parts) > 1 else "金"}
        }
    }

    sh = StarHunter(
        astro_calc_output=astro_input,
        target_year=args.year or datetime.now().year
    )
    result = sh.run(top_n=args.top)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
