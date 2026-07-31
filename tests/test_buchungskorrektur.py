"""Regression tests for mod_buchungskorrektur.

Input is tests/data/2026-July.md, a frozen copy of the July 2026 log that
exposed both bugs found while posting it:

  1. Every day after the first failed to save, because a finished Antrag
     leaves the session on wf_my and the next day was opened without
     re-entering the transaction.
  2. Overlapping bookings came back as a "Dennoch speichern?" warning that
     was misread as success, so days silently went unbooked.

Run:  python3 -m unittest discover -s tests
"""

import io
import unittest
from unittest import mock
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mod_buchungskorrektur as M

LOG = Path(__file__).resolve().parent / "data" / "2026-July.md"


class TestParseLog(unittest.TestCase):
    def setUp(self):
        self.entries = M.parse_log_file(LOG)
        self.days = M.group_by_date(self.entries)

    def test_parses_every_booking_line(self):
        self.assertEqual(len(self.entries), 54)
        self.assertEqual(len(self.days), 9)

    def test_covers_21_to_31_july_skipping_weekends(self):
        self.assertEqual(
            sorted(self.days),
            [date(2026, 7, d) for d in (21, 22, 23, 24, 27, 28, 29, 30, 31)],
        )

    def test_reads_project_code_from_between_the_colons(self):
        first = sorted(self.entries, key=lambda e: (e.date, e.from_time))[0]
        self.assertEqual(first.date, date(2026, 7, 21))
        self.assertEqual(first.from_time, "06:04")
        self.assertEqual(first.to_time, "07:23")
        self.assertEqual(first.project, "9300_2026")
        self.assertIn("update the migagen", first.comment)

    def test_only_known_projects_appear(self):
        self.assertEqual(
            {e.project for e in self.entries},
            {"9300_2026", "9567_AQURA", "Allg. Aufgaben 2026"},
        )

    def test_every_project_maps_to_an_activity_pattern(self):
        for project in {e.project for e in self.entries}:
            self.assertIn(project, M.PROJECT_ACTIVITY_MAP)

    def test_single_digit_hour_is_accepted(self):
        # "31.07 6:00 - 31.07 8:00" is written without a leading zero.
        july31 = self.days[date(2026, 7, 31)]
        self.assertIn("6:00", [e.from_time for e in july31])

    def test_no_entry_ends_before_it_starts(self):
        for e in self.entries:
            self.assertLessEqual(
                M.to_minutes(e.from_time), M.to_minutes(e.to_time),
                f"{e.date} {e.from_time}-{e.to_time}",
            )


class TestDayTotals(unittest.TestCase):
    # Totals as logged, before any overlap correction.
    EXPECTED = {
        21: 7.75, 22: 10.03, 23: 9.12, 24: 8.03, 27: 6.50,
        28: 8.95, 29: 9.88, 30: 8.82, 31: 8.50,
    }

    def test_hours_per_day(self):
        days = M.group_by_date(M.parse_log_file(LOG))
        for day, expected in self.EXPECTED.items():
            rows = days[date(2026, 7, day)]
            total = sum(M.to_minutes(e.to_time) - M.to_minutes(e.from_time)
                        for e in rows) / 60
            self.assertAlmostEqual(total, expected, places=2,
                                   msg=f"{day}.07")


class TestOverlapDetection(unittest.TestCase):
    """The two days Tisoware rejected, and only those two."""

    def setUp(self):
        self.days = M.group_by_date(M.parse_log_file(LOG))

    def sorted_day(self, day):
        return sorted(self.days[date(2026, 7, day)],
                      key=lambda e: M.to_minutes(e.from_time))

    def test_exactly_two_days_overlap(self):
        flagged = [d for d in sorted(self.days)
                   if M.find_overlaps(sorted(self.days[d],
                                             key=lambda e: M.to_minutes(e.from_time)))]
        self.assertEqual(flagged, [date(2026, 7, 23), date(2026, 7, 24)])

    def test_23_july_overlap_matches_server_message(self):
        # "Die Buchung bis 10:09 ueberlappt die Buchung ab 09:09."
        rows = self.sorted_day(23)
        self.assertEqual(M.find_overlaps(rows), [(2, 3)])
        self.assertEqual(rows[2].to_time, "10:09")
        self.assertEqual(rows[3].from_time, "09:09")

    def test_24_july_overlap_matches_server_message(self):
        # "Die Buchung bis 13:25 ueberlappt die Buchung ab 13:11."
        rows = self.sorted_day(24)
        self.assertEqual(M.find_overlaps(rows), [(1, 2)])
        self.assertEqual(rows[1].to_time, "13:25")
        self.assertEqual(rows[2].from_time, "13:11")

    def test_touching_bookings_are_not_overlaps(self):
        # 24.07 has 13:26-14:11 straight after 13:11-13:26.
        rows = self.sorted_day(24)
        self.assertEqual(rows[2].to_time, rows[3].from_time)
        self.assertNotIn((2, 3), M.find_overlaps(rows))

    def test_zero_length_bookings_are_not_overlaps(self):
        # 24.07 logs several instants, e.g. 20:20-20:20.
        rows = self.sorted_day(24)
        instants = [e for e in rows if e.from_time == e.to_time]
        self.assertTrue(instants)
        for i, e in enumerate(rows):
            for j, f in enumerate(rows):
                if i < j and e.from_time == e.to_time:
                    self.assertNotIn((i, j), M.find_overlaps(rows))


class TestAlignDown(unittest.TestCase):
    """Option 1: pull the earlier booking's end back to the later start."""

    def setUp(self):
        days = M.group_by_date(M.parse_log_file(LOG))
        self.rows = sorted(days[date(2026, 7, 23)],
                           key=lambda e: M.to_minutes(e.from_time))
        self.out, self.notes = M.align_earlier_end(self.rows)

    def test_clears_the_overlap(self):
        self.assertEqual(M.find_overlaps(self.out), [])

    def test_only_the_earlier_end_moves(self):
        self.assertEqual(self.out[2].to_time, "09:09")
        self.assertEqual(self.out[2].from_time, self.rows[2].from_time)
        self.assertEqual(self.out[3], self.rows[3])

    def test_keeps_every_entry(self):
        self.assertEqual(len(self.out), len(self.rows))

    def test_reduces_the_day_total_by_the_overlap(self):
        self.assertEqual(M.day_minutes(self.rows) - M.day_minutes(self.out), 60)

    def test_reports_what_it_changed(self):
        self.assertEqual(self.notes, ["[2] end 10:09 -> 09:09"])

    def test_refuses_to_collapse_an_entry(self):
        # Later entry starts before the earlier one does: nothing to pull back.
        rows = [
            M.LogEntry(date(2026, 7, 1), "09:00", "10:00", "P", "a"),
            M.LogEntry(date(2026, 7, 1), "09:00", "11:00", "P", "b"),
        ]
        out, notes = M.align_earlier_end(rows)
        self.assertEqual(out, rows)
        self.assertIn("cannot shorten", notes[0])


class TestAlignUp(unittest.TestCase):
    """Option 2: push the later booking's start out to the earlier end."""

    def setUp(self):
        days = M.group_by_date(M.parse_log_file(LOG))
        self.rows = sorted(days[date(2026, 7, 23)],
                           key=lambda e: M.to_minutes(e.from_time))
        self.out, self.notes = M.align_later_start(self.rows)

    def test_clears_the_overlap(self):
        self.assertEqual(M.find_overlaps(self.out), [])

    def test_only_the_later_start_moves(self):
        self.assertEqual(self.out[3].from_time, "10:09")
        self.assertEqual(self.out[3].to_time, self.rows[3].to_time)
        self.assertEqual(self.out[2], self.rows[2])

    def test_keeps_every_entry(self):
        self.assertEqual(len(self.out), len(self.rows))

    def test_reduces_the_day_total_by_the_overlap(self):
        self.assertEqual(M.day_minutes(self.rows) - M.day_minutes(self.out), 60)

    def test_reports_what_it_changed(self):
        self.assertEqual(self.notes, ["[3] start 09:09 -> 10:09"])

    def test_refuses_to_collapse_an_entry(self):
        # Later entry sits entirely inside the earlier one.
        rows = [
            M.LogEntry(date(2026, 7, 1), "09:00", "12:00", "P", "a"),
            M.LogEntry(date(2026, 7, 1), "10:00", "11:00", "P", "b"),
        ]
        out, notes = M.align_later_start(rows)
        self.assertEqual(out, rows)
        self.assertIn("cannot shift", notes[0])


class TestAlignBothDirections(unittest.TestCase):
    """Either option is a valid fix; they differ in which entry pays."""

    def setUp(self):
        days = M.group_by_date(M.parse_log_file(LOG))
        self.rows = sorted(days[date(2026, 7, 24)],
                           key=lambda e: M.to_minutes(e.from_time))

    def test_both_clear_the_overlap(self):
        for out, _ in (M.align_earlier_end(self.rows),
                       M.align_later_start(self.rows)):
            self.assertEqual(M.find_overlaps(out), [])

    def test_both_cost_the_same_minutes(self):
        down, _ = M.align_earlier_end(self.rows)
        up, _ = M.align_later_start(self.rows)
        self.assertEqual(M.day_minutes(down), M.day_minutes(up))
        self.assertEqual(M.day_minutes(self.rows) - M.day_minutes(down), 14)

    def test_they_charge_different_entries(self):
        down, _ = M.align_earlier_end(self.rows)
        up, _ = M.align_later_start(self.rows)
        self.assertEqual(down[1].to_time, "13:11")   # 12:30-13:25 shortened
        self.assertEqual(up[2].from_time, "13:25")   # 13:11-13:26 shortened
        self.assertNotEqual(down[1], up[1])

    def test_output_stays_sorted_by_start(self):
        for out, _ in (M.align_earlier_end(self.rows),
                       M.align_later_start(self.rows)):
            starts = [M.to_minutes(e.from_time) for e in out]
            self.assertEqual(starts, sorted(starts))


class TestSaveResponse(unittest.TestCase):
    """Bodies captured from the live server during the July run."""

    SAVED = ("Der Antrag wurde übernommen."
             " Wollen Sie einen weiteren Antrag anlegen?!#!wf_my")
    WARN_23 = ("Die Buchung bis 10:09 überlappt  \ndie Buchung ab"
               " 09:09.\n\nDennoch speichern?!#!")
    WARN_24 = ("Die Buchung bis 13:25 überlappt  \ndie Buchung ab"
               " 13:11.\n\nDennoch speichern?!#!")

    def test_page_name_after_separator_means_saved(self):
        self.assertEqual(M.classify_save_response(self.SAVED)[0], "saved")

    def test_empty_body_means_saved(self):
        self.assertEqual(M.classify_save_response("")[0], "saved")
        self.assertEqual(M.classify_save_response("OK!")[0], "saved")

    def test_overlap_warning_is_not_reported_as_saved(self):
        # The original bug: these were printed as OK and the day was lost.
        for body in (self.WARN_23, self.WARN_24):
            status, message = M.classify_save_response(body)
            self.assertEqual(status, "warning")
            self.assertIn("Dennoch speichern?", message)

    def test_clipboard_warning_flag_is_a_warning_too(self):
        self.assertEqual(M.classify_save_response("Etwas?!#!1")[0], "warning")

    def test_body_without_separator_is_an_error(self):
        status, message = M.classify_save_response(
            "Fehler: psnr = 0 ist unzulässig")
        self.assertEqual(status, "error")
        self.assertIn("psnr", message)

    def test_warning_strips_the_separator_from_the_message(self):
        self.assertNotIn("!#!", M.classify_save_response(self.WARN_23)[1])


class TestDayHeader(unittest.TestCase):
    """Day banner carries the total, right-aligned to the rule below it."""

    def test_total_is_flush_with_the_rule(self):
        header = M.format_day_header("24.07.2026", 11, 482)
        self.assertEqual(len(header), M.HEADER_WIDTH)
        self.assertTrue(header.endswith("TOTAL: 08:02"))

    def test_keeps_the_date_and_count_on_the_left(self):
        header = M.format_day_header("24.07.2026", 11, 482)
        self.assertTrue(header.startswith("Date: 24.07.2026 (11 entries)"))

    def test_total_is_hours_and_minutes_not_decimal(self):
        # 8.03h as a decimal, but 08:02 on the clock.
        self.assertIn("08:02", M.format_day_header("24.07.2026", 11, 482))

    def test_over_ten_hours_stays_two_digits(self):
        self.assertTrue(
            M.format_day_header("22.07.2026", 8, 602).endswith("TOTAL: 10:02"))

    def test_long_left_side_still_leaves_a_gap(self):
        header = M.format_day_header("22.07.2026", 1234567, 60)
        self.assertIn(" TOTAL: 01:00", header)

    def test_matches_the_logged_day_totals(self):
        days = M.group_by_date(M.parse_log_file(LOG))
        header = M.format_day_header(
            "24.07.2026", 11, M.day_minutes(days[date(2026, 7, 24)]))
        self.assertTrue(header.endswith("TOTAL: 08:02"))


class TestPrompts(unittest.TestCase):
    """Ctrl-C / Ctrl-D at a prompt must unwind cleanly, not traceback."""

    def setUp(self):
        # resolve_overlaps prints the day; keep it out of the test output.
        patcher = mock.patch("sys.stdout", new=io.StringIO())
        self.stdout = patcher.start()
        self.addCleanup(patcher.stop)

    def test_ctrl_c_raises_aborted(self):
        with mock.patch("builtins.input", side_effect=KeyboardInterrupt):
            with self.assertRaises(M.Aborted):
                M.ask("Choose [1/2/d/s]: ")

    def test_ctrl_d_raises_aborted(self):
        with mock.patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(M.Aborted):
                M.ask("Choose [1/2/d/s]: ")

    def test_aborted_does_not_chain_the_original(self):
        # "raise ... from None" keeps the traceback quiet for the user.
        with mock.patch("builtins.input", side_effect=KeyboardInterrupt):
            try:
                M.ask("x")
            except M.Aborted as exc:
                self.assertIsNone(exc.__cause__)

    def test_answer_is_stripped(self):
        with mock.patch("builtins.input", return_value="  2 \n"):
            self.assertEqual(M.ask("x"), "2")

    def test_overlap_prompt_propagates_the_abort(self):
        days = M.group_by_date(M.parse_log_file(LOG))
        rows = sorted(days[date(2026, 7, 23)],
                      key=lambda e: M.to_minutes(e.from_time))
        with mock.patch("builtins.input", side_effect=KeyboardInterrupt):
            with self.assertRaises(M.Aborted):
                M.resolve_overlaps(rows)

    def test_skip_returns_none_without_raising(self):
        days = M.group_by_date(M.parse_log_file(LOG))
        rows = sorted(days[date(2026, 7, 23)],
                      key=lambda e: M.to_minutes(e.from_time))
        with mock.patch("builtins.input", return_value="s"):
            self.assertIsNone(M.resolve_overlaps(rows))

    def test_a_clean_day_never_prompts(self):
        days = M.group_by_date(M.parse_log_file(LOG))
        rows = sorted(days[date(2026, 7, 21)],
                      key=lambda e: M.to_minutes(e.from_time))
        with mock.patch("builtins.input", side_effect=AssertionError("prompted")):
            self.assertEqual(M.resolve_overlaps(rows), rows)


class TestTimeHelpers(unittest.TestCase):
    def test_roundtrip(self):
        for text in ("00:00", "6:00", "09:09", "23:59"):
            self.assertEqual(M.to_hhmm(M.to_minutes(text)),
                             text.zfill(5))

    def test_minutes(self):
        self.assertEqual(M.to_minutes("00:00"), 0)
        self.assertEqual(M.to_minutes("13:11"), 791)


if __name__ == "__main__":
    unittest.main(verbosity=2)
