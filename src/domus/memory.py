import json
from pathlib import Path

from domus import db


def record_exchange(
    db_path: Path,
    *,
    chat_id: int,
    user_id: int | None,
    user_text: str,
    assistant_text: str,
    intents: list | None = None,
    private_mode: bool = False,
) -> None:
    """Persist a user/assistant turn for long-term context."""
    if private_mode:
        return
    intent_json = None
    if intents:
        intent_json = json.dumps(
            [
                {
                    "name": intent.name,
                    "item": intent.item,
                    "category": intent.category,
                }
                for intent in intents
            ]
        )
    db.record_conversation_turn(
        db_path,
        chat_id=chat_id,
        user_id=user_id,
        role="user",
        text=user_text,
        intent_json=intent_json,
    )
    db.record_conversation_turn(
        db_path,
        chat_id=chat_id,
        user_id=None,
        role="assistant",
        text=assistant_text,
    )


def remember_user_fact(
    db_path: Path,
    *,
    user_id: int | None,
    key: str,
    value: str,
    source: str = "conversation",
) -> None:
    if user_id is None:
        return
    db.upsert_memory_fact(db_path, user_id=user_id, fact_key=key, fact_value=value, source=source)


def build_openrouter_context(
    db_path: Path,
    *,
    chat_id: int | None,
    user_id: int | None,
    limit: int = 5,
) -> str:
    """Build a short memory block to inject into the OpenRouter system prompt."""
    lines: list[str] = []

    if user_id is not None:
        profile = db.get_user_profile(db_path, user_id)
        if profile:
            profile_bits: list[str] = [f"name={profile.display_name}"]
            if profile.diet:
                profile_bits.append(f"diet={profile.diet}")
            if profile.apartment:
                profile_bits.append(f"apartment={profile.apartment}")
            if profile.allergies:
                profile_bits.append(f"allergies={profile.allergies}")
            if profile.likes:
                profile_bits.append(f"likes={profile.likes}")
            if profile.dislikes:
                profile_bits.append(f"dislikes={profile.dislikes}")
            lines.append(f"Speaker ({profile.display_name}): " + "; ".join(profile_bits))

        facts = db.list_memory_facts(db_path, user_id=user_id, limit=8)
        if facts:
            fact_line = ", ".join(f"{fact.fact_key}={fact.fact_value}" for fact in facts)
            lines.append(f"Remembered facts: {fact_line}")

    if chat_id is not None:
        turns = db.list_recent_turns(db_path, chat_id=chat_id, limit=limit)
        if turns:
            lines.append("Recent conversation:")
            for turn in reversed(turns):
                speaker = "User" if turn.role == "user" else "Domus"
                lines.append(f"- {speaker}: {turn.text[:160]}")

        context = db.get_chat_context(db_path, chat_id)
        if context and (context.last_intent or context.last_item):
            hint = context.last_intent or "unknown"
            item = context.last_item or "none"
            lines.append(f"Short-term focus: last_intent={hint}, last_item={item!r}")

    if not lines:
        return ""
    return "Household memory (local only):\n" + "\n".join(lines)
