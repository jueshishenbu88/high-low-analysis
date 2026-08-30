# 高低点分析 skill（自用）

对一段日线 K 线做确定性分析：识别极值点（pivot 高/低）、计算最大回撤、
距"两年内最低点"的当前价位置。**计算全部为确定性纯函数**，可被用例精确断言。

## 设计原则
- **计算下沉**：所有数字由 `scripts/analyze.py` 算出，Agent 只做编排与解释。
- **不绑运行时**：现阶段核心是脚本 + 自动测试，不依赖任何 Agent CLI，本机任意可跑。
- **验证配置化**：`tests/cases.yaml` 可自定义用例（喂自己的 K 线 + 断言期望输出）。
- **默认即能跑**：`config.yaml` / `tests/cases.yaml` 提供默认值，删掉也能用内置默认。

## 目录结构
```
high-low-analysis/
├── config.yaml          # 可配置项（默认值即能跑）
├── scripts/
│   └── analyze.py       # 确定性计算：pivot 高低点 / max_drawdown / 距两年低点
├── tests/
│   ├── cases.yaml       # ← 用户配置的测试用例（喂数据 + 断言）
│   ├── run_tests.py     # 验证驱动，独立可跑
│   └── data/            # 用例用 K 线数据（合成/脱敏）
└── README.md
```

## 安装与使用

本 skill 是"脚本 + 自动测试"形态，可按两种方式使用：

### 方式一：作为 Agent Skill 一键安装（需要 Node.js ≥ 18）
任何有 Node 环境的机器（无需本仓库克隆）即可安装：
```bash
npx skills add 你的用户名/high-low-analysis
```
安装后，在支持 Agent Skills 的运行时（如 Claude Code / Cursor）中，即可通过对话直接调用
"高低点分析"能力（Agent 会自动编排 `analyze.py`）。

> 结构提示：本仓库根目录即一个 skill（`SKILL.md` 约定由 `npx skills add <owner/repo>` 解析），
> 若后续拆分成多个 skill 的合集，再进行 `owner/repo` 级组织。

### 方式二：本地直接运行（无 Node / 无需联网）
```bash
git clone https://github.com/你的用户名/high-low-analysis.git
cd high-low-analysis
pip install pyyaml          # 仅首次
python scripts/analyze.py tests/data/sample_uptrend_drawdown.json
```

### 拉取你自己的真实行情并分析
```bash
# 拉前复权日线并分析（复权方式可换成 hfq/none，见后文"复权方式"）
python scripts/fetch_kline.py 603082 tmp.json --adjust qfq
python scripts/analyze.py tmp.json
```

## 运行验证（本机，无需联网）
```bash
# 1. 需要 pyyaml（解析 cases.yaml）
pip install pyyaml

# 2. 跑全部测试（退出码 0=通过）
python tests/run_tests.py
```

## 单次分析（直接看结果）
```bash
python scripts/analyze.py tests/data/sample_uptrend_drawdown.json
```

## 新增口径能力（2026-08-30）
经真实数据（茅台/平安/北自/中安/协和/华阳/彩讯）验证后扩展：

| 维度 | 配置键 | 说明 |
|------|--------|------|
| **均线** | `ma_windows: [5,20,60]` | 现价相对各均线乖离 + 站上/跌破，空列表则省 |
| **回撤告警** | `drawdown_alert_pct: 45` | 最大回撤超该百分比 → `flags.high_drawdown=true`，不配则为 `None` |
| **低位筛选** | `low_level_alert_pct: 30` | 现价距区间最低 ≤ 该百分比 → `flags.at_two_year_low=true` |
| **纵向区间** | `compare_window_days` | 覆盖 `two_year_days` 的比较窗口（固定区间） |
| **价差/百分比** | `distance_mode: point\|pct` | `point` 用绝对价差，`pct` 用百分比溢价（默认） |
| **输出格式** | `output_format: json\|summary` | `summary` 输出人类可读文本摘要 |
| **复权方式** | `scripts/fetch_kline.py --adjust` | 拉数阶段 `qfq`/`hfq`/`none`；需重拉数据才生效 |

用例级可覆盖：`tests/cases.yaml` 中给某个用例加 `config:` 字段，动态切换不同口径验证
（验证本身也"配置化"）。测试驱动已支持列表索引断言与 `contains` 子串检查。

```bash
# 拉复权数据并分析（前复权默认）
python scripts/fetch_kline.py 603082 tmp.json --adjust qfq
python scripts/analyze.py tmp.json
```

## 如何"配置化"地扩展验证
1. 拷一个 `tests/data/*.json` 改你想要的 K 线（或用你的真实数据，注意隐私，建议只留本地）。
2. 在 `tests/cases.yaml` 追加一个用例，写 `path` + `op` + `expect` 断言。
3. 重跑 `python tests/run_tests.py`。
例如想让两年窗口用真实工作日，改 `config.yaml` 的 `two_year_days`。

## 规划（B 阶段，未实现，占位）
`config.yaml` 已预留 `datasource` 配置块。未来可加实时行情数据源
（如 tushare / akshare / eastmoney），让 `scripts/analyze.py` 支持按 `symbol`
直接拉数，替代离线喂数据。接口位置在设计上已留好，当前不做。

## 发布后的验证流程（README 已推到 GitHub 后用）

日常改了代码/用例后，先从根目录做一遍"发布版回归"，再确认仓库干净，最后才推。

```bash
# 1. 发布版回归（只依赖合成样例数据，clone 后开箱即跑）
python tests/run_tests.py

# 2. 本机完整回归（含真实数据，数据存本地、不入库）
python tests/run_tests.py --cases tests/cases.real.yaml

# 3. 确认无真实数据被误跟踪（应无 real/ 与 cases.real.yaml 输出）
git status --short
git ls-files | grep -E "tests/data/real|cases.real|__pycache__" || echo "OK: 干净"

# 4. 确认发布版用例仍是 5 个、全通过
python tests/run_tests.py && git add -A && git commit -m "docs: 补充发布后验证流程"

# 5. 推送到远端
git push
```

**发布后自测"别人能否一键安装"（在没有本仓库的临时目录）：**
```bash
mkdir -p /tmp/skills_verify && cd /tmp/skills_verify
npx skills add 你的用户名/high-low-analysis
# 若能拉取成功，说明发布生效；再用一个真实代码片段触发一次，确认分析可用
```

> 提醒：真实行情数据（`tests/data/real/`、`tests/cases.real.yaml`）始终只留在本机，
> 由 `.gitignore` 排除。发布仓库里只有合成样例数据，保证任何 clone 者开箱即过测试。