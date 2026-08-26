#!/usr/bin/env python3
"""Domus UI backend — a tiny, dependency-free HTTP bridge to the core brain.

This is the shared backend prototype for the future Domus frontends (macOS
desktop app, Android/iOS app). It intentionally uses only the Python standard
library so it runs anywhere the core package does. Every frontend talks to the
same JSON API:

    GET  /api/todos              -> { "todos": [...] }
    POST /api/message            -> { "reply": str, "todos": [...] }
    POST /api/todos/toggle       -> { "todos": [...] }

The static web client in ``ui/web`` is one such frontend; a native SwiftUI or
React Native app would call these same endpoints.

Run it (from the repo root):

    PYTHONPATH=src python ui/server.py            # http://127.0.0.1:8765
    PYTHONPATH=src python ui/server.py --port 9000

Point it at a specific database with DATABASE_PATH; set OPENROUTER_API_KEY for
smarter parsing. Neither is required — basic list/reminder commands work with
the built-in rules engine.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Make the core package importable when run directly (PYTHONPATH=src also works).
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from domus.core import (  # noqa: E402  (import after sys.path tweak)
    build_settings,
    handle_user_message,
    init_storage,
    list_open_todos,
    set_todo_done,
)
from domus.shopping import (  # noqa: E402
    effective_quantity,
    shopping_item_name,
)

WEB_DIR = Path(__file__).resolve().parent / "web"
DEFAULT_DB = REPO_ROOT / "data" / "domus_ui.db"

# A single shared "household" for this local prototype.
CHAT_ID = 1
USER_ID = 1

# The "Domus" wake word is a Telegram group-chat affordance. In a dedicated app
# you just talk, so we strip an optional leading "Domus" before routing.
_WAKE_PREFIX = re.compile(r"^\s*domus\b[\s,:;.\-]*", re.IGNORECASE)


def strip_wake_word(text: str) -> str:
    stripped = _WAKE_PREFIX.sub("", text).strip()
    return stripped or text.strip()

SETTINGS = build_settings(database_path=Path(os.getenv("DOMUS_UI_DB", str(DEFAULT_DB))))


def _todo_payload() -> list[dict]:
    todos = list_open_todos(SETTINGS.database_path)
    payload: list[dict] = []
    for todo in todos:
        is_shopping = todo.category == "shopping"
        payload.append(
            {
                "id": todo.id,
                "name": shopping_item_name(todo) if is_shopping else todo.text,
                "quantity": effective_quantity(todo) if is_shopping else None,
                "category": todo.category,
                "due_date": todo.due_date,
                "created_by": todo.created_by,
                "done": todo.done,
            }
        )
    return payload


class DomusHandler(BaseHTTPRequestHandler):
    server_version = "DomusUI/0.1"

    def log_message(self, fmt: str, *args) -> None:  # keep output tidy
        sys.stderr.write("[ui] " + (fmt % args) + "\n")

    # ---- helpers -------------------------------------------------------
    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _serve_static(self, rel: str) -> None:
        rel = rel.lstrip("/") or "index.html"
        target = (WEB_DIR / rel).resolve()
        if not str(target).startswith(str(WEB_DIR)) or not target.is_file():
            self.send_error(404, "Not found")
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---- routes --------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path.startswith("/api/todos"):
            self._send_json({"todos": _todo_payload()})
            return
        if self.path == "/" or not self.path.startswith("/api"):
            self._serve_static(self.path)
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/message":
            body = self._read_json()
            text = strip_wake_word((body.get("text") or "").strip())
            display_name = (body.get("user") or "You").strip() or "You"
            if not text:
                self._send_json({"error": "empty message"}, status=400)
                return
            reply = asyncio.run(
                handle_user_message(
                    text,
                    SETTINGS,
                    chat_id=CHAT_ID,
                    user_id=USER_ID,
                    display_name=display_name,
                )
            )
            self._send_json({"reply": reply, "todos": _todo_payload()})
            return

        if self.path == "/api/todos/toggle":
            body = self._read_json()
            try:
                todo_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            done = bool(body.get("done", True))
            set_todo_done(SETTINGS.database_path, todo_id, done=done)
            self._send_json({"todos": _todo_payload()})
            return

        self.send_error(404, "Not found")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Domus UI backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    init_storage(SETTINGS.database_path)
    server = ThreadingHTTPServer((args.host, args.port), DomusHandler)
    print(f"Domus UI running at http://{args.host}:{args.port}  (db: {SETTINGS.database_path})")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
