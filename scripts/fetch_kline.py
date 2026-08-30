"""从东方财富拉取日线并立即转为 analyze.py 需要的 JSON。

复权方式(adjust)与区间(beg/end)由参数/配置决定——这是"复权方式配置化"的落点。
secid 规则：沪市(60/68/9开头)=1.代码，深市(00/30开头)=0.代码，北交所(8/4开头)=0.代码。
用法：
  python scripts/fetch_kline.py <code> <out.json> [--adjust qfq|hfq|none] [--days 480] [--beg 2024-08-01] [--end 2050-12-31]
  adjust: qfq=前复权(默认) / hfq=后复权 / none=不复权
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

FQ_MAP = {"qfq": "1", "hfq": "2", "none": "0"}  # 东财 fqt 参数


def secid_for(code: str) -> str:
    """根据代码前缀推断 secid（沪=1.*，深/北=0.*）。"""
    code = code.strip()
    if code.startswith(("60", "68", "9")):
        return f"1.{code}"
    return f"0.{code}"


def fetch_klines(secid: str, fqt: str, beg: str, end: str) -> list:
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
           + urllib.parse.urlencode({
               "secid": secid,
               "fields1": "f1,f2,f3",
               "fields2": "f51,f52,f53,f54,f55,f56,f57",
               "klt": "101", "fqt": fqt,
               "beg": beg, "end": end,
               "_": "1"}))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = json.loads(r.read().decode("utf-8"))
    return (raw.get("data") or {}).get("klines") or []


def to_rows(lines: list) -> list:
    rows = []
    for line in lines:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        rows.append({
            "date": parts[0],
            "open": float(parts[1]),
            "high": float(parts[3]),
            "low": float(parts[4]),
            "close": float(parts[2]),
            "volume": float(parts[5]),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("code", help="股票代码，如 603082 / 000001")
    ap.add_argument("out", help="输出 JSON 路径")
    ap.add_argument("--adjust", choices=["qfq", "hfq", "none"], default="qfq",
                    help="复权方式：前复权(默认)/后复权/不复权")
    ap.add_argument("--beg", default=None, help="起始日期 YYYY-MM-DD，默认按 days 往前推")
    ap.add_argument("--end", default="2050-12-31")
    ap.add_argument("--days", type=int, default=480, help="默认拉取近 N 个交易日")
    args = ap.parse_args()

    fqt = FQ_MAP[args.adjust]
    beg = args.beg or "--days-based--"
    if beg == "--days-based--":
        # 按交易日粗略前推：使用东财支持 beg 按自然日；这里用 ~2.5 年自然日覆盖
        import datetime
        beg = (datetime.date.today() - datetime.timedelta(days=int(args.days * 1.5))).isoformat()

    secid = secid_for(args.code)
    lines = fetch_klines(secid, fqt, beg, args.end)
    if not lines:
        print(f"未拉到数据（secid={secid}），请检查代码或复权参数", file=sys.stderr)
        return 1

    rows = to_rows(lines)
    Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {"code": args.code, "secid": secid, "adjust": args.adjust, "bars": len(rows)}
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())