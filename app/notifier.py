"""结果通知：把任务结果推送到群机器人 Webhook。

设计原则：
1. **Webhook 地址永远不落代码、不落日志**，只从环境变量 / GitHub Secrets 读取；
2. 通知失败绝不能影响任务本身的退出码（业务优先，通知其次）；
3. 只用标准库 urllib，避免为了一个 POST 引入第三方依赖。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping

from .config import Config

DEFAULT_TIMEOUT_SECONDS = 10.0


def _mask(text: str, secret: str) -> str:
    """把敏感串从日志文本里抹掉，避免异常信息泄露 token。"""
    if not secret:
        return text
    return text.replace(secret, "***")


def send_notification(
    config: Config,
    text: str,
    env: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """发送通知，返回结构化结果；任何异常都被捕获成 status=failed。"""
    env = os.environ if env is None else env

    if not config.notify_enabled:
        return {"status": "skipped", "reason": "notify 未启用（notify.enabled=false）"}

    webhook = (env.get(config.notify_webhook_env) or "").strip()
    if not webhook:
        return {
            "status": "skipped",
            "reason": f"环境变量 {config.notify_webhook_env} 未设置",
        }

    # 钉钉/企业微信群机器人通用的文本消息体；其它平台按需替换 payload。
    payload = json.dumps(
        {"msgtype": "text", "text": {"content": text}}, ensure_ascii=False
    ).encode("utf-8")
    request = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(2048).decode("utf-8", errors="replace")
            return {"status": "sent", "http_status": response.status, "body": body[:200]}
    except urllib.error.HTTPError as exc:
        return {
            "status": "failed",
            "reason": f"HTTPError {exc.code}: {_mask(str(exc.reason), webhook)}",
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "status": "failed",
            "reason": f"{type(exc).__name__}: {_mask(str(exc), webhook)}",
        }


def format_message(config: Config, report: Mapping[str, Any]) -> str:
    """拼一条适合群聊阅读的纯文本通知。"""
    return (
        f"【{config.task_name}】{report.get('status')}\n"
        f"执行时间：{report.get('executed_at')}\n"
        f"消息：{report.get('message')}"
    )
