from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Mapping, Optional

from .models import EmailSettings, ReminderSettings


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_time(value: Optional[str], default: time) -> time:
    if not value:
        return default
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except Exception:
        return default


def _parse_int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _load_env_file(root: Path) -> None:
    env_path = root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


@dataclass
class AppConfig:
    root_dir: Path
    data_dir: Path
    assets_dir: Path
    db_path: Path
    gif_urls: list[str] = field(default_factory=list)
    openai_api_key: Optional[str] = None
    nutrition_api_key: Optional[str] = None
    email: EmailSettings = field(default_factory=EmailSettings)
    reminder: ReminderSettings = field(default_factory=ReminderSettings)
    target_calories: int = 1500
    deficit_goal: int = 500
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])

    def apply_overrides(self, overrides: Mapping[str, str]) -> None:
        if "target_calories" in overrides:
            self.target_calories = _parse_int(overrides["target_calories"], self.target_calories)
        if "deficit_goal" in overrides:
            self.deficit_goal = _parse_int(overrides["deficit_goal"], self.deficit_goal)
        if "reminder_time" in overrides:
            self.reminder.reminder_time = _parse_time(overrides["reminder_time"], self.reminder.reminder_time)
        if "reminder_enabled" in overrides:
            self.reminder.enabled = _parse_bool(overrides["reminder_enabled"], self.reminder.enabled)
        # Email overrides are stored with prefix email_
        email_fields = [
            "smtp_host",
            "smtp_port",
            "username",
            "password",
            "sender",
            "recipient",
            "use_tls",
        ]
        for field_name in email_fields:
            meta_key = f"email_{field_name}"
            if meta_key in overrides:
                current = getattr(self.email, field_name)
                if field_name == "smtp_port":
                    setattr(self.email, field_name, _parse_int(overrides[meta_key], current or 587))
                elif field_name == "use_tls":
                    setattr(self.email, field_name, _parse_bool(overrides[meta_key], True))
                else:
                    setattr(self.email, field_name, overrides[meta_key])
        if "openai_api_key" in overrides:
            self.openai_api_key = overrides["openai_api_key"]
        if "nutrition_api_key" in overrides:
            self.nutrition_api_key = overrides["nutrition_api_key"]


def load_config() -> AppConfig:
    root = Path(__file__).resolve().parents[1]
    _load_env_file(root)

    data_dir = root / "data"
    assets_dir = root / "assets"
    data_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "weight_loss.sqlite3"

    gif_urls_env = os.environ.get("MASCOT_GIFS", "")
    gif_urls = [item.strip() for item in gif_urls_env.split(",") if item.strip()]
    origins_env = os.environ.get("API_ALLOWED_ORIGINS", "*").strip()
    if origins_env in {"", "*"}:
        allowed_origins = ["*"]
    else:
        allowed_origins = [item.strip() for item in origins_env.split(",") if item.strip()]

    email = EmailSettings(
        smtp_host=os.environ.get("EMAIL_SMTP_HOST"),
        smtp_port=_parse_int(os.environ.get("EMAIL_SMTP_PORT"), 587),
        username=os.environ.get("EMAIL_SMTP_USERNAME"),
        password=os.environ.get("EMAIL_SMTP_PASSWORD"),
        sender=os.environ.get("EMAIL_SENDER"),
        recipient=os.environ.get("EMAIL_RECIPIENT"),
        use_tls=_parse_bool(os.environ.get("EMAIL_SMTP_USE_TLS"), True),
    )

    reminder = ReminderSettings(
        enabled=_parse_bool(os.environ.get("REMINDER_ENABLED"), True),
        reminder_time=_parse_time(os.environ.get("REMINDER_TIME"), time(8, 0)),
    )

    cfg = AppConfig(
        root_dir=root,
        data_dir=data_dir,
        assets_dir=assets_dir,
        db_path=db_path,
        gif_urls=gif_urls,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        nutrition_api_key=os.environ.get("NUTRITION_API_KEY"),
        email=email,
        reminder=reminder,
        target_calories=_parse_int(os.environ.get("TARGET_CALORIES"), 1500),
        deficit_goal=_parse_int(os.environ.get("DAILY_DEFICIT_GOAL"), 500),
        allowed_origins=allowed_origins,
    )
    return cfg
