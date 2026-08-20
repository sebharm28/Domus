DEFAULT_CATEGORIES = (
    "shopping",
    "household",
    "admin",
    "maintenance",
    "personal",
    "general",
)

SHOPPING_HINTS = {
    "milk",
    "bread",
    "eggs",
    "butter",
    "cheese",
    "pepper",
    "oil",
    "flour",
    "pasta",
    "rice",
    "fruit",
    "vegetable",
    "coffee",
    "tea",
}

HOUSEHOLD_HINTS = {"trash", "clean", "vacuum", "laundry", "plants", "watering", "filter"}
ADMIN_HINTS = {"rent", "transfer", "bill", "insurance", "contract", "bank"}
MAINTENANCE_HINTS = {"repair", "battery", "smoke detector", "service", "appointment"}


def normalize_category(category: str | None) -> str | None:
    if not category:
        return None
    cleaned = category.strip().lower()
    if cleaned in DEFAULT_CATEGORIES:
        return cleaned
    return "general"


def infer_category(text: str, category: str | None = None) -> str:
    explicit = normalize_category(category)
    if explicit:
        return explicit

    lowered = text.lower()
    if any(hint in lowered for hint in SHOPPING_HINTS) or "shopping" in lowered:
        return "shopping"
    if any(hint in lowered for hint in HOUSEHOLD_HINTS):
        return "household"
    if any(hint in lowered for hint in ADMIN_HINTS):
        return "admin"
    if any(hint in lowered for hint in MAINTENANCE_HINTS):
        return "maintenance"
    return "general"
