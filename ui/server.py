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
    add_item,
    add_recipe,
    build_settings,
    delete_item,
    get_profile,
    handle_user_message,
    init_storage,
    list_completion_stats,
    list_open_todos,
    list_profiles,
    list_recipe_tags,
    list_recipes,
    plan_recipe,
    set_todo_done,
    settings_payload,
    update_recipe,
    delete_recipe,
)
from domus import db
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
                "assigned_to": db.get_user_display_name(
                    SETTINGS.database_path,
                    todo.assigned_to_user_id,
                ),
                "apartment": todo.apartment,
                "done": todo.done,
            }
        )
    return payload


def _profiles_payload() -> list[dict]:
    return [
        {
            "id": profile.telegram_user_id,
            "display_name": profile.display_name,
            "username": profile.username,
            "apartment": profile.apartment,
            "diet": profile.diet,
            "allergies": profile.allergies,
            "likes": profile.likes,
            "dislikes": profile.dislikes,
        }
        for profile in list_profiles(SETTINGS.database_path)
    ]


def _stats_payload() -> list[dict]:
    return [
        {
            "display_name": stat.display_name,
            "count": stat.count,
            "samples": stat.samples,
        }
        for stat in list_completion_stats(SETTINGS.database_path, days=7)
    ]


def _recipe_payload() -> list[dict]:
    return [
        {
            "id": food.id,
            "name": food.name,
            "meal_type": food.meal_type,
            "ingredients": food.ingredients,
            "ingredient_details": food.ingredient_details,
            "tags": food.tags,
            "author": food.author,
            "prep_time_min": food.prep_time_min,
            "notes": food.notes,
        }
        for food in list_recipes(SETTINGS.database_path)
    ]


def _recipes_response() -> dict:
    return {
        "recipes": _recipe_payload(),
        "tags": list_recipe_tags(SETTINGS.database_path),
    }


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
        if self.path.startswith("/api/recipes"):
            self._send_json(_recipes_response())
            return
        if self.path.startswith("/api/profiles"):
            self._send_json({"profiles": _profiles_payload()})
            return
        if self.path.startswith("/api/settings"):
            self._send_json(settings_payload(SETTINGS))
            return
        if self.path.startswith("/api/stats"):
            self._send_json({"stats": _stats_payload()})
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
            user_id = int(body.get("user_id") or USER_ID)
            if not text:
                self._send_json({"error": "empty message"}, status=400)
                return
            reply = asyncio.run(
                handle_user_message(
                    text,
                    SETTINGS,
                    chat_id=CHAT_ID,
                    user_id=user_id,
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
            user_id = int(body.get("user_id") or USER_ID)
            set_todo_done(
                SETTINGS.database_path,
                todo_id,
                done=done,
                completed_by_user_id=user_id if done else None,
            )
            self._send_json({"todos": _todo_payload()})
            return

        if self.path == "/api/todos/add":
            body = self._read_json()
            name = (body.get("name") or "").strip()
            if not name:
                self._send_json({"error": "empty name"}, status=400)
                return
            category = (body.get("category") or "shopping").strip() or "shopping"
            due_date = (body.get("due_date") or None) or None
            add_item(
                SETTINGS.database_path,
                name,
                category=category,
                created_by="You",
                due_date=due_date,
            )
            self._send_json({"todos": _todo_payload()})
            return

        if self.path == "/api/todos/remove":
            body = self._read_json()
            try:
                todo_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            delete_item(SETTINGS.database_path, todo_id)
            self._send_json({"todos": _todo_payload()})
            return

        if self.path == "/api/recipes/plan":
            body = self._read_json()
            name = (body.get("name") or "").strip()
            if not name:
                self._send_json({"error": "empty name"}, status=400)
                return
            reply = plan_recipe(SETTINGS.database_path, name, created_by="You")
            self._send_json({"reply": reply, "todos": _todo_payload()})
            return

        if self.path == "/api/recipes/add":
            body = self._read_json()
            name = (body.get("name") or "").strip()
            if not name:
                self._send_json({"error": "Recipe name is required."}, status=400)
                return
            prep = body.get("prep_time_min")
            try:
                prep = int(prep) if prep not in (None, "") else None
            except (TypeError, ValueError):
                prep = None
            try:
                add_recipe(
                    SETTINGS.database_path,
                    name,
                    meal_type=(body.get("meal_type") or "dinner").strip() or "dinner",
                    ingredient_details=body.get("ingredients") or [],
                    tags=body.get("tags") or [],
                    notes=(body.get("notes") or None),
                    author=(body.get("author") or None),
                    prep_time_min=prep,
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(_recipes_response())
            return

        if self.path == "/api/recipes/update":
            body = self._read_json()
            try:
                food_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            prep = body.get("prep_time_min")
            try:
                prep_time_min = int(prep) if prep not in (None, "") else None
            except (TypeError, ValueError):
                prep_time_min = None
            try:
                update_recipe(
                    SETTINGS.database_path,
                    food_id,
                    name=body.get("name"),
                    meal_type=body.get("meal_type"),
                    ingredient_details=body.get("ingredients"),
                    prep_time_min=prep_time_min,
                    notes=body.get("notes"),
                    tags=body.get("tags"),
                    author=body.get("author"),
                    full_replace=bool(body.get("full_replace")),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(_recipes_response())
            return

        if self.path == "/api/recipes/delete":
            body = self._read_json()
            try:
                food_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            deleted = delete_recipe(SETTINGS.database_path, food_id)
            if deleted is None:
                self._send_json({"error": "recipe not found"}, status=404)
                return
            self._send_json({"deleted": deleted, **_recipes_response()})
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
