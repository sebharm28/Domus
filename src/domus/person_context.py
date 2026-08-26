from pathlib import Path

from domus import db


def resolve_assignee_user_id(
    db_path: Path,
    assignee: str | None,
    *,
    current_user_id: int | None,
) -> int | None:
    if not assignee:
        return None
    return db.resolve_user_id_by_name(db_path, assignee, current_user_id=current_user_id)


def format_assignee_label(db_path: Path, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    return db.get_user_display_name(db_path, user_id)


def handle_who_did_what(db_path: Path, *, days: int = 7) -> str:
    stats = db.list_completion_stats(db_path, days=days)
    if not stats:
        return f"No completed tasks recorded in the last {days} days."

    lines = [f"Who did what — last {days} days:"]
    for stat in stats:
        sample = ""
        if stat.samples:
            sample = f" e.g. {', '.join(stat.samples[:3])}"
        lines.append(f"• {stat.display_name}: {stat.count} completed{sample}")
    return "\n".join(lines)
