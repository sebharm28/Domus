from pathlib import Path

from domus import db, food_db
from domus.memory import remember_user_fact


def touch_user(
    db_path: Path,
    telegram_user_id: int,
    display_name: str,
    *,
    username: str | None = None,
) -> db.UserProfile:
    return db.upsert_user_profile(
        db_path,
        telegram_user_id,
        display_name,
        username=username,
    )


def format_profile(profile: db.UserProfile) -> str:
    lines = [f"Profile for {profile.display_name}:"]
    if profile.apartment:
        lines.append(f"• Apartment: {profile.apartment}")
    if profile.diet:
        lines.append(f"• Diet: {profile.diet}")
    if profile.allergies:
        lines.append(f"• Allergies: {profile.allergies}")
    if profile.likes:
        lines.append(f"• Likes: {profile.likes}")
    if profile.dislikes:
        lines.append(f"• Dislikes: {profile.dislikes}")
    if len(lines) == 1:
        lines.append("• No preferences saved yet.")
        lines.append('Try: "Domus, I\'m vegetarian" or "I really like currywurst".')
    return "\n".join(lines)


def handle_show_profile(db_path: Path, telegram_user_id: int) -> str:
    profile = db.get_user_profile(db_path, telegram_user_id)
    if profile is None:
        return "I don't have a profile for you yet — say something and I'll remember your name."
    return format_profile(profile)


def handle_update_profile(intent, db_path: Path, telegram_user_id: int) -> str:
    profile = db.get_user_profile(db_path, telegram_user_id)
    if profile is None:
        return "I couldn't find your profile."

    field = intent.category or "diet"
    allowed = {"apartment", "diet", "allergies", "dislikes", "likes"}
    if field not in allowed:
        return f"I can't update profile field {field!r} yet."

    value = (intent.item or "").strip()
    if not value:
        return "What should I update on your profile?"

    updated = db.update_user_profile(db_path, telegram_user_id, **{field: value})
    remember_user_fact(
        db_path,
        user_id=telegram_user_id,
        key=field,
        value=value,
        source="profile_update",
    )
    label = field.replace("_", " ")
    return f"Updated your {label} to {value!r}."


def handle_log_preference(intent, db_path: Path, telegram_user_id: int) -> str:
    profile = db.get_user_profile(db_path, telegram_user_id)
    if profile is None:
        return "I couldn't find your profile."

    value = (intent.item or "").strip()
    if not value:
        return "What should I remember that you like?"

    db.append_user_profile_list(db_path, telegram_user_id, "likes", value)
    remember_user_fact(
        db_path,
        user_id=telegram_user_id,
        key="likes",
        value=value,
        source="log_preference",
    )
    food_db.init_food_tables(db_path)
    food = food_db.add_custom_food(db_path, value)
    return (
        f'Got it — I\'ll remember you like {value!r}. '
        f'Added "{food.name}" to your meal ideas.'
    )


def handle_log_dispreference(intent, db_path: Path, telegram_user_id: int) -> str:
    profile = db.get_user_profile(db_path, telegram_user_id)
    if profile is None:
        return "I couldn't find your profile."

    value = (intent.item or "").strip()
    if not value:
        return "What should I remember that you don't like?"

    db.append_user_profile_list(db_path, telegram_user_id, "dislikes", value)
    remember_user_fact(
        db_path,
        user_id=telegram_user_id,
        key="dislikes",
        value=value,
        source="log_dispreference",
    )
    return f"Got it — I'll remember you don't like {value!r}."


def handle_intent(intent, db_path: Path, telegram_user_id: int) -> str:
    if intent.name == "show_profile":
        return handle_show_profile(db_path, telegram_user_id)
    if intent.name == "update_profile":
        return handle_update_profile(intent, db_path, telegram_user_id)
    if intent.name == "log_preference":
        return handle_log_preference(intent, db_path, telegram_user_id)
    if intent.name == "log_dispreference":
        return handle_log_dispreference(intent, db_path, telegram_user_id)
    return ""
