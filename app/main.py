"""程序入口：本地 ``python app/main.py`` 与云端 ``python -m app.main`` 行为一致。

退出码约定（GitHub Actions 靠它判断绿/红）：
- 0 = 成功
- 1 = 任务失败（异常、配置非法等）
"""

from __future__ import annotations

import json
import logging
import sys
import traceback

from .config import ConfigError, load_config
from .notifier import format_message, send_notification
from .task import run_task

LOGGER = logging.getLogger("cloud-auto-task")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
        stream=sys.stdout,
        force=True,
    )


def main() -> int:
    configure_logging()
    LOGGER.info("===== 云端任务开始 =====")

    try:
        config = load_config()
    except ConfigError as exc:
        LOGGER.error("配置错误：%s", exc)
        return 1

    LOGGER.info(
        "任务=%s 时区=%s 输出目录=%s",
        config.task_name,
        config.timezone,
        config.output_dir,
    )

    try:
        result = run_task(config)
    except Exception:  # noqa: BLE001 - 顶层兜底，必须打印完整堆栈再返回非 0
        LOGGER.error("任务执行失败：\n%s", traceback.format_exc())
        notice = send_notification(
            config, f"【{config.task_name}】任务失败，请查看 Actions 日志。"
        )
        LOGGER.info("失败通知结果：%s", notice)
        return 1

    report = result["report"]
    LOGGER.info("报告内容：\n%s", json.dumps(report, ensure_ascii=False, indent=2))
    LOGGER.info("已生成文件：%s", json.dumps(result["files"], ensure_ascii=False))

    notice = send_notification(config, format_message(config, report))
    LOGGER.info("通知结果：%s", json.dumps(notice, ensure_ascii=False))

    LOGGER.info("===== 云端任务成功结束 =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
