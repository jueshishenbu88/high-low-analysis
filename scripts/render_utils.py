"""IR 渲染层：把 analyze() 产出的稳定 IR（不偏不倚的分析事实）渲染成各种输出形态。

本模块是 archify 式"类型化 IR + 确定性渲染"的落地——同一份 IR 可复用到多种下游：
  - render_record(ir)   → JSON 完整记录（与旧 analyze 输出结构对齐，仅少了 config_used）
  - render_summary(ir)  → 人类可读文本摘要
  - feed_cases(ir)      → 供 tests/cases.yaml 断言（由 run_tests.py 使用）

所有渲染函数都是纯函数：只读 IR，零副作用、零外部调用。
"""
from __future__ import annotations

from typing import Any, Dict


def render_record(ir: Dict[str, Any]) -> Dict[str, Any]:
    """IR → JSON 记录。供 CLI/默认输出，字段与原 analyze 输出一一对应（不含 config_used）。"""
    return dict(ir)


def render_summary(ir: Dict[str, Any]) -> str:
    """IR → 人类可读文本摘要。逐字段确定性拼接，不改动 IR。"""
    lines = []
    lines.append(
        f"区间 {ir['first_date']} → {ir['last_date']}（{ir['bar_count']} 根）"
        f"｜最新收盘 {ir['last_close']}"
    )
    dd = ir["max_drawdown"]
    lines.append(
        f"最大回撤 {dd['drawdown_pct']}% "
        f"｜ 峰值 {dd['from_peak']}({dd['from_peak_date']}) "
        f"→ 谷 {dd['trough_price']}({dd['trough_date']})"
    )
    di = ir["distance_to_two_year_low"]
    if di.get("distance_mode") == "point":
        lines.append(
            f"距区间最低 {di['two_year_low']}({di['two_year_low_date']}) "
            f"价差 {di['price_gap']}"
        )
    else:
        lines.append(
            f"距区间最低 {di['two_year_low']}({di['two_year_low_date']}) "
            f"溢价 {di['pct_above_low']}%"
        )
    for ma in ir["moving_averages"] or []:
        pos = "上方" if ma["above"] else "下方"
        lines.append(
            f"MA{ma['window']} = {ma['ma_value']}（现价乖离 {ma['pct_offset']}%，位于均线{pos}）"
        )
    fl = ir["flags"]
    if fl["high_drawdown"] is True:
        lines.append("⚠ 最大回撤超过告警阈值")
    if fl["at_two_year_low"] is True:
        lines.append("⚠ 现价已位于区间最低点附近（低于低位阈值）")
    return "\n".join(lines)


def feed_cases_snapshot(ir: Dict[str, Any]) -> Dict[str, Any]:
    """IR → 供 cases.yaml 断言器扁平读取的快捷视图。

    保留对旧字段名的兼容：旧用例用 `max_drawdown.drawdown_pct` 等点路径读取，
    run_tests.py 直接从 IR 取，不经过本函数，故此处仅作为契约说明兜底。
    返回浅引用（不改动、不复制深层），调用方只读。
    """
    return ir