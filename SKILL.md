---
name: high-low-analysis
license: MIT
description: "对一段股票日线 K 线做确定性的高低点与风险分析：识别 pivot 极值高/低点、计算最大回撤、现价距两年内最低点的距离（价差或百分比）、当前价对 MA5/20/60 均线的乖离与站上/跌破，并按阈值输出回撤告警和低位筛选标记。触发场景（中英均可）：当用户要对一段 K 线做高低点分析、判断股票是否处于低位、看最大回撤、看现价离两年最低还有多远、或评估均线位置时调用；关键词 high-low analysis、pivot high/low、max drawdown、distance to two-year low、moving average deviation。计算全部由 scripts/analyze.py 完成（确定性纯函数，产稳定 IR 可被用例精确断言），Agent 只负责喂数据、编排脚本、解释与渲染输出。"
---

# 高低点分析（High-Low Analysis）

对一段**日线 K 线**做确定性分析：识别极值点（pivot 高/低）、计算最大回撤、
距"两年内最低点"的当前价位置、当前价相对均线的乖离与站上/跌破，并按阈值
给出回撤告警 / 低位筛选等标记。

**核心原则：计算下沉。** 所有数字由 `scripts/analyze.py` 算出，本 skill 只负责编排
脚本与解释结果，**绝不由 Agent 手算**，保证结果可复现、可被用例精确断言。

## When to Use（何时触发）

- 用户给一段 K 线，想知道其中**最高点 / 最低点（pivot）**在哪、何时。
- 用户想判断股票/标的当前的**最大回撤**、或现价**距两年内最低点还有多远**、是否处于历史低位。
- 用户想评估现价相对 **MA5 / MA20 / MA60** 的乖离程度、是否站上或跌破某条均线。
- 用户设置了回撤 / 低位阈值，想让脚本**自动打告警标记**。
- 触发词/意图：高低点、极值、最大回撤、两年低点、低位、均线乖离、drawdown、pivot、two-year low。

> **不触发**：只是要一张走势图（不分析）、要求预测未来价格/涨跌、或要求主观评级——本 skill 只做确定性的历史统计。

## How It Works（机制）

- **计算层** `scripts/analyze.py`：读入 K 线（JSON 数组），产出**稳定 IR**——一个
  不掺展示偏好的分析事实字典，结构契约见 `references/schema.json`。
- **渲染层** `scripts/render_utils.py`：纯函数，把同一份 IR 渲染成不同形态——
  `render_record()` 输出 JSON 记录、`render_summary()` 输出人类可读文本摘要。
- **配置** `config.yaml`：`pivot_window` / `min_pivot_gap` / `ma_windows` /
  `drawdown_alert_pct` / `low_level_alert_pct` / `compare_window_days` /
  `distance_mode(point|pct)` / `output_format(json|summary)`。
- **验证** `tests/run_tests.py`：配 `tests/cases.yaml` 自定义用例（喂 K 线 + 断言期望输出）。

## Steps（执行流程）

1. **确认数据**：拿到或拉取标的的日线 K 线（见下文"拉数据"）。推荐用 `scripts/fetch_kline.py`
   拉前复权（qfq）日线；也可直接喂本仓库 `tests/data/*.json` 的样例或用户提供的本地数据。
2. **跑计算**：
   ```bash
   python scripts/analyze.py <kline.json>
   # 或输出人类可读摘要：
   python scripts/analyze.py <kline.json> --format summary
   ```
   脚本会按 `config.yaml` 产出 pivot、最大回撤、距两年低点、均线乖离与 flags。
3. **解释结果**：把 IR 里的关键数字翻译成用户能懂的话——最近在哪个区间、
   最大回撤发生在何时、现价离两年最低还差多少（价差或百分比）、
   是否跌破某条均线、是否触发回撤告警 / 低位标记。
4. **按需渲染**：默认逐字段给结论；用户要结构化数据时用 JSON 记录，要口语说明用文本摘要。

## 拉取你自己的真实行情并分析

```bash
pip install pyyaml            # 仅首次
python scripts/fetch_kline.py 603082 tmp.json --adjust qfq   # 复权方式可换 hfq/none
python scripts/analyze.py tmp.json
```

## 运行验证（本机、无需联网）

```bash
pip install pyyaml
python tests/run_tests.py      # 退出码 0 = 通过
```

## 关键约束（务必遵守）

- **只读确定性**：数字一律来自 `scripts/analyze.py`，Agent 不做任何主观加权或手算；
  不输出预测、不给"买卖建议"，只陈述历史统计事实。
- **配置文件优先**：阈值与窗口取自 `config.yaml`；用户可调整 `drawdown_alert_pct` 等。
- **IR 与渲染分离**：不要改动 IR 字段去"适配展示"，需要新展示形态就调渲染层。
- **隐私**：用户真实行情数据只留在本机，不回推公开仓库；发布仓库只含 `tests/data/` 合成样例。