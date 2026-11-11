"""单元测试：只用标准库 unittest，``python -m unittest discover -s tests -v`` 即可运行。"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import Config, ConfigError, load_config
from app.notifier import format_message, send_notification
from app.task import build_report, render_markdown, run_task, write_reports

FIXED_NOW = datetime(2026, 11, 11, 9, 17, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


class ReportTests(unittest.TestCase):
    def test_build_report_has_expected_fields(self) -> None:
        config = Config(task_name="demo", message="hello", timezone="Asia/Shanghai")
        report = build_report(config, now=FIXED_NOW, env={"GITHUB_RUN_ID": "42"})

        self.assertEqual(report["task"], "demo")
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["message"], "hello")
        self.assertEqual(report["executed_at"], "2026-11-11T09:17:00+08:00")
        self.assertEqual(report["runtime"]["github_run_id"], "42")

    def test_report_time_is_timezone_aware(self) -> None:
        config = Config(timezone="Asia/Shanghai")
        report = build_report(config, now=FIXED_NOW)
        # 带 +08:00 才算"说清楚是几点"，裸时间戳在跨时区排查时会误导人。
        self.assertTrue(report["executed_at"].endswith("+08:00"))

    def test_markdown_contains_key_information(self) -> None:
        config = Config(task_name="demo")
        markdown = render_markdown(build_report(config, now=FIXED_NOW))
        self.assertIn("# 云端任务运行报告：demo", markdown)
        self.assertIn("2026-11-11T09:17:00+08:00", markdown)


class OutputTests(unittest.TestCase):
    def test_run_task_writes_all_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            config = Config(output_dir=output_dir, timezone="Asia/Shanghai")
            result = run_task(config, now=FIXED_NOW, env={})

            for key in ("json", "markdown", "history"):
                self.assertTrue(Path(result["files"][key]).is_file(), key)

            payload = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "success")

    def test_history_accumulates_one_line_per_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            config = Config(output_dir=output_dir)
            write_reports(build_report(config, now=FIXED_NOW), output_dir)
            write_reports(build_report(config, now=FIXED_NOW), output_dir)

            lines = (output_dir / "history.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)


class ConfigTests(unittest.TestCase):
    def test_env_overrides_file_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"task_name": "from-file"}), encoding="utf-8")

            config = load_config(config_path=path, env={"TASK_NAME": "from-env"})
            self.assertEqual(config.task_name, "from-env")

    def test_blank_env_var_does_not_override(self) -> None:
        # workflow_dispatch 没填输入时，GitHub 会传空字符串，不能把默认值冲掉。
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"message": "keep-me"}), encoding="utf-8")

            config = load_config(config_path=path, env={"TASK_MESSAGE": ""})
            self.assertEqual(config.message, "keep-me")

    def test_invalid_timezone_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"timezone": "Mars/Olympus"}), encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(config_path=path, env={})

    def test_invalid_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(config_path=path, env={})


class NotifierTests(unittest.TestCase):
    def test_disabled_notifier_is_skipped(self) -> None:
        result = send_notification(Config(notify_enabled=False), "hi", env={})
        self.assertEqual(result["status"], "skipped")

    def test_missing_webhook_is_skipped_not_crashed(self) -> None:
        config = Config(notify_enabled=True, notify_webhook_env="NOPE_WEBHOOK")
        result = send_notification(config, "hi", env={})
        self.assertEqual(result["status"], "skipped")
        self.assertIn("NOPE_WEBHOOK", result["reason"])

    def test_format_message_contains_task_name(self) -> None:
        config = Config(task_name="demo")
        text = format_message(config, build_report(config, now=FIXED_NOW))
        self.assertIn("demo", text)
        self.assertIn("2026-11-11T09:17:00+08:00", text)


if __name__ == "__main__":
    unittest.main()
