"""Smoke tests for SQLite schema and household / meal-plan persistence."""

import tempfile
import unittest
from pathlib import Path

from domus.core import init_storage
from domus import db, food_db
from domus.households import (
    MEMBER_ACTIVE,
    MEMBER_PENDING,
    accept_apartment_member,
    apartment_payload,
    create_apartment_with_owner,
    request_join_apartment,
)
from domus.meal_plan_views import calendar_week_bounds, meal_plan_payload, set_meal_plan_day


class DatabaseSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "test.db"
        init_storage(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_core_tables_exist(self) -> None:
        with db.connect(self.db_path) as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for name in (
            "todos",
            "users",
            "apartments",
            "apartment_members",
            "kitchen_notes",
            "bath_towels",
            "bath_medicine",
            "meal_plans",
            "foods",
        ):
            self.assertIn(name, tables)

    def test_profile_create_and_join_flow(self) -> None:
        db.upsert_user_profile(self.db_path, 1, "Owner")
        apt = create_apartment_with_owner(self.db_path, "Test Flat", owner_user_id=1)
        self.assertEqual(len(apt["join_code"]), 13)

        db.upsert_user_profile(self.db_path, 2, "Roommate")
        join = request_join_apartment(self.db_path, 2, apt["join_code"])
        self.assertEqual(join["status"], MEMBER_PENDING)

        accept_apartment_member(
            self.db_path,
            "Test Flat",
            2,
            accepted_by_user_id=1,
        )
        profile = db.get_user_profile(self.db_path, 2)
        self.assertEqual(profile.apartment, "Test Flat")
        payload = apartment_payload(self.db_path, "Test Flat")
        self.assertEqual(len(payload["members"]), 2)

    def test_meal_plan_persists_across_weeks(self) -> None:
        apartment = "Meal Test Apt"
        db.upsert_user_profile(self.db_path, 10, "Chef")
        create_apartment_with_owner(self.db_path, apartment, owner_user_id=10)
        next_week_start, _ = calendar_week_bounds(1)
        day = next_week_start.isoformat()
        set_meal_plan_day(self.db_path, day, "Pasta night", apartment=apartment)

        week0 = meal_plan_payload(self.db_path, week_offset=0, apartment=apartment)
        week1 = meal_plan_payload(self.db_path, week_offset=1, apartment=apartment)
        self.assertTrue(any(d["dish"] == "Pasta night" for d in week1["days"]))
        self.assertFalse(any(d["dish"] == "Pasta night" for d in week0["days"]))

    def test_meal_plan_prunes_old_weeks(self) -> None:
        apartment = "Prune Apt"
        db.upsert_user_profile(self.db_path, 20, "Planner")
        create_apartment_with_owner(self.db_path, apartment, owner_user_id=20)
        old_start, _ = calendar_week_bounds(-7)
        set_meal_plan_day(
            self.db_path,
            old_start.isoformat(),
            "Ancient stew",
            apartment=apartment,
        )
        food_db.prune_old_meal_plans(self.db_path, apartment, keep_weeks=6)
        entries = food_db.get_meal_plan_range(
            self.db_path,
            old_start.isoformat(),
            old_start.isoformat(),
            apartment=apartment,
        )
        self.assertEqual(entries, [])


if __name__ == "__main__":
    unittest.main()
