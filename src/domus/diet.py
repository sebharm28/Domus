from domus import db
from domus.food_db import Food

MEAT_TERMS = frozenset(
    {
        "chicken",
        "tuna",
        "salmon",
        "beef",
        "pork",
        "bacon",
        "ham",
        "fish",
        "meat",
    }
)
DAIRY_TERMS = frozenset(
    {
        "milk",
        "cheese",
        "yogurt",
        "mozzarella",
        "butter",
        "cream",
        "eggs",
    }
)
EGG_TERMS = frozenset({"eggs", "egg"})


def _ingredient_blob(food: Food) -> str:
    parts = [food.name.lower(), *(ingredient.lower() for ingredient in food.ingredients)]
    return " ".join(parts)


def _contains_any(blob: str, terms: frozenset[str]) -> bool:
    return any(term in blob for term in terms)


def food_ok_for_profile(food: Food, profile: db.UserProfile) -> bool:
    blob = _ingredient_blob(food)

    if profile.diet == "vegan":
        if _contains_any(blob, MEAT_TERMS | DAIRY_TERMS | EGG_TERMS):
            return False
    elif profile.diet == "vegetarian" and _contains_any(blob, MEAT_TERMS):
        return False
    elif profile.diet == "pescatarian" and _contains_any(
        blob, MEAT_TERMS - {"salmon", "tuna", "fish"}
    ):
        return False

    if profile.allergies:
        for allergen in profile.allergies.split(","):
            allergen = allergen.strip().lower()
            if allergen and allergen in blob:
                return False

    if profile.dislikes:
        for dislike in profile.dislikes.split(","):
            dislike = dislike.strip().lower()
            if dislike and dislike in blob:
                return False

    return True


def filter_foods_for_household(
    foods: list[Food],
    profiles: list[db.UserProfile],
) -> list[Food]:
    if not profiles:
        return foods
    return [food for food in foods if all(food_ok_for_profile(food, profile) for profile in profiles)]
