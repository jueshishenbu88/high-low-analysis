"""高低点分析 skill 的配置化验证驱动。

读 tests/cases.yaml（用户可自定义：喂数据 + 断言期望输出），
对 tests/ 下的 K 线数据文件运行 analyze.analyze()，并逐项断言。

独立可跑，不依赖任何 Agent/运行时：
    python tests/run_tests.py            # 跑发布版 cases.yaml
    python tests/run_tests.py --cases tests/cases.real.yaml   # 跑本机真实数据用例
退出码 0=全部通过，1=有失败。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 允许直接 import scripts.analyze（无论从仓库根还是 tests 目录调用）
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from scripts.analyze import analyze  # noqa: E402


def _render(ir, cfg):
    """按口径选择渲染器：output_format=summary 走文本摘要，否则走 JSON 记录。"""
    if cfg.get("output_format") == "summary":
        from scripts.render_utils import render_summary
        return render_summary(ir)
    from scripts.render_utils import render_record
    return render_record(ir)


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get(result, dotted: str):
    """按 a.b.c 路径取值；支持列表索引(n)与dict键；path='__str__' 返回字符串形式。

    返回 (found, value)：found=False 表示路径中任一环节缺失（供 does_not_exist 断言）。
    """
    if dotted == "__str__":
        return True, (result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))
    node = result
    for part in dotted.split("."):
        if isinstance(node, list) and part.isdigit():
            node = node[int(part)]
            continue
        if isinstance(node, dict):
            if part not in node:
                return False, None
            node = node[part]
        else:
            return False, None
    return True, node


def run_case(case: dict, tests_dir: Path, base_config: dict):
    name = case.get("name", "(未命名)")
    data_file = case["data_file"]  # 相对 tests/ 的 K 线 JSON
    data_path = tests_dir / data_file
    if not data_path.exists():
        return name, "ERROR", f"数据文件不存在: {data_file}"
    rows = load_json(data_path)
    # 用例级配置覆盖：case['config'] 中的字段覆盖全局 config（对应"配置化验证"）
    cfg = {**base_config, **(case.get("config") or {})}
    result = _render(analyze(rows, cfg), cfg)

    failures = []
    for ass in case.get("asserts", []):
        path = ass["path"]
        op = ass["op"]
        expect = ass.get("expect")  # exists/does_not_exist 等无值断言可省 expect
        found, actual = _get(result, path)
        ok = False
        if op == "eq":
            ok = found and actual == expect
        elif op == "approx":
            ok = found and isinstance(actual, (int, float)) and abs(actual - expect) < 1e-9
        elif op == "gt":
            ok = found and actual is not None and actual > expect
        elif op == "lt":
            ok = found and actual is not None and actual < expect
        elif op == "exists":
            ok = found
        elif op == "does_not_exist":
            ok = not found
        elif op == "contains":
            ok = found and isinstance(actual, str) and expect in actual
        else:
            ok = False
            failures.append(f"  未支持的断言 op: {op}")
        if not ok:
            failures.append(
                f"  [{path}] 期望 {op} {expect}，实际 {actual}"
            )
    return name, "PASS" if not failures else "FAIL", "\n".join(failures)


def main():
    ap = argparse.ArgumentParser(description="高低点分析验证驱动")
    ap.add_argument("--cases", default=None, help="用例文件路径（默认 tests/cases.yaml）")
    ap.add_argument("--config", default=None, help="口径配置路径（默认仓库根 config.yaml）")
    args = ap.parse_args()

    tests_dir = _ROOT / "tests"
    cases_path = Path(args.cases) if args.cases else tests_dir / "cases.yaml"
    config_path = Path(args.config) if args.config else _ROOT / "config.yaml"

    # config.yaml 可选；主脚本 analyze.py 的默认值已含全部字段
    config = {}
    if config_path.exists():
        try:
            import yaml
        except ImportError:
            print("[warn] 未安装 pyyaml，config.yaml 被跳过（使用 analyze.py 默认值）")
        else:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    if not cases_path.exists():
        print("未找到 tests/cases.yaml")
        sys.exit(1)

    try:
        import yaml
    except ImportError:
        print("本仓库依赖 pyyaml 以解析 cases.yaml。请先: pip install pyyaml")
        sys.exit(2)
    cases = yaml.safe_load(cases_path.read_text(encoding="utf-8")) or []

    passed, failed, errors = 0, 0, 0
    data_base = cases_path.parent  # data_file 相对用例文件所在目录解析
    print(f"共 {len(cases)} 个用例\n" + "-" * 48)
    for case in cases:
        name, status, detail = run_case(case, data_base, config)
        if status == "PASS":
            passed += 1
            print(f"  [PASS] {name}")
        elif status == "FAIL":
            failed += 1
            print(f"  [FAIL] {name}\n{detail}")
        else:
            errors += 1
            print(f"  [ERROR] {name}\n{detail}")

    print("-" * 48)
    print(f"结果: {passed} 通过, {failed} 失败, {errors} 错误")
    return 0 if failed == 0 and errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())