import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "domus.db"
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.2-3b-instruct"
DEFAULT_BRIEFING_HOUR = 8
DEFAULT_EVENING_BRIEFING_HOUR = 20
DEFAULT_QUIET_HOURS_START = 22
DEFAULT_QUIET_HOURS_END = 7


def _parse_bool(value: str, *, default: bool = False) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_pattern_list(raw: str) -> list[str]:
    if not raw.strip():
        return []
    if "|" in raw:
        return [part.strip() for part in raw.split("|") if part.strip()]
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openrouter_api_key: str | None
    openrouter_model: str
    database_path: Path
    briefing_hour: int
    evening_briefing_hour: int
    quiet_hours_enabled: bool
    quiet_hours_start: int
    quiet_hours_end: int
    redaction_enabled: bool
    redaction_patterns: tuple[str, ...]


def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and add your BotFather token."
        )

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip() or None
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip()
    db_path = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH)))
    briefing_hour = int(os.getenv("BRIEFING_HOUR", str(DEFAULT_BRIEFING_HOUR)))
    evening_briefing_hour = int(
        os.getenv("EVENING_BRIEFING_HOUR", str(DEFAULT_EVENING_BRIEFING_HOUR))
    )
    quiet_hours_enabled = _parse_bool(
        os.getenv("QUIET_HOURS_ENABLED", "true"),
        default=True,
    )
    quiet_hours_start = int(os.getenv("QUIET_HOURS_START", str(DEFAULT_QUIET_HOURS_START)))
    quiet_hours_end = int(os.getenv("QUIET_HOURS_END", str(DEFAULT_QUIET_HOURS_END)))
    redaction_enabled = _parse_bool(
        os.getenv("REDACTION_ENABLED", "false"),
        default=False,
    )
    redaction_patterns = tuple(
        _parse_pattern_list(os.getenv("REDACTION_PATTERNS", ""))
    )

    return Settings(
        telegram_bot_token=token,
        openrouter_api_key=api_key,
        openrouter_model=model,
        database_path=db_path,
        briefing_hour=briefing_hour,
        evening_briefing_hour=evening_briefing_hour,
        quiet_hours_enabled=quiet_hours_enabled,
        quiet_hours_start=quiet_hours_start,
        quiet_hours_end=quiet_hours_end,
        redaction_enabled=redaction_enabled,
        redaction_patterns=redaction_patterns,
    )
