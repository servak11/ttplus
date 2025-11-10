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

URL = 'http://menlogphost5.menlosystems.local/tisoware/twwebclient'


t=None


# test script to check sanity of the data in the list 
def find_unserializable(obj, path="root"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            find_unserializable(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            find_unserializable(item, f"{path}[{i}]")
    elif isinstance(obj, datetime):
        print(f"❌ Unserializable datetime object found at: {path}")



def add_treeview( root, records ):
    # Create a Treeview widget for the table
    #column_names = ("Record No", "Date", "Start Time", "End Time", "Project Key", "Comment", "Project Item")
    # list comprehension and string manipulation
    # to extract the field names from the header_info["fields"] list:
    header_info = tw_data["header"]
    column_names = [field.split("(str)")[0].strip() for field in header_info["fields"]]
    tree = ttk.Treeview(root, columns=column_names, show="headings")

    # Define column widths (first 4 narrow, last 3 wide)
    column_widths = [60, 120, 80, 80, 200, 300, 250]

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
    """
    booking page consists of 3 tabs "reiters"
    - buchung 
    - gbuchung
    - abfrage 

    <div class="tab-pane pl-3 abfrage reiter" role="tabpanel" id="abfrage" aria-expanded="false"><container>
    ...
    </container></div>
    active reiter has class "active" to the list
    """
    global t
    # http://menlogphost5.menlosystems.local/tisoware/twwebclient#gbuchung
    if(None==t):
        print ("Login first!")
    else:
        try:
            if not t.open_trans("Buchung"):
                print ("Sorry cannot open that (normal way) from:")
                print(t.get_driver().current_url)
                return
        except Exception as e:
            print ("Sorry cannot open that (except way) from:")
            print(t.get_driver().current_url)
            print(e)
            return

        d = t.get_driver()

        # Find the element by ID
        # and Remove the 'active' class using JavaScript from buchung
        # and Use JavaScript to add the "active" class to gbuchung and abfrage
        # and this way we see all needed info -- but not the bookign button right?
        # 
        # To display only the two tables (tblgetBuch and tblabfrage)
        # inside the container <div class="navcontainer">,
        # and overwrite any other content inside that container using Selenium,
        # use JavaScript injection via execute_script.
        # 
        #div = t.get_byid("buchung")
        #d.execute_script("arguments[0].classList.remove('active');", div)
        # 
        # activete getatigte buchungen
        div = t.get_byid("li_abfrage")
        div.click()
        div = t.get_byid("li_gbuchung")
        div.click()
        #table = t.E("tblabfrage")
        ##d.execute_script("document.getElementById('tblabfrage').style.display = 'block';")
        js_code = ""
        # run JavaScript read from file to append summary table at the end
        with open('tblabfrage.js', 'r') as file:
            js_code = file.read()
        d.execute_script(js_code)


def t_log_time():
    """
    This is the main application functionality: log work time (timetrack)
    The time logging happens when I log on and log off in the booking page, 
    and therefore the times are stored in the tool

    1. read_timetrack_list() from the tool in the browser

    2. Prepare to Display the log records in GUI (filter_old_records)
       - the older records ware loaded into d_tw_data_records (black color)
       - the new records found in brower will display in blue

    3. update_timetracking( tracker )
       - the 
    """
    global t
    global tree
    ##global tracker
    global tw_data
    # records read from tw_data.json
    global d_tw_data_records
    if(None==t):
        print ("Login firts!")
    else:
        t.open_trans("Erfassungsmappen")
        # read records from online database
        timetrack_list = t.read_timetrack_list()
        print(f"timetrack_list:")
        debug_flag = 0
        if debug_flag:
            for row in timetrack_list:
                print("  -- " + str(row))
        # get scope of dates from online records
        (earliest, latest) = analyze_timtrack_records(timetrack_list)
        print ("Read timetrack_list from date range:")
        print(f"  ** Earliest timestamp: {earliest}")
        print(f"  ** Latest   timestamp: {latest}")

        db = Database()
        database = db.load_data()
        print(f"Loaded Database '{db.filename}'.")
        d_ttplus_task_details = database["task_details"]
        print(f"Database contains '{len(d_ttplus_task_details)}' detail records.")

        print("Running TW report for online data:")
        report_tracker = TimeTracking()
        earliest_date = report_tracker.tw_report(
            d_ttplus_task_details,
            timetrack_list,
            empty_project_only=True
        )
        report_tracker.print_timetrack_deviation()
        print("Done TW report.")


        # leave only "old" records just for display
        d_tw_data_records = filter_old_records(timetrack_list, d_tw_data_records)
        if debug_flag:
            print ("There are", len(d_tw_data_records), "records after filtering.")
            print ("Adding", len(timetrack_list), "records from timetrack_list.")


        tw_data["header"]["updated_on"] = get_ts(datetime.now(), fmt=FMT_DATE)
        tw_data["header"]["date range"] = f"{earliest} - {latest}"
        # combine the lists


        tw_data["records"] = d_tw_data_records + timetrack_list
        FILENAME_TIMETRACK = "tw_data.json"
        write_timetrack_json( FILENAME_TIMETRACK, tw_data)

        # clear the tree in GUI
        for item in tree.get_children():
            tree.delete(item)

        # Insert "old" records into the table in black
        for record in d_tw_data_records:
            # add newest at the top
            tree.insert("", 0, values=record)

        # Insert "new" records into the table in blue
        for record in timetrack_list:
            # add newest at the top
            tree.insert("", 0, values=record, tags=("blue_text",))

        # resume working in displayed browser
        # will do nothing and return if browse was not executed
        # the tracker. deviation information conains the notes to log work
        t.update_timetracking( report_tracker )


        # tracker does not work
        # shall
        # 1. load ttplus, filter by dates (earliest, latest)
        # 2. calc deviation between ttplus and timetrack
        # 3. loop through deviation and find closest for every row
        # 4. write to row
        # 5. write to tw_data (update)

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
    # check
    #find_unserializable(tw_data["records"], path="tw_data")
    if 1:
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

if __name__ == "__main__":
    FILENAME_TIMETRACK = "tw_data.json"
    # option to execute online browsing for tw data
    OPT_UPDATE_DATABASE = False

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

    tw_data = {}
    # Check if the file exists
    if not os.path.exists(FILENAME_TIMETRACK):
        print(f"Database '{FILENAME_TIMETRACK}' does not exist.")
    else:
        print(f"Database '{FILENAME_TIMETRACK}' found - will show in GUI")
        tracker_db = Database(FILENAME_TIMETRACK)
        tw_data = tracker_db.load_data()

    # Extract records from JSON structure
    d_tw_data_records = tw_data.get("records", [])

    if 0:
        tracker = TimeTracking()
        print("Running TW report:")
        #find_unserializable(tw_data["records"][1], path="tw_data")
        earliest_date = tracker.tw_report(
            d_ttplus_task_details,
            d_tw_data_records,
            empty_project_only=True
        )
        tracker.print_timetrack_deviation()
        print("Done TW report.")
        #find_unserializable(tw_data["records"][1], path="tw_data")


    # Create the Tkinter window
    root = tk.Tk()
    root.title("Timetracking Records")
    #root.geometry("1200x600")  # Set window size to 800x600 pixels
    # please root window at ("Right Half of Screen")

    # Create a style object
    style = ttk.Style()
    style.theme_use("clam")  # Optional: use a clean theme

    # Set font for Treeview rows
    style.configure("Treeview", font=("Lucida Console", 9))

    # Set font for Treeview headings
    style.configure("Treeview.Heading", font=("Lucida Console", 9, "bold"))

    # Get screen dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight() - 200

    # Set width to half, height to full
    window_width = screen_width // 2
    window_height = screen_height

    # Position at right half (x = screen_width // 2)
    root.geometry(f"{window_width}x{window_height}+{screen_width // 2}+0")

    tree = add_treeview( root, d_tw_data_records )

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

