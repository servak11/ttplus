from selenium import webdriver
from selenium.webdriver.common.by       import By
from selenium.webdriver.common.keys     import Keys
from selenium.webdriver.chrome.options  import Options
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui      import WebDriverWait
from selenium.webdriver.support.ui      import Select
from selenium.webdriver.support import expected_conditions as EC

from dataclasses import dataclass
from typing import List

import json
import os
import time
from datetime import datetime, timedelta

from util.ts import *

import re

ALLG_PATTERN = r"[Aa]llg\."
URL = 'http://menlogphost5.menlosystems.local/tisoware/twwebclient'

@dataclass
class Entry:
    from_time:  str
    to_time:    str
    project:    str
    activity:   str
    comment:    str

driver = None

# connect to the webpage
# select PRZ sheet
# select and display the span of 2 weeks in the sheet
# return all inputs relevant for user from that sheet
# @return list of lists
# - each list contains values of row elements
#   row #
#   WeekDay, Date DD.MM.YYYY
#   TT:MM start
#   TT:MM end
#   project
#   comment
#   project item - note last item in the list,
#   because added from selector element in the end
def browse_data(
        #date: str,
        #data: List[Entry],
        #driver=None,
        url=None
    ):

    print("---------------------")
    print("browse_data() started")
    print("---------------------")

    # once using global driver variable,
    # and no headless mode
    # the browser will stay open until application closes
    global driver

    if 0:
        # Set up Edge options for headless mode (no visible window)
        edge_options = Options()
        edge_options.add_argument("--headless")
        # Improve performance
        edge_options.add_argument("--disable-gpu")  
        driver = webdriver.Edge(options=edge_options)

    #from selenium import webdriver
    edge_options = webdriver.EdgeOptions()
    #edge_options.add_argument("--headless")
    # Improve performance
    edge_options.add_argument("--disable-gpu")  
    edge_options.add_argument("--disable-features=EdgeIdentity")
    driver = webdriver.Edge(options=edge_options)

    if driver is None:
        # Initialize WebDriver
        driver = webdriver.Edge()
    if url is None:
        url = URL

    driver.get(URL)

    # Create a wait object (e.g., wait up to 10 seconds)
    wait = WebDriverWait(driver, 10)

    def E(id: str) -> WebElement:
        return wait.until(EC.presence_of_element_located((By.ID, id)))

    def wait_for_loaded():
        time.sleep(0.5)
        wait.until(lambda d: d.execute_script(
            """
            return document.readyState == "complete" && typeof spglNdNew == "function"
            """
            ))

    from config import u_r, p_d

    # Find the username and password fields and enter credentials
    E("Uname").send_keys(u_r[:len(u_r)-3])
    E("PWD").send_keys(p_d[:len(p_d)-3])
    # .click() generates error in headless mode
    # selenium.common.exceptions.ElementClickInterceptedException:
    # button is not clickable at point (250, 419)
    #E("an").click()
    driver.execute_script("arguments[0].click();", E("an"))

    menujson_element = E("menujson")
    menujson = json.loads(menujson_element.get_attribute("innerHTML"))

    def trans_name_from_text(text: str):
        for e in menujson:
            if e["Text"] == text:
                return e["TransName"]

    def open_trans(text: str):
        name = trans_name_from_text(text)
        driver.execute_script(f'spglNdNew("{name}")')
        wait_for_loaded()

    open_trans("Erfassungsmappen")

    time.sleep(1)

    print(f"Opening PRZ Selector ...")
    #
    # if(checkPickerVoll(this.id)){
    #     setConfirmedChange(this.id, &quot;false&quot;);
    #     return false;
    # }else{
    #     setConfirmedChange(this.id, &quot;false&quot;);initWokSheet(this.id);}
    # }
    #
    # onchange="{ if(checkPickerVoll(this.id))
    # {setConfirmedChange(this.id, &quot;false&quot;);
    # return false;}else{setConfirmedChange(this.id, &quot;false&quot;);initWokSheet(this.id);}}">
    #
    # <option value="0"> </option>
    # <option value="004"
    #     id="FromDate05.05.2025!&amp;!ToDate05.05.2025!&amp;!">002 -
    #     BDE</option>
    # <option value="005"
    #     id="FromDate05.05.2025!&amp;!ToDate05.05.2025!&amp;!">003 -
    #     PRZ (kumuliert)</option>
    activity = E("wrksht")
    activities = activity.find_elements(By.TAG_NAME, "option")
    a = None
    for a in activities:
        v = a.get_attribute("value")
        #print(f"V: {v} = {a.text}")
        v = a.get_attribute("selected")
        #print(f"S: {v} = {a.text}")
        v = a.get_attribute("id")
        #print(f"ID: {v} = {a.text}")
    print(f"ID: {v} = {a.text}")
    print()

    date_range = "FromDate26.05.2025!&amp;!ToDate30.05.2025!&amp;!"

    # 1. Select Zeiterfassungs Mappe - timetracking sheet
    #
    # Locate the select dropdown "Mappe", select value 006 for PRZ
    # <option value="006" selected="selected"
    #     id="FromDate05.05.2025!&amp;!ToDate05.05.2025!&amp;!">003 -
    #     PRZ (Zeitspanne)</option>
    dropdown = Select(driver.find_element("id", "wrksht"))
    dropdown.select_by_value("006")

    #time.sleep(3)

    # 2. Select the date range
    #
    # Calculate the date two weeks before today
    #new_date = (datetime.today() - timedelta(weeks=3)).strftime("%d.%m.%Y")
    NUM_WEEKS_BACK = 3
    new_date = get_ts(
        (datetime.today() - timedelta(weeks=NUM_WEEKS_BACK)),
        fmt = FMT_DATE
    )

    # the "to date" is today, leave as is
    # locate the input field for "from date"
    # select content (Ctrl-a), send new date there, Tab to update value
    frdate = E("frD")
    frdate.click()
    frdate.send_keys(Keys.CONTROL, "a")
    frdate.send_keys(new_date, Keys.TAB)

    # Verify the change
    print(f"Updated start date: {frdate.get_attribute('value')}")
    print()

    #time.sleep(1)

    # Button "OK" appears, type="submit" id="load" name="load"
    # Find the button and click it
    button = E("load")
    button.click()

    time.sleep(1)

    # The timetracking sheet would now be loaded into an IFRAME !
    #
    # Hierarchy
    # mainWinTable
    # - class content-main
    # -- reitermain
    # --- divAll
    # ---- div_tblfldfr
    # ----- .. table
    # ----- .. table
    # ----- .. td(iframe nmfrfrrest) td(id tren_tbl) td (iframe tblfldfr)
    # This is timetracking iframe
    # <iframe frameborder="0" id="tblfldfr" style="width: 692.478px; height: 485.115px; overflow: hidden; border: none;" src="../tisowareClient/0b6436d9657672fa53b2c26e73b0cd3e19c1f4ad86f7c7132fed37b0f151184d/inff1079215197.html" name="tblfldfr" scrolling="no" class="inbindresize"></iframe>
    #  tblfldfr
    #
    # Need to SWITCH to the iframe using its ID !
    iframe = driver.find_element(By.ID, "tblfldfr")
    driver.switch_to.frame(iframe)

    # Wait for the erfassung table to appear:
    table = wait.until(EC.presence_of_element_located((By.ID, "dvTblFLmain")))

    print("Table found:", table.id)
    # Find all rows inside the table
    rows = table.find_elements(By.TAG_NAME, "tr")
    # Get the row count
    row_count = len(rows)
    print(f"Number of rows: {row_count}")
    text_inputs = rows[0].find_elements(By.CSS_SELECTOR, "input[type='text']")
    inpus_count = len(text_inputs)
    # Print the IDs of all found input fields
    inf_list = []
    for inf in text_inputs:
        #print(inf.get_attribute("id") + ("-" * 15))
        inf_list.append( inf.get_attribute("id") )
    print(f"Reading {inpus_count} text inputs: {inf_list}")
    k=1
    row_list = []
    for row in rows:
        # find all input elements in selected row and add them to info row
        text_inputs = row.find_elements(By.CSS_SELECTOR, "input[type='text']")
        inf_list = []
        inf_list = [f"{k:>5}:"]  # row number
        for inf in text_inputs:  # get all values
            inf_list.append(inf.get_attribute("value"))
        #print("  ".join(inf_list))
        k=k+1
        # find the select element for "type of work" -- 2nd selector
        select_elements = row.find_elements(By.CSS_SELECTOR, "select")
        #print(select_elements[1].get_attribute("id"))
        selected_option = Select(select_elements[1]).first_selected_option
        #print(selected_option.text)
        inf_list.append(selected_option.text) # add option to the list
        row_list.append(inf_list)

    return row_list

    toT = E("tbl_12_1")
    toT.click()
    toT.send_keys(Keys.CONTROL, "a")
    toT.send_keys("entry.to_time", Keys.TAB)

    time.sleep(11)
    return

    # Locate the parent div element
    parent_div = driver.find_element(By.ID, "inTable")

    # Find all input fields inside the div
    input_fields = parent_div.find_elements(By.TAG_NAME, "input")

    # Print the input fields
    for input_field in input_fields[:40]:
        name = input_field.get_attribute("name")
        if name[:6] == "tbl_12":
            print(name, input_field.get_attribute("value"), input_field.get_attribute("type"))
            b="{ bubbles: true }"
            c="{ key: 'a' }"
            d="{ key: 'x' }"
            # Attempt 1. Try javascriptm to write into "hidden" field.
            #  - focus
            #  - change text
            #  - send input and change events -
            script2 = (
                f'e=document.getElementById("{name}");e.focus();'
                f'e.value = "YourTextHere";'
                f'e.type="text";'
                f'e.dispatchEvent(new Event("input", {b}));'
                f'e.dispatchEvent(new Event("change", {b}));'
                f'e.blur();'
                f'let event = new KeyboardEvent("keydown", {c});'
                f'e.dispatchEvent(event);'
                f'event = new KeyboardEvent("keydown", {d});'
                f'e.dispatchEvent(event);'
                f'setInterval(() => {{document.getElementById("tbl_12_1").value = "YourTextHere";}}, 1000);'
            )

            #f'document.querySelector("shadow-host").shadowRoot.getElementById("{name}").value = "YourTextHere";'
            driver.execute_script(script2)
            print(name, input_field.get_attribute("value"), input_field.get_attribute("type"))
            # inspite type="text" field still not interactable
            #input_field.send_keys(Keys.CONTROL, "a")
            print()
            #driver.execute_script("arguments[0].click();", input_field)
            # 
            # on hidden elements selenium throws 
            # selenium.common.exceptions.ElementNotInteractableException: Message: element not interactable
            #input_field.click()
            #input_field.get_attribute
            #input_field.send_keys(Keys.CONTROL, "a")
            #input_field.send_keys(Keys.BACKSPACE)
            #input_field.send_keys("test")


    # Now list all fields which are to be filled in
    #wait_for_loaded()
    if 0:
        for k in range(5):
            id  = f"tbl_7_{k}"
            print(id)
            try:
                input_field = E( id )
                # Select all and delete text
                input_field.send_keys(Keys.CONTROL, "a")
                input_field.send_keys(Keys.BACKSPACE)
                input_field.send_keys("test")
            except:
                print("cannot load")
            id  = f"tbl_12_{k}"
            print(id)
            try:
                input_field = E( id )
                # Select all and delete text
                input_field.send_keys(Keys.CONTROL, "a")
                input_field.send_keys(Keys.BACKSPACE)
                input_field.send_keys("test")
            except:
                print("cannot load")
    time.sleep(15)

    if 0:

        driver.execute_script(f'transaktionObj.toBuchEdit("{date}")')
        wait_for_loaded()

        E("inf").send_keys("Excel Übertrag", Keys.TAB)

        buchungen = E("tblbuchaend")
        print("TABLE", buchungen)

        for entry in data:
            time.sleep(0.5)

            tbody = buchungen.find_element(By.CSS_SELECTOR, "tbody")
            rows = tbody.find_elements(By.XPATH, './*')

            last_row = rows[-1]
            time.sleep(0.5)

            last_row.click()
            time.sleep(0.5)

            E("wttext1").send_keys("010", Keys.TAB)
            time.sleep(0.5)

            try:
                confirmDialog = E("btnNein").click()
                time.sleep(0.5)
            except Exception as exc:
                print("failed to close dialog:", exc)

            frT = E("frT")
            frT.click()
            frT.send_keys(Keys.CONTROL, "a")
            frT.send_keys(entry.from_time, Keys.TAB)

            toT = E("toT")
            toT.click()
            toT.send_keys(Keys.CONTROL, "a")
            toT.send_keys(entry.to_time, Keys.TAB)

            pr = E("pr")
            pr.send_keys(entry.project, Keys.TAB)
            time.sleep(0.5)

            activity = E("activity")
            activities = activity.find_elements(By.TAG_NAME, "option")
            default_activity = None
            matching_activity = None
            for a in activities:
                v = a.get_attribute("value")
                print(f"ACTIVITY: {v} = {a.text}")

                if re.search(ALLG_PATTERN, a.text) is not None:
                    default_activity = v
                if "XXX" not in a.text and re.search(entry.activity, a.text) is not None:
                    matching_activity = v

            print(f"wanted activity: {entry.activity}")
            print(f"default_activity = {default_activity}")
            print(f"matching_activity = {matching_activity}")

            if matching_activity is None:
                matching_activity = default_activity

            if matching_activity is not None:
                activitytext = E("activitytext")
                activitytext.click()
                activitytext.send_keys(Keys.CONTROL, "a")
                activitytext.send_keys(str(matching_activity), Keys.TAB)

            comment = E("com")
            comment.click()
            comment.send_keys(Keys.CONTROL, "a")
            comment.send_keys(str(entry.comment), Keys.TAB)

            time.sleep(0.5)

            E("netblbuchaend").click()

def update_timetracking( ):
    global driver
    if None == driver:
        return
    # In the browse_data() - Already SWITCHED to the iframe using its ID !
    # Create a wait object (again) using the browser driver
    wait = WebDriverWait(driver, 10)

    # Wait for the erfassung table to appear:
    table = wait.until(EC.presence_of_element_located((By.ID, "dvTblFLmain")))

    print("---------- update_timetracking")
    print("Table found:", table.id)
    # Find all rows inside the table
    rows = table.find_elements(By.TAG_NAME, "tr")
    # Get the row count
    row_count = len(rows)
    print(f"Number of rows: {row_count}")

    # text input fields need to be filled
    text_inputs = rows[0].find_elements(By.CSS_SELECTOR, "input[type='text']")
    inpus_count = len(text_inputs)
    # Print the IDs of all found input fields
    inf_list = []
    for inf in text_inputs:
        #print(inf.get_attribute("id") + ("-" * 15))
        inf_list.append( inf.get_attribute("id") )
    print(f"Writing {inpus_count} text inputs: {inf_list}")
    k=1
    # iterate through all rows in the Zeiterfassung HTML table
    for row in rows:
        # find all input elements in selected row and add them to info row
        text_inputs = row.find_elements(By.CSS_SELECTOR, "input[type='text']")
        if "" == text_inputs[3].get_attribute("value"):
            # found empty project field
            print(f"{k:>5}:")  # row number
            project_key = "9300_2025_Fs-DCP"
            text_inputs[3].send_keys( project_key )
            # after the project was selected,
            # the select control below will be populated
            # find the select element for "type of work" -- 2nd selector
            # select.select_by_index(len(select.options) - 1)
            select_elements = row.find_elements(By.CSS_SELECTOR, "select")
            select_elements[1].send_keys(Keys.END) # select last option
        k=k+1


if __name__ == "__main__":

    def analyze_timtrack_records(records):
        """
        Loop through the browser timetracking records,
        find and return the range of dates.
        See format of browse_data() output to find record structure.
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
        print ("Adding", len(timetrack_list), "records from browse_data().")
        k = len(filtered_records) + 1
        # make continuous row numbering
        for t in timetrack_list:
            t[0] = f"{k:>5}:"  # update row number
            k = k + 1
        return filtered_records


    FILENAME_TIMETRACK = "tw_data.json"
    # option to execute online browsing for tw data
    OPT_UPDATE_DATABASE = False

    tw_data = read_timetrack_json(FILENAME_TIMETRACK)

    # Extract records from JSON structure
    records = tw_data.get("records", [])

    analyze_timtrack_records(records)

    ### test
    #print (records[0])

    db_updated = 0
    timetrack_list = []
    if OPT_UPDATE_DATABASE:
        # TODO use the latest day to set the date in browse from which start browsing
        # TODO confine date not to cross 1st of the month 
        #   because dialog appears in tisoware 
        #   and more importantly no submit button will be available
        # use selenium to obtain the timekeeping data
        # TODO shall run in background thread ultimately
        timetrack_list = browse_data()

        db_updated = 1

        (earliest, latest) = analyze_timtrack_records(timetrack_list)

        # leave only old records
        records = filter_old_records(timetrack_list, records)

    else:
        print("skip browse_data()")


    if db_updated:
        # save time tracking data to file
        print("export data to database", FILENAME_TIMETRACK)
        if not "header" in tw_data:
            # Define header of the file with comments about the record structure
            header_info = {
                "description": "This file contains time-tracking records imported from tisoware.",
                "fields": [
                    "Record No (str): Unique identifier for each entry '   NN.'",
                    "Date (str): The date of work (Do, 22.05.2025)",
                    "Start Time (str): Time when work started",
                    "End Time (str): Time when work ended",
                    "Project Key (str): Identifier for the project",
                    "Comment (str): Notes about the work",
                    "Project Item (str): Subcategory of the project"
                ],
                "generated_on": get_ts(datetime.now(), fmt=FMT_DATE),
                "date range": f"{earliest} - {latest}"
            }
            # Combine header and records into a structured JSON file
            #json_data = {
            #    "header": header_info,
            #    "records": timetrack_list
            #}
            # add header if missing
            tw_data["header"] = header_info
        else:
            tw_data["header"]["updated_on"] = get_ts(datetime.now(), fmt=FMT_DATE)
            tw_data["header"]["date range"] = f"{earliest} - {latest}"

        # combine the lists
        tw_data["records"] = records + timetrack_list

        # Save to JSON file
        with open(FILENAME_TIMETRACK, "w", encoding="utf-8") as json_file:
            json.dump( tw_data, json_file, indent=2)

        print(f"Timetracking info stored to JSON file '{FILENAME_TIMETRACK}'")
    else:
        print(f"skip save database, as db_updated = {db_updated}")


    """
    Procedure:
    ----------
    1. Open selenium in GUI mode (no headless) - because need to review input
    2. Run browse_data():
       timetrack_list = browse_data()
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


    # resume working in displayed browser
    # will do nothing and return if browse was not executed
    update_timetracking( )


    # Check if the file exists
    if not os.path.exists(FILENAME_TIMETRACK):
        print(f"Database '{FILENAME_TIMETRACK}' does not exist.")
    else:
        print(f"Database '{FILENAME_TIMETRACK}' found - will show in GUI")

    if db_updated and 0:
        # Re-read the database
        # 
        # I have json file 
        #     ttdb = "tw_data.json"
        #  of following timetracking records
        #   [
        #     "    1:",               # record number
        #     "Do, 22.05.2025",       # date
        #     "06:06",                # start time
        #     "07:51",                # end time
        #     "9300_2025_Fs-DCP",     # project key
        #     "Firmware",             # comment about the work
        #     "65.10 Entwicklungsarbeit (8273)"   # project item
        #   ],
        # create table in Tkinter gui to display these records
        #
        # window geometry 800 x 600
        # first 4 columns shall be narrow, last 3 information columns wide

        # Load JSON data
        with open(FILENAME_TIMETRACK, "r", encoding="utf-8") as file:
            data = json.load(file)

        records = data.get("records", [])

    import tkinter as tk
    from tkinter import ttk

    # Create the Tkinter window
    root = tk.Tk()
    root.title("Timetracking Records")
    root.geometry("1200x600")  # Set window size to 800x600 pixels

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

    # Insert records into the table
    for record in records:
        tree.insert("", tk.END, values=record)


    # they insert in black color
    # now I need to insert new records from the timetrack_list
    # but display them in blue color
    # Define the tag with blue foreground
    tree.tag_configure("blue_text", foreground="blue")
    for record in timetrack_list:
        tree.insert("", tk.END, values=record, tags=("blue_text",))

    # Create a right-click menu
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Edit", command=lambda: print("Edit selected row"))
    menu.add_command(label="Delete", command=lambda: print("Delete selected row"))

    # Function to show menu on row click
    def show_menu(event):
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)  # Select the clicked row
            menu.post(event.x_root, event.y_root)

    # The Tkinter table displaying timetracking records
    # shall have action displaying menu
    # when man clicks any of the table rows
    #
    # Bind right-click action to the table
    tree.bind("<Button-3>", show_menu)  # Right-click (Windows/Linux)
    tree.bind("<Control-Button-1>", show_menu)  # Ctrl+Left-click (Mac)

    # Pack the table into the window
    tree.pack(expand=True, fill="both")

    # Run the Tkinter loop
    root.mainloop()

