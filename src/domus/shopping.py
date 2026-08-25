import re

from domus.db import Todo

_QUANTITY_PREFIX = re.compile(r"^(\d+)\s+(.+)$")
_QUANTITY_SUFFIX = re.compile(r"^(.+?)\s+x\s*(\d+)$", re.IGNORECASE)


def parse_item_quantity(text: str) -> tuple[str, int | None]:
    stripped = text.strip()
    match = _QUANTITY_PREFIX.match(stripped)
    if match:
        return match.group(2).strip(), int(match.group(1))
    suffix = _QUANTITY_SUFFIX.match(stripped)
    if suffix:
        return suffix.group(1).strip(), int(suffix.group(2))
    return stripped, None


def effective_quantity(todo: Todo) -> int:
    if todo.quantity is not None:
        return todo.quantity
    _, parsed = parse_item_quantity(todo.text)
    return parsed if parsed is not None else 1


def shopping_item_name(todo: Todo) -> str:
    name, _ = parse_item_quantity(todo.text)
    return name


def format_shopping_display(todo: Todo) -> str:
    name = shopping_item_name(todo)
    quantity = effective_quantity(todo)
    if quantity > 1:
        return f"{quantity}× {name}"
    return name
