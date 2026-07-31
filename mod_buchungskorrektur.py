"""Automate Buchungskorrektur posting to Tisoware via REST API.

Reads work entries from markdown log, maps project codes to activities,
and posts them to Tisoware's Buchungskorrektur workflow.
"""

import json
import re
import sys
import importlib.util
from datetime import datetime, date
from getpass import getpass
from pathlib import Path
from typing import NamedTuple, Optional
from configparser import ConfigParser

RED = "\033[31m"
BOLD = "\033[1m"
OFF = "\033[0m"

# Tisoware's AJAX save reply, per toSaveIn() in wf.workflow.js: an empty body
# or "OK!" means saved; otherwise the body splits on "!#!" and the part after
# the separator decides -- a page name (e.g. "wf_my") means saved, an empty
# part means the server raised a warning and wrote nothing until the request
# is repeated with wrnnflg=true. No separator at all is a hard error.
SEPARATOR = "!#!"

def load_http_client():
    """Load tisobridge.http_client without triggering main.py import."""
    http_client_path = Path.home() / 'tisobridge' / 'tisobridge' / 'http_client.py'
    spec = importlib.util.spec_from_file_location("_http_client_module", http_client_path)
    http_client = importlib.util.module_from_spec(spec)
    sys.modules['_http_client_module'] = http_client
    spec.loader.exec_module(http_client)
    return http_client

PROD_URL = "http://menlogphost5.menlosystems.local/tisoware/twwebclient"

# tisobridge is only needed to talk to the server. Keep the import failure
# recoverable so the parsing and overlap logic stays importable (and
# testable) on a machine without it.
try:
    http_client = load_http_client()
    TisoClient = http_client.TisoClient
    Booking = http_client.Booking
    PROD_URL = http_client.PROD_URL
    TISOBRIDGE_ERROR = None
except Exception as e:
    http_client = None
    TisoClient = None
    Booking = None
    TISOBRIDGE_ERROR = e

ALLG_PATTERN = r"[Aa]llg"
ENTWICKLUNG_PATTERN = r"[Ee]ntw"

# "Bemerkung zum Antrag" on the Buchungskorrektur form.
ANTRAG_INFO = "Nachbuchung"

HEADER_WIDTH = 70


class LogEntry(NamedTuple):
    date: date
    from_time: str
    to_time: str
    project: str
    comment: str


PROJECT_ACTIVITY_MAP = {
    "9300_2026": "65.10",
    "Allg. Aufgaben 2026": "10.10",
    "9567_AQURA": "54.10",
}


def parse_log_file(path: Path) -> list[LogEntry]:
    """Parse markdown log in format: 07 DD.MM HH:MM - DD.MM HH:MM :Project: Comment"""
    entries = []
    pattern = re.compile(
        r'(\d+)\s+'
        r'(\d+)\.(\d+)\s+(\d+):(\d+)\s+-\s+'
        r'(\d+)\.(\d+)\s+(\d+):(\d+)\s+'
        r':([^:]+):\s*(.+)'
    )

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            m = pattern.match(line)
            if not m:
                continue

            month, start_d, start_m, start_h, start_min, \
            end_d, end_m, end_h, end_min, project, comment = m.groups()

            year = 2026
            month = int(month)
            start_date = date(year, month, int(start_d))

            entries.append(LogEntry(
                date=start_date,
                from_time=f"{start_h}:{start_min}",
                to_time=f"{end_h}:{end_min}",
                project=project.strip(),
                comment=comment.strip(),
            ))

    return entries


def group_by_date(entries: list[LogEntry]) -> dict[date, list[LogEntry]]:
    """Group entries by date."""
    grouped = {}
    for entry in entries:
        if entry.date not in grouped:
            grouped[entry.date] = []
        grouped[entry.date].append(entry)
    return grouped


def classify_save_response(body: str) -> tuple[str, str]:
    """Map a save reply onto ("saved" | "warning" | "error", message).

    Mirrors toSaveIn() in wf.workflow.js; see SEPARATOR above.
    """
    body = body.strip()
    if body == "" or body == "OK!":
        return "saved", body
    if SEPARATOR not in body:
        return "error", body
    message, _, tail = body.partition(SEPARATOR)
    if tail.strip() in ("", "1"):
        return "warning", message.strip()
    return "saved", message.strip()


def save_bookings(client: TisoClient, bookings: list, info: str,
                  force: bool = False):
    """Post the save AJAX. force=True replays the JS toSaveIn(1) path, i.e.
    "Dennoch speichern?" answered with yes.

    Reimplemented here rather than calling client.save_bookings() because
    that one hardcodes wrnnflg=false and so can never clear a warning.
    """
    if client.page is None:
        raise RuntimeError("no page state; call open_buchung_edit() first")
    if client.page.fields.get("fld") != "wf_newdata":
        raise RuntimeError(
            f"expected fld=wf_newdata (booking-edit form), got"
            f" {client.page.fields.get('fld')!r}"
        )
    default_cc = ""
    m = re.search(r"CC=([^!]+)", client.page.fields.get("Default", ""))
    if m:
        default_cc = m.group(1)

    overrides = {
        "ajax": "ajax",
        "sbm": "save",
        "wrnnflg": "true" if force else "false",
        "confirmedChange": "false",
        "actFeld": "Comment",
        "inf": info,
        "cntbchngntmgdvr": str(len(bookings)),
        "aRwtbldocu": "0",
    }
    for i, b in enumerate(bookings):
        overrides[f"tbl{i}"] = json.dumps(b.to_row(i, default_cc))
    return client._submit_form_ajax(overrides)


class Aborted(Exception):
    """Ctrl-C or Ctrl-D at a prompt. Unwinds to main() for a clean exit."""


def ask(prompt: str) -> str:
    """input() that turns Ctrl-C / Ctrl-D into Aborted instead of a traceback."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise Aborted() from None


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def day_minutes(entries: list[LogEntry]) -> int:
    return sum(to_minutes(e.to_time) - to_minutes(e.from_time)
               for e in entries)


def format_day_header(date_str: str, count: int, minutes: int) -> str:
    """Day banner with the total right-aligned to the rule below it."""
    left = f"Date: {date_str} ({count} entries)"
    right = f"TOTAL: {to_hhmm(minutes)}"
    pad = max(1, HEADER_WIDTH - len(left) - len(right))
    return f"{left}{' ' * pad}{right}"


def find_overlaps(entries: list[LogEntry]) -> list[tuple[int, int]]:
    """Index pairs (i, j) in a start-sorted list where entry i runs past the
    start of entry j. Tisoware rejects these with "Die Buchung bis X
    ueberlappt die Buchung ab Y"."""
    pairs = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if to_minutes(entries[j].from_time) < to_minutes(entries[i].to_time):
                pairs.append((i, j))
    return pairs


def print_day_entries(entries: list[LogEntry], flagged: set[int]):
    for idx, e in enumerate(entries):
        span = to_minutes(e.to_time) - to_minutes(e.from_time)
        line = (f"  [{idx}] {e.from_time}-{e.to_time} ({span / 60:.2f}h) "
                f"{e.project:20} {e.comment}")
        print(f"{RED}{line}{OFF}" if idx in flagged else line)


def align_earlier_end(entries: list[LogEntry]) -> tuple[list[LogEntry], list[str]]:
    """Pull the earlier booking's end back to the later one's start, so the
    earlier entry gives up the overlapping minutes."""
    out = list(entries)
    notes = []
    for i, j in find_overlaps(out):
        new_end = out[j].from_time
        if to_minutes(new_end) <= to_minutes(out[i].from_time):
            notes.append(f"cannot shorten [{i}]: {out[i].from_time}-"
                         f"{out[i].to_time} would collapse, drop one instead")
            continue
        notes.append(f"[{i}] end {out[i].to_time} -> {new_end}")
        out[i] = out[i]._replace(to_time=new_end)
    return sorted(out, key=lambda e: to_minutes(e.from_time)), notes


def align_later_start(entries: list[LogEntry]) -> tuple[list[LogEntry], list[str]]:
    """Push the later booking's start forward to the earlier one's end, so the
    later entry gives up the overlapping minutes."""
    out = list(entries)
    notes = []
    for i, j in find_overlaps(out):
        new_start = out[i].to_time
        if to_minutes(new_start) >= to_minutes(out[j].to_time):
            notes.append(f"cannot shift [{j}]: {out[j].from_time}-"
                         f"{out[j].to_time} would collapse, drop one instead")
            continue
        notes.append(f"[{j}] start {out[j].from_time} -> {new_start}")
        out[j] = out[j]._replace(from_time=new_start)
    return sorted(out, key=lambda e: to_minutes(e.from_time)), notes


def resolve_overlaps(entries: list[LogEntry]) -> Optional[list[LogEntry]]:
    """Interactively clear overlaps. Returns the adjusted entries, or None to
    skip the day."""
    while True:
        overlaps = find_overlaps(entries)
        if not overlaps:
            return entries

        flagged = {i for pair in overlaps for i in pair}
        print(f"\n{BOLD}{len(overlaps)} overlap(s) -- Tisoware will refuse"
              f" these:{OFF}")
        for i, j in overlaps:
            cut = to_minutes(entries[i].to_time) - to_minutes(entries[j].from_time)
            print(f"  {RED}[{i}] ends {entries[i].to_time} but [{j}] starts"
                  f" {entries[j].from_time} ({cut} min){OFF}")
        print()
        print_day_entries(entries, flagged)

        i, j = overlaps[0]
        print(f"\n  1 = align down: end of the earlier entry"
              f" -> {entries[j].from_time} (shortens it)")
        print(f"  2 = align up:   start of the later entry"
              f" -> {entries[i].to_time} (shortens it)")
        print("  d = drop an entry")
        print("  s = skip this day")
        choice = ask("Choose [1/2/d/s]: ").lower()

        if choice == "s":
            return None

        if choice in ("1", "2"):
            entries, notes = (align_earlier_end(entries) if choice == "1"
                              else align_later_start(entries))
            for note in notes:
                print(f"  {note}")
            continue

        if choice == "d":
            raw = ask("  index to drop: ")
            if not raw.isdigit() or int(raw) >= len(entries):
                print("  no such index")
                continue
            dropped = entries[int(raw)]
            print(f"  dropping {dropped.from_time}-{dropped.to_time}"
                  f" {dropped.comment}")
            entries = entries[:int(raw)] + entries[int(raw) + 1:]
            continue

        print("  please answer 1, 2, d or s")


def get_activity_pattern(project: str) -> str:
    """Get activity search pattern for a project."""
    if project in PROJECT_ACTIVITY_MAP:
        return PROJECT_ACTIVITY_MAP[project]
    return ALLG_PATTERN


def post_bookings_for_date(
    client: TisoClient,
    trans_name: str,
    date_obj: date,
    entries: list[LogEntry],
    dry_run: bool = False,
    info: str = ANTRAG_INFO,
) -> bool:
    """Post all bookings for a single date. Returns True if successful."""
    date_str = date_obj.strftime("%d.%m.%Y")
    entries = sorted(entries, key=lambda e: to_minutes(e.from_time))
    logged_minutes = day_minutes(entries)

    print(f"\n{'=' * HEADER_WIDTH}")
    print(format_day_header(date_str, len(entries), logged_minutes))
    print('=' * HEADER_WIDTH)

    entries = resolve_overlaps(entries)
    if entries is None:
        print("Day skipped")
        return False

    # A saved Antrag ends the workflow and leaves the session on wf_my (the
    # "Wollen Sie einen weiteren Antrag anlegen?" state). Re-enter the
    # Buchungskorrektur transaction first, which is what clicking "Ja" does,
    # otherwise open_buchung_edit posts a spent form and save refuses.
    try:
        client.navigate(trans_name)
        client.open_buchung_edit(date_str)
    except Exception as e:
        print(f"Error opening date {date_str}: {e}")
        return False

    resolved = []
    for entry in entries:
        try:
            activity_pattern = get_activity_pattern(entry.project)
            aid, alabel = client.resolve_activity(
                entry.project,
                activity_pattern,
                ALLG_PATTERN,
                ENTWICKLUNG_PATTERN,
            )
            resolved.append((entry, aid, alabel))
            print(f"  {entry.from_time}-{entry.to_time} "
                  f"{entry.project!r:20} {aid:>4} {alabel!r:30} {entry.comment!r}")
        except Exception as e:
            print(f"  ERROR resolving {entry.project}: {e}")
            return False

    if not resolved:
        print("No entries to post")
        return False

    final_minutes = day_minutes(entries)
    if final_minutes != logged_minutes:
        print(f"  {'TOTAL: ' + to_hhmm(final_minutes):>{HEADER_WIDTH - 2}}"
              f"  (was {to_hhmm(logged_minutes)} as logged)")

    bookings = [
        Booking(
            from_time=e.from_time,
            to_time=e.to_time,
            project=e.project,
            activity=aid,
            comment=e.comment,
        )
        for e, aid, _ in resolved
    ]

    if dry_run:
        print(f"\n--dry-run: not saving {len(bookings)} booking(s)")
        return True

    confirm = ask(f"\nSave {len(bookings)} booking(s)? [y/N] ").lower()
    if confirm not in ("y", "yes", "j", "ja"):
        print("Skipped")
        return False

    try:
        resp = save_bookings(client, bookings, info)
        status, message = classify_save_response(resp.text)
        print(f"\nServer replied ({resp.status_code}): {resp.text.strip()[:200]!r}")

        if status == "warning":
            # Nothing was written yet; the server wants the toSaveIn(1) reply.
            print(f"\n{BOLD}Server warning -- NOT saved yet:{OFF}")
            print(f"  {message}")
            again = ask("Save anyway? [y/N] ").lower()
            if again not in ("y", "yes", "j", "ja"):
                print("NOT SAVED")
                return False
            resp = save_bookings(client, bookings, info, force=True)
            status, message = classify_save_response(resp.text)
            print(f"Server replied ({resp.status_code}):"
                  f" {resp.text.strip()[:200]!r}")

        if status == "saved":
            print("SAVED")
            return True

        print(f"FAILED: {message}")
        return False
    except Exception as e:
        print(f"Save error: {e}")
        return False


def load_credentials() -> tuple[Optional[str], Optional[str]]:
    """Load Tisoware credentials from ~/.tisobridge.conf or user input."""
    config = ConfigParser()
    config.read(Path.home() / ".tisobridge.conf")

    user = None
    password = None

    if config.has_section("default"):
        section = config["default"]
        user = section.get("user")
        password = section.get("password")

    if not user:
        user = ask("Tisoware username: ")
    if not password:
        try:
            password = getpass("Tisoware password: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise Aborted() from None

    return user, password


def main(
    log_path: Path,
    start_date: Optional[date] = None,
    dry_run: bool = False,
    url: str = PROD_URL,
):
    """Parse log and post Buchungskorrektur entries to Tisoware."""
    print(f"Reading log from {log_path}...")
    entries = parse_log_file(log_path)

    if not entries:
        print("No entries found in log")
        return

    grouped = group_by_date(entries)

    if start_date is None:
        start_date = min(grouped.keys())

    dates_to_post = sorted([d for d in grouped.keys() if d >= start_date])
    print(f"Found {len(entries)} entries across {len(grouped)} dates")
    print(f"Will post {len(dates_to_post)} date(s) starting from {start_date}")

    if dry_run:
        print("\n[DRY-RUN] Showing entries without posting...")
        client = None
    else:
        if TisoClient is None:
            print(f"Error: cannot load tisobridge ({TISOBRIDGE_ERROR}).")
            print("Posting needs ~/tisobridge plus 'requests' and"
                  " 'beautifulsoup4'; --dry-run works without it.")
            return
        user, password = load_credentials()
        print(f"\nLogging in as {user!r} against {url}...")
        client = TisoClient(base_url=url)
        try:
            client.login(user, password)
            # Resolve the menu entry once, from the welcome page that carries
            # menujson; later pages are re-entered via navigate(trans_name).
            trans_name = client.page.trans_name_for("Buchungskorrektur")
            if trans_name is None:
                print("Error: 'Buchungskorrektur' not found in the menu")
                return
        except Exception as e:
            print(f"Login error: {e}")
            return

    success_count = 0
    overlap_days = []
    saved_days = []
    aborted_on = None
    for position, d in enumerate(dates_to_post):
        if dry_run:
            rows = sorted(grouped[d], key=lambda e: to_minutes(e.from_time))
            overlaps = find_overlaps(rows)
            flagged = {i for pair in overlaps for i in pair}
            if overlaps:
                overlap_days.append(d)

            print(f"\n{'=' * HEADER_WIDTH}")
            print(format_day_header(d.strftime('%d.%m.%Y'), len(rows),
                                    day_minutes(rows)))
            print('=' * HEADER_WIDTH)

            for idx, entry in enumerate(rows):
                activity_pattern = get_activity_pattern(entry.project)
                duration = (to_minutes(entry.to_time)
                            - to_minutes(entry.from_time)) / 60

                line = (f"  {entry.from_time}-{entry.to_time} ({duration:.2f}h) "
                        f"{entry.project!r:20} [activity: {activity_pattern!r}]")
                print(f"{RED}{line}{OFF}" if idx in flagged else line)
                print(f"    Comment: {entry.comment!r}")

            for i, j in overlaps:
                print(f"  {RED}OVERLAP: ends {rows[i].to_time} but next starts"
                      f" {rows[j].from_time} -- Tisoware will refuse this{OFF}")
            success_count += 1
        else:
            try:
                if post_bookings_for_date(client, trans_name, d, grouped[d],
                                          dry_run=dry_run):
                    success_count += 1
                    saved_days.append(d)
            except (Aborted, KeyboardInterrupt):
                aborted_on = dates_to_post[position:]
                break

    if not dry_run:
        print(f"\n{'=' * HEADER_WIDTH}")
        if aborted_on:
            print("Interrupted.")
        if saved_days:
            print(f"Saved {len(saved_days)} day(s): "
                  + ", ".join(d.strftime("%d.%m") for d in saved_days))
        else:
            print("Nothing was saved.")

        remaining = aborted_on if aborted_on else [
            d for d in dates_to_post if d not in saved_days]
        if remaining:
            print(f"Not saved: "
                  + ", ".join(d.strftime("%d.%m") for d in remaining))
            print(f"Resume with: python3 {Path(sys.argv[0]).name}"
                  f" --from {remaining[0].strftime('%d.%m.%Y')}")
        return

    if dry_run:
        print(f"\n{'='*70}")
        print(f"Processed {success_count}/{len(dates_to_post)} date(s)")

        total_hours = 0
        for d in dates_to_post:
            for entry in grouped[d]:
                total_hours += (to_minutes(entry.to_time)
                                - to_minutes(entry.from_time)) / 60

        print(f"Total hours across all days: {total_hours:.1f}h")
        if overlap_days:
            days = ", ".join(d.strftime("%d.%m") for d in overlap_days)
            print(f"{RED}Overlaps on: {days}"
                  f" -- these need 1/2/d/s on the real run{OFF}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Post Buchungskorrektur entries from markdown log to Tisoware"
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path.home() / "ttplus" / "ml-test" / "2026-July" / "2026-July.md",
        help="Path to markdown log file",
    )
    parser.add_argument(
        "--from",
        type=lambda s: datetime.strptime(s, "%d.%m.%Y").date(),
        dest="start_date",
        default=None,
        help="Start date (dd.mm.yyyy), default: first entry",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview and exit without saving",
    )
    parser.add_argument(
        "--url",
        default=PROD_URL,
        help=f"Tisoware URL (default: {PROD_URL})",
    )

    args = parser.parse_args()
    try:
        main(args.log, args.start_date, args.dry_run, args.url)
    except (Aborted, KeyboardInterrupt):
        # Anything the day loop did not already report (Ctrl-C at the login
        # prompt, or between days).
        print("\nAborted, nothing further was sent.")
        sys.exit(130)
