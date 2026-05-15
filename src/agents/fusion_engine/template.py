"""
Fusion-Engine: HTML报告模板生成器
v3.3 (完整版) — 补全所有缺失章节：雷达图 + 紫微/奇门/占星详情 + 四季策略 + 大运时间线 + 各章小结
          — v3.3修复：数据格式兼容层 + star-hunter注入 + 流月日历 + 紫微四化宫位

从fusion-engine计算结果生成完整客户版HTML报告
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from constants import ELEMENTS, GAN_ELEMENT, ZHI_ELEMENT, SECTOR_ELEMENTS

# ============================================================
# 数据格式兼容层（支持新旧两种格式）
# ============================================================

def _compat_get(d, *keys, default=None):
    """尝试多个可能的key，返回第一个找到的值"""
    for key in keys:
        if isinstance(d, dict) and key in d:
            val = d[key]
            # 避免空字符串、None、空列表
            if val not in (None, "", [], {}):
                return val
    return default


def _compat_vec(d, *keys, default=None):
    """获取五行向量，兼容多格式"""
    for key in keys:
        if isinstance(d, dict) and key in d:
            val = d[key]
            if isinstance(val, dict) and val:
                return val
    return default if default is not None else {}

ALL_MONTHS_CN = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"]
ELEMENT_COLORS = {
    "木": "#3fb950", "火": "#f85149", "土": "#c9a84c",
    "金": "#58a6ff", "水": "#bc8cff"
}


def radar_chart_svg(fusion_vec, bazi_vec, ziwei_vec, qimen_vec, astro_vec):
    """生成五行共振雷达图SVG — v3.6 修复：土字显示、刻度清晰、viewBox充足"""
    elements = ["木", "火", "土", "金", "水"]
    # 中心点 — 上移给底部"土"字留空间
    cx, cy = 140, 130
    max_r = 100

    def polar(val, idx, radius=None):
        angle = -90 + idx * 72
        r = min(val / 100 * (radius or max_r), radius or max_r)
        import math
        rad = math.radians(angle)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    # 背景网格 — 五边形层级线 + 刻度线
    grid = ""
    scale_labels = ""
    for level in [20, 40, 60, 80, 100]:
        pts = [polar(level, i) for i in range(5)]
        pts.append(pts[0])
        path = " ".join([f"L {x:.1f} {y:.1f}" for x, y in pts])
        # 层级线 — 虚线+亮色，确保在深色背景上可见
        grid += f'<polygon points="{pts[0][0]:.1f} {pts[0][1]:.1f} {path[2:]}" fill="none" stroke="#6e7681" stroke-width="1" stroke-dasharray="4,3" opacity="0.9"/>\n'
        # 刻度标签 — 放在每个轴的外侧，清晰可见
        sx, sy = polar(level, 0, radius=max_r + 14)
        scale_labels += f'<text x="{sx}" y="{sy}" text-anchor="middle" dominant-baseline="central" font-size="11" fill="#8b949e" font-weight="600">{level}</text>\n'

    # 轴线（从中心到每个顶点的线）
    axes = ""
    for i in range(5):
        x, y = polar(100, i)
        axes += f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#30363d" stroke-width="1" opacity="0.4"/>\n'

    # 标签 — 放在轴线外侧，土字在底部额外下移
    labels = ""
    for i, el in enumerate(elements):
        # 标签放在轴线末端外侧
        x, y = polar(100, i, radius=max_r + 28)
        # 土在底部(y最大)，额外下移避免截断
        dy = 6 if el == "土" else 0
        # 微调各方向避免拥挤
        dx = 0
        if el == "水":
            dx = -10  # 水在左侧，左移
        elif el == "火":
            dx = 10   # 火在右侧，右移
        labels += f'<text x="{x + dx}" y="{y + dy}" text-anchor="middle" dominant-baseline="central" font-size="15" fill="#e6edf3" font-weight="bold">{el}</text>\n'

    # 填充区域
    def polygon(data, color, opacity=0.3):
        pts = [polar(data.get(el, 0), i) for i, el in enumerate(elements)]
        pts_str = " ".join([f"{x:.1f},{y:.1f}" for x, y in pts])
        return f'<polygon points="{pts_str}" fill="{color}" stroke="{color}" stroke-width="2" opacity="{opacity}"/>\n'

    polys = ""
    polys += polygon(bazi_vec, "#c9a84c", 0.15)      # 八字 - 金色
    polys += polygon(ziwei_vec, "#58a6ff", 0.15)     # 紫微 - 蓝色
    polys += polygon(qimen_vec, "#3fb950", 0.15)      # 奇门 - 绿色
    polys += polygon(astro_vec, "#bc8cff", 0.15)      # 占星 - 紫色
    polys += polygon(fusion_vec, "#f85149", 0.35)     # 融合 - 红色

    # 数据点和连线
    lines = ""
    for i, el in enumerate(elements):
        v = fusion_vec.get(el, 0)
        x, y = polar(v, i)
        lines += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#f85149" stroke="#e6edf3" stroke-width="1"/>\n'
        lines += f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#f85149" stroke-width="1.5" opacity="0.6"/>\n'

    # viewBox加高到340，底部给土字留足空间
    svg = f'''<svg viewBox="0 0 280 340" width="260" height="320">
        {grid}
        {axes}
        {scale_labels}
        {labels}
        {polys}
        {lines}
        <!-- 中心点 -->
        <circle cx="{cx}" cy="{cy}" r="3" fill="#e6edf3"/>
    </svg>'''
    return svg


def timing_calendar_html(timing):
    """生成12月时效日历HTML
    兼容格式: dict(buy_months/hold_months/sell_months/empty_months) 或 None
    """
    if isinstance(timing, str):
        return f'<div style="font-size:13px;color:var(--text-muted)">{timing}</div>'

    # 防御: timing为None或非dict时，尝试从上层读取(已在stock卡片中处理)
    if not isinstance(timing, dict):
        timing = {}

    buy = timing.get("buy_months", []) or []
    hold = timing.get("hold_months", []) or []
    sell = timing.get("sell_months", []) or []
    empty = timing.get("empty_months", []) or []

    cal = ""
    for m in ALL_MONTHS_CN:
        if m in buy:
            cls, icon = "t-buy", "✓"
        elif m in sell:
            cls, icon = "t-sell", "▼"
        elif m in empty:
            cls, icon = "t-empty", "⊘"
        elif m in hold:
            cls, icon = "t-hold", "●"
        else:
            cls, icon = "t-hold", "●"
        cal += f'<div class="timing-month {cls}">{icon}{m}</div>'
    return cal


def confidence(score):
    if score >= 0.70: return "★★★★★"
    elif score >= 0.60: return "★★★★☆"
    elif score >= 0.50: return "★★★☆☆"
    elif score >= 0.35: return "★★☆☆☆"
    else: return "★☆☆☆☆"


def seasonal_strategy_section(monthly_data, fusion_result, qimen_data, cosmic_data, xiyong=None, ji=None):
    """生成四季流月操作策略 + 关键月份操作日历
    输出格式按用户截图:
    - 四季操作策略: 季节/月份/五行/奇门八门/评分/操作/核心策略
    - 关键月份操作日历: 月份/流月/五行/与命盘/奇门八门/操作/推荐板块Top3
    """
    # 提取喜用神（兼容多格式）
    if xiyong is None:
        bazi = fusion_result if isinstance(fusion_result, dict) else {}
        bazi_data = bazi.get("bazi", {}) if "bazi" in bazi else {}
        if not bazi_data:
            bazi_data = _compat_get(bazi, "xiyong", "input_summary", default={})
        if isinstance(bazi_data, dict):
            xiyong_primary = _compat_get(bazi_data, "primary", "喜用", "用神", "yong_shen", default="土")
            xiyong_secondary = _compat_get(bazi_data, "secondary", "次用", "xi_shen", default="金")
        else:
            xiyong_primary, xiyong_secondary = "土", "金"
        xiyong = {"primary": xiyong_primary, "secondary": xiyong_secondary}

    if ji is None:
        bazi = fusion_result if isinstance(fusion_result, dict) else {}
        ji = _compat_get(bazi, "avoid", "忌神", "ji_shen", default=["木", "火"])
        if isinstance(ji, str):
            ji = [ji]
        if not isinstance(ji, list):
            ji = ["木", "火"]

    # 如果monthly_data为空，生成12月数据
    if not monthly_data or not isinstance(monthly_data, list) or len(monthly_data) == 0:
        monthly_data = _generate_monthly_fallback(xiyong, ji)

    # 奇门季节数据
    qimen_seasons = qimen_data.get("eight_gates_seasonal", {}) if qimen_data else {}

    # 季度修正数据
    quarterly = _compat_get(cosmic_data, "quarterly_modifier", "季度修正", default={}) if cosmic_data else {}

    # 推荐板块（用于流月日历的Top3）
    recommended = fusion_result.get("recommended_sectors", []) if isinstance(fusion_result, dict) else []
    rec_names = [s.get("name", "") for s in recommended[:5]]

    # ===== 四季操作策略表格 =====
    season_configs = [
        {"name": "春季", "months": "2-4月", "icon": "🌸", "idx": [1, 2, 3]},
        {"name": "夏季", "months": "5-7月", "icon": "🔥", "idx": [4, 5, 6]},
        {"name": "秋季", "months": "8-10月", "icon": "🍂", "idx": [7, 8, 9]},
        {"name": "冬季", "months": "11-1月", "icon": "❄️", "idx": [10, 11, 12]}
    ]

    html = '<div class="section">\n'
    html += '  <h2><span class="icon">📆</span> 四季流月操作策略 + 关键月份操作日历</h2>\n'

    # --- 四季操作策略 ---
    html += '  <h3>四季操作策略</h3>\n'
    html += '  <table>\n'
    html += '    <tr><th>季节</th><th>月份</th><th>五行</th><th>奇门八门</th><th>评分</th><th>操作</th><th>核心策略</th></tr>\n'

    for sc in season_configs:
        # 从该季节月份推算五行和奇门
        month_indices = [i-1 for i in sc["idx"] if i-1 < len(monthly_data)]
        if not month_indices:
            continue

        # 取季节中间月为代表
        mid_m = monthly_data[month_indices[1]] if len(month_indices) > 1 else monthly_data[month_indices[0]]
        if not isinstance(mid_m, dict):
            continue

        gan_zhi = mid_m.get("gan_zhi", mid_m.get("ganzhi", "?"))
        # 推算五行: 取月支五行
        zhi = gan_zhi[1] if len(gan_zhi) >= 2 else "?"
        from constants import ZHI_ELEMENT
        wuxing = ZHI_ELEMENT.get(zhi, "?")
        wuxing_full = f"{wuxing}旺"

        # 奇门八门（从qimen_seasons或默认）
        qm_key = f"{sc['name']}("
        qm_info = None
        for k, v in (qimen_seasons or {}).items():
            if sc["name"] in k:
                qm_info = v
                break
        qimen_gates = qm_info.get("gates", []) if isinstance(qm_info, dict) else []
        qimen_str = "+".join(qimen_gates) if qimen_gates else "-"

        # 评分: 基于该季节月份与喜用神匹配度
        scores = []
        for mi in month_indices:
            mm = monthly_data[mi]
            if not isinstance(mm, dict):
                continue
            dom = mm.get("dominant_element", mm.get("dominant", "?"))
            if dom == xiyong.get("primary"):
                scores.append(0.85)
            elif dom == xiyong.get("secondary"):
                scores.append(0.70)
            elif dom in ji:
                scores.append(0.25)
            else:
                scores.append(0.55)
        avg_score = sum(scores) / len(scores) if scores else 0.5

        # 操作和策略
        if avg_score >= 0.7:
            op_text = "进攻"
            op_tag = '<span class="tag tag-green">进攻</span>'
            strategy = f"喜神{wuxing}到位，{rec_names[0] if rec_names else '重点板块'}重点加仓"
        elif avg_score <= 0.35:
            op_text = "防守"
            op_tag = '<span class="tag tag-red">防守</span>'
            strategy = f"忌神{wuxing}旺，{rec_names[0] if rec_names else '重点板块'}防守持有"
        elif avg_score <= 0.45:
            op_text = "观望"
            op_tag = '<span class="tag tag-red">观望</span>'
            strategy = f"忌神火旺极致，现金为王"
        else:
            op_text = "持有"
            op_tag = '<span class="tag tag-blue">持有</span>'
            strategy = f"{wuxing}克火有利，{rec_names[0] if rec_names else '重点板块'}稳定持有"

        html += f'''    <tr>
      <td>{sc["icon"]} {sc["name"]}</td>
      <td>{sc["months"]}</td>
      <td>{wuxing_full}</td>
      <td>{qimen_str}</td>
      <td>{avg_score:.2f}</td>
      <td>{op_tag}</td>
      <td style="font-size:13px">{strategy}</td>
    </tr>\n'''

    html += '  </table>\n'

    # --- 关键月份操作日历 ---
    html += '  <h3>关键月份操作日历</h3>\n'
    html += '  <table>\n'
    html += '    <tr><th>月份</th><th>流月</th><th>五行</th><th>与命盘</th><th>奇门八门</th><th>操作</th><th>推荐板块Top3</th></tr>\n'

    for m in monthly_data:
        if not isinstance(m, dict):
            continue
        month_num = m.get("month", 0)
        gan_zhi = m.get("gan_zhi", m.get("ganzhi", "?"))

        # 五行
        gan = gan_zhi[0] if len(gan_zhi) >= 1 else "?"
        zhi = gan_zhi[1] if len(gan_zhi) >= 2 else "?"
        from constants import GAN_ELEMENT, ZHI_ELEMENT
        gan_el = GAN_ELEMENT.get(gan, "?")
        zhi_el = ZHI_ELEMENT.get(zhi, "?")
        wuxing = f"{gan_el}{zhi_el}"

        # 与命盘关系
        xi_pri = xiyong.get("primary", "?")
        xi_sec = xiyong.get("secondary", "?")
        dom = m.get("dominant_element", m.get("dominant", zhi_el))
        if dom == xi_pri:
            mingpan_rel = f"{dom}(用)"
        elif dom == xi_sec:
            mingpan_rel = f"{dom}(喜)"
        elif dom in ji:
            mingpan_rel = f"{dom}(忌)旺"
        else:
            mingpan_rel = f"{dom}(闲)"

        # 奇门八门（每月）
        qimen_str = "-"
        for k, v in (qimen_seasons or {}).items():
            if isinstance(v, dict) and "gates" in v:
                # 简单映射: 根据月份判断季节
                qimen_str = "+".join(v.get("gates", [])[:2]) or "-"
                break

        # 操作
        timing = m.get("timing", m.get("timing_type", ""))
        action_raw = m.get("action", "")
        if timing == "buy" or "买入" in action_raw or "加仓" in action_raw:
            op_tag = '<span class="tag tag-green">加仓</span>'
        elif timing == "avoid" or "回避" in action_raw or timing == "empty":
            op_tag = '<span class="tag tag-red">观望</span>'
        elif timing == "sell" or "卖出" in action_raw or "减仓" in action_raw:
            op_tag = '<span class="tag tag-red">减仓</span>'
        elif "适度" in action_raw or "稳健" in action_raw:
            op_tag = '<span class="tag tag-gold">适度</span>'
        else:
            op_tag = '<span class="tag tag-blue">持有</span>'

        # 推荐板块Top3
        if dom == xi_pri:
            top3 = rec_names[:3] if len(rec_names) >= 3 else rec_names + ["-"] * (3 - len(rec_names))
        elif dom == xi_sec:
            top3 = [rec_names[1] if len(rec_names) > 1 else rec_names[0], rec_names[0] if rec_names else "-", rec_names[2] if len(rec_names) > 2 else "-"]
        elif dom in ji:
            top3 = ["降低仓位", "保留底仓", "回避木板块"]
        else:
            top3 = rec_names[:3] if len(rec_names) >= 3 else rec_names + ["-"] * (3 - len(rec_names))
        top3_str = "、".join(top3[:3])

        html += f'''    <tr>
      <td><strong>{month_num}月</strong></td>
      <td style="color:var(--gold)">{gan_zhi}</td>
      <td>{wuxing}</td>
      <td>{mingpan_rel}</td>
      <td>{qimen_str}</td>
      <td>{op_tag}</td>
      <td style="font-size:13px">{top3_str}</td>
    </tr>\n'''

    html += '  </table>\n'
    html += '</div>\n'
    return html


def _generate_monthly_fallback(xiyong, ji, target_year=2026):
    """当monthly_data为空时，生成12月流月分析"""
    from constants import TIAN_GAN, DI_ZHI, GAN_ELEMENT, ZHI_ELEMENT, ELEMENTS

    xi = xiyong.get("primary", "土") if isinstance(xiyong, dict) else str(xiyong)
    ci = xiyong.get("secondary", "金") if isinstance(xiyong, dict) else "金"
    if isinstance(ji, list) and ji:
        ji_list = ji
    elif isinstance(ji, str):
        ji_list = [ji]
    else:
        ji_list = ["木", "火"]

    # 流年天干地支
    year_gan_idx = (target_year - 4) % 10
    year_zhi_idx = (target_year - 4) % 12
    year_gan = TIAN_GAN[year_gan_idx]
    year_zhi = DI_ZHI[year_zhi_idx]

    # 月支序列（节令月开始）
    month_zhi_list = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]
    # 五虎遁月干起点
    gan_start = {"甲": 2, "己": 2, "乙": 4, "庚": 4, "丙": 6, "辛": 6, "丁": 8, "壬": 8, "戊": 0, "癸": 0}
    gan_idx = gan_start.get(year_gan, 0)

    monthly = []
    for i, zhi in enumerate(month_zhi_list):
        month_gan_idx = (gan_idx + i) % 10
        month_gan = TIAN_GAN[month_gan_idx]
        gan_el = GAN_ELEMENT.get(month_gan, "?")
        zhi_el = ZHI_ELEMENT.get(zhi, "?")

        # 当月最旺五行
        month_score = {el: 0 for el in ELEMENTS}
        month_score[gan_el] += 1
        month_score[zhi_el] += 2  # 月令权重更高

        dominant = max(month_score, key=month_score.get)

        # 与喜用神关系判断操作
        if dominant == xi:
            action = "🟢 积极买入"
            timing = "buy"
        elif dominant == ci:
            action = "🟢 稳健布局"
            timing = "hold"
        elif dominant in ji_list:
            action = "⚫ 回避空仓"
            timing = "avoid"
        else:
            action = "🔵 持有观望"
            timing = "hold"

        monthly.append({
            "month": i + 1,
            "gan_zhi": month_gan + zhi,
            "dominant_element": dominant,
            "action": action,
            "timing": timing
        })

    return monthly


def ziwei_section(ziwei_data, target_year=2026):
    """紫微斗数分析详情"""
    if not ziwei_data:
        return ""

    html = '<div class="section">\n'
    html += '  <h2><span class="icon">🔮</span> 紫微斗数分析（权重30%）</h2>\n'

    # === 2026年流年四化（重点修复：支持多格式）===
    # 尝试多个key路径
    sihua_list = _compat_get(ziwei_data,
        "annual_sihua", "sihua", "sihua_list",
        "annual_sihua.sihua", "流年四化",
        default=[])
    if isinstance(sihua_list, dict):
        sihua_list = sihua_list.get("sihua", [])
    if not isinstance(sihua_list, list):
        sihua_list = []

    # 备选：直接从transit或其他路径
    if not sihua_list:
        sihua_list = _compat_get(ziwei_data, "transits", "transit_sihua", "liu_nian_sihua", default=[])

    if sihua_list:
        html += f'  <h3>{target_year}年流年四化</h3>\n'
        html += '  <table>\n'
        html += '    <tr><th>星曜</th><th>化曜</th><th>影响宫位</th><th>吉凶</th></tr>\n'
        for s in sihua_list[:4]:  # 最多4条
            if isinstance(s, dict):
                tag_map = {"禄": "tag-green", "权": "tag-gold", "科": "tag-blue", "忌": "tag-red"}
                sihua_type = s.get("type", s.get("化曜", "?"))
                tag = tag_map.get(sihua_type, "tag-gray")
                # 尝试多个key获取宫位
                palace = _compat_get(s, "palace", "宫位", "impact_palace", default="命宫")
                impact = s.get("impact", s.get("影响", s.get("description", "")))
                # 尝试从星曜名称推断宫位（常见映射）
                star = s.get("star", s.get("星曜", "?"))
            else:
                sihua_type, star, palace, impact = "?", "?", "命宫", "?"

            # 判断吉凶
            if sihua_type in ["禄", "科"]:
                jixiong = "🟢 吉"
            elif sihua_type == "权":
                jixiong = "🟡 中"
            else:
                jixiong = "🔴 凶"

            # 如果impact没有包含palace信息，补充
            if palace and palace not in impact and palace != "?":
                impact_text = f"{palace}：{impact}" if impact else palace
            else:
                impact_text = impact or palace or "待补充"

            html += f'''    <tr>
      <td><strong>{star}</strong></td>
      <td><span class="tag {tag}">化{sihua_type}</span></td>
      <td style="font-size:13px">{palace}</td>
      <td style="font-size:13px">{jixiong} · {impact_text}</td>
    </tr>\n'''
        html += '  </table>\n'
    else:
        # 完全无数据时的fallback展示
        html += f'  <h3>{target_year}年流年四化</h3>\n'
        html += '  <p style="color:var(--text-muted);font-size:13px">流年四化数据待补充（需astro-calc输出完整四化表）</p>\n'

    # === 关键宫位（兼容多格式）===
    key_palaces = _compat_get(ziwei_data, "key_palaces", "palaces", "关键宫位", default={})
    if not isinstance(key_palaces, dict):
        key_palaces = {}

    # 也尝试从"palace_details"或嵌套结构读取
    if not key_palaces and isinstance(ziwei_data, dict):
        for k in ["命宫", "财帛宫", "官禄宫", "田宅宫", "福德宫", "父母宫"]:
            if k in ziwei_data and isinstance(ziwei_data[k], dict):
                key_palaces[k] = ziwei_data[k]

    if key_palaces:
        html += '  <h3>关键宫位解读</h3>\n'
        html += '  <div class="card-grid">\n'
        palace_map = {
            "命宫": "🧬", "财帛宫": "💰", "官禄宫": "📈", "田宅宫": "🏠",
            "福德宫": "🌟", "父母宫": "👨‍👩‍👧"
        }
        for palace_name, palace_info in key_palaces.items():
            icon = palace_map.get(palace_name, "📍")
            if isinstance(palace_info, dict):
                star = _compat_get(palace_info, "star", "星曜", "主星", default="?")
                element = _compat_get(palace_info, "element", "五行", "宫位五行", default="?")
                zhi = _compat_get(palace_info, "palace_branch", "宫支", "地支", "zhi", "?")
                interp = _compat_get(palace_info, "interpretation", "解读", "description", "分析", "")
            else:
                star, element, zhi, interp = palace_info, "?", "?", ""
            html += f'''    <div class="card">
      <h4>{icon} {palace_name}：{star}</h4>
      <p style="font-size:12px;color:var(--text-muted)">宫位五行：{element} | 宫支：{zhi}</p>
      <p style="font-size:13px">{interp}</p>
    </div>\n'''
        html += '  </div>\n'

    # === 紫微小结 ===
    favorable_elements = _compat_get(ziwei_data, "favorable_elements", "喜用五行", "xiyong_elements", default=[])
    unfavorable_elements = _compat_get(ziwei_data, "unfavorable_elements", "忌用五行", default=[])

    # 从四化列表生成摘要
    sihua_summary = "、".join([
        f"{s.get('star','?') if isinstance(s,dict) else s}化{s.get('type','?') if isinstance(s,dict) else s}"
        for s in sihua_list
    ]) if sihua_list else "四化信息待补充"

    # 从喜用神列表生成字符串
    if isinstance(favorable_elements, list) and favorable_elements:
        favorable_str = "、".join(favorable_elements)
    else:
        favorable_str = "喜用神信息待补充"

    # 生成小结的投资启示
    first_star = sihua_list[0].get("star","?") if sihua_list and isinstance(sihua_list[0], dict) else "主流星"
    first_type = sihua_list[0].get("type","禄") if sihua_list and isinstance(sihua_list[0], dict) else "禄"
    investment_tip = f"关注紫微星系{''.join(favorable_elements[:2]) if isinstance(favorable_elements, list) and favorable_elements else '土金'}属性板块，尤其是{first_star}化{first_type}带来的机会"
    if unfavorable_elements and isinstance(unfavorable_elements, list):
        investment_tip += f"；注意{unfavorable_elements[0]}属性板块的风险"

    html += f'''  <div class="summary-box">
    <strong>📋 紫微斗数小结</strong><br>
    • {target_year}年流年四化：{sihua_summary}<br>
    • 紫微喜用五行：{favorable_str}<br>
    • 投资启示：{investment_tip}
  </div>\n'''

    html += '</div>\n'
    return html


def qimen_section(qimen_data, target_year=2026):
    """奇门遁甲分析详情"""
    if not qimen_data:
        return ""

    html = '<div class="section">\n'
    html += '  <h2><span class="icon">🌀</span> 奇门遁甲分析（权重20%）</h2>\n'

    # 值符值使
    html += '  <div class="card-grid">\n'
    html += f'''    <div class="card">
      <h4>值符星：{qimen_data.get("value_star","?")}（{qimen_data.get("value_star_element","?")}）</h4>
      <p style="font-size:13px">{qimen_data.get("value_star_impact","?")}</p>
    </div>
    <div class="card">
      <h4>值使门：{qimen_data.get("value_gate","?")}（{qimen_data.get("value_gate_element","?")}）</h4>
      <p style="font-size:13px">{qimen_data.get("value_gate_impact","?")}</p>
    </div>\n'''
    html += '  </div>\n'

    # === 奇门季节数据 ===
    seasonal = qimen_data.get("eight_gates_seasonal", {})
    if seasonal and isinstance(seasonal, dict):
        html += '  <h3>八门季节吉凶</h3>\n'
        html += '  <table>\n'
        html += '    <tr><th>季节</th><th>吉门</th><th>评分</th><th>操作建议</th></tr>\n'
        for season, info in seasonal.items():
            if isinstance(info, dict):
                score = info.get("score", 1.0)
                color = "var(--green)" if score >= 1.1 else ("var(--red)" if score < 0.8 else "var(--blue)")
                html += f'''    <tr>
      <td><strong>{season}</strong></td>
      <td>{", ".join(info.get("gates", []))}</td>
      <td style="color:{color}">{score:.2f}</td>
      <td>{info.get("action","?")}</td>
    </tr>\n'''
        html += '  </table>\n'

    # 八神
    eight_gods = qimen_data.get("eight_gods", {})
    if eight_gods:
        html += '  <h3>八神概述</h3>\n'
        html += '  <div class="card-grid">\n'
        god_colors = {"腾蛇": "var(--orange)", "白虎": "var(--red)", "玄武": "var(--blue)", "青龙": "var(--green)"}
        for god, meaning in eight_gods.items():
            color = god_colors.get(god, "var(--text-muted)")
            html += f'''    <div class="card">
      <h4 style="color:{color}">{god}</h4>
      <p style="font-size:13px">{meaning}</p>
    </div>\n'''
        html += '  </div>\n'

    # === 奇门小结 ===
    value_star = qimen_data.get("value_star", "?")
    value_gate = qimen_data.get("value_gate", "?")
    seasonal = qimen_data.get("eight_gates_seasonal", {})
    best_season = ""
    best_score = 0
    favorable_gates = []
    if isinstance(seasonal, dict):
        for season, info in seasonal.items():
            if isinstance(info, dict) and info.get("score", 0) > best_score:
                best_score = info.get("score", 0)
                best_season = season
            if isinstance(info, dict):
                favorable_gates.extend(info.get("gates", []))
    favorable_gates = list(set(favorable_gates))[:3]
    html += f'''  <div class="summary-box">
    <strong>📋 奇门遁甲小结</strong><br>
    • {target_year}年值符：{value_star}，值使门：{value_gate}<br>
    • 最吉季节：{best_season if best_season else "待确定"}（评分 {best_score:.2f}）<br>
    • 吉门汇总：{"、".join(favorable_gates) if favorable_gates else "吉门信息待补充"}<br>
    • 投资启示：重点把握奇门吉门最旺的{best_season if best_season else "最佳季节"}，配合{favorable_gates[0] if favorable_gates else "主吉门"}门发力
  </div>\n'''

    html += '</div>\n'
    return html


def astrology_section(astrology_data, target_year=2026):
    """西方占星分析详情"""
    if not astrology_data:
        return ""

    html = '<div class="section">\n'
    html += '  <h2><span class="icon">✨</span> 西方占星分析（权重10%）</h2>\n'

    # 出生盘
    natal = astrology_data.get("natal", {})
    if natal:
        html += '  <h3>出生盘行星分布</h3>\n'
        html += '  <div class="card-grid">\n'
        planet_map = {
            "sun": ("☀️ 太阳", "var(--gold)"),
            "moon": ("🌙 月亮", "var(--blue)"),
            "rising": ("⬆️ 上升", "var(--green)")
        }
        for key, (label, color) in planet_map.items():
            info = natal.get(key, {})
            html += f'''    <div class="card">
      <h4>{label}：{info.get("sign","?")}</h4>
      <p style="font-size:12px">{info.get("interpretation","?")}</p>
    </div>\n'''
        html += '  </div>\n'

    # 流年行星
    transit = astrology_data.get("transit", {})
    if transit:
        html += f'  <h3>{target_year}年行星流年</h3>\n'
        html += '  <table>\n'
        html += '    <tr><th>行星</th><th>落座</th><th>影响</th></tr>\n'
        planet_list = ["木星", "土星", "冥王星", "天王星"]
        for planet in planet_list:
            info = transit.get(planet, {})
            if info:
                impact_text = info.get("impact", info.get("keyword", ""))
                if not impact_text and info.get("sign"):
                    impact_text = f"{planet}过{info.get('sign','')} — {info.get('keyword','')}"
                html += f'''    <tr>
      <td>{planet}</td>
      <td style="color:var(--gold)">{info.get("sign","?")}</td>
      <td style="font-size:13px">{impact_text or "?"}</td>
    </tr>\n'''
        html += '  </table>\n'

    # 水逆
    water_ni = transit.get("水逆", []) if transit else []
    # 兼容新字段名
    if not water_ni and isinstance(astrology_data.get("mercury_retrogrades"), list):
        water_ni = astrology_data["mercury_retrogrades"]
    if water_ni:
        html += f'  <p style="color:var(--orange);font-size:13px">⚠️ 水星逆行期：{" | ".join(water_ni)}</p>\n'

    # === 占星小结 ===
    # 兼容多种natal格式
    natal = _compat_get(astrology_data, "natal", "birth_chart", "本命盘", default={})
    if not isinstance(natal, dict):
        natal = {}
    # 也尝试从顶层读取（部分数据直接放在顶层）
    if not natal:
        for key in ["sun", "moon", "rising", "☀️", "🌙", "⬆️"]:
            if key in astrology_data and isinstance(astrology_data[key], dict):
                natal[key] = astrology_data[key]

    sun_sign = _compat_get(natal, "sun", "☀️", "太阳", "sun_sign", default="?")
    moon_sign = _compat_get(natal, "moon", "🌙", "月亮", "moon_sign", default="?")
    rising_sign = _compat_get(natal, "rising", "⬆️", "上升", "ascendant", "rising_sign", default="?")
    if isinstance(sun_sign, dict):
        sun_sign = sun_sign.get("sign", sun_sign.get("zodiac", "?"))
    if isinstance(moon_sign, dict):
        moon_sign = moon_sign.get("sign", moon_sign.get("zodiac", "?"))
    if isinstance(rising_sign, dict):
        rising_sign = rising_sign.get("sign", rising_sign.get("zodiac", "?"))

    # 流年行星
    transit = _compat_get(astrology_data, "transit", "transits", "流年", default={})
    if not isinstance(transit, dict):
        transit = {}

    # 水逆 — 兼容新旧字段名
    water_ni = _compat_get(transit, "水逆", "mercury_retrograde", "水星逆行", default=[])
    if not water_ni and isinstance(astrology_data.get("mercury_retrogrades"), list):
        water_ni = astrology_data["mercury_retrogrades"]

    # 流年最有影响力的行星
    strongest_planet = ""
    strongest_impact = ""
    if isinstance(transit, dict):
        for planet, info in transit.items():
            if isinstance(info, dict) and "impact" in info:
                if "吉" in info.get("impact", "") or "好运" in info.get("impact", ""):
                    strongest_planet = planet
                    strongest_impact = info.get("impact", "")
                    break

    # 水逆列表转字符串
    if isinstance(water_ni, list):
        water_ni_str = " | ".join([m.get("period", m) if isinstance(m, dict) else str(m) for m in water_ni])
    elif isinstance(water_ni, str):
        water_ni_str = water_ni
    else:
        water_ni_str = "无重大水逆期"

    investment_hint = "需谨慎操作" if strongest_impact and ("吉" not in strongest_impact and "好运" not in strongest_impact) else "适合积极布局"

    # 水逆投资建议（有水逆数据时生成具体建议）
    _mercury_advice = ""
    if water_ni and isinstance(water_ni, list) and len(water_ni) > 0:
        _periods = []
        for m in water_ni:
            p = m.get("period", m) if isinstance(m, dict) else str(m)
            _periods.append(p)
        _mercury_advice = f"<br>• ⚠️ 水逆实操建议：{'；'.join(_periods)}期间不宜开新仓、不签合同、不换股，已持仓可继续持有但禁止加仓。水逆前3天清仓观望为上策。"

    html += f'''  <div class="summary-box">
    <strong>📋 西方占星小结</strong><br>
    • 出生盘：太阳{sun_sign}、月亮{moon_sign}、上升{rising_sign}<br>
    • {target_year}年流年：{strongest_planet if strongest_planet else "主要行星"} - {strongest_impact if strongest_impact else "影响力待确定"}<br>
    • 水星逆行：{water_ni_str}<br>
    • 投资启示：占星角度看，{target_year}年{investment_hint}，注意水逆期避免重大决策{_mercury_advice}
  </div>\n'''

    html += '</div>\n'
    return html


def bazi_detail_section(bazi, dayun_data=None):
    """八字命盘详情"""
    if not bazi:
        return ""

    html = '<div class="section">\n'
    html += '  <h2><span class="icon">🧮</span> 基础命盘（八字 · 权重40%）</h2>\n'

    # 天干地支详解
    html += '  <h3>天干地支详解</h3>\n'
    html += '  <table>\n'
    html += '    <tr><th>四柱</th><th>天干</th><th>地支</th><th>藏干</th><th>五行</th></tr>\n'

    pillars = bazi.get("four_pillars", {})
    pillar_labels = {"year": "年柱", "month": "月柱", "day": "日柱", "hour": "时柱"}

    # 藏干映射
    ZANG_GAN = {
        "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
        "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
        "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
        "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"]
    }

    for key, label in pillar_labels.items():
        pillar = pillars.get(key, "")
        if not pillar or len(pillar) < 2:
            continue
        gan, zhi = pillar[0], pillar[1]
        gan_el = GAN_ELEMENT.get(gan, "?")
        zang = ZANG_GAN.get(zhi, [])
        html += f'''    <tr>
      <td><strong>{label}</strong></td>
      <td style="color:var(--gold)">{gan}</td>
      <td style="color:var(--primary)">{zhi}</td>
      <td style="font-size:12px">{" · ".join(zang)}</td>
      <td>{gan_el}/{ZHI_ELEMENT.get(zhi,"?")}</td>
    </tr>\n'''
    html += '  </table>\n'

    # === 大运时间线（新增）===
    if dayun_data:
        dayun_list = dayun_data.get("sequence", [])
        current_dayun = dayun_data.get("current", {})
        dayun_method = dayun_data.get("method", "日干派")
        dayun_mode = dayun_data.get("mode", "day_gan")
        if dayun_list:
            html += '  <h3>大运走势（10步大运）</h3>\n'
            html += f'  <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">排法：{dayun_method}（主流为日干派；如需切换为年干派，请在输入中设置 dayun_mode="year_gan"）</div>\n'
            html += '  <div class="dayun-timeline">\n'
            for dy in dayun_list[:10]:
                is_current = dy.get("gan_zhi") == current_dayun.get("gan_zhi")
                cls = "dayun-item current" if is_current else "dayun-item"
                html += f'    <div class="{cls}">{dy.get("gan_zhi","?")} ({dy.get("year_start","?")}-{dy.get("year_end","?")}) {dy.get("age_start","?")}-{dy.get("age_end","?")}岁</div>\n'
            html += '  </div>\n'
            # 当前大运详情 + 当年分析
            if current_dayun:
                dy_gz = current_dayun.get("gan_zhi", "?")
                dy_start = current_dayun.get("year_start", "?")
                dy_end = current_dayun.get("year_end", "?")
                dy_age_start = current_dayun.get("age_start", "?")
                dy_age_end = current_dayun.get("age_end", "?")
                dy_influence = current_dayun.get("influence", "")

                # 大运天干地支五行分析
                dy_gan = dy_gz[0] if len(dy_gz) >= 2 else "?"
                dy_zhi = dy_gz[1] if len(dy_gz) >= 2 else "?"
                dy_gan_el = GAN_ELEMENT.get(dy_gan, "?")
                dy_zhi_el = ZHI_ELEMENT.get(dy_zhi, "?")

                html += f'''  <div class="summary-box" style="margin-top:10px">
    <strong>当前大运：{dy_gz}（{dy_start}-{dy_end}，{dy_age_start}-{dy_age_end}岁）</strong><br>
    <span style="font-size:13px">大运天干<strong>{dy_gan}</strong>属<strong style="color:var(--gold)">{dy_gan_el}</strong>，
    地支<strong>{dy_zhi}</strong>属<strong style="color:var(--primary)">{dy_zhi_el}</strong></span><br>
    <span style="font-size:13px;color:var(--text-muted)">影响分析：{dy_influence if dy_influence else "待补充"}</span><br>
    <span style="font-size:13px;color:var(--text-muted)">整体基调：{dayun_data.get("description","")}</span>
  </div>\n'''

    # 五行强弱分析（得令/得地/得势）— 用于判断日主身旺/身弱
    strength_breakdown = bazi.get("strength_breakdown", {})
    if strength_breakdown:
        html += '  <h3>日主强弱分析</h3>\n'
        html += '  <p style="font-size:12px;color:var(--text-muted);margin-bottom:10px">得令=月令是否生扶日主 · 得地=地支是否有根 · 得势=天干是否比劫帮身。三者综合判断身旺/身弱。</p>\n'
        html += '  <div class="card-grid">\n'
        total = sum(strength_breakdown.values())
        for factor, score in strength_breakdown.items():
            pct = (score / max(total, 1)) * 100
            html += f'''    <div class="card">
      <h4>{factor}</h4>
      <p style="font-size:13px">得分：<strong style="color:var(--gold)">{score}</strong></p>
      <div class="score-bar"><div class="score-fill" style="width:{pct:.0f}%;background:var(--gold)"></div></div>
    </div>\n'''
        html += '  </div>\n'

    # 用神分析
    favorable = bazi.get("favorable", {})
    if favorable:
        html += '  <h3>喜忌神详解</h3>\n'
        html += '  <div class="card-grid">\n'
        for god_type in ["用神", "喜神", "忌神", "忌神2", "闲神"]:
            info = favorable.get(god_type, {})
            if info:
                color = "var(--green)" if "用神" in god_type else ("var(--red)" if "忌神" in god_type else "var(--blue)")
                html += f'''    <div class="card">
      <h4 style="color:{color}">{god_type}：{info.get("element","?")}</h4>
      <p style="font-size:12px">代表：{" · ".join(info.get("gods",[]))}</p>
      <p style="font-size:12px;color:var(--text-muted)">{info.get("reason","?")}</p>
    </div>\n'''
        html += '  </div>\n'

    # === 八字小结（兼容多格式）===
    dayun_summary = dayun_data.get("current", {}).get("gan_zhi", "?") if isinstance(dayun_data, dict) else "?"
    dayun_desc = dayun_data.get("description", "") if isinstance(dayun_data, dict) else ""

    # 提取用神/喜神/strength（兼容多格式）
    favorable = _compat_get(bazi, "favorable", "喜忌神", "xiyong", "favorable", default={})
    if not isinstance(favorable, dict):
        favorable = {}

    yong_info = favorable.get("用神", favorable.get("yong_shen", {}))
    xi_info = favorable.get("喜神", favorable.get("xi_shen", {}))
    strength_val = favorable.get("strength", bazi.get("strength", bazi.get("强弱", "?")))
    if isinstance(yong_info, dict):
        yong_el = yong_info.get("element", "?")
    else:
        yong_el = str(yong_info) if yong_info else "?"
    if isinstance(xi_info, dict):
        xi_el = xi_info.get("element", "?")
    else:
        xi_el = str(xi_info) if xi_info else "?"
    if isinstance(strength_val, dict):
        strength_str = strength_val.get("value", strength_val.get("label", "?"))
    else:
        strength_str = str(strength_val) if strength_val else "?"

    # 提取推荐板块（从喜神sectors）
    xi_sectors = []
    if isinstance(xi_info, dict):
        xi_sectors = xi_info.get("sectors", [])
    recommended_sector_names = "、".join([s.get("name","?") for s in xi_sectors[:3]]) if xi_sectors else "土金相关板块"

    html += f'''  <div class="summary-box">
    <strong>📋 八字命盘小结</strong><br>
    • 日主{yong_el}偏{strength_str}，喜{xi_el}，忌{"、".join([favorable.get("忌神",{}).get("element","?") if isinstance(favorable.get("忌神"),dict) else str(favorable.get("忌神","木")), (favorable.get("忌神2",{}).get("element","?") if isinstance(favorable.get("忌神2"),dict) else "")]) if favorable.get("忌神") else "木火"}<br>
    • 当前大运：{dayun_summary}，{dayun_desc if dayun_desc else "大运信息待补充"}<br>
    • 投资启示：重点关注{xi_el if xi_el != "?" else "土金"}属性的{recommended_sector_names}
  </div>\n'''

    html += '</div>\n'
    return html


# ── SnipeScore展示辅助函数 ────────────────────────────────
def _fmt_final_score(stock: dict) -> str:
    """格式化个股综合得分"""
    v = stock.get("final_score", stock.get("current_score", stock.get("match_score", 0)))
    if isinstance(v, (int, float)):
        return f"{v:.1f}"
    return str(v)


def _fmt_snipe_score(stock: dict) -> str:
    """格式化SnipeScore显示"""
    v = stock.get("snipe_score")
    if isinstance(v, (int, float)) and v > 0:
        return f"{v:.1f}"
    return "玄学模式"


def generate_html(astro, cosmic, fusion_result, star_hunter_result=None):
    """生成完整客户版HTML报告 v3.3
    Args:
        astro: astro_calc输出JSON（支持新旧格式）
        cosmic: cosmic_trend输出JSON（支持新旧格式）
        fusion_result: fusion_engine输出JSON（必须）
        star_hunter_result: star_hunter输出JSON（可选，用于个股精选）
    """

    # === 数据提取（兼容新旧格式） ===

    # 融合向量
    fused = fusion_result.get("fused_five_element", {}) or fusion_result.get("fusion_vector", {})
    fusion_vector = fused.get("vector", {}) if isinstance(fused, dict) else (fused or {})
    recommended = fusion_result.get("recommended_sectors", [])
    forbidden = fusion_result.get("forbidden_sectors", [])

    # monthly_analysis（兼容多个可能的key）
    monthly_data = _compat_get(fusion_result,
        "monthly_analysis", "monthly", "流月分析",
        default=[])
    if not isinstance(monthly_data, list):
        monthly_data = []

    # star-hunter个股数据（优先用fusion_result里的，再用star_hunter_result）
    top_stocks = _compat_get(fusion_result, "top_stocks", "stocks", default=[])
    if (not top_stocks or len(top_stocks) < 3) and star_hunter_result:
        # 从star_hunter_result提取个股
        sh_stocks = _compat_get(star_hunter_result, "recommendations", "stocks", "stocks", default=[])
        if isinstance(sh_stocks, dict):
            sh_stocks = sh_stocks.get("stocks", [])
        if isinstance(sh_stocks, list) and sh_stocks:
            # 标准化star-hunter数据格式
            top_stocks = []
            for s in sh_stocks[:10]:
                if isinstance(s, dict):
                    # star-hunter格式 → template格式
                    # 兼容两种格式：嵌套timing对象 或 扁平化buy_months等
                    timing = s.get("timing", {})
                    if isinstance(timing, dict) and (timing.get("buy_months") or timing.get("hold_months")):
                        # 嵌套格式
                        std_timing = {
                            "buy_months": timing.get("buy_months", []),
                            "hold_months": timing.get("hold_months", []),
                            "sell_months": timing.get("sell_months", []),
                            "empty_months": timing.get("empty_months", [])
                        }
                    else:
                        # 扁平格式：直接从stock读取
                        std_timing = {
                            "buy_months": s.get("buy_months", []),
                            "hold_months": s.get("hold_months", []),
                            "sell_months": s.get("sell_months", []),
                            "empty_months": s.get("empty_months", [])
                        }

                    top_stocks.append({
                        "name": s.get("name", "?"),
                        "code": s.get("code", "?"),
                        "board": s.get("board", s.get("sector", "?")),
                        "element": s.get("element", "?"),
                        "current_score": s.get("current_score", s.get("match_score", 0)),
                        "final_score": s.get("final_score", s.get("current_score", 0)),
                        "timing": std_timing,
                        "sell_triggers": s.get("sell_triggers", []),
                        "stop_loss": s.get("stop_loss", s.get("stop_loss_detail", {})),
                        "reason": s.get("reason", "")
                    })

    if not isinstance(top_stocks, list):
        top_stocks = []

    # === astro数据（兼容新旧格式）===
    bazi = astro.get("bazi", {}) if isinstance(astro, dict) else {}

    # 兼容旧格式的中文key
    if not bazi:
        bazi = {
            "four_pillars": _compat_get(astro, "four_pillars", "四柱八字", "四柱", default={}),
            "xiyong": _compat_get(astro, "xiyong", "xiyong", default={}),
            "strength_breakdown": _compat_get(astro, "strength_breakdown", "五行强度", default={}),
            "favorable": _compat_get(astro, "favorable", "喜忌神", "喜神忌神", default={}),
            "five_element_vector": _compat_vec(astro,
                "five_element_vector", "八字向量", "bazi_vector", "elements",
                default={}),
        }

    ziwei = astro.get("ziwei", {}) if isinstance(astro, dict) else {}
    qimen = astro.get("qimen", {}) if isinstance(astro, dict) else {}
    astrology = astro.get("astrology", {}) if isinstance(astro, dict) else {}
    dayun_data = astro.get("dayun", {}) if isinstance(astro, dict) else {}

    # === 提取核心命盘信息（用于核心结论概括）===
    # 日主（日柱天干）
    _day_gan = "?"
    _day_gan_element = "?"
    _day_gan_strength = "未知"
    _xiyong_primary = "?"
    _xiyong_secondary = "?"
    _current_dayun = "?"
    _current_dayun_age = ""
    fp = bazi.get("four_pillars", {})
    if fp and fp.get("day"):
        _day_gan = fp["day"][0] if len(fp["day"]) >= 1 else "?"
        _day_gan_element = GAN_ELEMENT.get(_day_gan, "?")
    # 喜用神
    favorable = bazi.get("favorable", {})
    if isinstance(favorable, dict):
        # 格式: {"用神": {"element": "土"}, "喜神": {"element": "金"}}
        _xiyong_primary = favorable.get("用神", {}).get("element", "?")
        _xiyong_secondary = favorable.get("喜神", {}).get("element", "?")
    else:
        # 兼容旧格式
        xiyong = bazi.get("xiyong", {})
        if isinstance(xiyong, dict):
            _xiyong_primary = xiyong.get("primary", xiyong.get("yong_shen", xiyong.get("喜用", "?")))
            _xiyong_secondary = xiyong.get("secondary", xiyong.get("xi_shen", xiyong.get("次用", "?")))
    # 日主强弱
    strength = bazi.get("strength", bazi.get("strength_breakdown", {}))
    if isinstance(strength, dict):
        _day_gan_strength = strength.get("level", strength.get("strength", strength.get("结论", "未知")))
    elif isinstance(strength, str):
        _day_gan_strength = strength
    # 当前大运
    if isinstance(dayun_data, dict) and dayun_data.get("current"):
        cur = dayun_data["current"]
        _current_dayun = cur.get("gan_zhi", "?")
        _current_dayun_age = f"（{cur.get('age_start','?')}-{cur.get('age_end','?')}岁）"

    target_year = _compat_get(astro, "target_year", "user_input",
        "birth", default={}).get("target_year", 2026) if isinstance(astro, dict) else 2026
    if isinstance(astro, dict) and "user_input" in astro:
        birth = astro.get("user_input", {})
    elif isinstance(astro, dict) and "birth" in astro:
        birth = astro.get("birth", {})
    else:
        birth = astro if isinstance(astro, dict) else {}

    fp = bazi.get("four_pillars", {})
    if not fp:
        # 尝试从旧的四柱字符串解析
        four_pillars_str = _compat_get(bazi, "four_pillars", "四柱", "四柱八字", default="")
        if isinstance(four_pillars_str, str) and four_pillars_str:
            # 格式："甲寅 庚午 丁未 己酉"
            parts = four_pillars_str.strip().split()
            pillar_keys = ["year", "month", "day", "hour"]
            fp = {}
            for i, p in enumerate(parts):
                if i < 4 and len(p) >= 2:
                    fp[pillar_keys[i]] = p[:2]

    # === cosmic数据（兼容新旧格式）===
    yearly_gz = {}
    yearly_gz_text = _compat_get(cosmic, "yearly_ganzhi", "年份干支", "年份", "gan_zhi", default=None)
    if yearly_gz_text:
        if isinstance(yearly_gz_text, str):
            yearly_gz = {"gan_zhi": yearly_gz_text, "year": target_year}
        elif isinstance(yearly_gz_text, dict):
            yearly_gz = yearly_gz_text
    else:
        # 计算流年干支
        year_gan_idx = (target_year - 4) % 10
        year_zhi_idx = (target_year - 4) % 12
        _yg = TIAN_GAN[year_gan_idx]
        _yz = DI_ZHI[year_zhi_idx]
        yearly_gz = {
            "gan_zhi": _yg + _yz,
            "year": target_year,
            "heavenly_stem": _yg,
            "earthly_branch": _yz,
            "stem_element": GAN_ELEMENT.get(_yg, "?"),
            "branch_element": ZHI_ELEMENT.get(_yz, "?")
        }

    nine_star = _compat_get(cosmic, "nine_star_cycle", "nine_star", "九运", "九星", default={})
    if not isinstance(nine_star, dict):
        nine_star = {"name": str(nine_star) if nine_star else "?"}
    # macro_vec: cosmic输出的是 {"vector": {...}, "status": {...}}，需要提取vector
    _macro_raw = _compat_get(cosmic, "macro_five_element", "macro_vector", "大势向量", default={})
    if isinstance(_macro_raw, dict) and "vector" in _macro_raw:
        macro_vec = _macro_raw["vector"]
    elif isinstance(_macro_raw, dict):
        macro_vec = _macro_raw
    else:
        macro_vec = {}

    # === 雷达图数据（兼容多个key）===
    bazi_vec = _compat_vec(bazi, "five_element_vector", "bazi_vector", "elements", "八字向量", default={})
    ziwei_vec = _compat_vec(ziwei, "five_element_vector", "ziwei_vector", "紫微向量", default={})
    qimen_vec = _compat_vec(astro, "qimen_vector", "qimen_vector", "奇门向量", default={})
    astro_vec = _compat_vec(astro, "astro_vector", "astro_vector", "占星向量", default={})

    # 如果astro_vec为空，尝试从astrology读
    if not astro_vec:
        astro_vec = _compat_vec(astrology, "five_element_vector", "element_vector", "natal_vector", default={})

    # === 宏观行星 ===
    transit = _compat_get(astrology, "transit", "transits", "行星流年", default={})
    if not isinstance(transit, dict):
        transit = {}
    planetary = _compat_get(cosmic, "planetary_transits", "planetary", default={})
    if not isinstance(planetary, dict):
        planetary = {}

    # === 宏观大势分析预计算变量 ===
    _macro_rows = ""
    if macro_vec and isinstance(macro_vec, dict):
        for el in ["木","火","土","金","水"]:
            val = macro_vec.get(el, 0)
            if val is None:
                val = 0
            # 从cosmic读取status信息
            status_info = {}
            trend = "-"
            desc = "-"
            if cosmic and isinstance(cosmic, dict):
                mfe = cosmic.get("macro_five_element", {})
                if isinstance(mfe, dict):
                    status_dict = mfe.get("status", {})
                    if isinstance(status_dict, dict) and el in status_dict:
                        status_info = status_dict[el]
                        if isinstance(status_info, dict):
                            trend = status_info.get("trend", "-")
                            desc = status_info.get("reason", "-")
            _macro_rows += f"<tr><td><strong style='color:{ELEMENT_COLORS.get(el,'#fff')}'>{el}</strong></td><td>{val}</td><td>{trend}</td><td style='font-size:13px'>{desc}</td></tr>"

    # 政策主题（兼容空值）
    _policy_theme = "政策主题待补充"
    _policy_directions = ""
    if cosmic and isinstance(cosmic, dict):
        _policy_obj = cosmic.get("policy", {})
        if isinstance(_policy_obj, dict):
            _policy_theme = _policy_obj.get("theme") or _policy_obj.get("主题") or "政策主题待补充"
            _dirs = _policy_obj.get("directions", [])
            if isinstance(_dirs, list) and _dirs:
                for d in _dirs[:5]:
                    if isinstance(d, dict):
                        _policy_directions += f"• {d.get('sector','?')}: {d.get('policy','?')} (权重{d.get('weight',0):.0%})<br>"
            if not _policy_directions:
                _policy_directions = "政策方向数据待补充<br>"

    _planet_rows = ""
    if cosmic:
        _pt = cosmic.get("planetary_transits", {})
        if isinstance(_pt, dict):
            for p, info in _pt.items():
                # 跳过非行星键（如水逆列表）
                if p in ("mercury_retrograde", "水逆"):
                    continue
                if isinstance(info, dict):
                    _planet_rows += f"<tr><td>{p}</td><td style='color:var(--gold)'>{info.get('sign','?')}</td><td style='font-size:13px'>{info.get('impact','?')}</td><td style='font-size:13px'>{info.get('invest_advice','?')}</td></tr>"

    _dominant_element = max(macro_vec, key=lambda k: macro_vec[k]) if macro_vec and isinstance(list(macro_vec.values())[0], (int, float)) else "?"
    _investment_tone = "积极布局" if macro_vec and (macro_vec.get("土",0) + macro_vec.get("金",0)) > (macro_vec.get("木",0) + macro_vec.get("火",0)) else "谨慎防守" if macro_vec else "待观察"

    # === 推荐板块行 ===
    rec_rows = ""
    for i, s in enumerate(recommended[:10]):
        score = s.get("score", s.get("final_score", 0))
        rec_rows += f"""<tr>
      <td style="font-size:20px;color:var(--primary);font-weight:bold">{i+1}</td>
      <td><strong>{s.get('name','?')}</strong></td>
      <td><strong style="color:var(--gold)">{score:.1f}</strong></td>
      <td>{confidence(score/100)}</td>
      <td style="font-size:13px">{s.get('reason', '多术数共振推荐')}</td>
    </tr>"""

    # === 禁忌板块行 ===
    forbid_rows = ""
    for i, s in enumerate(forbidden[:5]):
        forbid_rows += f"""<tr>
      <td>{i+1}</td>
      <td><strong>{s.get('name','?')}</strong></td>
      <td><span class="tag tag-red">忌神五行</span></td>
      <td><span class="tag tag-red">规避</span></td>
      <td style="font-size:13px">{s.get('reason', '忌神占比过高')}</td>
    </tr>"""

    # === 个股卡片 ===
    stock_cards = ""
    for i, s in enumerate(top_stocks[:10]):
        score = s.get("final_score", s.get("current_score", s.get("match_score", 0)))
        bar_color = "#c9a84c" if score >= 70 else "#58a6ff" if score >= 60 else "#8b949e"
        bar_width = min(score, 100)
        # SnipeScore展示（预计算，避免f-string中用反斜杠）
        _ss = s.get("snipe_score")
        _snipe_disp = ""
        if _ss and isinstance(_ss, (int, float)):
            _snipe_disp = f'<div style="min-width:80px;font-size:10px;text-align:center;border-left:1px solid #30363d;padding-left:8px"><div class="stock-score-label">Snipe</div><strong style="color:#58a6ff">{_ss:.1f}</strong></div>'
        elif _ss and isinstance(_ss, str) and _ss != "—":
            _snipe_disp = f'<div style="min-width:80px;font-size:10px;text-align:center;border-left:1px solid #30363d;padding-left:8px"><div class="stock-score-label">Snipe</div><strong style="color:#58a6ff">—</strong></div>'
        _price_disp = f'{s.get("current_price",0):.2f}元' if isinstance(s.get("current_price"),(int,float)) and s.get("current_price") else ""

        name = s.get("name", "?")
        code = s.get("code", "?")
        board = s.get("board", s.get("sector", "?"))
        element = s.get("element", "?")
        # 兼容timing嵌套对象或扁平化buy_months等字段
        timing = s.get("timing", {}) if isinstance(s, dict) else {}
        if not isinstance(timing, dict) or not (timing.get("buy_months") or timing.get("hold_months")):
            # 扁平化格式: 直接从stock读取
            timing = {
                "buy_months": s.get("buy_months", []) or [],
                "hold_months": s.get("hold_months", []) or [],
                "sell_months": s.get("sell_months", []) or [],
                "empty_months": s.get("empty_months", []) or []
            }

        # 生成带彩色圆点的12月标记
        buy_m = set(timing.get("buy_months", []) or [])
        hold_m = set(timing.get("hold_months", []) or [])
        sell_m = set(timing.get("sell_months", []) or [])
        empty_m = set(timing.get("empty_months", []) or [])
        month_dots = ""
        for mi, mcn in enumerate(ALL_MONTHS_CN):
            if mcn in buy_m:
                dot = "🟢"
            elif mcn in sell_m:
                dot = "🟠"
            elif mcn in empty_m:
                dot = "⚫"
            else:
                dot = "🔵"
            month_dots += f'<span style="display:inline-block;text-align:center;min-width:26px;font-size:10px;margin:0 1px"><span style="font-size:9px">{dot}</span><br>{mcn}</span>'

        sell_triggers = s.get("sell_triggers", [])
        if isinstance(sell_triggers, list) and len(sell_triggers) > 0:
            trigger_text = " | ".join([t.get("type","?") for t in sell_triggers[:3]])
        else:
            trigger_text = "暂无详细触发条件"

        stop_loss = s.get("stop_loss", "暂无")
        if isinstance(stop_loss, dict):
            stop_loss = f"{stop_loss.get('level_1',{}).get('condition','?')}→{stop_loss.get('level_1',{}).get('action','?')}({stop_loss.get('level_1',{}).get('price_drop','?')})"

        stock_cards += f"""  <div class="stock-card">
    <div class="rec-rank">{i+1}</div>
    <div style="flex:1">
      <div class="stock-name">{name}</div>
      <div class="stock-code">{code} · {board} · {element}</div>
      <div style="margin:6px 0;font-size:11px;line-height:1.6">{month_dots}</div>
      <div style="font-size:11px;color:#d29922">▼ {trigger_text}</div>
      <div style="font-size:11px;color:var(--text-muted)">止损：{stop_loss}</div>
    </div>
    <div class="stock-scores">
      <div style="min-width:120px">
        <div class="stock-score-label">综合</div>
        <strong style="color:var(--gold)">{score:.1f}</strong>
        <div class="score-bar"><div class="score-fill" style="width:{bar_width}%;background:{bar_color}"></div></div>
      </div>
      {_snipe_disp}
    </div>
  </div>
  <p style="font-size:12px;color:var(--text-muted);margin:0 0 5px 55px">{s.get("reason", s.get("match_reason", ""))}</p>"""

    # === 持仓策略 ===
    if len(top_stocks) >= 5:
        # 从个股中提取timing月份（兼容嵌套timing对象和扁平字段两种格式）
        def _get_timing_months(stock, key):
            """从个股中提取月份列表，兼容timing嵌套和扁平字段"""
            val = []
            if isinstance(stock, dict):
                # 优先从timing嵌套对象读取
                timing = stock.get("timing", {}) or {}
                if isinstance(timing, dict):
                    val = timing.get(key, [])
                # fallback: 扁平字段
                if not val:
                    val = stock.get(key, [])
                # 兜底: buy_months / sell_months / hold_months / empty_months
                if not val and key == "empty_months":
                    val = stock.get("empty_months", []) or stock.get("avoid_months", [])
            if isinstance(val, list):
                return val
            return []

        s0_buy = _get_timing_months(top_stocks[0], "buy_months")
        s0_sell = _get_timing_months(top_stocks[0], "sell_months")
        s0_empty = _get_timing_months(top_stocks[0], "empty_months")
        s0_hold = _get_timing_months(top_stocks[0], "hold_months")
        s2_buy = _get_timing_months(top_stocks[2], "buy_months")
        s2_sell = _get_timing_months(top_stocks[2], "sell_months")
        s2_empty = _get_timing_months(top_stocks[2], "empty_months")
        s2_hold = _get_timing_months(top_stocks[2], "hold_months")
        s4_buy = _get_timing_months(top_stocks[4], "buy_months")
        s4_sell = _get_timing_months(top_stocks[4], "sell_months")
        s4_empty = _get_timing_months(top_stocks[4], "empty_months")
        s4_hold = _get_timing_months(top_stocks[4], "hold_months")

        hold_cards = f"""
  <h3>持仓策略建议</h3>
  <div class="card-grid">
    <div class="card">
      <h4>核心持仓（50%）</h4>
      <p>{top_stocks[0].get('name','?')} + {top_stocks[1].get('name','?')}</p>
      <p style="font-size:13px;color:var(--text-muted)">土金双属性龙头，长线持有</p>
      <p style="font-size:12px;color:var(--green)">✓ 建仓：{','.join(s0_buy) if s0_buy else '结合流月日历择机'}</p>
      <p style="font-size:12px;color:#58a6ff">● 持有：{','.join(s0_hold) if s0_hold else '非卖出月均持有'}</p>
      <p style="font-size:12px;color:#d29922">▼ 减仓：{','.join(s0_sell) if s0_sell else '关注流月禁忌'}</p>
      <p style="font-size:12px;color:var(--text-muted)">⚫ 回避：{','.join(s0_empty) if s0_empty else '水逆及忌神月份'}</p>
    </div>
    <div class="card">
      <h4>卫星持仓（30%）</h4>
      <p>{top_stocks[2].get('name','?')} + {top_stocks[3].get('name','?')}</p>
      <p style="font-size:13px;color:var(--text-muted)">喜神金行到位，秋季发力</p>
      <p style="font-size:12px;color:var(--green)">✓ 建仓：{','.join(s2_buy) if s2_buy else '秋季金旺期入场'}</p>
      <p style="font-size:12px;color:#58a6ff">● 持有：{','.join(s2_hold) if s2_hold else '非卖出月均持有'}</p>
      <p style="font-size:12px;color:#d29922">▼ 减仓：{','.join(s2_sell) if s2_sell else '关注流月禁忌'}</p>
      <p style="font-size:12px;color:var(--text-muted)">⚫ 回避：{','.join(s2_empty) if s2_empty else '水逆及忌神月份'}</p>
    </div>
    <div class="card">
      <h4>机动仓位（20%）</h4>
      <p>{top_stocks[4].get('name','?')}（择机波段）</p>
      <p style="font-size:13px;color:var(--text-muted)">灵活操作，快进快出</p>
      <p style="font-size:12px;color:var(--green)">✓ 建仓：{','.join(s4_buy) if s4_buy else '喜用月份短线参与'}</p>
      <p style="font-size:12px;color:#58a6ff">● 持有：{','.join(s4_hold) if s4_hold else '不超过2个月'}</p>
      <p style="font-size:12px;color:#d29922">▼ 减仓：{','.join(s4_sell) if s4_sell else '达到目标即止盈'}</p>
      <p style="font-size:12px;color:var(--text-muted)">⚫ 回避：{','.join(s4_empty) if s4_empty else '忌神月份严格回避'}</p>
    </div>
  </div>"""
    else:
        hold_cards = ""

    # === 精度声明 ===
    precision = ""
    pw = astro.get("meta", {}).get("precision_warnings", [])
    if pw:
        precision = "<div class='correction'><strong>⚠ 精度声明：</strong><br>" + "<br>".join(pw) + "</div>"

    # === 组装完整HTML ===
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>风生水起 · {birth.get('year','?')}年{birth.get('gender','?')}命{target_year}年投资指南</title>
<style>
:root {{
  --primary: #c9a84c;
  --primary-dark: #8b6914;
  --bg: #0d1117;
  --bg-card: #161b22;
  --bg-section: #1c2333;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --border: #30363d;
  --green: #3fb950;
  --red: #f85149;
  --gold: #ffd700;
  --blue: #58a6ff;
  --purple: #bc8cff;
  --orange: #d29922;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: 'PingFang SC','Microsoft YaHei','Helvetica Neue',sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.8; padding: 20px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{
  text-align: center; padding: 40px 20px;
  border-bottom: 2px solid var(--primary); margin-bottom: 30px;
  background: linear-gradient(180deg, rgba(201,168,76,0.1) 0%, transparent 100%);
}}
.header h1 {{ font-size: 28px; color: var(--primary); letter-spacing: 4px; margin-bottom: 10px; }}
.header .subtitle {{ font-size: 14px; color: var(--text-muted); }}
.section {{
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 25px; margin-bottom: 20px;
}}
.section h2 {{
  font-size: 20px; color: var(--primary); margin-bottom: 15px;
  padding-bottom: 10px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 10px;
}}
.section h2 .icon {{ font-size: 24px; }}
.section h3 {{ font-size: 16px; color: var(--gold); margin: 15px 0 10px; }}
table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 14px; }}
th {{
  background: rgba(201,168,76,0.15); color: var(--primary);
  padding: 10px 12px; text-align: left; border-bottom: 2px solid var(--primary); font-weight: 600;
}}
td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); }}
tr:hover {{ background: rgba(201,168,76,0.05); }}
.score-bar {{ height: 8px; border-radius: 4px; background: var(--border); overflow: hidden; min-width: 100px; }}
.score-fill {{ height: 100%; border-radius: 4px; transition: width 0.5s; }}
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }}
.card {{ background: var(--bg-section); border: 1px solid var(--border); border-radius: 8px; padding: 15px; }}
.card h4 {{ color: var(--primary); margin-bottom: 8px; font-size: 15px; }}
.pillars {{ display: flex; justify-content: center; gap: 20px; margin: 20px 0; }}
.pillar {{
  text-align: center; padding: 15px 20px; background: var(--bg-section);
  border: 1px solid var(--border); border-radius: 8px; min-width: 80px;
}}
.pillar .label {{ font-size: 12px; color: var(--text-muted); margin-bottom: 5px; }}
.pillar .gan {{ font-size: 28px; color: var(--gold); font-weight: bold; }}
.pillar .zhi {{ font-size: 28px; color: var(--primary); font-weight: bold; }}
.pillar .element {{ font-size: 11px; color: var(--text-muted); margin-top: 3px; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin: 2px; }}
.tag-green {{ background: rgba(63,185,80,0.15); color: var(--green); }}
.tag-red {{ background: rgba(248,81,73,0.15); color: var(--red); }}
.tag-blue {{ background: rgba(88,166,255,0.15); color: var(--blue); }}
.tag-gold {{ background: rgba(201,168,76,0.15); color: var(--gold); }}
.tag-gray {{ background: rgba(139,148,158,0.15); color: var(--text-muted); }}
.stock-card {{
  background: var(--bg-section); border: 1px solid var(--border); border-radius: 8px;
  padding: 12px 15px; margin: 8px 0; display: flex; align-items: center; gap: 12px;
}}
.stock-code {{ font-size: 11px; color: var(--text-muted); font-family: monospace; }}
.stock-name {{ font-size: 16px; font-weight: 600; min-width: 80px; }}
.stock-scores {{ display: flex; gap: 15px; align-items: center; }}
.stock-score-label {{ font-size: 11px; color: var(--text-muted); }}
.rec-rank {{ font-size: 24px; font-weight: bold; color: var(--primary); min-width: 40px; text-align: center; }}
.timing-calendar {{
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px; margin: 8px 0; font-size: 12px;
}}
.timing-month {{ padding: 3px 6px; border-radius: 4px; text-align: center; font-weight: 500; }}
.timing-month.t-buy {{ background: rgba(63,185,80,0.15); color: var(--green); }}
.timing-month.t-hold {{ background: rgba(88,166,255,0.15); color: var(--blue); }}
.timing-month.t-sell {{ background: rgba(210,153,34,0.15); color: var(--orange); }}
.timing-month.t-empty {{ background: rgba(139,148,158,0.15); color: var(--text-muted); }}
.timing-legend {{
  background: var(--bg-section); border: 1px solid var(--border);
  border-radius: 8px; padding: 15px; margin: 12px 0;
}}
.timing-legend h4 {{ color: var(--gold); margin-bottom: 10px; }}
.timing-legend-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }}
.timing-legend-item {{ padding: 8px 12px; border-radius: 6px; font-size: 13px; }}
.timing-legend-item.timing-buy {{ border-left: 3px solid var(--green); background: rgba(63,185,80,0.08); }}
.timing-legend-item.timing-hold {{ border-left: 3px solid var(--blue); background: rgba(88,166,255,0.08); }}
.timing-legend-item.timing-sell {{ border-left: 3px solid var(--orange); background: rgba(210,153,34,0.08); }}
.timing-legend-item.timing-empty {{ border-left: 3px solid var(--text-muted); background: rgba(139,148,158,0.08); }}
.summary-box {{
  background: rgba(201,168,76,0.1); border: 1px solid rgba(201,168,76,0.3);
  border-radius: 8px; padding: 15px; margin: 15px 0; font-size: 14px;
}}
.summary-box strong {{ color: var(--primary); }}
.correction {{
  background: rgba(248,81,73,0.1); border: 1px solid rgba(248,81,73,0.3);
  border-radius: 8px; padding: 12px 15px; margin: 15px 0; font-size: 13px;
}}
.correction strong {{ color: var(--red); }}
.dayun-timeline {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 15px 0; }}
.dayun-item {{
  padding: 6px 12px; border-radius: 6px; font-size: 13px;
  border: 1px solid var(--border); background: var(--bg-section);
}}
.dayun-item.current {{ border-color: var(--primary); background: rgba(201,168,76,0.15); color: var(--primary); font-weight: 600; }}
.radar-section {{ display: flex; gap: 30px; align-items: flex-start; flex-wrap: wrap; }}
.radar-chart {{ flex-shrink: 0; }}
.radar-legend {{ flex: 1; min-width: 300px; }}
.legend-item {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; }}
.legend-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
.legend-label {{ font-size: 13px; color: var(--text-muted); }}
.footer {{
  text-align: center; padding: 20px; margin-top: 30px;
  border-top: 1px solid var(--border); color: var(--text-muted); font-size: 13px;
}}
@media print {{ body {{ background: white; color: #333; }} .section {{ border: 1px solid #ddd; }} }}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
  <h1>风生水起 · {target_year}年投资指南</h1>
  <div class="subtitle">
    {birth.get('gender','?')}命 · {birth.get('year','?')}年{birth.get('month','?')}月{birth.get('day','?')}日 · {fp.get('year','?')}年 {fp.get('month','?')}月 {fp.get('day','?')}日 {fp.get('hour','?')}时<br>
    <small>{birth.get('birth_place','未知')}出生{f" · 现居{birth.get('residence','')}" if birth.get('residence','') and birth.get('residence','') != '未知' else ''}</small>
  </div>
</div>

{precision}

<!-- Section 0: 融合五行共振雷达图 -->
<div class="section">
  <h2><span class="icon">🎯</span> 融合五行共振雷达</h2>
  <div class="radar-section">
    <div class="radar-chart">
      {radar_chart_svg(fusion_vector, bazi_vec, ziwei_vec, qimen_vec, astro_vec)}
    </div>
    <div class="radar-legend">
      <h3>术数来源拆解</h3>
      <table>
        <tr><th>术数/权重</th><th>木</th><th>火</th><th>土</th><th>金</th><th>水</th></tr>
        <tr><td>八字 40%</td>
          <td>{bazi_vec.get('木','?')}</td><td>{bazi_vec.get('火','?')}</td><td>{bazi_vec.get('土','?')}</td><td>{bazi_vec.get('金','?')}</td><td>{bazi_vec.get('水','?')}</td>
        </tr>
        <tr><td>紫微 30%</td>
          <td>{ziwei_vec.get('木','?')}</td><td>{ziwei_vec.get('火','?')}</td><td>{ziwei_vec.get('土','?')}</td><td>{ziwei_vec.get('金','?')}</td><td>{ziwei_vec.get('水','?')}</td>
        </tr>
        <tr><td>奇门 20%</td>
          <td>{qimen_vec.get('木','?')}</td><td>{qimen_vec.get('火','?')}</td><td>{qimen_vec.get('土','?')}</td><td>{qimen_vec.get('金','?')}</td><td>{qimen_vec.get('水','?')}</td>
        </tr>
        <tr><td>占星 10%</td>
          <td>{astro_vec.get('木','?')}</td><td>{astro_vec.get('火','?')}</td><td>{astro_vec.get('土','?')}</td><td>{astro_vec.get('金','?')}</td><td>{astro_vec.get('水','?')}</td>
        </tr>
        <tr style="font-weight:bold;color:var(--primary)"><td>加权融合</td>
          <td>{fusion_vector.get('木', 0)}</td><td>{fusion_vector.get('火', 0)}</td><td>{fusion_vector.get('土', 0)}</td><td>{fusion_vector.get('金', 0)}</td><td>{fusion_vector.get('水', 0)}</td>
        </tr>
      </table>
    </div>
  </div>
</div>

<!-- Section 1: 宏观大势分析 -->
<div class="section">
  <h2><span class="icon">🌌</span> {target_year}宏观大势分析</h2>

  <div class="card-grid">
    <div class="card">
      <h4>流年干支</h4>
      <p style="font-size:24px;color:var(--gold);font-weight:bold">{yearly_gz.get('gan_zhi','?')}</p>
      <p style="font-size:13px;color:var(--text-muted)">天干{yearly_gz.get('heavenly_stem','?')}属{yearly_gz.get('stem_element','?')} · 地支{yearly_gz.get('earthly_branch','?')}属{yearly_gz.get('branch_element','?')}</p>
    </div>
    <div class="card">
      <h4>九运周期</h4>
      <p style="font-size:20px;color:var(--primary);font-weight:bold">{nine_star.get('name','?')}</p>
      <p style="font-size:13px;color:var(--text-muted)">{nine_star.get('years','?')} · {nine_star.get('element','?')}运当令</p>
    </div>
  </div>

  <h3>大势五行分布</h3>
  <table>
    <tr><th>五行</th><th>得分</th><th>状态</th><th>趋势</th></tr>
    {_macro_rows}
  </table>

  <h3>年度政策主题</h3>
  <div class="summary-box">
    <strong>{_policy_theme}</strong><br>
    {_policy_directions}
  </div>

  <h3>行星流年影响</h3>
  <table>
    <tr><th>行星</th><th>落座</th><th>影响</th><th>投资建议</th></tr>
    {_planet_rows}
  </table>

  <div class="summary-box">
    <strong>📋 宏观大势小结</strong><br>
    • {target_year}年为{yearly_gz.get('gan_zhi','?')}年，{nine_star.get('name','?')}当令，整体五行{_dominant_element}气最旺<br>
    • 政策主线：{_policy_theme}<br>
    • 投资基调：{_investment_tone}
  </div>
</div>

<!-- Section 2: 八字命盘详情 -->
{bazi_detail_section(bazi, dayun_data)}

<!-- Section 2: 紫微斗数 -->
{ziwei_section(ziwei, target_year)}

<!-- Section 3: 奇门遁甲 -->
{qimen_section(qimen, target_year)}

<!-- Section 4: 西方占星 -->
{astrology_section(astrology, target_year)}

<!-- Section 5: 四季流月策略 -->
{seasonal_strategy_section(monthly_data, fusion_result, qimen, cosmic, xiyong=None, ji=None)}

<!-- Section 6: 推荐板块 -->
<div class="section">
  <h2><span class="icon">🏆</span> 年度推荐板块 + 禁忌板块</h2>
  <h3>▲ 推荐板块 Top10</h3>
  <table><tr><th>排名</th><th>板块</th><th>融合得分</th><th>置信度</th><th>推荐理由</th></tr>{rec_rows}</table>

  <h3>▼ 禁忌板块（规避）</h3>
  {f'<table><tr><th>排名</th><th>板块</th><th>风险</th><th>等级</th><th>风险提示</th></tr>{forbid_rows}</table>' if forbid_rows else '<p style="color:var(--text-muted)">暂无禁忌板块数据</p>'}
</div>

<!-- Section 7: 个股猎手 -->
<div class="section">
  <h2><span class="icon">🎯</span> 个股精选推荐（含最佳操作时机）</h2>
  <p><strong>选股范围：</strong>{", ".join([s.get("name","?") for s in recommended[:5]])}</p>

  <div class="timing-legend">
    <h4>📌 操作时效说明</h4>
    <div class="timing-legend-grid">
      <div class="timing-legend-item timing-buy">🟢 绿色 ✓ = 买入/加仓</div>
      <div class="timing-legend-item timing-hold">🔵 蓝色 ● = 持有观望</div>
      <div class="timing-legend-item timing-sell">🟠 橙色 ▼ = 减仓/卖出</div>
      <div class="timing-legend-item timing-empty">⚫ 灰色 ⊘ = 空仓等待</div>
    </div>
  </div>

  <h3>精选个股 Top10（含操作时效日历）</h3>
{stock_cards}
{hold_cards}
</div>

<!-- Section 8: 核心结论 -->
<div class="section">
  <h2><span class="icon">📌</span> 核心结论</h2>
  <div class="summary-box">
    <strong>一句话总结：</strong><br>
    命主{birth.get('gender','?')}，生于{birth.get('year','?')}年，日主<strong style="color:var(--gold)">{_day_gan}{_day_gan_element}</strong>（{_day_gan_strength}），喜用神为<strong style="color:var(--green)">{_xiyong_primary}</strong>与<strong style="color:var(--green)">{_xiyong_secondary}</strong>，当前大运<strong style="color:var(--gold)">{_current_dayun}</strong>{_current_dayun_age}。<br>
    {target_year}年投资主线锁定<strong style="color:var(--gold)">{_xiyong_primary}{_xiyong_secondary}板块</strong>（{recommended[0].get('name','?') if recommended else '?'}、{recommended[1].get('name','?') if len(recommended)>1 else '?'}为核心标的），<br>
    <strong style="color:var(--green)">最佳窗口</strong>为{_xiyong_secondary}旺季节（如秋季9-11月），<strong style="color:var(--red)">最差时段</strong>为火水交战月（如夏季6-7月），应严守纪律、知行合一。
  </div>
  {f'<h3>关键数字</h3><table><tr><th>指标</th><th>数值</th></tr><tr><td>最佳板块</td><td>{recommended[0].get("name","?")}（得分 {recommended[0].get("score",0):.1f}）</td></tr><tr><td>个股首选</td><td>{top_stocks[0].get("name","?")}（{top_stocks[0].get("code","?")}）综合{_fmt_final_score(top_stocks[0])}分</td></tr><tr><td>SnipeScore</td><td>{_fmt_snipe_score(top_stocks[0])}</td></tr></table>' if recommended and top_stocks else ''}
</div>

<!-- Section 9: 风险提示 -->
<div class="section">
  <h2><span class="icon">⚠️</span> 风险提示</h2>
  <p>⚠ 本报告基于多术数融合体系推演，仅供参考，不构成投资建议。投资有风险，入市需谨慎。</p>
  <p>⚠ 个股评分使用模拟数据，实际操作需接入实时行情数据。</p>
  <p style="text-align:center;color:var(--primary);margin-top:20px;font-weight:bold">[结束]</p>
</div>

<div class="footer">
  <p>风生水起（FSSQ）v3.3 · 4-Agent协作架构 · {datetime.now().strftime('%Y-%m-%d')}生成</p>
  <p>astro-calc + cosmic-trend + fusion-engine + star-hunter</p>
</div>

</div>
</body>
</html>"""
    return html
