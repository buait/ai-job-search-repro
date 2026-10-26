#!/usr/bin/env python3
"""求职战况仪表盘（Job Dashboard State）——把分散的申请记录聚合为一张中文战报。

ai-job-search 工作区把求职数据散落在多个位置：`documents/applications/` 下的
申请记录、`job_scraper/seen_jobs.json` 的岗位轨迹、`salary_data.json` 的薪资
行情。每次复盘都要人工翻文件，既慢又容易漏。本工具把这些数据源聚合为一份
统一的中文战报，方便求职者一眼看清申请漏斗、渠道分布与薪资行情。

三个数据源全部是"可选的"：缺任何一个都不会报错，只会在战报里显示 N/A。
这样即使用户只跑过 `/scrape` 或只维护过 salary 数据，也能拿到有意义的输出。

用法：
    python tools/dashboard_state.py                       # 输出 Markdown 战报
    python tools/dashboard_state.py --json                # 输出 JSON 战报
    python tools/dashboard_state.py --format markdown     # 等价于默认
    python tools/dashboard_state.py --root <WORKSPACE>    # 指定工作区根目录

退出码：0 成功；1 用法或数据错误。
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

# 应用状态词 -> 规范状态（支持中英文，大小写不敏感）
STATE_KEYWORDS = {
    # 英文状态词
    "applied": "已投递",
    "submitted": "已投递",
    "application sent": "已投递",
    "sent": "已投递",
    "in progress": "进行中",
    "in review": "进行中",
    "reviewing": "进行中",
    "screening": "进行中",
    "interview": "面试中",
    "interviewing": "面试中",
    "phone screen": "面试中",
    "screen": "面试中",
    "assessment": "面试中",
    "test": "面试中",
    "offer": "已获Offer",
    "offered": "已获Offer",
    "offer received": "已获Offer",
    "rejected": "已拒绝",
    "rejection": "已拒绝",
    "withdrawn": "已撤回",
    "withdrew": "已撤回",
    "ghosted": "无回音",
    "no response": "无回音",
    "closed": "已关闭",
    "accepted": "已接受",
    "hired": "已接受",
    # 中文状态词
    "已投递": "已投递",
    "进行中": "进行中",
    "面试": "面试中",
    "面试中": "面试中",
    "offer": "已获Offer",
    "拒绝": "已拒绝",
    "被拒": "已拒绝",
    "撤回": "已撤回",
    "无回音": "无回音",
    "关闭": "已关闭",
    "录用": "已接受",
}

# 战报中状态展示顺序（漏斗视角：越往下越深入）
STATE_ORDER = ["已投递", "进行中", "面试中", "已获Offer", "已接受", "已拒绝", "已撤回", "无回音", "已关闭"]


def configure_utf8(stream):
    """让 piped 输出在 Windows 旧控制台上也使用 UTF-8，避免中文乱码。"""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8")


def workspace_root(explicit):
    """确定工作区根目录：优先命令行参数，其次脚本位置的上两级。"""
    if explicit:
        return Path(explicit).resolve()
    return Path(__file__).resolve().parent.parent


def parse_application_file(path):
    """从单份申请记录 Markdown 中提取 (company, status, date, source)。

    解析策略保持宽松：优先读 YAML frontmatter（--- 开头段落），其次扫描正文中
    的 `Status:` / `状态` / `Date:` / `日期` 行，最后用文件名兜底。任何一步
    失败都不抛异常，只返回能拿到的字段。
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    lines = text.splitlines()
    fm = {}
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                break
            if ":" in stripped:
                key, _, value = stripped.partition(":")
                fm[key.strip().lower()] = value.strip()

    status = ""
    record_date = ""
    source = ""
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("status:") or lowered.startswith("状态:"):
            status = stripped.split(":", 1)[1].strip()
        elif lowered.startswith("date:") or lowered.startswith("日期:") or lowered.startswith("applied:"):
            record_date = stripped.split(":", 1)[1].strip()
        elif lowered.startswith("source:") or lowered.startswith("来源:") or lowered.startswith("portal:"):
            source = stripped.split(":", 1)[1].strip()

    status = fm.get("status", status)
    record_date = fm.get("date", fm.get("applied", record_date))
    source = fm.get("source", fm.get("portal", source))

    company = fm.get("company", path.stem)
    return {
        "company": company,
        "status": status,
        "date": record_date,
        "source": source,
        "file": str(path),
    }


def normalize_status(raw):
    """把中英文状态词归一化为规范中文状态，未知状态归入「进行中」。"""
    if not raw:
        return "进行中"
    key = raw.strip().lower()
    if key in STATE_KEYWORDS:
        return STATE_KEYWORDS[key]
    for token, canonical in STATE_KEYWORDS.items():
        if token and token.lower() in key:
            return canonical
    return "进行中"


def scan_applications(root):
    """扫描 documents/applications/ 下所有 .md 申请记录。"""
    app_dir = root / "documents" / "applications"
    if not app_dir.is_dir():
        return []
    records = []
    for path in sorted(app_dir.glob("*.md")):
        parsed = parse_application_file(path)
        if parsed:
            parsed["status"] = normalize_status(parsed["status"])
            records.append(parsed)
    return records


def scan_seen_jobs(root):
    """读取 job_scraper/seen_jobs.json 统计岗位轨迹（宽松解析）。"""
    seen_file = root / "job_scraper" / "seen_jobs.json"
    if not seen_file.is_file():
        return None
    try:
        data = json.loads(seen_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None

    jobs = data if isinstance(data, list) else data.get("jobs", [])
    if not isinstance(jobs, list):
        return None

    portals = {}
    statuses = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        portal = job.get("portal") or job.get("source") or job.get("site") or "未知渠道"
        portals[portal] = portals.get(portal, 0) + 1
        status = job.get("status") or job.get("verdict") or ""
        statuses[status] = statuses.get(status, 0) + 1
    return {"total": len(jobs), "portals": portals, "statuses": statuses}


def scan_salary(root):
    """读取 salary_data.json 统计薪资行情摘要（宽松解析）。"""
    salary_file = root / "salary_data.json"
    if not salary_file.is_file():
        return None
    try:
        data = json.loads(salary_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None

    companies = data if isinstance(data, list) else data.get("companies", data.get("data", []))
    if not isinstance(companies, list):
        return None
    return {"company_count": len(companies)}


def aggregate(records, seen_jobs, salary):
    """汇总各数据源，生成战报数据模型。"""
    status_counts = {s: 0 for s in STATE_ORDER}
    sources = {}
    latest = []
    for r in records:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        src = r["source"] or "未知渠道"
        sources[src] = sources.get(src, 0) + 1
        entry = {"company": r["company"], "status": r["status"], "date": r["date"]}
        if entry["date"]:
            latest.append(entry)
    latest.sort(key=lambda e: e["date"], reverse=True)

    total = len(records)
    interview = status_counts.get("面试中", 0)
    offer = status_counts.get("已获Offer", 0) + status_counts.get("已接受", 0)
    rejected = status_counts.get("已拒绝", 0)

    tips = []
    if total == 0:
        tips.append("还没有申请记录。先跑 /setup 填好个人档案，再用 /scrape 收集岗位、/apply 提交申请。")
    else:
        if interview == 0 and total >= 3:
            tips.append("申请了不少但还没进入面试，建议检查简历与目标岗位的匹配度，或调整投递渠道。")
        if interview > 0 and offer == 0:
            tips.append("已有面试但未拿到 Offer，建议用 /interview 做针对性面试准备，并复盘每场面试。")
        if rejected > total * 0.6:
            tips.append("拒绝率偏高，可以试试把申请集中在更匹配的岗位，并让 /apply 按岗位要求改写简历。")
        if total >= 10 and interview / total < 0.2:
            tips.append("面试转化率偏低（低于 20%），优先优化简历关键词与项目经历描述。")

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "applications": {
            "total": total,
            "status_counts": status_counts,
            "sources": sources,
            "latest": latest[:5],
        },
        "seen_jobs": seen_jobs,
        "salary": salary,
        "funnel": {"interview": interview, "offer": offer, "rejected": rejected},
        "tips": tips,
    }


def render_markdown(report):
    """把战报数据模型渲染为 Markdown 中文战报。"""
    apps = report["applications"]
    funnel = report["funnel"]
    lines = []
    lines.append("# 求职战况仪表盘")
    lines.append("")
    lines.append(f"> 生成时间：{report['generated_at']}（本地时间）")
    lines.append("")
    lines.append("## 一、申请漏斗")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("| --- | --- |")
    lines.append(f"| 累计申请 | {apps['total']} |")
    lines.append(f"| 面试中 | {funnel['interview']} |")
    lines.append(f"| 已获 Offer / 已接受 | {funnel['offer']} |")
    lines.append(f"| 已拒绝 | {funnel['rejected']} |")
    lines.append("")
    lines.append("### 状态分布")
    lines.append("")
    non_zero = {k: v for k, v in apps["status_counts"].items() if v}
    if non_zero:
        lines.append("| 状态 | 数量 |")
        lines.append("| --- | --- |")
        for state in STATE_ORDER:
            if state in non_zero:
                lines.append(f"| {state} | {non_zero[state]} |")
    else:
        lines.append("_暂无状态数据_")
    lines.append("")

    if apps["sources"]:
        lines.append("## 二、渠道分布")
        lines.append("")
        lines.append("| 渠道 | 申请数 |")
        lines.append("| --- | --- |")
        for src, count in sorted(apps["sources"].items(), key=lambda x: -x[1]):
            lines.append(f"| {src} | {count} |")
        lines.append("")

    if apps["latest"]:
        lines.append("## 三、最近动态")
        lines.append("")
        lines.append("| 日期 | 公司 | 状态 |")
        lines.append("| --- | --- | --- |")
        for e in apps["latest"]:
            lines.append(f"| {e['date']} | {e['company']} | {e['status']} |")
        lines.append("")

    seen = report["seen_jobs"]
    if seen:
        lines.append("## 四、岗位轨迹")
        lines.append("")
        lines.append(f"- 已见岗位总数：{seen['total']}")
        if seen["portals"]:
            portal_text = "、".join(f"{k} {v}" for k, v in sorted(seen["portals"].items(), key=lambda x: -x[1]))
            lines.append(f"- 渠道分布：{portal_text}")
        lines.append("")

    salary = report["salary"]
    if salary:
        lines.append("## 五、薪资行情")
        lines.append("")
        lines.append(f"- 薪资数据中的公司数：{salary.get('company_count', 'N/A')}")
        lines.append("")

    if report["tips"]:
        lines.append("## 六、复盘建议")
        lines.append("")
        for tip in report["tips"]:
            lines.append(f"- {tip}")
        lines.append("")

    lines.append("---")
    lines.append("_由 dashboard_state.py 自动生成，数据来自 documents/applications、job_scraper/seen_jobs.json 与 salary_data.json。_")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="求职战况仪表盘：聚合申请记录、岗位轨迹与薪资行情，输出中文战报。"
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式（等价于 --format json）")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="输出格式")
    parser.add_argument("--root", help="工作区根目录（默认取脚本上两级目录）")
    args = parser.parse_args(argv)

    configure_utf8(sys.stdout)
    root = workspace_root(args.root)
    records = scan_applications(root)
    seen_jobs = scan_seen_jobs(root)
    salary = scan_salary(root)
    report = aggregate(records, seen_jobs, salary)

    if args.json or args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
