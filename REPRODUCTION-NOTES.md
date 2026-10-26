# REPRODUCTION-NOTES（复现说明）

本文档记录本次对 GitHub 热门项目的复现与优化过程。**注意：本文件不属于原项目内容，是复刻者新增的说明文档。**

## 一、原仓库信息

| 项目 | 内容 |
| --- | --- |
| 原仓库名称 | ai-job-search（AI Job Search） |
| 原仓库地址 | https://github.com/ai-job-search-dev/ai-job-search（原 MadsLorentzen/ai-job-search） |
| 原仓库简介 | 跑在你自己电脑上的 AI 求职申请框架，基于 Claude Code 构建：评估岗位、定制简历、写求职信、准备面试 |
| 原仓库语言 | Python / TypeScript / Shell |
| 原仓库 License | MIT License（本仓库完整保留） |
| 复现日期 | 2026-10-26 |

## 二、复现方式说明

1. **抓榜**：通过 GitHub Trending 官方榜及多个榜单站点（OssRadar、StartupCorners、AIDaily 等）交叉获取当日热门项目。由于直连 github.com 网络超时，改用 GitHub CLI（gh api）获取仓库元数据与 tarball。
2. **选项目**：从榜单中挑选与"AI Agent 实际运用"强相关的项目，要求体量适中（仓库 < 30MB）、结构清晰。最终选定 **ai-job-search**：当日新增 star 约 3,890（GitHub 官方 Trending 榜首），压缩包约 1.5MB，结构清晰（命令 / 技能 / 工具 / 测试分层明确）。
3. **获取源码**：通过 `gh api repos/<owner>/<repo>/tarball` 下载官方 tarball 并解压（等价于完整快照，且天然不含 .git 历史）。
4. **断血缘**：将源码复制到独立目录（跳过 .git），重新 `git init`，与上游仓库彻底脱离提交历史关联。
5. **优化**：新增"求职战况仪表盘"能力（详见第三节），并补充中文说明文档。
6. **提交推送**：以独立身份 commit，创建公开仓库并推送。

## 三、优化内容

本次复现选择"为 AI 求职工作区新增战况复盘能力"作为优化方向，原因：原项目功能丰富但数据分散，求职者复盘时需要人工翻找多个目录，缺乏"一眼看懂"的总览视图。优化后，一张中文战报即可覆盖申请漏斗、渠道分布、岗位轨迹、薪资行情与复盘建议。

**新增文件清单：**

| 文件 | 说明 |
| --- | --- |
| `tools/dashboard_state.py` | 核心聚合工具（约 400 行），扫描申请记录 / 岗位轨迹 / 薪资行情，输出中文 Markdown 或 JSON 战报；内置 4 条复盘建议规则；中英文状态词自动归一化；Windows 下 UTF-8 输出兼容 |
| `tests/test_dashboard_state.py` | 14 个单元测试，覆盖状态归一化、文件解析、聚合统计、CLI JSON 往返与中文输出 |
| `.claude/commands/dashboard.md` | 新增 `/dashboard` 命令，编排工具运行与战报解读 |
| `.claude/skills/job-application-assistant/10-job-dashboard.md` | 新增"求职战况仪表盘"技能方法论文档（中文） |
| `README_zh.md` | 中文补充说明（面向中文使用者） |
| `REPRODUCTION-NOTES.md` | 本文档 |

**优化特点：**

- 所有新增模块独立、可测试，不修改原项目任何现有文件逻辑（CHANGELOG 追加记录除外）。
- 三个数据源全部可选，缺数据时显示 N/A，绝不报错或编造。
- 战报语言固定中文，贴近中文求职者使用习惯。

## 四、维护记录表

| 日期 | 操作 | 说明 |
| --- | --- | --- |
| 2026-10-26 | 首次复现 | 复现 ai-job-search，新增求职战况仪表盘能力，14 个新增测试全部通过 |

## 五、验证情况

- 新增测试：`python3 -m unittest tests.test_dashboard_state` → 14 项全部通过
- 战报工具实测：`python3 tools/dashboard_state.py` → 正常输出中文战报（空工作区显示提示文案，不报错）