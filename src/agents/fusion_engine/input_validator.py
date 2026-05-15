"""
fusion-engine: input_validator — 上游数据校验（守门员）
v3.0

负责校验astro-calc和cosmic-trend的输出，确保数据正确后再融合。
"""
import sys
import os
from datetime import datetime

_src_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _src_root)
from constants import *


class InputValidationError(Exception):
    """上游数据校验失败异常"""
    pass


def validate_inputs(astro_json, cosmic_json, target_year=None):
    """
    校验上游Agent输出

    Args:
        astro_json: astro-calc输出JSON
        cosmic_json: cosmic-trend输出JSON
        target_year: 目标年份（可选，默认从astro读取）

    Returns:
        dict: 校验结果 {"valid": bool, "errors": list, "warnings": list}

    Raises:
        InputValidationError: 校验失败时抛出
    """
    errors = []
    warnings = []

    # 1. astro-calc校验
    if not astro_json:
        errors.append("astro-calc输出为空")
    else:
        # meta校验
        meta = astro_json.get("meta", {})
        validation_status = meta.get("validation", "UNKNOWN")

        # 检查必要字段
        required_fields = ["bazi", "dayun"]
        for field in required_fields:
            if field not in astro_json:
                errors.append(f"astro-calc缺少必要字段: {field}")

        # 大运年份覆盖校验
        dayun = astro_json.get("dayun", {})
        current = dayun.get("current", {})
        if current:
            year_start = current.get("year_start")
            year_end = current.get("year_end")

            # 确定目标年份
            t_year = target_year or astro_json.get("bazi", {}).get("target_year") or datetime.now().year

            if year_start and year_end:
                if not (year_start <= t_year <= year_end):
                    errors.append(
                        f"大运年份不匹配: 目标{t_year}年，"
                        f"当前大运{current.get('gan_zhi')}范围{year_start}-{year_end}"
                    )

        # 八字日柱校验
        bazi = astro_json.get("bazi", {})
        four_pillars = bazi.get("four_pillars", {})
        day_pillar = four_pillars.get("day") or bazi.get("day_pillar")
        if day_pillar:
            # 检查日柱格式（两字）
            if len(day_pillar) != 2:
                errors.append(f"日柱格式错误: {day_pillar}（应为两字）")
            elif day_pillar[0] not in TIAN_GAN:
                errors.append(f"日柱天干错误: {day_pillar[0]}（不在天干表中）")
            elif day_pillar[1] not in DI_ZHI:
                errors.append(f"日柱地支错误: {day_pillar[1]}（不在地支表中）")

    # 2. cosmic-trend校验
    if not cosmic_json:
        warnings.append("cosmic-trend输出为空，将使用默认宏观数据")
    else:
        # 年份一致校验
        astro_year = target_year or astro_json.get("bazi", {}).get("target_year") or datetime.now().year
        cosmic_year = cosmic_json.get("meta", {}).get("target_year")

        if cosmic_year and astro_year and cosmic_year != astro_year:
            errors.append(
                f"宏观数据年份不匹配: cosmic={cosmic_year}, astro={astro_year}"
            )

        # 检查必要字段
        required_cosmic = ["yearly_ganzhi", "nine_star_cycle", "macro_five_element"]
        for field in required_cosmic:
            if field not in cosmic_json:
                warnings.append(f"cosmic-trend缺少字段: {field}（将使用默认值）")

    # 3. 综合判定
    result = {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "timestamp": datetime.now().isoformat()
    }

    if errors:
        error_msg = (
            "═══════════════════════════════════════════════\n"
            "  fusion-engine 校验失败报告\n"
            "═══════════════════════════════════════════════\n\n"
            f"发现 {len(errors)} 个错误，{len(warnings)} 个警告\n\n"
        )

        if astro_json:
            error_msg += "上游Agent: astro-calc\n"
            for e in errors[:3]:  # 只显示前3个
                error_msg += f"  ✗ {e}\n"
            error_msg += "\n"

        if cosmic_json:
            error_msg += "上游Agent: cosmic-trend\n"
            for w in warnings[:3]:
                error_msg += f"  ⚠ {w}\n"

        error_msg += (
            "\n处理结果：已中止融合，请修复上游数据后重新运行。\n"
            "═══════════════════════════════════════════════"
        )
        result["error_report"] = error_msg

    return result


def can_degrade(validation_result):
    """判断是否可降级运行"""
    # 只有警告没有错误时可以降级
    return validation_result["valid"] or (
        len(validation_result["errors"]) == 0 and
        len(validation_result["warnings"]) > 0
    )
