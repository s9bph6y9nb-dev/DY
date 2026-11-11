"""业务逻辑：生成一份运行报告，并落盘为 JSON + Markdown。

这里刻意不依赖任何第三方库，也不访问网络——
"业务逻辑保持可本地复现"是能写出单元测试的前提。
"""

from __future__ import annotations

import json
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .config import Config
from zoneinfo import ZoneInfo


def now_in(timezone: str) -> datetime:
    """取指定 IANA 时区的当前时间（带时区偏移，isoformat 会带上 +08:00）。"""
    return datetime.now(ZoneInfo(timezone))


def build_report(
    config: Config,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """生成报告字典。``now`` / ``env`` 可注入，方便单元测试。"""
    env = os.environ if env is None else env
    moment = now if now is not None else now_in(config.timezone)
    return {
        "task": config.task_name,
        "status": "success",
        "executed_at": moment.isoformat(timespec="seconds"),
        "timezone": config.timezone,
        "message": config.message,
        "runtime": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "github_run_id": env.get("GITHUB_RUN_ID", ""),
            "github_workflow": env.get("GITHUB_WORKFLOW", ""),
            "github_sha": env.get("GITHUB_SHA", "")[:7],
            "github_run_number": env.get("GITHUB_RUN_NUMBER", ""),
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    """把报告渲染成人类可读的 Markdown。"""
    runtime = report.get("runtime") or {}
    lines = [
        f"# 云端任务运行报告：{report.get('task', 'unknown')}",
        "",
        "| 项目 | 值 |",
        "| --- | --- |",
        f"| 状态 | `{report.get('status', '')}` |",
        f"| 执行时间 | `{report.get('executed_at', '')}` |",
        f"| 时区 | `{report.get('timezone', '')}` |",
        f"| Python | `{runtime.get('python_version', '')}` |",
        f"| Run ID | `{runtime.get('github_run_id') or '本地运行'}` |",
        f"| Commit | `{runtime.get('github_sha') or '本地运行'}` |",
        "",
        "## 消息",
        "",
        str(report.get("message", "")),
        "",
        "> 本文件由 app/task.py 自动生成，请勿手工编辑。",
        "",
    ]
    return "\n".join(lines)


def write_reports(
    report: Mapping[str, Any], output_dir: Path
) -> dict[str, str]:
    """写出 result.json / report.md / history.jsonl，返回相对路径字典。

    注意：Runner 是一次性环境，这些文件会随 Job 结束而消失。
    必须靠 Artifact 上传或提交回仓库才能留存（见 README 第 4 节）。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "result.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    md_path = output_dir / "report.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")

    # 追加一行历史记录：演示"想跨天累积状态"时最朴素的做法。
    # 在云端它只在本 Job 内有效，真正的持久化见 README 第 4 节。
    history_path = output_dir / "history.jsonl"
    line = json.dumps(
        {
            "executed_at": report.get("executed_at"),
            "status": report.get("status"),
        },
        ensure_ascii=False,
    )
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "history": str(history_path),
    }


def run_task(
    config: Config,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """执行任务：构造报告 → 落盘 → 返回结果。"""
    report = build_report(config, now=now, env=env)
    files = write_reports(report, config.output_dir)
    return {"report": report, "files": files}
