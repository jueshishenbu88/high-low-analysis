"""把东方财富 K 线返回转换为 analyze.py 需要的 JSON 格式。

东财 fields2=f51,f52,f53,f54,f55,f56,f57 → 每行：
    日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额
analyze.py 需要：date, open, high, low, close, volume
用法：python scripts/ea_kline_to_json.py <eastmoney_klines.json> <out.json>
"""
import json
import sys
from pathlib import Path


def convert(src: Path, dst: Path) -> int:
    raw = json.loads(src.read_text(encoding="utf-8"))
    kl = (raw.get("data") or {}).get("klines") or []
    rows = []
    for line in kl:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        date, open_p, close_p, high_p, low_p, volume = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        rows.append({
            "date": date,
            "open": float(open_p),
            "high": float(high_p),
            "low": float(low_p),
            "close": float(close_p),
            "volume": float(volume),
        })
    dst.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("用法: python scripts/ea_kline_to_json.py <in.json> <out.json>")
    n = convert(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"转换 {n} 条 -> {sys.argv[2]}")