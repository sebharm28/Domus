#!/usr/bin/env python3
"""Domus UI backend — a tiny, dependency-free HTTP bridge to the core brain.

This is the shared backend prototype for the future Domus frontends (macOS
desktop app, Android/iOS app). It intentionally uses only the Python standard
library so it runs anywhere the core package does. Every frontend talks to the
same JSON API:

    GET  /api/todos              -> { "todos": [...] }
    GET  /api/reminders          -> { "recurring", "pending_timers", "recent_timers" }
    GET  /api/briefing           -> { "date_label", "due_today", "shopping", ... }
    GET  /api/chat/history       -> { "history": [...] }
    POST /api/message            -> { "reply", "todos", "reminders" }
    POST /api/todos/quantity       -> { "shopping", "tasks", "todos" }
    POST /api/todos/toggle         -> { "shopping", "tasks", "todos" }

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
from urllib.parse import parse_qs, urlparse

# Make the core package importable when run directly (PYTHONPATH=src also works).
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from domus.core import (  # noqa: E402  (import after sys.path tweak)
    add_item,
    add_recipe,
    build_settings,
    chat_history_payload,
    daily_briefing_payload,
    delete_item,
    delete_recipe,
    get_profile,
    handle_user_message,
    init_storage,
    list_completion_stats,
    list_open_todos,
    list_profiles,
    list_recipe_tags,
    list_recipes,
    plan_recipe,
    reminders_payload,
    set_todo_done,
    settings_payload,
    update_recipe,
)
from domus.bath_hub import (
    add_medicine,
    cleaning_payload,
    delete_medicine,
    log_towel_use,
    log_towel_washed,
    medicine_payload,
    toggle_cleaning_item,
    towels_payload,
)
from domus.household_notes import (
    create_kitchen_note,
    delete_kitchen_note,
    kitchen_notes_payload,
    update_kitchen_note,
)
from domus.meal_plan_views import (
    meal_plan_payload,
    plan_calendar_week,
    set_meal_plan_day,
    suggest_meal_plan_day,
)
from domus import db, food_db
from domus.cleaning_plan import (
    add_chore,
    assign_chore,
    cleaning_plan_payload,
    mark_chore_done,
)
from domus.households import (
    accept_apartment_member,
    apartment_for_user,
    apartment_payload,
    chat_id_for_apartment,
    chat_id_for_user,
    create_apartment_with_owner,
    get_or_create_apartment_chat,
    init_households,
    kick_apartment_member,
    leave_apartment,
    membership_status,
    pending_count_for_owner,
    regenerate_join_code,
    request_join_apartment,
)
from domus.shopping import (  # noqa: E402
    effective_quantity,
    shopping_item_name,
)

WEB_DIR = Path(__file__).resolve().parent / "web"
DEFAULT_DB = REPO_ROOT / "data" / "domus_ui.db"

USER_ID = 1

# The "Domus" wake word is a Telegram group-chat affordance. In a dedicated app
# you just talk, so we strip an optional leading "Domus" before routing.
_WAKE_PREFIX = re.compile(r"^\s*domus\b[\s,:;.\-]*", re.IGNORECASE)


def strip_wake_word(text: str) -> str:
    stripped = _WAKE_PREFIX.sub("", text).strip()
    return stripped or text.strip()

SETTINGS = build_settings(database_path=Path(os.getenv("DOMUS_UI_DB", str(DEFAULT_DB))))


def _user_id_from_request(path: str, body: dict | None = None) -> int:
    qs = parse_qs(urlparse(path).query)
    if "user_id" in qs:
        try:
            return int(qs["user_id"][0])
        except (TypeError, ValueError, IndexError):
            pass
    if body and body.get("user_id") is not None:
        try:
            return int(body["user_id"])
        except (TypeError, ValueError):
            pass
    return USER_ID


def _week_offset_from_request(path: str) -> int:
    qs = parse_qs(urlparse(path).query)
    if "week" not in qs:
        return 0
    try:
        return int(qs["week"][0])
    except (TypeError, ValueError, IndexError):
        return 0


def _session(user_id: int) -> dict:
    apartment = apartment_for_user(SETTINGS.database_path, user_id)
    chat_id = chat_id_for_user(SETTINGS.database_path, user_id)
    profile = get_profile(SETTINGS.database_path, user_id)
    return {
        "user_id": user_id,
        "apartment": apartment,
        "chat_id": chat_id,
        "display_name": profile.display_name if profile else "You",
    }


def _todo_item_dict(todo) -> dict:
    is_shopping = todo.category == "shopping"
    return {
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
        "assigned_to_user_id": todo.assigned_to_user_id,
        "apartment": todo.apartment,
        "done": todo.done,
    }


def _todo_payload(apartment: str | None = None) -> list[dict]:
    if apartment:
        todos = db.list_open_todos(SETTINGS.database_path, apartment=apartment)
    else:
        todos = list_open_todos(SETTINGS.database_path)
    return [_todo_item_dict(todo) for todo in todos]


def _shopping_payload() -> list[dict]:
    todos = list_open_todos(SETTINGS.database_path, category="shopping")
    return [_todo_item_dict(todo) for todo in todos]


def _tasks_payload(apartment: str | None = None) -> list[dict]:
    if apartment:
        todos = db.list_open_todos(SETTINGS.database_path, apartment=apartment)
    else:
        todos = list_open_todos(SETTINGS.database_path)
    tasks = [todo for todo in todos if todo.category != "shopping"]
    return [_todo_item_dict(todo) for todo in tasks]


def _todos_api_response(apartment: str | None) -> dict:
    shopping = _shopping_payload()
    tasks = _tasks_payload(apartment)
    return {
        "shopping": shopping,
        "tasks": tasks,
        "todos": shopping + tasks,
    }


def _profile_dict(profile) -> dict:
    apartment = profile.apartment
    chat_id = chat_id_for_apartment(SETTINGS.database_path, apartment) if apartment else chat_id_for_user(
        SETTINGS.database_path, profile.telegram_user_id
    )
    join_code = None
    if apartment:
        from domus.households import apartment_payload as apt_payload

        join_code = apt_payload(SETTINGS.database_path, apartment).get("join_code")
    return {
        "id": profile.telegram_user_id,
        "display_name": profile.display_name,
        "username": profile.username,
        "apartment": apartment,
        "chat_id": chat_id,
        "join_code": join_code,
        "membership_status": membership_status(SETTINGS.database_path, profile.telegram_user_id),
        "diet": profile.diet,
        "allergies": profile.allergies,
        "likes": profile.likes,
        "dislikes": profile.dislikes,
    }


def _profiles_payload() -> list[dict]:
    return [_profile_dict(profile) for profile in list_profiles(SETTINGS.database_path)]


def _next_user_id() -> int:
    profiles = list_profiles(SETTINGS.database_path)
    if not profiles:
        return 1
    return max(profile.telegram_user_id for profile in profiles) + 1


def _stats_payload(
    *,
    apartment: str | None = None,
    person_id: int | None = None,
    days: int = 7,
) -> list[dict]:
    return [
        {
            "display_name": stat.display_name,
            "count": stat.count,
            "samples": stat.samples,
            "user_id": stat.user_id,
            "apartment": stat.apartment,
        }
        for stat in list_completion_stats(
            SETTINGS.database_path,
            days=days,
            apartment=apartment,
            user_id=person_id,
        )
    ]


def _stats_filters_from_path(path: str, session: dict) -> tuple[str | None, int | None]:
    qs = parse_qs(urlparse(path).query)
    apartment = session.get("apartment")
    person_id: int | None = None
    if qs.get("apartment", [""])[0].strip().lower() == "all":
        apartment = None
    elif qs.get("apartment", [""])[0].strip():
        apartment = qs["apartment"][0].strip()
    if qs.get("person", [""])[0].strip().lower() == "all":
        person_id = None
    elif qs.get("person", [""])[0].strip():
        try:
            person_id = int(qs["person"][0])
        except (TypeError, ValueError):
            person_id = session.get("user_id")
    return apartment, person_id


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
        user_id = _user_id_from_request(self.path)
        session = _session(user_id)

        if self.path.startswith("/api/todos"):
            self._send_json(_todos_api_response(session["apartment"]))
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
            apt_filter, person_filter = _stats_filters_from_path(self.path, session)
            self._send_json(
                {
                    "stats": _stats_payload(apartment=apt_filter, person_id=person_filter),
                    "filters": {"apartment": apt_filter, "person_id": person_filter},
                }
            )
            return
        if self.path.startswith("/api/reminders"):
            self._send_json(
                reminders_payload(
                    SETTINGS.database_path,
                    chat_id=session["chat_id"],
                )
            )
            return
        if self.path.startswith("/api/kitchen-notes"):
            apartment = session["apartment"]
            if not apartment:
                self._send_json({"error": "apartment required"}, status=400)
                return
            self._send_json(kitchen_notes_payload(SETTINGS.database_path, apartment))
            return
        if self.path.startswith("/api/bath/cleaning"):
            apartment = session["apartment"]
            if not apartment:
                self._send_json({"error": "apartment required"}, status=400)
                return
            self._send_json(cleaning_payload(SETTINGS.database_path, apartment))
            return
        if self.path.startswith("/api/bath/towels"):
            apartment = session["apartment"]
            if not apartment:
                self._send_json({"error": "apartment required"}, status=400)
                return
            self._send_json(towels_payload(SETTINGS.database_path, apartment))
            return
        if self.path.startswith("/api/bath/medicine"):
            apartment = session["apartment"]
            if not apartment:
                self._send_json({"error": "apartment required"}, status=400)
                return
            self._send_json(medicine_payload(SETTINGS.database_path, apartment))
            return
        if self.path.startswith("/api/meal-plan"):
            week = _week_offset_from_request(self.path)
            self._send_json(
                meal_plan_payload(
                    SETTINGS.database_path,
                    week_offset=week,
                    apartment=session["apartment"],
                )
            )
            return
        if self.path.startswith("/api/apartment"):
            apartment = session["apartment"]
            if not apartment:
                self._send_json({"error": "apartment required"}, status=400)
                return
            self._send_json(apartment_payload(SETTINGS.database_path, apartment))
            return
        if self.path.startswith("/api/cleaning-plan"):
            apartment = session["apartment"]
            if not apartment:
                self._send_json({"error": "apartment required"}, status=400)
                return
            self._send_json(cleaning_plan_payload(SETTINGS.database_path, apartment))
            return
        if self.path.startswith("/api/briefing"):
            self._send_json(
                daily_briefing_payload(
                    SETTINGS.database_path,
                    apartment=session["apartment"],
                )
            )
            return
        if self.path.startswith("/api/chat/history"):
            self._send_json(
                {
                    "apartment": session["apartment"],
                    "chat_id": session["chat_id"],
                    "history": chat_history_payload(
                        SETTINGS.database_path,
                        chat_id=session["chat_id"],
                        limit=50,
                    ),
                }
            )
            return
        if self.path == "/" or not self.path.startswith("/api"):
            self._serve_static(self.path)
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/message":
            body = self._read_json()
            text = strip_wake_word((body.get("text") or "").strip())
            user_id = _user_id_from_request(self.path, body)
            session = _session(user_id)
            display_name = (body.get("user") or session["display_name"]).strip() or "You"
            if not text:
                self._send_json({"error": "empty message"}, status=400)
                return
            reply = asyncio.run(
                handle_user_message(
                    text,
                    SETTINGS,
                    chat_id=session["chat_id"],
                    user_id=user_id,
                    display_name=display_name,
                )
            )
            self._send_json(
                {
                    "reply": reply,
                    "apartment": session["apartment"],
                    "chat_id": session["chat_id"],
                    **_todos_api_response(session["apartment"]),
                    "reminders": reminders_payload(
                        SETTINGS.database_path,
                        chat_id=session["chat_id"],
                    ),
                }
            )
            return

        if self.path == "/api/todos/toggle":
            body = self._read_json()
            try:
                todo_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            done = bool(body.get("done", True))
            user_id = _user_id_from_request(self.path, body)
            session = _session(user_id)
            set_todo_done(
                SETTINGS.database_path,
                todo_id,
                done=done,
                completed_by_user_id=user_id if done else None,
            )
            self._send_json(_todos_api_response(session["apartment"]))
            return

        if self.path == "/api/todos/add":
            body = self._read_json()
            name = (body.get("name") or "").strip()
            if not name:
                self._send_json({"error": "empty name"}, status=400)
                return
            category = (body.get("category") or "shopping").strip() or "shopping"
            due_date = (body.get("due_date") or None) or None
            assigned_to_user_id = body.get("assigned_to_user_id")
            if assigned_to_user_id is not None:
                try:
                    assigned_to_user_id = int(assigned_to_user_id)
                except (TypeError, ValueError):
                    self._send_json({"error": "invalid assigned_to_user_id"}, status=400)
                    return
            user_id = _user_id_from_request(self.path, body)
            session = _session(user_id)
            display_name = (body.get("user") or session["display_name"]).strip() or "You"
            add_item(
                SETTINGS.database_path,
                name,
                category=category,
                created_by=display_name,
                due_date=due_date,
                created_by_user_id=user_id,
                assigned_to_user_id=assigned_to_user_id,
                apartment=session["apartment"],
            )
            self._send_json(_todos_api_response(session["apartment"]))
            return

        if self.path == "/api/todos/quantity":
            body = self._read_json()
            try:
                todo_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            session = _session(_user_id_from_request(self.path, body))
            todo = db.get_open_todo(SETTINGS.database_path, todo_id)
            if todo is None or todo.category != "shopping":
                self._send_json({"error": "shopping item not found"}, status=404)
                return
            if body.get("quantity") is not None:
                try:
                    new_qty = int(body["quantity"])
                except (TypeError, ValueError):
                    self._send_json({"error": "invalid quantity"}, status=400)
                    return
            else:
                try:
                    delta = int(body.get("delta", 0))
                except (TypeError, ValueError):
                    self._send_json({"error": "invalid delta"}, status=400)
                    return
                new_qty = effective_quantity(todo) + delta
            if new_qty < 1:
                delete_item(SETTINGS.database_path, todo_id)
            else:
                db.update_todo(SETTINGS.database_path, todo_id, quantity=new_qty)
            self._send_json(_todos_api_response(session["apartment"]))
            return

        if self.path == "/api/profiles/register":
            body = self._read_json()
            display_name = (body.get("display_name") or "").strip()
            mode = (body.get("mode") or "create").strip().lower()
            if not display_name:
                self._send_json({"error": "display_name required"}, status=400)
                return
            try:
                user_id = int(body["user_id"]) if body.get("user_id") is not None else _next_user_id()
            except (TypeError, ValueError):
                self._send_json({"error": "invalid user_id"}, status=400)
                return
            db.upsert_user_profile(
                SETTINGS.database_path,
                user_id,
                display_name,
            )
            try:
                if mode == "join":
                    join_code = (body.get("join_code") or "").strip()
                    if not join_code:
                        self._send_json({"error": "join_code required"}, status=400)
                        return
                    join_result = request_join_apartment(
                        SETTINGS.database_path,
                        user_id,
                        join_code,
                    )
                    profile = db.get_user_profile(SETTINGS.database_path, user_id)
                    self._send_json(
                        {
                            "profile": _profile_dict(profile),
                            "profiles": _profiles_payload(),
                            "join": join_result,
                        }
                    )
                    return
                apartment = (body.get("apartment") or "").strip()
                if not apartment:
                    self._send_json({"error": "apartment required"}, status=400)
                    return
                apt = create_apartment_with_owner(
                    SETTINGS.database_path,
                    apartment,
                    user_id,
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            profile = db.get_user_profile(SETTINGS.database_path, user_id)
            self._send_json(
                {
                    "profile": _profile_dict(profile),
                    "profiles": _profiles_payload(),
                    "apartment": apt,
                }
            )
            return

        if self.path == "/api/apartment/accept":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            try:
                member_id = int(body.get("member_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "member_id required"}, status=400)
                return
            if not session["apartment"]:
                self._send_json({"error": "apartment required"}, status=400)
                return
            try:
                payload = accept_apartment_member(
                    SETTINGS.database_path,
                    session["apartment"],
                    member_id,
                    accepted_by_user_id=session["user_id"],
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({**payload, "profiles": _profiles_payload()})
            return

        if self.path == "/api/apartment/kick":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            try:
                member_id = int(body.get("member_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "member_id required"}, status=400)
                return
            if not session["apartment"]:
                self._send_json({"error": "apartment required"}, status=400)
                return
            try:
                payload = kick_apartment_member(
                    SETTINGS.database_path,
                    session["apartment"],
                    member_id,
                    kicked_by_user_id=session["user_id"],
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({**payload, "profiles": _profiles_payload()})
            return

        if self.path == "/api/apartment/leave":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            try:
                leave_apartment(SETTINGS.database_path, session["user_id"])
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({"profiles": _profiles_payload(), "left": True})
            return

        if self.path == "/api/apartment/regenerate-code":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            if not session["apartment"]:
                self._send_json({"error": "apartment required"}, status=400)
                return
            try:
                payload = regenerate_join_code(
                    SETTINGS.database_path,
                    session["apartment"],
                    owner_user_id=session["user_id"],
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(payload)
            return

        if self.path == "/api/profiles/update":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            target_id = session["user_id"]
            if body.get("profile_id") is not None:
                try:
                    target_id = int(body["profile_id"])
                except (TypeError, ValueError):
                    self._send_json({"error": "invalid profile_id"}, status=400)
                    return
            if target_id != session["user_id"]:
                self._send_json({"error": "can only edit your own profile"}, status=403)
                return
            updates: dict = {}
            for field in ("diet", "allergies", "dislikes", "likes"):
                if field in body:
                    updates[field] = (body.get(field) or "").strip()
            if not updates:
                self._send_json({"error": "nothing to update"}, status=400)
                return
            try:
                profile = db.update_user_profile(SETTINGS.database_path, target_id, **updates)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(
                {
                    "profile": _profile_dict(profile),
                    "profiles": _profiles_payload(),
                }
            )
            return

        if self.path == "/api/cleaning-plan/done":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            if not session["apartment"]:
                self._send_json({"error": "apartment required"}, status=400)
                return
            try:
                chore_id = int(body.get("chore_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "chore_id required"}, status=400)
                return
            self._send_json(
                mark_chore_done(
                    SETTINGS.database_path,
                    session["apartment"],
                    chore_id,
                    done_by_user_id=session["user_id"],
                    done_by_name=session["display_name"],
                )
            )
            return

        if self.path == "/api/cleaning-plan/add":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            if not session["apartment"]:
                self._send_json({"error": "apartment required"}, status=400)
                return
            label = (body.get("label") or "").strip()
            try:
                interval = int(body.get("interval_days", 7))
            except (TypeError, ValueError):
                interval = 7
            try:
                payload = add_chore(
                    SETTINGS.database_path,
                    session["apartment"],
                    label,
                    interval_days=max(1, interval),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(payload)
            return

        if self.path == "/api/cleaning-plan/assign":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            if not session["apartment"]:
                self._send_json({"error": "apartment required"}, status=400)
                return
            try:
                chore_id = int(body.get("chore_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "chore_id required"}, status=400)
                return
            assignee = body.get("assigned_to_user_id")
            if assignee is not None and assignee != "":
                try:
                    assignee = int(assignee)
                except (TypeError, ValueError):
                    self._send_json({"error": "invalid assignee"}, status=400)
                    return
            else:
                assignee = None
            try:
                payload = assign_chore(
                    SETTINGS.database_path,
                    session["apartment"],
                    chore_id,
                    assignee,
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(payload)
            return

        if self.path == "/api/todos/remove":
            body = self._read_json()
            try:
                todo_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            session = _session(_user_id_from_request(self.path, body))
            delete_item(SETTINGS.database_path, todo_id)
            self._send_json(_todos_api_response(session["apartment"]))
            return

        if self.path == "/api/recipes/plan":
            body = self._read_json()
            name = (body.get("name") or "").strip()
            if not name:
                self._send_json({"error": "empty name"}, status=400)
                return
            session = _session(_user_id_from_request(self.path, body))
            reply = plan_recipe(
                SETTINGS.database_path,
                name,
                created_by=session["display_name"],
            )
            self._send_json({"reply": reply, **_todos_api_response(session["apartment"])})
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

        if self.path == "/api/kitchen-notes/create":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            if not session["apartment"]:
                self._send_json({"error": "apartment required"}, status=400)
                return
            note = create_kitchen_note(
                SETTINGS.database_path,
                apartment=session["apartment"],
                author_user_id=session["user_id"],
                author_name=session["display_name"],
                body=(body.get("body") or ""),
                color=(body.get("color") or "yellow"),
            )
            self._send_json(kitchen_notes_payload(SETTINGS.database_path, session["apartment"]))
            return

        if self.path == "/api/kitchen-notes/update":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            try:
                note_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            updated = update_kitchen_note(
                SETTINGS.database_path,
                note_id,
                body=body.get("body"),
                color=body.get("color"),
            )
            if updated is None:
                self._send_json({"error": "note not found"}, status=404)
                return
            self._send_json(kitchen_notes_payload(SETTINGS.database_path, session["apartment"]))
            return

        if self.path == "/api/kitchen-notes/delete":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            try:
                note_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            if not delete_kitchen_note(SETTINGS.database_path, note_id):
                self._send_json({"error": "note not found"}, status=404)
                return
            self._send_json(kitchen_notes_payload(SETTINGS.database_path, session["apartment"]))
            return

        if self.path == "/api/bath/cleaning/toggle":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            if not session["apartment"]:
                self._send_json({"error": "apartment required"}, status=400)
                return
            item_key = (body.get("item_key") or body.get("key") or "").strip()
            try:
                payload = toggle_cleaning_item(
                    SETTINGS.database_path,
                    session["apartment"],
                    item_key,
                    done_by=session["display_name"],
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(payload)
            return

        if self.path == "/api/bath/towels/use":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            label = (body.get("label") or "").strip()
            if not session["apartment"] or not label:
                self._send_json({"error": "apartment and label required"}, status=400)
                return
            self._send_json(log_towel_use(SETTINGS.database_path, session["apartment"], label))
            return

        if self.path == "/api/bath/towels/washed":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            label = (body.get("label") or "").strip()
            if not session["apartment"] or not label:
                self._send_json({"error": "apartment and label required"}, status=400)
                return
            self._send_json(log_towel_washed(SETTINGS.database_path, session["apartment"], label))
            return

        if self.path == "/api/bath/medicine/add":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            name = (body.get("name") or "").strip()
            if not session["apartment"] or not name:
                self._send_json({"error": "apartment and name required"}, status=400)
                return
            self._send_json(
                add_medicine(
                    SETTINGS.database_path,
                    session["apartment"],
                    name,
                    expiry_date=(body.get("expiry_date") or None),
                    quantity_note=(body.get("quantity_note") or None),
                )
            )
            return

        if self.path == "/api/bath/medicine/delete":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            try:
                item_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            if not delete_medicine(SETTINGS.database_path, item_id):
                self._send_json({"error": "not found"}, status=404)
                return
            self._send_json(medicine_payload(SETTINGS.database_path, session["apartment"]))
            return

        if self.path == "/api/meal-plan/set":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            day = (body.get("day") or "").strip()
            dish = (body.get("dish") or body.get("name") or "").strip()
            if not day or not dish:
                self._send_json({"error": "day and dish required"}, status=400)
                return
            try:
                set_meal_plan_day(
                    SETTINGS.database_path,
                    day,
                    dish,
                    apartment=session["apartment"],
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            week = _week_offset_from_request(f"?week={body.get('week_offset', 0)}")
            self._send_json(
                meal_plan_payload(
                    SETTINGS.database_path,
                    week_offset=week,
                    apartment=session["apartment"],
                )
            )
            return

        if self.path == "/api/meal-plan/clear":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            day = (body.get("day") or "").strip()
            if not day:
                self._send_json({"error": "day required"}, status=400)
                return
            food_db.delete_meal_plan_day(
                SETTINGS.database_path,
                day,
                apartment=session["apartment"],
            )
            week = _week_offset_from_request(f"?week={body.get('week_offset', 0)}")
            self._send_json(
                meal_plan_payload(
                    SETTINGS.database_path,
                    week_offset=week,
                    apartment=session["apartment"],
                )
            )
            return

        if self.path == "/api/meal-plan/suggest":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            day = (body.get("day") or "").strip()
            if not day:
                self._send_json({"error": "day required"}, status=400)
                return
            profiles = list_profiles(SETTINGS.database_path)
            try:
                suggest_meal_plan_day(
                    SETTINGS.database_path,
                    day,
                    apartment=session["apartment"],
                    profiles=profiles,
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            week = _week_offset_from_request(f"?week={body.get('week_offset', 0)}")
            self._send_json(
                meal_plan_payload(
                    SETTINGS.database_path,
                    week_offset=week,
                    apartment=session["apartment"],
                )
            )
            return

        if self.path == "/api/meal-plan/auto":
            body = self._read_json()
            session = _session(_user_id_from_request(self.path, body))
            week = int(body.get("week_offset", 0) or 0)
            profiles = list_profiles(SETTINGS.database_path)
            planned, missing = plan_calendar_week(
                SETTINGS.database_path,
                week_offset=week,
                apartment=session["apartment"],
                created_by=session["display_name"],
                profiles=profiles,
                replace=True,
            )
            payload = meal_plan_payload(
                SETTINGS.database_path,
                week_offset=week,
                apartment=session["apartment"],
            )
            payload["planned_count"] = len(planned)
            payload["shopping_added"] = missing
            self._send_json(payload)
            return

        if self.path == "/api/reminders/remove":
            body = self._read_json()
            try:
                reminder_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            removed = db.remove_reminder_by_id(SETTINGS.database_path, reminder_id)
            if removed is None:
                self._send_json({"error": "reminder not found"}, status=404)
                return
            session = _session(_user_id_from_request(self.path, body))
            self._send_json(
                {
                    "removed": removed.text,
                    **reminders_payload(
                        SETTINGS.database_path,
                        chat_id=session["chat_id"],
                    ),
                }
            )
            return

        if self.path == "/api/reminders/cancel-timer":
            body = self._read_json()
            try:
                timer_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._send_json({"error": "invalid id"}, status=400)
                return
            cancelled = db.cancel_one_shot_by_id(SETTINGS.database_path, timer_id)
            if cancelled is None:
                self._send_json({"error": "timer not found"}, status=404)
                return
            session = _session(_user_id_from_request(self.path, body))
            self._send_json(
                {
                    "cancelled": cancelled.text,
                    **reminders_payload(
                        SETTINGS.database_path,
                        chat_id=session["chat_id"],
                    ),
                }
            )
            return

        self.send_error(404, "Not found")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Domus UI backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    init_storage(SETTINGS.database_path)
    init_households(SETTINGS.database_path)
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
