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

    def test_household_auth_create_join_login(self) -> None:
        from domus.household_auth import (
            create_household_account,
            generate_household_otp,
            join_household_new_member,
            login_existing_entity,
            resolve_session,
        )

        created = create_household_account(
            self.db_path,
            "Auth Test Home",
            "Admin",
            "secret123",
        )
        self.assertTrue(created["session_token"])
        self.assertEqual(len(created["invite_token"]), 32)

        sess = resolve_session(self.db_path, created["session_token"])
        self.assertIsNotNone(sess)
        self.assertEqual(sess["display_name"], "Admin")

        joined = join_household_new_member(
            self.db_path,
            created["invite_token"],
            "Roomie",
            password="secret123",
        )
        self.assertEqual(joined["profile"]["display_name"], "Roomie")

        login = login_existing_entity(
            self.db_path,
            created["invite_token"],
            joined["profile"]["id"],
            password="secret123",
        )
        self.assertNotEqual(login["session_token"], joined["session_token"])

        otp = generate_household_otp(
            self.db_path,
            "Auth Test Home",
            created_by_user_id=created["profile"]["id"],
        )
        self.assertEqual(len(otp["code"]), 6)

    def test_household_export_import_anonymize(self) -> None:
        from domus.household_auth import (
            create_household_account,
            export_household,
            import_household,
            join_household_new_member,
        )
        from domus import db as db_mod

        created = create_household_account(self.db_path, "Export Apt", "Sebastian", "pass1234")
        apt = created["household"]["apartment"]
        admin_id = created["profile"]["id"]
        join_household_new_member(
            self.db_path,
            created["invite_token"],
            "Alex",
            password="pass1234",
        )
        db_mod.add_todo(
            self.db_path,
            "Test task",
            created_by="Sebastian",
            category="general",
            apartment=apt,
            created_by_user_id=admin_id,
        )

        bundle = export_household(
            self.db_path,
            apt,
            anonymize=True,
            requested_by_user_id=admin_id,
        )
        self.assertTrue(bundle["anonymized"])
        self.assertTrue(any(m["display_name"].startswith("Member") for m in bundle["members"]))

        imported = import_household(
            self.db_path,
            bundle,
            "Sebastian",
            "newpass1",
            new_household_name="Export Apt Copy",
        )
        self.assertEqual(imported["profile"]["display_name"], "Sebastian")
        self.assertIn("session_token", imported)

    def test_consolidate_duplicate_household_members(self) -> None:
        from domus.household_auth import (
            consolidate_duplicate_household_members,
            create_device_session,
            create_household_account,
            prune_orphan_users,
        )

        created = create_household_account(self.db_path, "Dup Apt", "Sebastian", "pass1234")
        apt = created["household"]["apartment"]
        keep_id = created["profile"]["id"]
        db.upsert_user_profile(self.db_path, keep_id + 1, "Sebastian")
        now = db.connect(self.db_path)
        with now as conn:
            conn.execute(
                """
                INSERT INTO apartment_members
                    (apartment_label, user_id, role, status, requested_at, joined_at)
                VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (apt, keep_id + 1, "owner", MEMBER_ACTIVE),
            )
        create_device_session(self.db_path, keep_id + 1, apt)
        db.upsert_user_profile(self.db_path, keep_id + 2, "Sebastian")
        prune_orphan_users(self.db_path)

        kept = consolidate_duplicate_household_members(self.db_path, apt)
        self.assertEqual(kept, keep_id + 1)
        payload = apartment_payload(self.db_path, apt)
        self.assertEqual(len(payload["members"]), 1)
        self.assertEqual(payload["members"][0]["display_name"], "Sebastian")

    def test_create_household_rejects_duplicate_name(self) -> None:
        from domus.household_auth import create_household_account

        create_household_account(self.db_path, "Unique Apt", "Sebastian", "pass1234")
        with self.assertRaises(ValueError):
            create_household_account(self.db_path, "Unique Apt", "Alex", "pass5678")


if __name__ == "__main__":
    unittest.main()
