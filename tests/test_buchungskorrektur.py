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

    def test_skip_on_k_returns_none_without_raising(self):
        days = M.group_by_date(M.parse_log_file(LOG))
        rows = sorted(days[date(2026, 7, 23)],
                      key=lambda e: M.to_minutes(e.from_time))
        with mock.patch("builtins.input", return_value="k"):
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


# --------------------------------------------------------------------------
# tasks.json input (August 2026)
#
# DB is a frozen copy of bring_up_tasks.json as brought in from home, so
# editing the live database cannot change these results. It carries the three
# data faults that the markdown log never had:
#
#   1. "Friday task pleaceholder / Planner" rows -- padding entered on
#      Thursday, which would double-count the real Friday work.
#   2. 13.08 11:45-11:33, an entry recorded backwards.
#   3. 18.08 (10:42) and 19.08 (11:00), days over the 10 h Tisoware limit.
# --------------------------------------------------------------------------

DB = Path(__file__).resolve().parent / "data" / "bring_up_tasks.json"


class TestParseJson(unittest.TestCase):
    def setUp(self):
        self.raw = M.parse_json_file(DB)
        self.entries = M.drop_ignored(self.raw)
        self.days = M.group_by_date(self.entries)

    def test_reads_every_detail_row(self):
        self.assertEqual(len(self.raw), 138)

    def test_timestamps_become_hhmm(self):
        e = next(e for e in self.entries if e.date == date(2026, 8, 4))
        self.assertEqual((e.from_time, e.to_time), ("06:10", "11:45"))

    def test_date_comes_from_the_start_timestamp(self):
        self.assertIn(date(2026, 8, 24), self.days)

    def test_no_row_spans_midnight(self):
        # to_time is read as a wall clock, so a cross-day row would silently
        # lose its date part.
        for e in self.entries:
            self.assertGreaterEqual(M.to_minutes(e.to_time) + 24 * 60,
                                    M.to_minutes(e.from_time))

    def test_project_comes_from_the_task_name(self):
        e = next(e for e in self.entries
                 if e.task == "#19183 canopen-bootloader")
        self.assertEqual(e.project, "9567_AQURA")

    def test_every_mapped_project_has_an_activity(self):
        for project in M.TASK_PROJECT_MAP.values():
            self.assertIn(project, M.PROJECT_ACTIVITY_MAP)

    def test_suffix_picks_the_json_parser(self):
        self.assertEqual(len(M.load_entries(DB)), len(self.raw))

    def test_suffix_picks_the_markdown_parser(self):
        self.assertEqual(len(M.load_entries(LOG)), 54)


class TestCommentFormat(unittest.TestCase):
    def test_task_prefix_then_description(self):
        self.assertEqual(
            M.build_comment("#19118 MWUBC Bias Controller Firmware",
                            "build the xplained MWUBC variant"),
            "#19118 MWUBC/build the xplained MWUBC variant")

    def test_prefix_is_capped(self):
        got = M.build_comment("x" * 40, "d")
        self.assertEqual(got, "x" * M.TASK_NAME_PREFIX + "/d")

    def test_prefix_does_not_keep_a_trailing_space(self):
        # "#19118 MWUBC Bias..."[:13] ends on a space; it would read as
        # "#19118 MWUBC /..." with the separator hanging off it.
        self.assertNotIn(" /", M.build_comment("#19118 MWUBC Bias", "d"))

    def test_short_task_name_is_untouched(self):
        self.assertEqual(M.build_comment("Meetings", "planning KW33"),
                         "Meetings/planning KW33")

    def test_json_entries_carry_the_combined_comment(self):
        entries = M.drop_ignored(M.parse_json_file(DB))
        e = next(e for e in entries
                 if e.date == date(2026, 8, 13) and e.task == "Meetings")
        self.assertEqual(e.comment, "Meetings/planning KW33")


class TestIgnoredTasks(unittest.TestCase):
    def setUp(self):
        self.raw = M.parse_json_file(DB)
        self.entries = M.drop_ignored(self.raw)

    def test_placeholder_rows_are_dropped(self):
        self.assertEqual(len(self.raw) - len(self.entries), 6)

    def test_nothing_ignored_survives(self):
        for e in self.entries:
            self.assertNotIn(e.task, M.IGNORED_TASKS)

    def test_the_parser_still_returns_them(self):
        # They must reach the caller so an emptied day can be reported
        # instead of vanishing.
        self.assertTrue(any(e.task in M.IGNORED_TASKS for e in self.raw))

    def test_14_august_is_left_with_nothing(self):
        emptied = set(M.group_by_date(self.raw)) - set(
            M.group_by_date(self.entries))
        self.assertIn(date(2026, 8, 14), emptied)

    def test_markdown_entries_are_never_ignored(self):
        entries = M.parse_log_file(LOG)
        self.assertEqual(len(M.drop_ignored(entries)), len(entries))


class TestUnmapped(unittest.TestCase):
    def test_reports_task_names_with_no_project(self):
        entries = M.drop_ignored(M.parse_json_file(DB))
        self.assertEqual(M.find_unmapped(entries),
                         {"Setup Raspbery Pi fwpi": 2,
                          "Infrastructure Issues": 1})

    def test_august_range_is_fully_mapped(self):
        # The two unmapped names are July-only, so posting 01.08-24.08 must
        # not stop on them.
        entries = [e for e in M.drop_ignored(M.parse_json_file(DB))
                   if date(2026, 8, 1) <= e.date <= date(2026, 8, 24)]
        self.assertEqual(M.find_unmapped(entries), {})

    def test_mapped_entries_are_not_reported(self):
        self.assertEqual(M.find_unmapped(M.parse_log_file(LOG)), {})


class TestInvertedEntries(unittest.TestCase):
    def setUp(self):
        self.entries = M.drop_ignored(M.parse_json_file(DB))
        self.days = M.group_by_date(self.entries)

    def day(self, d):
        return sorted(self.days[d], key=lambda e: M.to_minutes(e.from_time))

    def test_finds_the_backwards_entry_on_13_august(self):
        rows = self.day(date(2026, 8, 13))
        self.assertEqual(M.find_inverted(rows), [1])
        self.assertEqual((rows[1].from_time, rows[1].to_time),
                         ("11:45", "11:33"))

    def test_only_two_backwards_entries_in_the_whole_database(self):
        found = [e for e in self.entries
                 if M.to_minutes(e.to_time) < M.to_minutes(e.from_time)]
        self.assertEqual(sorted(e.date for e in found),
                         [date(2026, 7, 15), date(2026, 8, 13)])

    def test_a_normal_day_has_none(self):
        self.assertEqual(M.find_inverted(self.day(date(2026, 8, 4))), [])

    def test_zero_length_entry_is_not_inverted(self):
        rows = [M.LogEntry(date(2026, 8, 1), "09:00", "09:00", "P", "a")]
        self.assertEqual(M.find_inverted(rows), [])

    def test_swap_clears_it(self):
        rows = self.day(date(2026, 8, 13))
        fixed, _ = M.swap_inverted(rows)
        self.assertEqual(M.find_inverted(fixed), [])

    def test_swap_reads_the_times_the_other_way_round(self):
        rows = self.day(date(2026, 8, 13))
        fixed, _ = M.swap_inverted(rows)
        e = next(e for e in fixed if e.task == "Meetings")
        self.assertEqual((e.from_time, e.to_time), ("11:33", "11:45"))

    def test_swap_keeps_every_entry(self):
        rows = self.day(date(2026, 8, 13))
        self.assertEqual(len(M.swap_inverted(rows)[0]), len(rows))

    def test_swap_makes_the_day_total_positive(self):
        rows = self.day(date(2026, 8, 13))
        fixed, _ = M.swap_inverted(rows)
        self.assertEqual(M.day_minutes(fixed), M.day_minutes(rows) + 24)

    def test_swap_reports_what_it_changed(self):
        _, notes = M.swap_inverted(self.day(date(2026, 8, 13)))
        self.assertEqual(notes, ["[1] 11:45-11:33 -> 11:33-11:45"])

    def test_swap_output_stays_sorted(self):
        fixed, _ = M.swap_inverted(self.day(date(2026, 8, 13)))
        starts = [M.to_minutes(e.from_time) for e in fixed]
        self.assertEqual(starts, sorted(starts))

    def test_resolve_swaps_on_1(self):
        rows = self.day(date(2026, 8, 13))
        with mock.patch.object(M, "ask", side_effect=["1"]):
            out = M.resolve_inverted(rows)
        self.assertEqual(M.find_inverted(out), [])

    def test_resolve_skips_on_k(self):
        rows = self.day(date(2026, 8, 13))
        with mock.patch.object(M, "ask", side_effect=["k"]):
            self.assertIsNone(M.resolve_inverted(rows))

    def test_resolve_drops_on_d(self):
        rows = self.day(date(2026, 8, 13))
        with mock.patch.object(M, "ask", side_effect=["d", "1"]):
            out = M.resolve_inverted(rows)
        self.assertEqual(len(out), len(rows) - 1)
        self.assertEqual(M.find_inverted(out), [])

    def test_a_clean_day_never_prompts(self):
        rows = self.day(date(2026, 8, 4))
        with mock.patch.object(M, "ask",
                               side_effect=AssertionError("prompted")):
            self.assertEqual(M.resolve_inverted(rows), rows)

    def test_resolve_propagates_the_abort(self):
        rows = self.day(date(2026, 8, 13))
        with mock.patch.object(M, "ask", side_effect=M.Aborted):
            with self.assertRaises(M.Aborted):
                M.resolve_inverted(rows)


class TestOverDayLimit(unittest.TestCase):
    def setUp(self):
        self.entries = M.drop_ignored(M.parse_json_file(DB))
        self.days = M.group_by_date(self.entries)

    def day(self, d):
        return sorted(self.days[d], key=lambda e: M.to_minutes(e.from_time))

    def test_limit_is_ten_hours(self):
        self.assertEqual(M.MAX_DAY_MINUTES, 600)

    def test_18_and_19_august_are_over(self):
        over = [d for d in sorted(self.days)
                if date(2026, 8, 1) <= d <= date(2026, 8, 24)
                and M.day_minutes(self.days[d]) > M.MAX_DAY_MINUTES]
        self.assertEqual(over, [date(2026, 8, 18), date(2026, 8, 19)])

    def test_totals_match_the_audit(self):
        self.assertEqual(M.to_hhmm(M.day_minutes(self.days[date(2026, 8, 18)])),
                         "10:42")
        self.assertEqual(M.to_hhmm(M.day_minutes(self.days[date(2026, 8, 19)])),
                         "11:00")

    def test_trim_brings_the_day_to_the_limit(self):
        fixed, _ = M.trim_from_end(self.day(date(2026, 8, 19)))
        self.assertEqual(M.day_minutes(fixed), M.MAX_DAY_MINUTES)

    def test_trim_only_touches_the_latest_entries(self):
        rows = self.day(date(2026, 8, 19))
        fixed, _ = M.trim_from_end(rows)
        # 60 min to cut: [7] runs 45 min and goes entirely, the remaining
        # 15 come off the end of [6]. Everything earlier is untouched.
        self.assertEqual(fixed[:6], rows[:6])
        self.assertEqual(fixed[-1].to_time, "16:30")

    def test_trim_cascades_past_a_too_short_last_entry(self):
        rows = self.day(date(2026, 8, 19))
        fixed, _ = M.trim_from_end(rows)
        self.assertEqual(len(fixed), len(rows) - 1)

    def test_trim_reports_what_it_changed(self):
        _, notes = M.trim_from_end(self.day(date(2026, 8, 19)))
        self.assertEqual(notes, ["[7] 16:45-17:30 dropped (-45 min)",
                                 "[6] end 16:45 -> 16:30 (-15 min)"])

    def test_trim_shortens_without_dropping_when_it_fits(self):
        rows = self.day(date(2026, 8, 18))
        fixed, notes = M.trim_from_end(rows)
        self.assertEqual(len(fixed), len(rows))
        self.assertEqual(notes, ["[1] end 17:48 -> 17:06 (-42 min)"])
        self.assertEqual(M.day_minutes(fixed), M.MAX_DAY_MINUTES)

    def test_trim_leaves_a_day_under_the_limit_alone(self):
        rows = self.day(date(2026, 8, 4))
        fixed, notes = M.trim_from_end(rows)
        self.assertEqual(fixed, rows)
        self.assertEqual(notes, [])

    def test_trim_skips_zero_length_entries(self):
        # 19.08 opens with 06:06-06:06, which has nothing to give up.
        fixed, _ = M.trim_from_end(self.day(date(2026, 8, 19)))
        self.assertEqual((fixed[0].from_time, fixed[0].to_time),
                         ("06:06", "06:06"))

    def test_trim_never_inverts_an_entry(self):
        fixed, _ = M.trim_from_end(self.day(date(2026, 8, 19)))
        self.assertEqual(M.find_inverted(fixed), [])

    def test_resolve_trims_on_1(self):
        rows = self.day(date(2026, 8, 19))
        with mock.patch.object(M, "ask", side_effect=["1"]):
            out = M.resolve_over_limit(rows)
        self.assertEqual(M.day_minutes(out), M.MAX_DAY_MINUTES)

    def test_resolve_skips_on_k(self):
        rows = self.day(date(2026, 8, 19))
        with mock.patch.object(M, "ask", side_effect=["k"]):
            self.assertIsNone(M.resolve_over_limit(rows))

    def test_resolve_drops_on_d(self):
        rows = self.day(date(2026, 8, 18))
        with mock.patch.object(M, "ask", side_effect=["d", "0"]):
            out = M.resolve_over_limit(rows)
        self.assertEqual(len(out), len(rows) - 1)
        self.assertLessEqual(M.day_minutes(out), M.MAX_DAY_MINUTES)

    def test_a_day_under_the_limit_never_prompts(self):
        rows = self.day(date(2026, 8, 4))
        with mock.patch.object(M, "ask",
                               side_effect=AssertionError("prompted")):
            self.assertEqual(M.resolve_over_limit(rows), rows)

    def test_resolve_propagates_the_abort(self):
        rows = self.day(date(2026, 8, 19))
        with mock.patch.object(M, "ask", side_effect=M.Aborted):
            with self.assertRaises(M.Aborted):
                M.resolve_over_limit(rows)


class TestDropEntry(unittest.TestCase):
    def rows(self):
        return [M.LogEntry(date(2026, 8, 1), "09:00", "10:00", "P", "a"),
                M.LogEntry(date(2026, 8, 1), "10:00", "11:00", "P", "b")]

    def test_removes_the_named_index(self):
        with mock.patch.object(M, "ask", side_effect=["0"]):
            out = M.drop_entry(self.rows())
        self.assertEqual([e.comment for e in out], ["b"])

    def test_out_of_range_changes_nothing(self):
        rows = self.rows()
        with mock.patch.object(M, "ask", side_effect=["9"]):
            self.assertEqual(M.drop_entry(rows), rows)

    def test_non_numeric_changes_nothing(self):
        rows = self.rows()
        with mock.patch.object(M, "ask", side_effect=["x"]):
            self.assertEqual(M.drop_entry(rows), rows)


class TestAugustOverlaps(unittest.TestCase):
    def test_overlap_days_in_range(self):
        days = M.group_by_date(M.drop_ignored(M.parse_json_file(DB)))
        found = [d for d in sorted(days)
                 if date(2026, 8, 1) <= d <= date(2026, 8, 24)
                 and M.find_overlaps(
                     sorted(days[d], key=lambda e: M.to_minutes(e.from_time)))]
        self.assertEqual(found, [date(2026, 8, 3), date(2026, 8, 10),
                                 date(2026, 8, 11), date(2026, 8, 21),
                                 date(2026, 8, 24)])


class TestDayDelta(unittest.TestCase):
    def test_short_day_is_negative_and_bad(self):
        self.assertEqual(M.day_delta(5 * 60 + 55), ("-02:05", True))

    def test_normal_day_is_positive_and_fine(self):
        self.assertEqual(M.day_delta(9 * 60 + 54), ("+01:54", False))

    def test_exactly_eight_hours_is_fine(self):
        self.assertEqual(M.day_delta(8 * 60), ("+00:00", False))

    def test_exactly_ten_hours_is_still_fine(self):
        # The limit is what Tisoware refuses to exceed, not to reach.
        self.assertEqual(M.day_delta(10 * 60), ("+02:00", False))

    def test_one_minute_over_ten_hours_is_bad(self):
        self.assertEqual(M.day_delta(10 * 60 + 1), ("+02:01", True))

    def test_one_minute_under_eight_hours_is_bad(self):
        self.assertEqual(M.day_delta(8 * 60 - 1), ("-00:01", True))


class TestDayFlags(unittest.TestCase):
    def setUp(self):
        self.days = M.group_by_date(M.drop_ignored(M.parse_json_file(DB)))

    def flags(self, d):
        return M.day_flags(self.days[d])

    def test_clean_day(self):
        self.assertEqual(self.flags(date(2026, 8, 4)), ["clean"])

    def test_overlap_day(self):
        self.assertEqual(self.flags(date(2026, 8, 3)), ["overlap"])

    def test_backwards_day(self):
        self.assertEqual(self.flags(date(2026, 8, 13)), ["backwards"])

    def test_hours_are_not_reported_as_a_repair(self):
        # 19.08 runs 11:00; that belongs in the vs-8h column, not here.
        self.assertEqual(self.flags(date(2026, 8, 19)), ["clean"])

    def test_short_day_is_not_reported_as_a_repair(self):
        self.assertEqual(self.flags(date(2026, 8, 12)), ["clean"])

    def test_backwards_is_listed_before_overlap(self):
        rows = [M.LogEntry(date(2026, 8, 1), "09:00", "12:00", "P", "a"),
                M.LogEntry(date(2026, 8, 1), "11:00", "10:00", "P", "b")]
        self.assertEqual(M.day_flags(rows), ["backwards", "overlap"])


class TestContainment(unittest.TestCase):
    """A meeting logged while a longer task was still running. Neither align
    direction fits: option 1 throws away the time after the meeting, option 2
    would collapse the meeting."""

    def setUp(self):
        # 24.08 as it was posted: 21:09-21:20 sits inside 21:07-22:00.
        self.rows = [
            M.LogEntry(date(2026, 8, 24), "20:51", "21:07", "P", "c3"),
            M.LogEntry(date(2026, 8, 24), "21:07", "22:00", "P", "soak"),
            M.LogEntry(date(2026, 8, 24), "21:09", "21:20", "P", "confirm"),
        ]

    def test_containment_is_detected(self):
        self.assertIn((1, 2), M.find_contained(self.rows))

    def test_touching_entries_are_not_containment(self):
        self.assertNotIn((0, 1), M.find_contained(self.rows))

    def test_identical_spans_are_not_containment(self):
        rows = [M.LogEntry(date(2026, 8, 1), "09:00", "10:00", "P", "a"),
                M.LogEntry(date(2026, 8, 1), "09:00", "10:00", "P", "b")]
        self.assertEqual(M.find_contained(rows), [])

    def test_align_up_refuses_the_enclosed_entry(self):
        _, notes = M.align_later_start(self.rows)
        self.assertTrue(any("would collapse" in n for n in notes))

    def test_split_keeps_the_enclosing_time(self):
        out, _ = M.split_around(self.rows, 1, 2)
        spans = [(e.from_time, e.to_time) for e in out]
        self.assertIn(("21:07", "21:09"), spans)
        self.assertIn(("21:20", "22:00"), spans)

    def test_split_clears_the_overlap(self):
        out, _ = M.split_around(self.rows, 1, 2)
        self.assertEqual(M.find_overlaps(out), [])

    def test_split_loses_only_the_inner_minutes(self):
        out, _ = M.split_around(self.rows, 1, 2)
        self.assertEqual(M.day_minutes(self.rows) - M.day_minutes(out), 11)

    def test_split_keeps_the_inner_entry_untouched(self):
        out, _ = M.split_around(self.rows, 1, 2)
        self.assertIn(("21:09", "21:20"), [(e.from_time, e.to_time) for e in out])

    def test_split_drops_an_empty_half(self):
        # Inner starts exactly where outer does, so there is no leading half.
        rows = [M.LogEntry(date(2026, 8, 1), "09:00", "11:00", "P", "outer"),
                M.LogEntry(date(2026, 8, 1), "09:00", "10:00", "P", "inner")]
        out, notes = M.split_around(rows, 0, 1)
        self.assertEqual(len(out), 2)
        self.assertTrue(any("one half was empty" in n for n in notes))

    def test_split_refuses_when_the_inner_is_not_inside(self):
        # Would otherwise extend the outer entry to reach it, booking time
        # that was never worked.
        rows = [M.LogEntry(date(2026, 8, 1), "09:00", "10:00", "P", "a"),
                M.LogEntry(date(2026, 8, 1), "14:00", "15:00", "P", "b")]
        out, notes = M.split_around(rows, 0, 1)
        self.assertEqual(out, rows)
        self.assertIn("is not", notes[0])

    def test_split_never_extends_the_outer_entry(self):
        out, _ = M.split_around(self.rows, 1, 2)
        halves = [e for e in out if e.comment == "soak"]
        for h in halves:
            self.assertGreaterEqual(M.to_minutes(h.from_time),
                                    M.to_minutes(self.rows[1].from_time))
            self.assertLessEqual(M.to_minutes(h.to_time),
                                 M.to_minutes(self.rows[1].to_time))

    def test_split_output_stays_sorted(self):
        out, _ = M.split_around(self.rows, 1, 2)
        starts = [M.to_minutes(e.from_time) for e in out]
        self.assertEqual(starts, sorted(starts))


class TestMoveEntry(unittest.TestCase):
    """Relocating a record whole, the repair align cannot do."""

    def setUp(self):
        self.rows = [
            M.LogEntry(date(2026, 8, 24), "20:51", "21:07", "P", "c3"),
            M.LogEntry(date(2026, 8, 24), "21:07", "22:00", "P", "soak"),
            M.LogEntry(date(2026, 8, 24), "21:09", "21:20", "P", "confirm"),
        ]

    def test_moves_behind_the_anchor(self):
        out, _ = M.move_after(self.rows, 2, 1)
        moved = next(e for e in out if e.comment == "confirm")
        self.assertEqual((moved.from_time, moved.to_time), ("22:00", "22:11"))

    def test_keeps_the_duration(self):
        out, _ = M.move_after(self.rows, 2, 1)
        moved = next(e for e in out if e.comment == "confirm")
        span = M.to_minutes(moved.to_time) - M.to_minutes(moved.from_time)
        self.assertEqual(span, 11)

    def test_day_total_is_unchanged(self):
        out, _ = M.move_after(self.rows, 2, 1)
        self.assertEqual(M.day_minutes(out), M.day_minutes(self.rows))

    def test_clears_the_containment(self):
        out, _ = M.move_after(self.rows, 2, 1)
        self.assertEqual(M.find_contained(out), [])

    def test_never_inverts(self):
        out, _ = M.move_after(self.rows, 2, 1)
        self.assertEqual(M.find_inverted(out), [])

    def test_keeps_every_entry(self):
        out, _ = M.move_after(self.rows, 2, 1)
        self.assertEqual(len(out), len(self.rows))

    def test_leaves_the_other_entries_alone(self):
        out, _ = M.move_after(self.rows, 2, 1)
        spans = [(e.from_time, e.to_time) for e in out]
        self.assertIn(("20:51", "21:07"), spans)
        self.assertIn(("21:07", "22:00"), spans)

    def test_reports_what_it_changed(self):
        _, notes = M.move_after(self.rows, 2, 1)
        self.assertIn("21:09-21:20 -> 22:00-22:11", notes[0])
        self.assertIn("11 min kept", notes[0])

    def test_output_stays_sorted(self):
        out, _ = M.move_after(self.rows, 2, 1)
        starts = [M.to_minutes(e.from_time) for e in out]
        self.assertEqual(starts, sorted(starts))

    def test_refuses_to_run_past_midnight(self):
        rows = [M.LogEntry(date(2026, 8, 1), "23:00", "23:50", "P", "a"),
                M.LogEntry(date(2026, 8, 1), "23:30", "23:59", "P", "b")]
        out, notes = M.move_after(rows, 1, 0)
        self.assertEqual(out, rows)
        self.assertIn("past midnight", notes[0])

    def test_prompt_moves_on_two_indices(self):
        with mock.patch.object(M, "ask", side_effect=["2", "1"]):
            out = M.move_entry(self.rows)
        self.assertEqual(M.find_contained(out), [])

    def test_prompt_rejects_an_entry_after_itself(self):
        with mock.patch.object(M, "ask", side_effect=["1", "1"]):
            self.assertEqual(M.move_entry(self.rows), self.rows)

    def test_prompt_rejects_a_bad_index(self):
        with mock.patch.object(M, "ask", side_effect=["9"]):
            self.assertEqual(M.move_entry(self.rows), self.rows)

    def test_resolve_offers_move(self):
        with mock.patch.object(M, "ask", side_effect=["m", "2", "1"]):
            out = M.resolve_overlaps(self.rows)
        self.assertEqual(M.find_overlaps(out), [])
        self.assertEqual(M.day_minutes(out), M.day_minutes(self.rows))

    def test_resolve_offers_split(self):
        with mock.patch.object(M, "ask", side_effect=["s"]):
            out = M.resolve_overlaps(self.rows)
        self.assertEqual(M.find_overlaps(out), [])
