"""Behavior checks for import escaping, time zones and generated operations. MIT."""
import json
import sqlite3
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from airport_sample.fetch import ROOT
from airport_sample.generate import build, sql_literal, timestamp
from airport_sample.validate import validate


class SampleTests(unittest.TestCase):
    def test_sql_preserves_source_characters(self):
        db = sqlite3.connect(":memory:")
        for value in ["O'Hare", "back\\slash", "空港\nsecond line", '"Quoted", comma', "x'); DROP TABLE airport; --"]:
            self.assertEqual(db.execute("SELECT " + sql_literal(value)).fetchone()[0], value)
        self.assertIsNone(db.execute("SELECT " + sql_literal("")).fetchone()[0])

    def test_dst_and_international_date_line(self):
        la = ZoneInfo("America/Los_Angeles")
        self.assertEqual(timestamp(datetime(2026, 3, 8, 9, 30, tzinfo=timezone.utc).astimezone(la)), "2026-03-08 01:30:00")
        self.assertEqual(timestamp(datetime(2026, 3, 8, 10, 30, tzinfo=timezone.utc).astimezone(la)), "2026-03-08 03:30:00")
        self.assertEqual(timestamp(datetime(2026, 1, 1, 16, 0, tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Tokyo"))), "2026-01-02 01:00:00")

    def test_small_snapshot_integrity(self):
        result = validate(ROOT / "data/source", ROOT / "data/small")
        self.assertEqual(result["result"], "passed")

    def test_reproducible_and_reject_overbooking(self):
        config = json.loads((ROOT / "config/small.json").read_text())
        config.update(flight_count=20, days=3, passenger_count=30, bookings_per_flight=3)
        first = build(ROOT / "data/source", config)
        second = build(ROOT / "data/source", config)
        self.assertEqual(first, second)
        self.assertEqual(len(first["flight"]), 20)
        self.assertEqual(len(first["booking"]), 60)
        config["bookings_per_flight"] = 181
        with self.assertRaises(ValueError):
            build(ROOT / "data/source", config)


if __name__ == "__main__":
    unittest.main()
