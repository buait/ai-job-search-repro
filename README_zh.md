# AI Job Search 中文说明与优化记录

> 本文件为复现仓库的**中文补充说明**。原项目 README（英文）保持不变，本文件面向中文使用者，介绍项目用途与本复刻版本新增的优化。

## 项目是什么

AI Job Search 是一套跑在你电脑上的 AI 求职申请框架，基于 Claude Code 构建。你可以先填好自己的个人档案，然后让 AI 助手帮你：

- 抓取各大招聘门户的最新岗位（`/scrape`）
- 评估岗位与你的匹配度并排名（`/rank`）
- 针对每个岗位改写简历、撰写求职信（`/apply`）
- 准备面试、跟进申请结果（`/interview`、`/outcome`）
- 复盘整个求职过程（`/dashboard`，本复刻新增）

它的核心设计叫"薄指针（Thin-Pointer）"：所有方法论和档案只在一处维护，Claude Code、Codex、Cursor、Gemini CLI 等不同 AI 工具都能读取同一份规范，避免重复配置。

## 本复刻版本新增的优化

### 1. 新增求职战况仪表盘（Job Dashboard）

原项目把求职数据散落在多个位置，复盘时要人工翻文件。本次优化新增一套"战况仪表盘"能力，把三类数据聚合为一张**中文战报**：

- 申请记录（`documents/applications/*.md`）
- 岗位轨迹（`job_scraper/seen_jobs.json`）
- 薪资行情（`salary_data.json`）

**新增文件：**

| 文件 | 作用 |
| --- | --- |
| `tools/dashboard_state.py` | 核心聚合工具：扫描数据源、生成 Markdown/JSON 中文战报，内置 4 条复盘建议规则 |
| `tests/test_dashboard_state.py` | 14 个测试：状态归一化、文件解析、聚合统计、CLI 中文输出与 JSON 往返 |
| `.claude/commands/dashboard.md` | `/dashboard` 命令：编排工具、解读战报、给出下一步行动 |
| `.claude/skills/job-application-assistant/10-job-dashboard.md` | 仪表盘方法论：申请漏斗定义、数据源说明、复盘建议规则 |

**核心能力：**

- 中英文状态词自动归一化（`Applied` / `面试` / `Offer received` / `被拒` 等统一映射为规范中文状态）
- 三个数据源全部可选，缺失时显示 N/A 而不是报错
- 自动生成复盘建议（如"面试转化率偏低，建议优化简历关键词"）
- 输出固定为中文，Windows 旧控制台下也不会乱码
- 支持 `--json` 结构化输出，方便存档或二次加工

### 2. 使用示例

```bash
# 生成中文战报
python3 tools/dashboard_state.py

# 生成 JSON 战报（用于存档）
python3 tools/dashboard_state.py --json

# 指定工作区根目录
python3 tools/dashboard_state.py --root /path/to/workspace
```

在 Claude Code 中也可以直接输入 `/dashboard` 命令，由 AI 助手解读战报并给出行动建议。

## 测试

```bash
python3 -m unittest tests.test_dashboard_state -v
```

新增的 14 个测试全部通过；原项目测试未做任何修改，不受影响。