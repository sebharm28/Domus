from __future__ import annotations

from datetime import datetime
from pathlib import Path

from domus.config import PROJECT_ROOT

DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"


def _sanitize(text: str) -> str:
    return " ".join(text.split())


class ConversationLog:
    """Append-only conversation log, one file per bot session."""

    def __init__(self, log_dir: Path = DEFAULT_LOG_DIR) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.started_at = datetime.now()
        filename = self.started_at.strftime("session_%Y-%m-%d_%H-%M-%S.log")
        self.path = self.log_dir / filename
        self._file = self.path.open("a", encoding="utf-8")
        self._write(f"# Session started {self.started_at:%Y-%m-%d %H:%M:%S}")

    def log_exchange(self, user_name: str, user_message: str, bot_reply: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = (
            f"{timestamp}, {_sanitize(user_message)} ({user_name}) - "
            f"{_sanitize(bot_reply)} (Domus)"
        )
        self._write(line)

    def close(self) -> None:
        if self._file.closed:
            return
        ended_at = datetime.now()
        self._write(f"# Session ended {ended_at:%Y-%m-%d %H:%M:%S}")
        self._file.close()

    def _write(self, line: str) -> None:
        self._file.write(line + "\n")
        self._file.flush()
