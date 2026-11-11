"""配置读取与校验。

优先级从高到低：
1. 环境变量（云端通过 ``env:`` / Secrets 注入）
2. ``config/config.json``（本地私有配置，已 gitignore）
3. ``config/config.example.json``（仓库里的模板）
4. 代码内置默认值

这样设计的原因：同一个程序既能在本地跑，也能在 GitHub Runner 上跑，
区别只在于"配置从哪来"，业务代码一个字都不用改。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TASK_NAME = "daily-cloud-task"
DEFAULT_MESSAGE = "GitHub Actions 云端任务执行成功"
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_WEBHOOK_ENV = "DINGTALK_WEBHOOK"


class ConfigError(ValueError):
    """配置缺失、格式错误或取值非法。"""


@dataclass(frozen=True)
class Config:
    """一次任务运行所需的全部配置。"""

    task_name: str = DEFAULT_TASK_NAME
    message: str = DEFAULT_MESSAGE
    timezone: str = DEFAULT_TIMEZONE
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    notify_enabled: bool = False
    notify_webhook_env: str = DEFAULT_WEBHOOK_ENV


def project_root() -> Path:
    """仓库根目录（app/ 的上一级）。"""
    return Path(__file__).resolve().parent.parent


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:  # 文件不存在 / 无权限
        raise ConfigError(f"无法读取配置文件 {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件不是合法 JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"配置文件顶层必须是 JSON 对象: {path}")
    return data


def _pick_config_file(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    root = project_root()
    for candidate in (root / "config" / "config.json", root / "config" / "config.example.json"):
        if candidate.is_file():
            return candidate
    return None


def _as_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off", ""}:
            return False
    raise ConfigError(f"{field_name} 必须是布尔值，收到: {value!r}")


def _validate(config: Config) -> Config:
    if not config.task_name.strip():
        raise ConfigError("task_name 不能为空")
    if not str(config.timezone).strip():
        raise ConfigError("timezone 不能为空，例如 Asia/Shanghai")
    try:
        ZoneInfo(config.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        hint = "（Windows 本地缺少时区库时执行：pip install tzdata）"
        raise ConfigError(f"无法识别的 IANA 时区: {config.timezone}{hint}") from exc
    if not str(config.output_dir).strip():
        raise ConfigError("output_dir 不能为空")
    return config


def load_config(
    config_path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    """合并文件配置与环境变量，返回校验后的 :class:`Config`。"""
    env = os.environ if env is None else env

    data: dict[str, Any] = {}
    picked = _pick_config_file(config_path)
    if picked is not None:
        data = _read_json(picked)

    notify_section = data.get("notify") or {}
    if not isinstance(notify_section, dict):
        raise ConfigError("notify 配置必须是 JSON 对象")

    config = Config(
        task_name=str(data.get("task_name", DEFAULT_TASK_NAME)),
        message=str(data.get("message", DEFAULT_MESSAGE)),
        timezone=str(data.get("timezone", DEFAULT_TIMEZONE)),
        output_dir=Path(str(data.get("output_dir", DEFAULT_OUTPUT_DIR))),
        notify_enabled=_as_bool(notify_section.get("enabled", False), field_name="notify.enabled"),
        notify_webhook_env=str(notify_section.get("webhook_env", DEFAULT_WEBHOOK_ENV)),
    )

    # 环境变量覆盖。注意：workflow_dispatch 未填写时会把空字符串传进来，
    # 空字符串一律视为"没设置"，否则会把文件里的默认值冲掉。
    overrides: dict[str, Any] = {}
    if env.get("TASK_NAME", "").strip():
        overrides["task_name"] = env["TASK_NAME"].strip()
    if env.get("TASK_MESSAGE", "").strip():
        overrides["message"] = env["TASK_MESSAGE"].strip()
    if env.get("TASK_TIMEZONE", "").strip():
        overrides["timezone"] = env["TASK_TIMEZONE"].strip()
    if env.get("TASK_OUTPUT_DIR", "").strip():
        overrides["output_dir"] = Path(env["TASK_OUTPUT_DIR"].strip())
    if "TASK_NOTIFY_ENABLED" in env:
        overrides["notify_enabled"] = _as_bool(
            env["TASK_NOTIFY_ENABLED"], field_name="TASK_NOTIFY_ENABLED"
        )
    if env.get("TASK_WEBHOOK_ENV", "").strip():
        overrides["notify_webhook_env"] = env["TASK_WEBHOOK_ENV"].strip()

    if overrides:
        config = replace(config, **overrides)

    return _validate(config)
