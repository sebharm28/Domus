import unittest
from pathlib import Path

from domus import food_db


class RecipeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_recipes.db")
        if self.db_path.exists():
            self.db_path.unlink()
        food_db.init_food_tables(self.db_path)

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_seeded_foods_have_details_and_tags(self) -> None:
        foods = food_db.list_foods(self.db_path)
        self.assertTrue(foods)
        sample = foods[0]
        # Backfilled details carry the ingredient names (amounts blank for seeds).
        self.assertEqual(
            [d["name"] for d in sample.ingredient_details], sample.ingredients
        )
        # Seeded tags include the meal type so the filter works out of the box.
        self.assertIn(sample.meal_type, sample.tags)

    def test_add_recipe_with_amounts_tags_author(self) -> None:
        recipe = food_db.add_recipe(
            self.db_path,
            "pumpkin soup",
            meal_type="dinner",
            ingredient_details=[
                {"name": "pumpkin", "amount": "1 kg"},
                {"name": "cream", "amount": "200 ml"},
                {"name": "", "amount": "ignored"},  # skipped
            ],
            tags=["soup", "autumn", "dinner"],
            notes="# Pumpkin soup\nRoast then blend.",
            author="Sebastian",
        )
        self.assertEqual(recipe.name, "Pumpkin Soup")
        self.assertEqual(recipe.author, "Sebastian")
        # Names for the card (no amounts), details for the popup (with amounts).
        self.assertEqual(recipe.ingredients, ["pumpkin", "cream"])
        self.assertEqual(recipe.ingredient_details[0], {"name": "pumpkin", "amount": "1 kg"})
        # Tags de-duplicated; meal_type present; custom tags kept.
        self.assertIn("soup", recipe.tags)
        self.assertIn("autumn", recipe.tags)
        self.assertIn("dinner", recipe.tags)
        self.assertEqual(len([t for t in recipe.tags if t.lower() == "dinner"]), 1)

    def test_add_recipe_duplicate_name_raises(self) -> None:
        food_db.add_recipe(self.db_path, "My Dish", meal_type="lunch")
        with self.assertRaises(ValueError):
            food_db.add_recipe(self.db_path, "my dish", meal_type="dinner")

    def test_update_recipe_notes_and_tags(self) -> None:
        recipe = food_db.add_recipe(self.db_path, "Test Meal", meal_type="lunch")
        updated = food_db.update_recipe(
            self.db_path,
            recipe.id,
            notes="**bold** note",
            tags=["quick", "quick", "lunch"],
        )
        assert updated is not None
        self.assertEqual(updated.notes, "**bold** note")
        # De-duplicated case-insensitively.
        self.assertEqual(sorted(t.lower() for t in updated.tags), ["lunch", "quick"])

    def test_list_tags_distinct(self) -> None:
        food_db.add_recipe(self.db_path, "Broth", meal_type="dinner", tags=["Soup"])
        tags = food_db.list_tags(self.db_path)
        lowered = [t.lower() for t in tags]
        self.assertIn("soup", lowered)
        self.assertIn("breakfast", lowered)
        # No duplicates (case-insensitive).
        self.assertEqual(len(lowered), len(set(lowered)))


if __name__ == "__main__":
    unittest.main()
