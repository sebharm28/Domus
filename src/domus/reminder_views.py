"""JSON-friendly reminder payloads for UI and API layers."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from domus import db
from domus.dates import format_due_date
from domus.recurrence import format_recurrence
from domus.reminders import _format_fire_at, _minutes_until


def reminders_payload(db_path: Path, *, chat_id: int | None = None) -> dict:
    today = date.today()
    recurring = []
    for reminder in db.list_reminders(db_path):
        next_due = date.fromisoformat(reminder.next_due)
        recurring.append(
            {
                "id": reminder.id,
                "text": reminder.text,
                "recurrence": reminder.recurrence,
                "schedule_label": format_recurrence(reminder.recurrence),
                "next_due": reminder.next_due,
                "next_due_label": format_due_date(reminder.next_due),
                "created_by": reminder.created_by,
                "is_overdue": next_due < today,
            }
        )

    pending = []
    for timer in db.list_pending_one_shot_reminders(db_path, chat_id=chat_id):
        minutes = _minutes_until(timer.fire_at)
        pending.append(
            {
                "id": timer.id,
                "text": timer.text,
                "fire_at": timer.fire_at,
                "fire_at_local": _format_fire_at(timer.fire_at),
                "minutes_until": minutes,
                "created_by": timer.created_by,
            }
        )

    recent = []
    if chat_id is not None:
        for timer in db.list_recent_one_shot_reminders(db_path, chat_id):
            recent.append(
                {
                    "id": timer.id,
                    "text": timer.text,
                    "fire_at": timer.fire_at,
                    "fire_at_local": _format_fire_at(timer.fire_at),
                    "created_by": timer.created_by,
                }
            )

    return {
        "recurring": recurring,
        "pending_timers": pending,
        "recent_timers": recent,
    }


def chat_history_payload(
    db_path: Path,
    *,
    chat_id: int,
    limit: int = 50,
) -> list[dict]:
    turns = db.list_conversation_turns(db_path, chat_id=chat_id, limit=limit)
    payload: list[dict] = []
    for turn in turns:
        entry: dict = {
            "id": turn.id,
            "role": turn.role,
            "text": turn.text,
            "created_at": turn.created_at,
        }
        if turn.user_id is not None:
            entry["user_id"] = turn.user_id
            profile = db.get_user_profile(db_path, turn.user_id)
            if profile:
                entry["display_name"] = profile.display_name
        if turn.intent_json:
            try:
                entry["intents"] = json.loads(turn.intent_json)
            except json.JSONDecodeError:
                entry["intents"] = []
        payload.append(entry)
    return payload
