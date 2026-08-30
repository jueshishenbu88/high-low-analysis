"""高低点分析的确定性计算核心。

本模块只做确定性的数学计算：极值点、回撤、距离两年内最低点的位置。
全部为纯函数（无 IO、无网络、无随机），输出可被 tests/cases.yaml 精确断言。
输入是 K 线数据（按日期升序），产出结构化的 JSON 结果。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, List, Optional


# --------------------------------------------------------------------------- #
# 类型与数据结构
# --------------------------------------------------------------------------- #

@dataclass
class Bar:
    """一根 K 线。date 格式 YYYY-MM-DD，价格数字。"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


# --------------------------------------------------------------------------- #
# 数据处理与配置（保持简单，全部确定性）
# --------------------------------------------------------------------------- #

DEFAULT_CONFIG = {
    "pivot_window": 5,       # 判定极值点时的左右窗口 K 线根数（pivot 高/低）
    "drawdown_peak_window": 120,  # 回撤回溯峰值的最大 K 线根数
    "min_pivot_gap": 3,      # 两个相邻极值点之间的最小 K 线间隔
    "two_year_days": 480,    # "两年"在日线下的近似交易日数
    # 判断阈值（告警/筛选）
    "drawdown_alert_pct": None,   # 最大回撤超过该百分比则 flags.high_drawdown=True
    "low_level_alert_pct": None,  # 现价距两年最低低于该百分比则 flags.at_two_year_low=True
    "ma_windows": [],        # 要计算的均线窗口，如 [5, 20, 60]；空则不输出
    # 数据口径
    "compare_window_days": None,  # 覆盖 two_year_days 的"纵向比较区间"；None=用 two_year_days
    "distance_mode": "pct",       # "pct"=距最低(%/现价比); "point"=距最低(绝对价差)
    "output_format": "json",      # "json"(默认) / "summary"(文本摘要)
}


def load_bars_jsons(rows: list[dict]) -> List[Bar]:
    """从 JSON 对象列表（字典型）构造 Bar，按 date 排序。"""
    bars = []
    for r in rows:
        bars.append(Bar(
            date=str(r["date"]),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]) if r.get("volume") is not None else None,
        ))
    bars.sort(key=lambda b: b.date)
    return bars


# --------------------------------------------------------------------------- #
# 确定性指标计算
# --------------------------------------------------------------------------- #

def is_pivot_high(bars: List[Bar], i: int, window: int) -> bool:
    """bars[i] 是否为局部高点：在 [i-window, i+window] 内最高，且严格两侧有 K 线。"""
    lo = max(0, i - window)
    hi = min(len(bars), i + window + 1)
    if i - lo < window or hi - i - 1 < window:
        return False  # 边界点不算极值，避免不稳定的端点
    v = bars[i].high
    for j in range(lo, hi):
        if j != i and bars[j].high >= v + 1e-9:
            return False
    return True


def is_pivot_low(bars: List[Bar], i: int, window: int) -> bool:
    lo = max(0, i - window)
    hi = min(len(bars), i + window + 1)
    if i - lo < window or hi - i - 1 < window:
        return False
    v = bars[i].low
    for j in range(lo, hi):
        if j != i and bars[j].low <= v - 1e-9:
            return False
    return True


def find_pivots(bars: List[Bar], window: int, min_gap: int) -> List[dict]:
    """顺序识别 pivot 高/低，并做最小间隔去重。返回最值点列表。"""
    highs, lows = [], []
    n = len(bars)
    for i in range(n):
        if is_pivot_high(bars, i, window):
            highs.append(i)
        if is_pivot_low(bars, i, window):
            lows.append(i)

    # 合并两侧并带方向，再按最小间隔过滤（保留极值时更强的那个）
    pivots = [("H", i) for i in highs] + [("L", i) for i in lows]
    pivots.sort(key=lambda x: x[1])
    kept: List[tuple] = []
    for kind, i in pivots:
        if kept and i - kept[-1][1] < min_gap:
            # 距上一个更近：比较极值强度，保留更极端者
            prev_kind, prev_i = kept[-1]
            if kind == "L" and prev_kind == "H":
                if bars[i].low <= bars[prev_i].high:  # 新低更强，替换
                    kept[-1] = (kind, i)
                continue
            if kind == "H" and prev_kind == "L":
                continue  # 高/低交替，保留
        else:
            kept.append((kind, i))

    result = []
    for kind, i in kept:
        b = bars[i]
        result.append({
            "date": b.date,
            "type": "high" if kind == "H" else "low",
            "price": b.high if kind == "H" else b.low,
        })
    return result


def max_drawdown(bars: List[Bar], peak_window: int) -> dict:
    """在 peak_window 内计算最大回撤：峰到谷的最大百分比跌幅。"""
    if not bars:
        return {"from_peak": None, "from_peak_date": None, "trough_price": None,
                "trough_date": None, "drawdown_pct": 0.0}
    peak = bars[0].high
    peak_date = bars[0].date
    max_dd = 0.0
    max_peak, max_peak_date = peak, peak_date
    trough_price = bars[0].low
    trough_date = bars[0].date
    for b in bars:
        if b.high > peak:
            # 创新高，回撤归零并重置当前峰值
            peak, peak_date = b.high, b.date
            continue
        dd = (peak - b.low) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            max_peak, max_peak_date = peak, peak_date
            trough_price, trough_date = b.low, b.date

    return {
        "from_peak": round(max_peak, 4),
        "from_peak_date": max_peak_date,
        "trough_price": round(trough_price, 4),
        "trough_date": trough_date,
        "drawdown_pct": round(max_dd * 100.0, 2),
    }


def distance_to_two_year_low(bars: List[Bar], days: int, mode: str = "pct",
                             fixed_window_days: Optional[int] = None) -> dict:
    """当前价 vs 最近 days 根（默认两年）K 线最低点的位置。

    mode: "pct" 返回现价相对最低点的百分比溢价；"point" 返回绝对价差。
    fixed_window_days: 显式指定"纵向比较区间"的 K 线根数，覆盖 days；None=用 days。
    """
    if not bars:
        return {"two_year_low": None, "low_date": None, "pct_above_low": 0.0,
                "price_gap": None, "current_price": None}
    window_days = fixed_window_days or days
    window = bars[-window_days:] if len(bars) >= window_days else bars
    low = min(b.low for b in window)
    low_date = min((b.date for b in window if b.low == low))
    cur = bars[-1].close
    pct = (cur - low) / low * 100.0 if low > 0 else 0.0
    price_gap = round(cur - low, 4)
    return {
        "two_year_low": round(low, 4),
        "two_year_low_date": low_date,
        "current_price": round(cur, 4),
        "pct_above_low": round(pct, 2),
        "price_gap": price_gap,
        "distance_mode": mode,
    }


def moving_average(bars: List[Bar], window: int) -> dict:
    """最近一个窗口的简单移动平均(收盘)，以及现价相对该均线的百分比偏差。"""
    if window <= 0 or len(bars) < window:
        return {"window": window, "ma_value": None, "pct_offset": None,
                "above": None}
    seg = bars[-window:]
    val = sum(b.close for b in seg) / window
    cur = bars[-1].close
    offset = (cur - val) / val * 100.0 if val > 0 else 0.0
    return {
        "window": window,
        "ma_value": round(val, 4),
        "pct_offset": round(offset, 2),
        "above": cur >= val,  # 现价站上该均线与否
    }


def build_flags(mdd: dict, dist: dict, cfg: dict) -> dict:
    """根据阈值配置生成告警/筛选标记（确定性）。阈值未配置时对应标记为 None。"""
    flags = {"high_drawdown": None, "at_two_year_low": None}
    dd_pct = mdd.get("drawdown_pct")
    if cfg.get("drawdown_alert_pct") is not None and dd_pct is not None:
        flags["high_drawdown"] = dd_pct > cfg["drawdown_alert_pct"]
    low_pct = dist.get("pct_above_low")
    if cfg.get("low_level_alert_pct") is not None and low_pct is not None:
        flags["at_two_year_low"] = low_pct <= cfg["low_level_alert_pct"]
    return flags


# --------------------------------------------------------------------------- #
# 对外主入口
# --------------------------------------------------------------------------- #


def analyze(rows: list[dict], config: Optional[dict] = None) -> dict:
    """主入口：给定 K 线（dict 列表）与可选配置，返回结构化分析 JSON。

    全部确定性，不含任何外部调用。config 缺省时用 DEFAULT_CONFIG。
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    bars = load_bars_jsons(rows)

    mdd = max_drawdown(bars, cfg["drawdown_peak_window"])
    dist = distance_to_two_year_low(
        bars, cfg["two_year_days"], cfg["distance_mode"],
        cfg.get("compare_window_days"))
    mds = [moving_average(bars, w) for w in cfg["ma_windows"] or []]
    flags = build_flags(mdd, dist, cfg)

    # 只产出稳定 IR（分析事实），不掺配置快照。展示形态由 render_utils 决定，
    # 调用方按需选择 render_record / render_summary，本函数不再吞渲染。
    return {
        "bar_count": len(bars),
        "first_date": bars[0].date if bars else None,
        "last_date": bars[-1].date if bars else None,
        "last_close": round(bars[-1].close, 4) if bars else None,
        "pivots": find_pivots(bars, cfg["pivot_window"], cfg["min_pivot_gap"]),
        "max_drawdown": mdd,
        "distance_to_two_year_low": dist,
        "moving_averages": mds,
        "flags": flags,
    }


# --------------------------------------------------------------------------- #
# CLI：从 JSON 文件读取并输出结果（供 tests/run_tests.py 复用调用）
# --------------------------------------------------------------------------- #

def analyze_jsonl(path: str, config: Optional[dict] = None) -> dict:
    """从 JSON/JSONL 文件加载 K 线并分析。file 可以是 .json(列表) 或 .yaml?——本函数只吃 JSON。"""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)  # 期望为 list[dict]
    return analyze(raw, config)


if __name__ == "__main__":
    import sys
    from render_utils import render_record, render_summary
    if len(sys.argv) < 2:
        print("用法: python analyze.py <kline.json> [config.json]")
        sys.exit(2)
    cfg = None
    if len(sys.argv) >= 3:
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            cfg = json.load(f)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        rows = json.load(f)
    ir = analyze(rows, cfg)
    _cfg = {**DEFAULT_CONFIG, **(cfg or {})}
    # 计算层不再吞渲染：由调用方按 output_format 选择渲染器
    if _cfg.get("output_format") == "summary":
        print(render_summary(ir))
    else:
        print(json.dumps(render_record(ir), ensure_ascii=False, indent=2))