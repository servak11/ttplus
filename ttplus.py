## ttplus - work time tracker
#
# TKinter Application shall display two tables
#
# # Requirement 1. General GUI setup.
# Table 1. Table displays the work tasks.
# Columns: ID, Task Name, Total work time
#
# Textfield 1. The textfield between the tables allow to edit the task name.
#
# Table 2. Table displays details of the work tasks.
# Columns: Start Time, End Time, What was done
#
# Textfield 2. The textfield below the tables 2 allow to edit the selected task detail (What was done).
#
# # Requirement 8. Database.
# The work tasks shall be stored in the json database.
# At the application start the json database is loaded and its data is displayed in the Table 1.
#
# For each work task in the table 1 there can be several entries of details (a list).
# The details are also stored in the json database and loaded into application at start.
# When we select a work task in the table 1,
# the corresponding list of details is loaded and displayed into the table 2.
#
# # Requirement 2. First task entry:
# In the beginning, when there is no json database written, there is one entry in the table 1.
# The text of that entry is grey.
# When we click on the entry,
# the task name is duplicated in the textfield 1 where it can be edited.
# The ID of the first task is 1.
#
# # Requirement 9. Display list of details for selected work task:
# As the user selects a work task, the table 2 is loaded with work task details.
# At the end of the list a grey list item named "add detail ..." is added.
# This allows to add a new task detail if needed.
#
# # Requirement 3. Task name editor:
# As the user types in the textfield 1,
# the typed text also appears back into Task Name entry selected in the table.
# The text of the Task Name is displayed blue, not gray anymore.
#
# # Requirement 11. Delete task.
# To the right of the textfield 1 there shall be button  displaying delete icon.
# When pressed, the action is to delete the selected task from the table and from the database.
#
# # Requirement 4. Entry for adding a new Task :
# If we selected the entry for a new task:
# As soon as we started typing in the textfield 1, an entry for another new task is created in table 1,
# The text of that entry is grey, the text of that entry saying "new task ..."
# The ID of such new task shall be equal to the number of existing tasks,
# which automatically makes it unique.
#
# # Requirement 5. Task detail editor:
# As the user types in the textfield 2,
# the typed text also appears back into the "What was done" task detail entry selected in the table 2.
# The text of the "What was done" is displayed blue, not gray anymore.
#
# # Requirement 6. Entry for adding a new task detail:
# If we selected the entry for a new task task detail:
# As soon as we started typing in the textfield 2, an entry for another new task detail is created in table 2,
# The text of that entry is grey, the text of that entry saying "add detail ..."
# The ID of such new task detail shall be equal to the number of existing tasks,
# which automatically makes it unique.
#
# # Requirement 7. First Entry for task detail:
# As the task is created and displayed blue in the table 1, its first entry in the detail table is created.
# Its start time is automatically written with current time of the day.
# The detail is displayed grey saying "add detail ..."
#
# Requirement 10. Geometry
# TKinter app geometry("800x500")
# The width of the ID column narrow, 20 points.
# Also STart Time and End Time columns shall be narrow.
# The time shall be in format HH:MM, no seconds.
#
#
# Requirement 13. decoration
# In the code at the place where TKinter application is created add a commend line saying
# "=== MAIN APPLICATION ==="

#
# Requirement 14. Table Widget module
# The table definition shall reside in a reusable class within a standalone Python module.
# This class shall accept the columns definition structure,
# derive from the TKinter TreeView table class
# and handle the TreeView table creation for both Table 1 and Table 2.
# The module name is mod_table
# The module has methods
# - __init__ which call TreeView super()
# - insert_data
# - clear_table
# - populate
#

#
# Requirement 15. Database access module
# The database shall be encapsulated  in a reusable class within a standalone Python module.
# Along with the methods load_data and db.save_data

#
# Requirement 16. Short field names
# to reduce the load on the database, the fields shall be named by their shortcuts
# represented by the following translation dictionary
# db_field_shortnames = {
#    "fti":"Full Task ID"
#    "sti":"Short Task ID"
#    "tnm":"Task Name"
#    "twt":"Total work time"
#}

################ **Requirements for Task Identification**
# Requirement 21. **Date-Time Stamp-Based ID Generation:**
# - Each task must have a unique `Task ID` based on the date and time of its creation
# - the format `YYYYMMDDHHMMSS` shall be used
#
# Requirement 22. **Hash of the Timestamp for Access:**
# - A shorter, hashed version of the `Task ID` shal be generated
#   using a secure hashing algorithm (e.g., MD5).
# - The hashed ID should have a fixed length of 5 characters
# Rationale. The hash shall be used for efficient access and display.
#
# Requirement 23. **Using Hash as `iid` in TreeView:**
# - The hashed ID must be used as the `iid` parameter when inserting rows into the Tkinter `TreeView`.
# Rationale. This enables direct access to rows in the table without requiring iteration.
#
# Requirement 24. **Storing Hash in the Database:**
# - Both the full `Task ID` and its hashed version shall be stored in the database.
# - The full `Task ID` will be used for retrieval and sorting, while the hashed ID will simplify access and display.
#
## Implementation Details:
# - **Task Creation:** 
# - When a new task is created, generate both the `Task ID` (date-time stamp) and its hashed version.
# - Use the hash in the table (`iid`) and database for efficient handling.
#
# - **Efficient Retrieval:**
# - Use the full `Task ID` stored in the database for detailed lookups.
# - The hashed ID can be used for quick access within the TreeView.
#
# - **Task Display:**
# - Show only the hashed ID in the `Task ID` column for clarity and brevity.

import tkinter as tk
from tkinter import ttk
from tkinter import PhotoImage

from mod_table import TableWidget
import const

from mod_db import Database
from mod_about import AboutDialog
from mod_detaileditor import TaskDetailEditor

from util.mod_ts import *

# Task 1
## Design the Time Tracker
# Create application window
root = tk.Tk()
# Tkinter on Linux supports PNG or GIF images for icons.
# use iconphoto():
# root.iconbitmap("img/ttplus.ico")
root.iconphoto(False, tk.PhotoImage(file="img/ttplus.png"))  # Use PNG instead of ICO
root.title("Work Tasks Plus")
root.geometry("800x700+500+75")


def on_close():
    print("db.save_data(database)")
    db.save_data(database)
    root.quit()
    root.destroy()  # Destroy the Tkinter window


root.protocol("WM_DELETE_WINDOW", on_close)  # Handle window close event


# Populate Table 1
def populate_table1():
    table1.clear_table()
    # database["work_tasks"] ->> dict!
    #print( database["work_tasks"].__class__ )
    if len( database["work_tasks"] ) == 0:
        database["work_tasks"] = {}
    table1.populate(database["work_tasks"])
    # !!! always keep track of newly created task otherwise impossible to save later
    global task_placeholder_id
    task_placeholder_id = add_new_task_placeholder()

def generate_task_id():
    """Generate a unique Task ID based on the current timestamp."""
    from datetime import datetime
    return datetime.now().strftime(FMT_LONG)

def generate_short_task_id(full_task_id, length=5):
    """Generate a shorter, hashed version of the Task ID."""
    import hashlib
    hash_object = hashlib.md5(full_task_id.encode())
    return hash_object.hexdigest()[:length]

def add_new_task_placeholder():
    """
    Add a grey placeholder entry for a new task in Table 1.

    This function creates a new task entry with a grey color, indicating it is a placeholder.
    The placeholder entry allows the user to start editing a new task.

    Returns:
        str: The task ID of the newly created placeholder task.

    Note:
        Always keep track of the returned task ID.
        If not tracked, it may become impossible
        to save or update the placeholder task in the database.
    """
    new_task_id = generate_task_id()
    short_task_id = generate_short_task_id(new_task_id)
    #print("add_new_task_placeholder new_task_id = ",new_task_id)
    table1.insert("", "end", iid=short_task_id, values=(short_task_id, "new task ...", "0"), tags=("grey",))
    return new_task_id

def extract_items(data_dict, index_list):
    # Extract structures from a dictionary that match given indexes.
    # the json indexes are strings, so convert to string when searching
    l=[]
    for index in index_list:
        if str(index) in data_dict:
            l.append(data_dict[str(index)][0].copy())
    return l


def subst_timestamp(l):
    # l is a list with task_details
    for dict1 in l:
        # for the timestamp string
        # - the format `YYYYMMDDHHMMSS` shall be used
        # Extract HH:MM from the timestamp string
        ts = dict1["Start Time"]
        dict1["Start Time"] = dm_hm(ts)
        ts = dict1["End Time"]
        dict1["End Time"] = dm_hm(ts)
    return l

# Populate Table 2 provided the details list
def populate_table2(detail_list):
    table2.clear_table()
    # - the selected task was changed,
    # need to reset task detail editor in disabled state
    # - clear and disable the editor before loading new task data
    tde.reset_editor()
    if(detail_list):
        #print(detail_list)
        # TableWidget populate takes a dictionary, create it from the list, key is index
        task_details = {} #extract_items(database["task_details"], dlist)
        k=1
        for d in detail_list:
            # display readable timestamp, compose copy of dictionary to protect the original database
            d1 = {}
            d1["Start Time"]    = dm_hm(d["Start Time"])
            d1["End Time"]      = dm_hm(d["End Time"])
            d1["What was done"] = str(d["What was done"])
            task_details[k]=d1
            k=k+1
        table2.populate(task_details)
    add_new_detail_placeholder()

# Add grey placeholder for a new task detail
# at this point the placeholder is just in the table
# it comes into database only when edited for the first time
def add_new_detail_placeholder():
    # Ensure task ID exists in the database
    # if task_id not in database["task_details"]:
        # database["task_details"][task_id] = []

    # Append placeholder detail to the database
    # use the same method which does generate_task_id() - because the id is timestamp based
    #placeholder_detail = {"Start Time": generate_task_id(), "End Time": "", "What was done": "add detail ..."}
    placeholder_detail = (dm_hm(generate_task_id()), "", "add detail ...")
    #database["task_details"][task_id].append(placeholder_detail)

    # this functoin requires dict, but we havbe just list at the moment it was not zet created
    #subst_timestamp(placeholder_detail)

    # Save database and update the table
    #db.save_data(database)
    #table2.insert("", "end", values=(placeholder_detail["Start Time"], placeholder_detail["End Time"], placeholder_detail["What was done"]),
    table2.insert_data(placeholder_detail, tags=("grey",))
    #print("add_new_detail_placeholder ")

# Dynamically update Task Name in Table 1
def update_task_name(event=None):
    selected_item = table1.selection()
    if selected_item:
        #print(event)
        # Check if the key is alphanumeric or modifies the text of the task name
        ## if event.char.isprintable ():
        #if not event.state=="Control":
        values = table1.item(selected_item)["values"] # read the full row from table 1
        new_name = textfield_task_name.get()          # read the new name being composed in textfield 1
        if values[const.TABLE_FIELD_TASK_NAME] != new_name:
            ## the name could be the same if a control key pressed on keyboard
            # other methods of check did not work, or too complex
            #if event.keysym.isalnum() or event.keysym in ["space", "BackSpace", "Delete"]:
            # put new text if the task name into the table
            values[const.TABLE_FIELD_TASK_NAME] = new_name

            ############### update the value in the table
            #print("update_task_name row ",values)
            table1.item(selected_item, values=values)   # update table value
            table1.item(selected_item, tags=("blue",))  # update table color

            ############### update the value in the database
            #
            task_id = values[const.TABLE_FIELD_ID]
            #
            create_new_task = 0
            task_dict = database["work_tasks"].get(task_id)
            if task_dict == None: # entry did not exist
                create_new_task = 1

            if create_new_task: # entry did not exist
                ############### use placeholder
                # this was a placeholder, convert it into a real task
                global task_placeholder_id
                task_id = generate_short_task_id(task_placeholder_id)
                status_bar.s_set("add new task",task_id)
                database["work_tasks"][task_id] = {
                            "fti": task_placeholder_id,
                            "sti": task_id,
                            "tnm": new_name,
                            "twt": "0",
                        }
                # create list of task detail items
                database["task_details"][task_id] = []

                # create new task id and use it for the placeholder
                task_placeholder_id = add_new_task_placeholder()
            else:
                ############### update the existing dictionary entry
                #if task_dict["sti"] == task_id:
                #print("update_task_name task id",task_id,"gets new_name",new_name)
                task_dict["tnm"] = new_name

            #db.save_data(database)

# keyboard event in the edited note
#
# still I would like to compress the note so it takes less space,
# typically the note will contain only readable text characters,
# which compression module in python is best for this task
# - compress the note text and save into json database
# - restore from json database, decompress and display in the tkinter text fiels
def update_task_note(event=None):
    selected_item = table2.selection()
    
    # TODO no need to check selected_item,
    # it is only possible to land here if it was selected
    #if selected_item:

    # find index of current note in the database
    task_id = table1.item(table1.selection(), "values")[0]
    detail_index = table2.index(selected_item[0])

    # get full record of the details
    l=database["task_details"].get(task_id)
    # store the edited note there
    new_detail = tde.get_note()
    try:
        if(len(l[detail_index]["note"]) != len(new_detail)):
            #print(len(l[detail_index]["note"]),"!=",len(new_detail))
            pass
    except KeyError:
        ### it is not bad if the note text was not available
        pass
    l[detail_index]["note"]         = new_detail
    l[detail_index]["Start Time"]   = tde.get_start_time  ()
    l[detail_index]["End Time"]     = tde.get_end_time    ()
    # TODO add automatic end time update as soon as we type in the note or name field

# Dynamically update Task Detail in Table 2
# - originally called this on change in detail name
# - now we have more controls in task detail editor
#
# This function is the central point
# of updating the tables AND the database
# with the data provided by the task detail editor
#
# The function is called as a callback from the Task Detail Editor
# Because it has full access to database, it provides the following:
# d_new_details - the dictionary of changed items only
def update_task_details(d_new_details):
    #print("d_new_details =",d_new_details)
    selected_item = table2.selection()
    # print("selected_item =",selected_item)
    
    # TODO no need to check selected_item,
    # it is only possible to land here if it was selected
    #if selected_item:

    # find index of current note in the database
    task_id = table1.item(table1.selection(), "values")[0]
    detail_index = table2.index(selected_item[0])

    detail_list = database["task_details"].get(task_id)

    if(detail_index >= len(detail_list)):
        ### ADD new detail entry to the database
        # this is the last entry, which is always the placeholder
        #print("!",detail_list.__class__,"detail_list contains", len(detail_list), "details, but selected item", (detail_index+1) )
        #print("Placeholder Modified!")
        #
        # Attention d_new_details contains only modified details, 
        # therefore we need to use tde.get_data() to obtain full details and add it to database
        # The database entry was already created for the details in the TDE
        # when the on_table2_select() was triggered, just take that data back!
        detail_list.append(tde.get_data())

        # Voila! Now add new placeholder
        add_new_detail_placeholder()

        # Below test the full details must be now good in the database
        #detail_list_check = database["task_details"].get(task_id) #[detail_index]
        #print(detail_list_check.__class__,"detail_list_check now contains", len(detail_list_check), "details" )
    else:
        ### UPDATE existing detail entry into the database
        # was already done in the TDE because the entry was referenced there (see self.d1)
        #print("+",detail_list.__class__,"detail_list contains", len(detail_list), "details, selected item", (detail_index+1) )
        pass

    # read the full row from table 2 to later update it
    values = table2.item(selected_item)["values"]
    new_detail = tde.get_name()
    #status_bar.s_set("edit detail",str(detail_index),"of task",str(task_id),new_detail)
    # print("-- OLD Values = ",values)

    # print("updated DATA1 ",
        # database["task_details"].get(task_id)[detail_index]
    # )
    # print("-- NEW Values = ",list(tde.d1.values())[:3])
    # if omit the "note" field in the record, it would match the table exactly
    # update table values, but remember we need to convert to H:M format!
    ## so seems easier to create new list
    l = (
        dm_hm(tde.d1["Start Time"]),
        dm_hm(tde.d1["End Time"]),
        str(tde.d1["What was done"])
        
    )
    ### UPDATE existing detail entry into the table view
    # because the values were updated directly in the database record provided by reference to the editor,
    # need only to update the values in the GUI table2
    # it seems easier just to update all values in the tablle
    table2.item(selected_item, values=l, tags=("blue",))

# Delete the selected task from Table 1 and the database
def delete_task():
    selected_item = table1.selection()
    if selected_item:
        task_id = table1.item(selected_item, "values")[0]
        # Remove from database
        database["work_tasks"] = [task for task in database["work_tasks"] if task["Task ID"] != task_id]
        if task_id in database["task_details"]:
            del database["task_details"][task_id]
        #db.save_data(database)
        # Remove from Table 1
        table1.delete(selected_item)
        # Clear Table 2
        for row in table2.get_children():
            table2.delete(row)

# force select a task in table 1
# we can only select anything by first selecting the task
# @param task_id id of the task to select in the table1
def select_task_by_id(task_id):
    # search for table entry with this task_id
    for item in table1.get_children():
        values = table1.item(item, "values")
        if task_id in values:
            # Select the task row in the table
            table1.selection_set(item)
            # TODO the selected task was changed, need to reset task detail editor in disabled state
            # Tested: the select event triggered automatically
            #table1.event_generate("<<TreeviewSelect>>")  # Trigger selection event
            break  # Stop after first match

cur_selected_item = None

# Handle selection of a new task in Table 1
#
# Tkinter Treeview, si = table.item(selected_item) returns dictionary
# with keys like "text", "image", and "values"
#
# Here
# task_id   = si["values"][0]
# task_name = si["values"][1]
# 
def on_table1_select(event):
    tde.stop_clock()
    selected_item = table1.selection()
    #print("selected_item list = ", selected_item)
    global cur_selected_item
    if cur_selected_item == selected_item[0]:
        # selected item clicked again, nothing to do
        return
    # remember selected item
    cur_selected_item = selected_item[0]
    #print("cur selected_item = ", cur_selected_item)
    # tuple
    #print("class = ", selected_item.__class__)
    # read the full data row from table 1
    values = table1.item(selected_item, "values")
    #print("values = ", values) # tuple
    # dict
    #print("class of table1.item(selected_item) = ", table1.item(selected_item).__class__)
    #print("dict = ", table1.item(selected_item))
    # load the task name for editing
    textfield_task_name.delete(0, tk.END)
    textfield_task_name.insert(0, values[1])
    if selected_item:
        # find the selected task in the database
        task_id = values[0]
        status_bar.s_set("Selected task ",task_id)
        detail_list = database["task_details"].get(task_id)
        # detail_list is the list of dictionaries
        #print(" -> assert ",short_task_id,"==",task["sti"])
        populate_table2(detail_list)

def calculate_total_work_time(task_id):
    """
    Calculate total work time for a task.

    For the given task_id, this function iterates over the list of task details in the database,
    computes the time difference (delta) between 'Start Time' and 'End Time' for each detail,
    sums up all time differences, and returns the total work time as a string in HH:MM format.

    Parameters:
        task_id (str): The unique identifier of the task.

    Returns:
        str: Total work time in "HH:MM" format.
    """
    detail_list = database["task_details"].get(task_id, [])
    total_minutes = 0
    for detail in detail_list:
        try:
            tss = dt_str(detail["Start Time"])
            tse = dt_str(detail["End Time"])
            delta = tse - tss
            total_minutes += delta.seconds // 60
        except Exception:
            pass  # skip details with missing or malformed times

    return f"{total_minutes // 60:02}:{total_minutes % 60:02}"

def on_table2_select(event):
    """
    Handle selection of a task detail in Table 2 (the task details table).

    This function is triggered by the Tkinter "<<TreeviewSelect>>" event
    when the user selects a row in the Table 2.
    It performs the following actions:
        - Stops any running time tracking in the detail editor.
        - Clears the detail note field.
        - Determines the selected task and detail index from the GUI.
        - Loads the selected detail's data from the database.
        - Loads the detail data into the TaskDetailEditor.

    Parameters:
        event (tkinter.Event): The event object generated by the Tkinter binding for "<<TreeviewSelect>>".
            Not currently used in the function, but can provide useful information such as:
                - event.widget: The widget that triggered the event (Table 2).
                - event.type: The type of the event ("<<TreeviewSelect>>").
                - event.widget.selection(): The selected item(s) in Table 2.

    Possible improvements:
        - Use event.widget instead of relying on the global 'table2' variable, increasing modularity.
        - Extract more context from the event if needed (e.g., multiple selection support).
        - Add error handling for edge cases (e.g., selection cleared, placeholder row selected).

    Returns:
        None
    """
    tde.stop_clock()
    tde.clear_note()
    selected_item = table2.selection()
    if selected_item:
        ### Find data and Load the Detail Editor
        # find index of current note in the database
        task_id = table1.item(table1.selection(), "values")[0]
        # get index of current detail in the table2
        detail_index = table2.index(selected_item[0])
        status_bar.s_set("Selected task detail #",detail_index," of task ",task_id)

        # calculate_total_work_time(task_id), format as HH:MM
        twt = calculate_total_work_time(task_id)

        # Update database and table1
        database["work_tasks"][task_id]["twt"] = twt

        # Find the item in table1
        # and update the "Total work time" column
        # (assuming it's the 3rd column, index 2)
        values = list(table1.item(table1.selection(), "values"))
        values[2] = twt
        table1.item(table1.selection(), values=values)

        try:
            # get full record of the details
            d_entry = database["task_details"].get(task_id)[detail_index]
            # this is the place to match the tde entry with timetracking
            # and update status
            from mod_timetrack import TimeTracking
            tracker = TimeTracking()
            # TODO move this to TimeTracking task
            status_bar. s_set(
                "Timekeeping earliest date " + # earliest_date
                tracker.tw_report(database["task_details"]).strftime('%d.%m.%Y')
            )
            db_sts = dt_str(d_entry["Start Time"])
            status_bar. s_act(
                db_sts, 
                tracker.check_deviation(d_entry)
            )

            # If the task was overdue, display a red status message
            #if time_diff_minutes != 0:
            #    status_bar.s_set(datetime.strptime(closest_dt, "%d.%m.%Y%H:%M"))
        except IndexError:
            ### in case of placeholder the data would not load
            #d_entry = None # NO!!! create new entry already?
            # Attention! In the database the entry would only be created
            # after on_change() triggered in details editor
            # -> that would trigger update_task_details()
            id = generate_task_id()
            d_entry = {
                "Start Time"    : id,
                "End Time"      : id,
                "What was done" : "add detail ..."
            }
            tde.run_clock()

        tde.load_data( d_entry )

def show_about():
    AboutDialog(master=root)

def show_report():
    # go through all
    #detail_list = database["task_details"].get(task_id)
    #print("detail_list = ")
    # will print number of tasks:
    #print(f"* Number of records per task ({len(database["task_details"])} tasks)")
    #for task_detail_list in database["task_details"].values():
    #    print(f"{}" ... len(task_detail_list))
    # compose list
    report_list=[]
    for task_id, task_detail_list in database["task_details"].items():
        for detail_dict in task_detail_list:
            sts = detail_dict["Start Time"]
            ets = detail_dict["End Time"]
            wwd = detail_dict["What was done"]
            s = f"{sts[4:6]} {dm_hm(sts)} - {dm_hm(ets)} : {database['work_tasks'][task_id]['tnm']:16}... {wwd}"
            report_list.append(s)
            #print(s)
    # sort list
    print("\n".join(sorted(report_list)))


def tt_test_action():
    select_task_by_id("e8ad4")


# show report for the selected task
# goal to determine time spent
def show_task_report():
    # find index of current note in the database
    task_id = table1.item(table1.selection(), "values")[0]

    # get full list of the detail dictionaries
    l = database["task_details"].get(task_id)
    print(f"detail dictionariy size {len(l)}")
    i = 0
    effort = 0 # minutes
    print("NN : effort [\"What was done\"]")
    print("---:---------------------------")
    for dict in l:
        # get timestamps
        tss = get_dt(dict["Start Time"])
        tse = get_dt(dict["End Time"])
        # Compute difference
        delta = tse - tss
        # Format difference in hh:mm
        report = f"{delta.seconds // 3600:02}:{(delta.seconds % 3600) // 60:02}"
        i=i+1
        print(f"{i:>2} : {report} {dict['What was done']}")
        effort = effort + (delta.seconds // 60)
    effort_total = f"{effort // 60:03}:{(effort % 60):02}"
    print("---:---------------------------")
    print(f"TTL: {effort_total}")


    # store the edited note there
    #l[detail_index]["note"]         = new_detail
    #l[detail_index]["Start Time"]   = tde.get_start_time  ()
    #l[detail_index]["End Time"]     = tde.get_end_time    ()




# === MAIN APPLICATION ===

db = Database()
database = db.load_data()

task_placeholder_id = "00000"


# Create status bar and print database info there initially
# the class StatusBar calls pack()
from mod_statusbar import StatusBar
info = (str(database["work_tasks"].__class__),"database contains",str(len(database["work_tasks"])),"records")
status_bar = StatusBar(root)


# Create a menu bar
menu_bar = tk.Menu(root)
root.config(menu=menu_bar)

# Add the "Help" menu
help_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_command(label="About", command=show_about)
menu_bar.add_command(label="Work Report", command=show_report)
menu_bar.add_command(label="Detail Effort Report", command=show_task_report)
menu_bar.add_command(label="Test", command=tt_test_action)
#menu_bar.add_command(label="TW", command=tw_report)

# Table 1 (Work Tasks)
frame1 = ttk.LabelFrame(root, text="Work Tasks")
frame1.pack(fill="both", padx=8, pady=8)

# Configure the TreeView style for headings
style = ttk.Style()
style.configure("Treeview.Heading", background="blue")
style.configure("Treeview", font=("Tahoma", 10))  # Set the global font for the Treeview

columns1 = (("ID",20), ("Task Name",400), ("Total work time",0))
table1 = TableWidget(frame1, columns1)
table1.tag_configure("grey", foreground="grey")
table1.tag_configure("blue", foreground="blue")
table1.bind("<<TreeviewSelect>>", on_table1_select)
table1.si = 1 # column 0 is timestamp, start display from 1

populate_table1()


# Frame for Textfield 1 and Delete Button
frame_task_editor = tk.Frame(root)
frame_task_editor.pack(pady=8)


# Textfield 1 (Task Name Editor)
textfield_task_name = tk.Entry(frame_task_editor, width=50)
textfield_task_name.pack(side="left", padx=8)
textfield_task_name.bind("<KeyRelease>", update_task_name)


# Delete Button
delete_icon = PhotoImage(file="img/del.png")
delete_button = tk.Button(frame_task_editor, image=delete_icon, command=delete_task)
delete_button.pack(side="left")


# Table 2 (Task Details)
frame2 = ttk.LabelFrame(root, text="Task Details")
frame2.pack(fill="both", padx=8, pady=8)


columns2 = (("Start Time",20), ("End Time",20), ("What was done",500))
table2 = TableWidget(frame2, columns2)
table2.tag_configure("grey", foreground="grey")
table2.tag_configure("blue", foreground="blue")
table2.bind("<<TreeviewSelect>>", on_table2_select)

tde=TaskDetailEditor(root)
tde.pack(pady=5)
tde.set_callback(update_task_details)
#tde.task_detail.bind("<KeyRelease>", update_task_detail)
#tde.notes.bind("<KeyRelease>", update_task_note)
#tde.notes.bind("<KeyRelease>", update_task_note)


root.mainloop()
