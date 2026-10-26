"""Tests for tools/dashboard_state.py - job dashboard aggregation."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import dashboard_state  # noqa: E402


class StateNormalizationTests(unittest.TestCase):
    def test_english_status_maps_to_chinese(self):
        self.assertEqual(dashboard_state.normalize_status("Applied"), "已投递")
        self.assertEqual(dashboard_state.normalize_status("Interview"), "面试中")
        self.assertEqual(dashboard_state.normalize_status("Offer received"), "已获Offer")
        self.assertEqual(dashboard_state.normalize_status("rejected"), "已拒绝")

    def test_chinese_status_passes_through(self):
        self.assertEqual(dashboard_state.normalize_status("面试中"), "面试中")
        self.assertEqual(dashboard_state.normalize_status("已获Offer"), "已获Offer")

    def test_empty_status_defaults_to_in_progress(self):
        self.assertEqual(dashboard_state.normalize_status(""), "进行中")
        self.assertEqual(dashboard_state.normalize_status(None), "进行中")

    def test_unknown_status_defaults_to_in_progress(self):
        self.assertEqual(dashboard_state.normalize_status("something-weird"), "进行中")


class ApplicationParsingTests(unittest.TestCase):
    def _make_root(self):
        return Path(tempfile.mkdtemp(prefix="dash-test-"))

    def _write_app(self, root, name, body):
        app_dir = root / "documents" / "applications"
        app_dir.mkdir(parents=True, exist_ok=True)
        path = app_dir / f"{name}.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_parses_frontmatter(self):
        root = self._make_root()
        self._write_app(root, "acme", "---\ncompany: Acme Inc\nstatus: Interview\ndate: 2026-10-20\n---\n# Acme\n")
        records = dashboard_state.scan_applications(root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["company"], "Acme Inc")
        self.assertEqual(records[0]["status"], "面试中")
        self.assertEqual(records[0]["date"], "2026-10-20")

    def test_parses_inline_lines(self):
        root = self._make_root()
        self._write_app(root, "globex", "# Globex\n\nStatus: Rejected\n\nDate: 2026-10-21\n")
        records = dashboard_state.scan_applications(root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["company"], "globex")
        self.assertEqual(records[0]["status"], "已拒绝")

    def test_missing_app_dir_returns_empty(self):
        root = self._make_root()
        self.assertEqual(dashboard_state.scan_applications(root), [])


class AggregationTests(unittest.TestCase):
    def _make_root(self):
        return Path(tempfile.mkdtemp(prefix="dash-test-"))

    def _write_app(self, root, name, status, date):
        app_dir = root / "documents" / "applications"
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / f"{name}.md").write_text(
            f"---\ncompany: {name}\nstatus: {status}\ndate: {date}\n---\n",
            encoding="utf-8",
        )

    def test_status_counts_and_sources(self):
        root = self._make_root()
        self._write_app(root, "acme", "Applied", "2026-10-20")
        self._write_app(root, "globex", "Interview", "2026-10-21")
        self._write_app(root, "initech", "rejected", "2026-10-22")
        records = dashboard_state.scan_applications(root)
        report = dashboard_state.aggregate(records, None, None)
        counts = report["applications"]["status_counts"]
        self.assertEqual(counts["已投递"], 1)
        self.assertEqual(counts["面试中"], 1)
        self.assertEqual(counts["已拒绝"], 1)
        self.assertEqual(report["funnel"]["interview"], 1)
        self.assertEqual(report["applications"]["total"], 3)

    def test_latest_sorted_by_date(self):
        root = self._make_root()
        self._write_app(root, "old", "Applied", "2026-10-01")
        self._write_app(root, "new", "Interview", "2026-10-25")
        records = dashboard_state.scan_applications(root)
        report = dashboard_state.aggregate(records, None, None)
        latest = report["applications"]["latest"]
        self.assertEqual(latest[0]["company"], "new")
        self.assertEqual(len(latest), 2)

    def test_seen_jobs_count(self):
        root = self._make_root()
        seen_dir = root / "job_scraper"
        seen_dir.mkdir(parents=True, exist_ok=True)
        (seen_dir / "seen_jobs.json").write_text(
            json.dumps({"jobs": [{"portal": "freehire"}, {"portal": "freehire"}, {"portal": "linkedin"}]}),
            encoding="utf-8",
        )
        seen = dashboard_state.scan_seen_jobs(root)
        self.assertEqual(seen["total"], 3)
        self.assertEqual(seen["portals"]["freehire"], 2)

    def test_aggregate_generates_tips_for_empty(self):
        root = self._make_root()
        report = dashboard_state.aggregate([], None, None)
        self.assertGreaterEqual(len(report["tips"]), 1)

    def test_markdown_rendering_contains_sections(self):
        root = self._make_root()
        self._write_app(root, "acme", "Applied", "2026-10-20")
        records = dashboard_state.scan_applications(root)
        report = dashboard_state.aggregate(records, None, None)
        md = dashboard_state.render_markdown(report)
        self.assertIn("# 求职战况仪表盘", md)
        self.assertIn("累计申请", md)
        self.assertIn("acme", md)


class CliTests(unittest.TestCase):
    def test_cli_json_roundtrip(self):
        with tempfile.TemporaryDirectory(prefix="dash-cli-") as tmp:
            root = Path(tmp)
            app_dir = root / "documents" / "applications"
            app_dir.mkdir(parents=True)
            (app_dir / "acme.md").write_text(
                "---\ncompany: Acme\nstatus: Interview\ndate: 2026-10-20\n---\n", encoding="utf-8"
            )
            proc = subprocess.run(
                [sys.executable, str(TOOLS_DIR / "dashboard_state.py"), "--json", "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["applications"]["total"], 1)

    def test_cli_markdown_utf8(self):
        with tempfile.TemporaryDirectory(prefix="dash-cli-") as tmp:
            root = Path(tmp)
            app_dir = root / "documents" / "applications"
            app_dir.mkdir(parents=True)
            (app_dir / "acme.md").write_text(
                "---\ncompany: Acme\nstatus: Interview\ndate: 2026-10-20\n---\n", encoding="utf-8"
            )
            proc = subprocess.run(
                [sys.executable, str(TOOLS_DIR / "dashboard_state.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("# 求职战况仪表盘", proc.stdout)


if __name__ == "__main__":
    unittest.main()
