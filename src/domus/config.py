import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "domus.db"
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.2-3b-instruct"
DEFAULT_BRIEFING_HOUR = 8


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openrouter_api_key: str | None
    openrouter_model: str
    database_path: Path
    briefing_hour: int


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

    return Settings(
        telegram_bot_token=token,
        openrouter_api_key=api_key,
        openrouter_model=model,
        database_path=db_path,
        briefing_hour=briefing_hour,
    )
