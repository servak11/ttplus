from mod_browser import Tiso

from mod_timetrack import TimeTracking
from mod_db import Database

import json
import os
import time
from datetime import datetime, timedelta

from util.ts import *

import tkinter as tk
from tkinter import ttk

# starter control
import threading
from web.socket_listener import socket_listener



URL = 'http://menlogphost5.menlosystems.local/tisoware/twwebclient'


"""
This is the Zeiterfassung menu as of 28.01.2026

<ul class="mm-listview">
<li class="mm-listitem">
    <a class="conmenu mm-listitem__text" title="Buchung / Web-Terminal ( PWB )"
       href="#"
       onmousedown="{setValue(&quot;tekeine&quot;,&quot;TimingProtocol&quot;);}"
       onclick="{setValueInForm(&quot;IsReact&quot;,&quot;False&quot;);setValueInForm(&quot;TransID&quot;,&quot;385&quot;); spglNdNew(&quot;TimingProtocol&quot;);;}"
       oncontextmenu="{menuContextMenuShow(&quot;id_menu_con&quot;, event); return false;;}">
            <i class=" fa-light fa-fw fa-sign-in" title="Buchung / Web-Terminal ( PWB )"></i>Buchung / Web-Terminal</a></li>
<li class="mm-listitem"><a class="conmenu mm-listitem__text" title="Erfassungsmappen ( PEM )" href="#" onmousedown="{setValue(&quot;tekeine&quot;,&quot;WorkSheetPortfolio&quot;);}" onclick="{setValueInForm(&quot;IsReact&quot;,&quot;False&quot;);setValueInForm(&quot;TransID&quot;,&quot;151&quot;); spglNdNew(&quot;WorkSheetPortfolio&quot;);;}" oncontextmenu="{menuContextMenuShow(&quot;id_menu_con&quot;, event); return false;;}"><i class=" fa-light fa-fw fa-folder" title="Erfassungsmappen ( PEM )"></i>Erfassungsmappen</a></li>
<li class="mm-listitem"><a class="conmenu mm-listitem__text" title="Jahreskalender ( PAE )" href="#" onmousedown="{setValue(&quot;tekeine&quot;,&quot;Calendar&quot;);}" onclick="{setValueInForm(&quot;IsReact&quot;,&quot;False&quot;);setValueInForm(&quot;TransID&quot;,&quot;54&quot;); spglNdNew(&quot;Calendar&quot;);;}" oncontextmenu="{menuContextMenuShow(&quot;id_menu_con&quot;, event); return false;;}"><i class=" fa-light fa-fw" data-icon="N" title="Jahreskalender ( PAE )">  </i>Jahreskalender</a></li>
<li class="mm-listitem"><a class="conmenu mm-listitem__text" title="Monatsuebersicht ( PST )" href="#" onmousedown="{setValue(&quot;tekeine&quot;,&quot;TimeSheet&quot;);}" onclick="{setValueInForm(&quot;IsReact&quot;,&quot;False&quot;);setValueInForm(&quot;TransID&quot;,&quot;35&quot;); spglNdNew(&quot;TimeSheet&quot;);;}" oncontextmenu="{menuContextMenuShow(&quot;id_menu_con&quot;, event); return false;;}"><i class=" fa-light fa-fw" data-icon="v" title="Monatsuebersicht ( PST )">  </i>Monatsuebersicht</a></li></ul>
"""


# ── Pure helpers (no GUI / no session state) ──────────────────────────────────

# test script to check sanity of the data in the list
def find_unserializable(obj, path="root"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            find_unserializable(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            find_unserializable(item, f"{path}[{i}]")
    elif isinstance(obj, datetime):
        print(f"Unserializable datetime object found at: {path}")


def analyze_timtrack_records(records):
    """
    Loop through the browser timetracking records,
    find and return the range of dates.
    See format of browser.read_timetrack_list() output to find record structure.
    Return: tuple
        (earliest date of records, latest date of records)
    """
    if [] == records:
        print("analyze_timtrack_records: No records to analyze.")
        return (None, None)

    timestamps = []
    for row in records:
        if len(row) < 4:
            print("analyze_timtrack_records: Skipping invalid record:", row)
            continue
        date_str    = row[1] # Example: "Do, 22.05.2025"
        start_time  = row[2] # Example: "06:06"
        end_time    = row[3] # Example: "07:51"

        # Parse date ignoring day name (split by comma and take the second part)
        date_part = date_str[2:]

        # Convert date and time to datetime objects
        # Combine date and time
        format = "%H:%M, %d.%m.%Y"
        start_dt = get_dt( start_time + date_part, format )
        end_dt   = get_dt( end_time   + date_part, format )

        # Add both timestamps to the list
        # .extend() is more efficient when adding multiple items at once
        timestamps.extend([start_dt, end_dt])

    # Find earliest and latest timestamps
    earliest    = min(timestamps)
    latest      = max(timestamps)

    return (earliest, latest)


def read_timetrack_json(jsonfn):
    """read database of timetrack records from json file and return as dictionary"""
    # Check if the file exists
    if os.path.exists(jsonfn):
        # Read the JSON data
        with open(jsonfn, "r", encoding="utf-8") as file:
            return json.load(file)
    else:
        print(f"File '{jsonfn}' does not exist.")
        return {}


def write_timetrack_json(jsonfn, tw_data):
    """write database of timetrack records to json file"""
    with open(jsonfn, "w", encoding="utf-8") as json_file:
        json.dump( tw_data, json_file, indent=2)
    print(f"Timetracking info stored to JSON file '{jsonfn}'")


def filter_old_records( timetrack_list, records):
    """
    Procedure:
    - go through the list of "old" records and remove all records
      which have exactly same date (column "Date") and time (column "Start Time")
      as the records in the "timetrack_list"
    - update the line numbers in the timetrack_list

    So this function only retains the old records from the records.

    Args:
        timetrack_list - new records read online
        records - "old" records read from tw_data.json
    Return:
        filtered_list - "old" records - the list which only contains records which are not in the timetrack_list
    """
    # Filter the "old" list using the list comprehension
    # The old and new (timetrack) lists might overlap.
    # So leave only records which not yet in timetrack_list to color them black (old).

    print(f"filter_old_records():")
    print(f"  ** `old` records: {len(records)}")
    print(f"  ** timetrack_list records: {len(timetrack_list)}")

    for t in timetrack_list:
        print(t, len(t))

    filtered_records = [
        r for r in records
        if (r[1], r[2]) not in [(t[1], t[2]) for t in timetrack_list]
    ]
    k = len(filtered_records) + 1
    # make continuous row numbering
    for t in timetrack_list:
        t[0] = f"{k:>5}:"  # update row number
        k = k + 1
    return filtered_records


# ── BuchenScreen: the Tisoware timetracking applet ────────────────────────────

class BuchenScreen(tk.Toplevel):
    """
    Company timetracking applet (Tisoware / Selenium booking interface).

    Launched from the ttplus tracker as a separate, persistent window
    (a "kind of applet"). It shows the timetracking records read from
    tw_data.json and lets the user log in to Tisoware, book work times,
    and pull the "Erfassungsmappen" report. Deviations are matched against
    the ttplus task details of the currently open project (json_database).

    Why a Toplevel and not a switched screen:
        The Selenium session (self.t) and the single socket listener are
        expensive/awkward to rebuild. Keeping the applet in its own window
        lets the user navigate the main window (Project Manager / tracker)
        without tearing the browser session down.

    Parameters:
        parent:        the long-lived main window (TTPlusWindow).
        json_database: the ttplus project file to match bookings against.
    """

    # A single socket listener per process; started once (see plan section 3.5).
    _socket_started = False
    # The currently open applet, so the socket-triggered booking finds a target.
    _active = None

    DEFAULT_COLUMNS = ("Record No", "Date", "Start Time", "End Time",
                       "Project Key", "Comment", "Project Item")
    FILENAME_TIMETRACK = "tw_data.json"

    def __init__(self, parent, json_database="tasks.json"):
        super().__init__(parent)
        self.title("Timetracking Records")

        self.parent = parent
        # ttplus project whose task details we match bookings against
        self.json_database = json_database

        # Selenium session, created lazily on the first Login click
        self.t = None

        # timetrack records database (from Tisoware) - separate from the project db
        self.tw_data = {}
        if os.path.exists(self.FILENAME_TIMETRACK):
            print(f"Database '{self.FILENAME_TIMETRACK}' found - will show in GUI")
            self.tw_data = Database(self.FILENAME_TIMETRACK).load_data()
        else:
            print(f"Database '{self.FILENAME_TIMETRACK}' does not exist.")
        self.records = self.tw_data.get("records", [])

        self._setup_style()
        self._place_right_half()
        self._build_widgets()

        # register as the active applet and make sure the socket listener runs
        BuchenScreen._active = self
        self._start_socket_listener_once()

        # closing the applet must not close the whole application
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- layout ----

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # dedicated style so we do not clobber the main app's Treeview fonts
        style.configure("Buchen.Treeview", font=("Lucida Console", 9))
        style.configure("Buchen.Treeview.Heading", font=("Lucida Console", 9, "bold"))

    def _place_right_half(self):
        # position the window on the right half of the screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight() - 200
        window_width = screen_width // 2
        window_height = screen_height
        self.geometry(f"{window_width}x{window_height}+{screen_width // 2}+0")

    def _build_widgets(self):
        # toolbar on top, status bar on the bottom, table fills the rest
        self._build_toolbar()

        self.status_var = tk.StringVar(master=self, value="Ready")
        status = tk.Label(self, textvariable=self.status_var,
                          bd=1, relief=tk.SUNKEN, anchor="w")
        status.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree = self._build_treeview()
        self.menu = self._build_context_menu()
        # show a right-click menu when a table row is clicked
        self.tree.bind("<Button-3>", self._show_menu)        # Windows/Linux
        self.tree.bind("<Control-Button-1>", self._show_menu) # Mac
        self.tree.pack(expand=True, fill="both")

    def _build_treeview(self):
        header_info = self.tw_data.get("header", {})
        fields = header_info.get("fields")
        if fields:
            # extract field names from the "name (str)..." header entries
            column_names = [f.split("(str)")[0].strip() for f in fields]
        else:
            column_names = list(self.DEFAULT_COLUMNS)

        tree = ttk.Treeview(self, columns=column_names,
                            show="headings", style="Buchen.Treeview")

        # first 4 columns narrow, last 3 wide
        column_widths = [60, 120, 80, 80, 200, 300, 250]
        for col, width in zip(column_names, column_widths):
            tree.heading(col, text=col)
            tree.column(col, width=width)

        tree.tag_configure("blue_text", foreground="blue")

        # newest at the top
        for record in self.records:
            tree.insert("", 0, values=record)
        return tree

    def _build_context_menu(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Edit", command=lambda: print("Edit selected row"))
        menu.add_command(label="Delete", command=lambda: print("Delete selected row"))
        return menu

    def _show_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)  # select the clicked row
            self.menu.post(event.x_root, event.y_root)

    def _build_toolbar(self):
        toolbar = tk.Frame(self)
        toolbar.pack(side="top", fill="x")
        buttons = (
            ("Login",        self.login),
            ("Home",         self.home),
            ("Book",         self.book_time),
            ("Report",       self.log_time),
            ("See Urlaub",   self.urlaub),
            ("Stempelkarte", self.sk),
        )
        for text, command in buttons:
            tk.Button(toolbar, text=text, command=command).pack(
                side="left", padx=2, pady=2)

    def _log(self, msg):
        print("STATUS:", msg)
        try:
            self.status_var.set(str(msg))
        except Exception:
            pass

    # ---- Tisoware session actions ----

    def login(self):
        if self.t and self.t.is_alive():
            self.t.login()
        else:
            self.t = Tiso()
        self._log("Login requested")

    def _open_trans(self, menu_text):
        """Open a Tisoware menu transaction; returns True on success."""
        if self.t is None:
            self._log("Login first!")
            return False
        try:
            if not self.t.open_trans(menu_text):
                self._log("Sorry cannot open that (normal way)")
                print(self.t.get_driver().current_url)
                return False
        except Exception:
            self._log("Sorry cannot open that (exception) - window was closed")
            return False
        return True

    def home(self):
        """open tisoware user home page"""
        self._open_trans("Home")

    def urlaub(self):
        """open Abwesenheitserfassung / Jahreskalender page"""
        self._open_trans("Jahreskalender")

    def sk(self):
        """open Stempelkarte / Monatsuebersicht page"""
        self._open_trans("Monatsuebersicht")

    def book_time(self):
        """
        Open the Tisoware booking page and inject tblabfrage.js so the
        summary table is appended to the booking table.
        """
        print(">>> book_time() called")
        menu_text = "Buchung / Web-Terminal"  # after 28.01.2026

        if (self.t is None) or (not self.t.is_already_logged_in()):
            self._log("Login first!")
            return

        if not self._open_trans(menu_text):
            return

        d = self.t.get_driver()

        # activate the "getatigte buchungen" (abfrage) tab, then gbuchung,
        # then append the summary table via the injected script
        div = self.t.EW("li_abfrage")
        if div:
            div.click()
        div = self.t.EW("li_gbuchung")
        if div:
            div.click()
            with open("tblabfrage.js", "r") as file:
                js_code = file.read()
            d.execute_script(js_code)

    def log_time(self):
        """
        Main functionality: read the online timetrack records, match them
        against the current ttplus project, store the merged list, and refresh
        the table (old records black, new records blue).
        """
        if self.t is None:
            self._log("Login first!")
            return

        self.t.open_trans("Erfassungsmappen")

        # read records from online database
        timetrack_list = self.t.read_timetrack_list()
        print("timetrack_list:")
        for row in timetrack_list:
            print("  -- " + str(row))

        (earliest, latest) = analyze_timtrack_records(timetrack_list)
        print("Read timetrack_list from date range:")
        print(f"  ** Earliest timestamp: {earliest}")
        print(f"  ** Latest   timestamp: {latest}")

        # match against the currently open ttplus project (not a fixed default)
        db = Database(self.json_database)
        database = db.load_data()
        print(f"Loaded Database '{db.filename}'.")
        d_ttplus_task_details = database["task_details"]
        print(f"Database contains '{len(d_ttplus_task_details)}' detail records.")

        print("Running TW report for online data:")
        report_tracker = TimeTracking()
        report_tracker.tw_report(
            d_ttplus_task_details,
            timetrack_list,
            empty_project_only=True
        )
        report_tracker.print_timetrack_deviation()
        print("*** Done TW report.")

        # leave only "old" records just for display
        self.records = filter_old_records(timetrack_list, self.records)
        print("There are", len(self.records), "records after filtering.")
        print("Adding", len(timetrack_list), "records from timetrack_list.")

        self.tw_data.setdefault("header", {})
        self.tw_data["header"]["updated_on"] = get_ts(datetime.now(), fmt=FMT_DATE)
        self.tw_data["header"]["date range"] = f"{earliest} - {latest}"
        # combine and store the merged list in the json file
        self.tw_data["records"] = self.records + timetrack_list
        write_timetrack_json(self.FILENAME_TIMETRACK, self.tw_data)

        # refresh the table
        for item in self.tree.get_children():
            self.tree.delete(item)
        # "old" records in black (newest on top)
        for record in self.records:
            self.tree.insert("", 0, values=record)
        # "new" records in blue
        for record in timetrack_list:
            self.tree.insert("", 0, values=record, tags=("blue_text",))

        # resume working in the displayed browser (no-op if browser not open)
        self.t.update_timetracking(report_tracker)

    # ---- socket listener (single instance per process) ----

    @classmethod
    def _start_socket_listener_once(cls):
        """
        Start the remote-trigger socket listener exactly once for the whole
        process. The listener is a daemon with a blocking accept loop, so it
        cannot be cleanly stopped; starting it more than once would stack
        threads fighting over the same port. Bookings are dispatched to
        whichever applet is currently open (cls._active).
        """
        if cls._socket_started:
            return
        cls._socket_started = True

        # schedule GUI work on the long-lived main window, not on the applet,
        # so the callback keeps working across applet open/close cycles
        root = cls._active.parent
        cls._socket_status_var = tk.StringVar(master=root, value="socket idle")
        thread = threading.Thread(
            target=socket_listener,
            args=(root, cls._socket_status_var, cls._dispatch_book),
            daemon=True,
        )
        thread.start()
        print("started socket listener thread for BuchenScreen")

    @classmethod
    def _dispatch_book(cls):
        # runs on the Tkinter main thread (socket_listener uses root.after)
        if cls._active is not None:
            cls._active.book_time()
        else:
            print("BuchenScreen: remote booking ignored - applet is closed")

    def _on_close(self):
        if BuchenScreen._active is self:
            BuchenScreen._active = None
        self.destroy()


if __name__ == "__main__":
    # Standalone launch: hide an empty root and show the applet as a Toplevel.
    root = tk.Tk()
    root.withdraw()
    app = BuchenScreen(root, json_database="tasks.json")
    # exit the process when the applet window is closed
    app.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
