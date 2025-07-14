from mod_browser import Tiso

import json
import os
import time
from datetime import datetime, timedelta

from util.ts import *

import tkinter as tk
from tkinter import ttk

URL = 'http://menlogphost5.menlosystems.local/tisoware/twwebclient'


t=None


def add_treeview( root, records ):
    # Create a Treeview widget for the table
    #column_names = ("Record No", "Date", "Start Time", "End Time", "Project Key", "Comment", "Project Item")
    # list comprehension and string manipulation
    # to extract the field names from the header_info["fields"] list:
    header_info = tw_data["header"]
    column_names = [field.split("(str)")[0].strip() for field in header_info["fields"]]
    tree = ttk.Treeview(root, columns=column_names, show="headings")

    # Define column widths (first 4 narrow, last 3 wide)
    column_widths = [60, 100, 80, 80, 200, 250, 250]

    for col, width in zip(column_names, column_widths):
        tree.heading(col, text=col)
        tree.column(col, width=width)

    # Define the tag with blue foreground
    tree.tag_configure("blue_text", foreground="blue")

    # Insert records into the table
    for record in records:
        # add at the top
        tree.insert("", 0, values=record)

    return tree


def t_login():
    global t
    t=Tiso()

def t_book_time():
    global t
    # http://menlogphost5.menlosystems.local/tisoware/twwebclient#gbuchung
    if(None==t):
        print ("Login firts!")
    else:
        t.open_trans("Buchung")

def t_log_time():
    global t
    global tree
    global tracker
    global records
    if(None==t):
        print ("Login firts!")
    else:
        t.open_trans("Erfassungsmappen")
        timetrack_list = t.read_timetrack_list()
        (earliest, latest) = analyze_timtrack_records(timetrack_list)
        # leave only old records
        records = filter_old_records(timetrack_list, records)

        tw_data["header"]["updated_on"] = get_ts(datetime.now(), fmt=FMT_DATE)
        tw_data["header"]["date range"] = f"{earliest} - {latest}"
        # combine the lists
        tw_data["records"] = records + timetrack_list
        FILENAME_TIMETRACK = "tw_data.json"
        write_timetrack_json( FILENAME_TIMETRACK, tw_data)

        # clear the tree
        for item in tree.get_children():
            tree.delete(item)

        # Insert "old" records into the table in black
        for record in records:
            # add newest at the top
            tree.insert("", 0, values=record)

        for record in timetrack_list:
            # add newest at the top
            tree.insert("", 0, values=record, tags=("blue_text",))

        # resume working in displayed browser
        # will do nothing and return if browse was not executed
        t.update_timetracking( tracker )


def add_toolbar( root ):

    # Toolbar frame
    toolbar = tk.Frame(root)
    toolbar.pack(side="top", fill="x")

    # Add buttons to the toolbar
    btn_login   = tk.Button(toolbar, text="Login" , command=t_login)
    btn_book    = tk.Button(toolbar, text="Book"  , command=t_book_time)
    btn_report  = tk.Button(toolbar, text="Report", command=t_log_time)

    btn_login.pack(side="left", padx=2, pady=2)
    btn_book.pack(side="left", padx=2, pady=2)
    btn_report.pack(side="left", padx=2, pady=2)

# Function to show menu on row click
def show_menu(event):
    item = tree.identify_row(event.y)
    if item:
        tree.selection_set(item)  # Select the clicked row
        menu.post(event.x_root, event.y_root)

def add_menu(root):
    # Create a right-click menu
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Edit", command=lambda: print("Edit selected row"))
    menu.add_command(label="Delete", command=lambda: print("Delete selected row"))
    return menu


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

    print(f"Earliest timestamp: {earliest}")
    print(f"Latest   timestamp: {latest}")

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
    - go through the list of old "records" and remove all records
      which have exactly same date (column "Date") and time (column "Start Time")
      as the records in the "timetrack_list"
    - update the line numbers in the timetrack_list

    So this function only retains the old records from the records.

    Args:
        records - the list of "records" contains outdated information
        timetrack_list - the list of "timetrack_list" contains new information from tisoware
    Return:
        filtered_list - new list - the list which only contains records which are not in the timetrack_list
    """
    # Filter directly within the list comprehension
    filtered_records = [
        r for r in records
        if (r[1], r[2]) not in [(t[1], t[2]) for t in timetrack_list]
    ]
    print ("There are", len(filtered_records), "records after filtering.")
    print ("Adding", len(timetrack_list), "records from timetrack_list.")
    k = len(filtered_records) + 1
    # make continuous row numbering
    for t in timetrack_list:
        t[0] = f"{k:>5}:"  # update row number
        k = k + 1
    return filtered_records

if __name__ == "__main__":
    FILENAME_TIMETRACK = "tw_data.json"
    # option to execute online browsing for tw data
    OPT_UPDATE_DATABASE = False

    tw_data = read_timetrack_json(FILENAME_TIMETRACK)

    # Extract records from JSON structure
    records = tw_data.get("records", [])


    """
    Procedure:
    ----------
    1. Open selenium in GUI mode (no headless) - because need to review input
    2. Run:
       timetrack_list = Tiso.read_timetrack_list()
       # creates list of timetrack entries, some filled and some empty
    3. Load tasks.json database using mod_db
    4. Create tracker = TimeTracking() from mod_timetrack
       execute tracker.tw_report with option empty_project_only=True
    5. Iterate through empty entries, fill in project and subproject part
       and add comment from the timetrack_deviation list
    """
    from mod_db import Database
    db = Database()
    database = db.load_data()

    from mod_timetrack import TimeTracking
    tracker = TimeTracking()
    earliest_date = tracker.tw_report(
        database["task_details"],
        empty_project_only=True
    )
    tracker.print_timetrack_deviation()


    # Check if the file exists
    if not os.path.exists(FILENAME_TIMETRACK):
        print(f"Database '{FILENAME_TIMETRACK}' does not exist.")
    else:
        print(f"Database '{FILENAME_TIMETRACK}' found - will show in GUI")


    # Create the Tkinter window
    root = tk.Tk()
    root.title("Timetracking Records")
    #root.geometry("1200x600")  # Set window size to 800x600 pixels
    # please root window at ("Right Half of Screen")

    # Get screen dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight() - 200

    # Set width to half, height to full
    window_width = screen_width // 2
    window_height = screen_height

    # Position at right half (x = screen_width // 2)
    root.geometry(f"{window_width}x{window_height}+{screen_width // 2}+0")

    tree = add_treeview( root, records )

    menu = add_menu(root)

    # The Tkinter table displaying timetracking records
    # shall have action displaying menu
    # when man clicks any of the table rows
    #
    # Bind right-click action to the table
    tree.bind("<Button-3>", show_menu)  # Right-click (Windows/Linux)
    tree.bind("<Control-Button-1>", show_menu)  # Ctrl+Left-click (Mac)

    # Pack the table into the window
    tree.pack(expand=True, fill="both")

    add_toolbar( root )

    # Run the Tkinter loop
    root.mainloop()

