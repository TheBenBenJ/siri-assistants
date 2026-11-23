#!/usr/bin/env python3
"""Offline unit tests for `spoken_dates.py` French date and time parsing/formatting."""

import datetime
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import spoken_dates  # noqa: E402


class TestSpokenDates(unittest.TestCase):
    def setUp(self) -> None:
        # Monday, 23 November 2026
        self.today = datetime.date(2026, 11, 23)

    def test_spoken_date_relative_and_iso(self) -> None:
        self.assertEqual(spoken_dates.spoken_date("2026-12-05", self.today), datetime.date(2026, 12, 5))
        self.assertEqual(spoken_dates.spoken_date("aujourd'hui", self.today), self.today)
        self.assertEqual(spoken_dates.spoken_date("demain", self.today), datetime.date(2026, 11, 24))
        self.assertEqual(spoken_dates.spoken_date("après-demain", self.today), datetime.date(2026, 11, 25))
        self.assertEqual(spoken_dates.spoken_date("la semaine prochaine", self.today), datetime.date(2026, 11, 30))

    def test_spoken_date_weekdays_and_calendar_dates(self) -> None:
        self.assertEqual(spoken_dates.spoken_date("vendredi", self.today), datetime.date(2026, 11, 27))
        # Saying "lundi" on Monday means next Monday (+7 days)
        self.assertEqual(spoken_dates.spoken_date("lundi", self.today), datetime.date(2026, 11, 30))
        self.assertEqual(spoken_dates.spoken_date("3 décembre", self.today), datetime.date(2026, 12, 3))
        self.assertEqual(spoken_dates.spoken_date("1er janvier", self.today), datetime.date(2027, 1, 1))
        self.assertEqual(spoken_dates.spoken_date("15/12", self.today), datetime.date(2026, 12, 15))
        with self.assertRaises(ValueError):
            spoken_dates.spoken_date("n'importe quoi", self.today)

    def test_spoken_moment_and_speech_formatting(self) -> None:
        self.assertEqual(
            spoken_dates.spoken_moment("vendredi à 14h30", self.today),
            (datetime.date(2026, 11, 27), datetime.time(14, 30)),
        )
        self.assertEqual(
            spoken_dates.spoken_moment("demain midi", self.today),
            (datetime.date(2026, 11, 24), datetime.time(12, 0)),
        )
        self.assertEqual(
            spoken_dates.spoken_moment("18h", self.today),
            (self.today, datetime.time(18, 0)),
        )
        self.assertEqual(spoken_dates.say_date(datetime.date(2026, 11, 1)), "dimanche 1er novembre")
        self.assertEqual(spoken_dates.say_date(datetime.date(2026, 11, 27)), "vendredi 27 novembre")
        self.assertEqual(spoken_dates.say_time(datetime.time(9, 0)), "9 h")
        self.assertEqual(spoken_dates.say_time(datetime.time(14, 30)), "14 h 30")


if __name__ == "__main__":
    unittest.main()
