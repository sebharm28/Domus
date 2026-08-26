import unittest
from pathlib import Path

from domus import db, food_db
from domus.intents import _parse_with_rules, Intent
from domus.meals import handle_add_recipe, parse_add_recipe_phrase
from domus.todos import handle_intent


class ParseAddRecipeTests(unittest.TestCase):
    def test_colon_format(self) -> None:
        parsed = parse_add_recipe_phrase("add meal grilled cheese: bread, cheese, butter")
        self.assertIsNotNone(parsed)
        name, ingredients, meal_type = parsed  # type: ignore[misc]
        self.assertEqual(name, "grilled cheese")
        self.assertEqual(ingredients, ["bread", "cheese", "butter"])
        self.assertIsNone(meal_type)

    def test_with_format(self) -> None:
        parsed = parse_add_recipe_phrase("save recipe pumpkin soup with pumpkin, cream and broth")
        self.assertIsNotNone(parsed)
        name, ingredients, meal_type = parsed  # type: ignore[misc]
        self.assertEqual(name, "pumpkin soup")
        self.assertEqual(ingredients, ["pumpkin", "cream", "broth"])

    def test_meal_type_prefix(self) -> None:
        parsed = parse_add_recipe_phrase("add lunch recipe omelette: eggs, cheese")
        self.assertIsNotNone(parsed)
        name, ingredients, meal_type = parsed  # type: ignore[misc]
        self.assertEqual(name, "omelette")
        self.assertEqual(meal_type, "lunch")

    def test_does_not_match_plain_add(self) -> None:
        self.assertIsNone(parse_add_recipe_phrase("add milk to the list"))

    def test_rules_parser(self) -> None:
        intents = _parse_with_rules("add meal grilled cheese: bread, cheese, butter")
        self.assertEqual(intents[0].name, "add_recipe")
        self.assertEqual(intents[0].item, "grilled cheese")
        self.assertEqual(intents[0].new_item, "bread|cheese|butter")


class HandleAddRecipeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_add_recipe_nlp.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        food_db.init_food_tables(self.db_path)
        self.user_id = 7001
        db.upsert_user_profile(self.db_path, self.user_id, "Sebastian")

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_handle_add_recipe_persists_food(self) -> None:
        intent = Intent(
            name="add_recipe",
            item="grilled cheese",
            new_item="bread|cheese|butter",
            category="dinner",
        )
        reply = handle_add_recipe(intent, self.db_path, author="Sebastian")
        self.assertIn("Grilled Cheese", reply)
        food = food_db.find_food_by_name(self.db_path, "grilled cheese")
        self.assertIsNotNone(food)
        assert food is not None
        self.assertEqual(sorted(food.ingredients), ["bread", "butter", "cheese"])
        self.assertEqual(food.author, "Sebastian")

    def test_handle_via_todo_router(self) -> None:
        intent = Intent(
            name="add_recipe",
            item="quick pasta",
            new_item="pasta|garlic|olive oil",
        )
        reply = handle_intent(
            intent,
            self.db_path,
            created_by="Sebastian",
            telegram_user_id=self.user_id,
        )
        self.assertIn("Quick Pasta", reply)
        food = food_db.find_food_by_name(self.db_path, "quick pasta")
        self.assertIsNotNone(food)

    def test_duplicate_recipe_message(self) -> None:
        intent = Intent(name="add_recipe", item="broth", new_item="water|stock")
        handle_add_recipe(intent, self.db_path)
        reply = handle_add_recipe(intent, self.db_path)
        self.assertIn("already exists", reply.lower())


if __name__ == "__main__":
    unittest.main()
