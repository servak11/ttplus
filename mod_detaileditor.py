## ttplus - work time tracker
#
## The Task Detail editor 
# class TaskDetailEditor(tk.LabelFrame):
#
# The Task Detail editor shall be inside a LabelFrame named "Detail Editor" with padding 5
# it shall contain two lines of controls 
# - first line of controls shall have multiple controls:
# -- a Label showing current date DD.MM.YYYY
# -- a TimeSpinControl to edit the hours of task starting time,
# -- a TimeSpinControl to edit the minutes of the starting time,
# -- a TimeSpinControl to edit the hours of task ending time,
# -- a TimeSpinControl to edit the minutes the ending time,
# -- a longer TextField to edit task detail which wills the line until the right border
# - second line has a large text field filling the window until its bottom and used for editing notes of the task detail
#
# The Task Detail editor shall be incapsulated into a python class
#
# The Task Detail editor record format
#   "Start Time": "20250414122311", # timestamp
#   "End Time": "2222041415550000", # timestamp
#   "What was done": "Here note detail name (short)",
#   "note": "Here note detail full detail including hyperlinks highlighting"
#
import tkinter as tk
from util.mod_ts import *
from mod_timespin import TimeSpinControl
from mod_datelabel import DateLabel

import webbrowser
import re

class TaskDetailEditor(tk.LabelFrame):
    def __init__(self, master, **kwargs):
        # Create the LabelFrame
        #self.detail_editor = tk.LabelFrame(master, text="Detail Editor", padx=5, pady=5)
        super().__init__(master, text="Detail Editor", padx=5, pady=5, **kwargs)
        self.pack(fill="both", expand=True, padx=5, pady=5)

        # First Line of Controls
        self._create_note_detail_head()

        # Second Line of Controls
        self._create_note_detail_editor()
        
        self.timestamp = ""
        ## Reference to the Database entry currently loaded into the editor
        self.d1 = None
        self.count_time = False
        self.note_loaded = False

        # Bind events for all controls
        self.task_detail.bind("<KeyRelease>", self._on_change)
        self.notes.bind("<KeyRelease>", self._on_change)
        self.start_hour.bind("<KeyRelease>", self._on_change)
        self.start_hour.bind("<ButtonRelease-1>", self._on_change)
        self.start_minute.bind("<KeyRelease>", self._on_change)
        self.start_minute.bind("<ButtonRelease-1>", self._on_change)
        self.end_hour.bind("<KeyRelease>", self._on_change)
        self.end_hour.bind("<ButtonRelease-1>", self._on_change)
        self.end_minute.bind("<KeyRelease>", self._on_change)
        self.end_minute.bind("<ButtonRelease-1>", self._on_change)

    def _create_note_detail_head(self):
        self.first_line = tk.Frame(self)
        self.first_line.pack(fill="x", padx=5, pady=5)
        fr = self.first_line

        # Current date label => put into first_line
        self.date_control = DateLabel( fr )
        self.date_control.pack(side="left", padx=5)
        self.date_control.set_callback(self.update_detail_date)

        # current_date = datetime.now().strftime("%d.%m.%Y")
        # # date_label holds the date of the note detail
        # self.date_label = tk.Label(fr,
            # text=current_date,
            # font=("Verdana", 12))
        # self.date_label.pack(side="left", padx=5)

        # # Placeholder for the spin control
        # self.spinbox = None
        # self.spin_var = tk.IntVar(value=0)  # Controls the spinbox value

        # TimeSpinControls for start and end times of the note detail - editable
        self.start_hour = TimeSpinControl(fr, max_value=23)
        self.start_hour.pack(side="left", padx=5)
        
        self.start_minute = TimeSpinControl(fr, max_value=59)
        self.start_minute.pack(side="left", padx=5)

        self.end_hour = TimeSpinControl(fr, max_value=23)
        self.end_hour.pack(side="left", padx=5)
        
        self.end_minute = TimeSpinControl(fr, max_value=59)
        self.end_minute.pack(side="left", padx=5)

        # Text field for task detail name
        self.task_detail = tk.Entry(fr, font=("Verdana", 12))
        self.task_detail.pack(side="left", fill="x", expand=True, padx=5)
        self.task_detail.insert(0, "Task Detail")
        #self.task_detail.config(state=tk.DISABLED)

        self._disable_widgets(self.first_line)

    # Get all child widgets in the given frame
    # Check if widget supports config method and disable widget
    # this is to avoid generation of exceptions in onchange when note not loaded
    def _disable_widgets(self,frame):
        for widget in frame.winfo_children():  
            if hasattr(widget, "config"):
                try:
                    widget.config(state=tk.DISABLED)
                except tk.TclError:
                    pass  # Ignore Frames that do not support 'state'
    def _enable_widgets(self,frame):
        for widget in frame.winfo_children():  
            if hasattr(widget, "config"):
                try:
                    widget.config(state=tk.NORMAL)
                except tk.TclError:
                    pass  # Ignore Frames that do not support 'state'

    def _create_note_detail_editor(self):
        self.second_line = tk.Frame(self)
        self.second_line.pack(fill="both", expand=True, padx=5, pady=5)

        # Large text field for the task detail notes
        self.notes = tk.Text(
            self.second_line,
            wrap="word",
            font=("Lucida Console", 11),
            undo=True
        )
        self.notes.pack(fill="both", expand=True, padx=5, pady=5)
        # Disable editing until note selection is made
        self.notes.insert("1.0", "Please select note ...")
        self.notes.edit_reset()
        self.notes.config(state=tk.DISABLED)

        # Bind Ctrl+Z for Undo
        self.notes.bind("<Control-z>", self._undo_text)
        # Bind Ctrl+Y for Redo (optional)
        self.notes.bind("<Control-y>", self._redo_text)

    def _undo_text(self, event=None):
        """Undo last action in text editor"""
        ### Note that when unoing too much,
        ### all previous notes which were shown in the TDE would appear
        ### unless reset
        ### - text_widget.edit_reset()
        ### This ensures that any undo actions
        ### will only apply to changes made after this reset point.
        try:
            self.notes.edit_undo()
        except tk.TclError: # nothing to redo
            #print("nothing to undo")
            pass
        return "break"  # Prevent default event propagation

    def _redo_text(self, event=None):
        """Redo last undone action"""
        try:
            self.notes.edit_redo()
        except tk.TclError: # nothing to redo
            #print("nothing to redo")
            pass
        return "break"

    # callback installed by  _detect_and_tag_links(self)
    # to open a link detected in the note detail
    def _open_link(self,event):
        tag_range = self.notes.tag_ranges("hyperlink")
        if tag_range:
            url = self.notes.get(tag_range[0], tag_range[1])
            webbrowser.open(url)

    # the text of the detail does not change when links are detected and tagged
    # in a Tkinter Text widget. The actual string content remains untouched
    # — the only modification is the visual formatting applied through tags
    def _detect_and_tag_links(self):
        content = self.notes.get("1.0", tk.END)
        #matches = re.finditer(r'https?://\S+', content)
        matches = re.finditer(r'https?://[^\s,;]+[.][a-zA-Z]{2,}', content)
        count_links = 0
        tg="none"
        for match in matches:
            count_links = count_links + 1
            # get absolute position in the entire text
            start_pos = match.start() 
            end_pos = match.end()

            # convert absolute position to Tkinter index (line.character)
            tag_start = self.notes.index(f"1.0+{start_pos} chars")
            tag_end = self.notes.index(f"1.0+{end_pos} chars")

            tg="hyperlink"
            self.notes.tag_add(tg, tag_start, tag_end)
            self.notes.tag_configure(tg, foreground="blue", underline=True)
            self.notes.tag_bind(tg, "<Button-1>", self._open_link)
        #print(f"Converted to {tg}: {count_links} links")

    def set_callback(self, update_task_details_method):
        self.callback = update_task_details_method

    # provide callback to the date control to return changed date here
    # new_date shall be returned in format strftime("%Y%m%d")
    def update_detail_date(self, new_date):
        if self.date_control.date_changed:
            # take changed timestamp
            d = new_date[:8]
            # and add it to the start and end times
            self.d1["Start Time"]           = d + self.d1["Start Time"] [8:]
            self.d1["End Time"]             = d + self.d1["End Time"]   [8:]
            if self.callback:
                self.callback({})

    # reset editor to clear display of previous note info
    def reset_editor(self):
        self.d1 = None
        # clear note name before disabling it
        self.set_name        ("")
        # clear note text
        self.notes.config(state=tk.NORMAL)
        self.notes.insert("1.0", "Please select note ...")
        self.set_note        ("Please select note ...")
        self.notes.edit_reset()
        self.notes.config(state=tk.DISABLED)
        self.start_hour     .delete(0, "end")
        self.start_minute   .delete(0, "end")
        self.end_hour       .delete(0, "end")
        self.end_minute     .delete(0, "end")
        self._disable_widgets(self.first_line)
        self._disable_widgets(self.second_line)
        #TODO this was used to remove the first line of control from the view
        # but did not find way to restore it!
        #self.first_line.pack_forget()  # Hide the frame from the layout

    def load_data(self, dict_data):
        """
        Load the provided dictionary structure into the editor.

        This method processes the input dictionary and populates the editor with its data. 
        The dictionary should follow a specific structure compatible with the editor's requirements.

        Args:
            dict_data (dict): A dictionary containing the data to be loaded into the editor. 
                              The keys and values in the dictionary
                              must conform to the editor's format.

        Returns:
            None: This function does not return a value but modifies the editor's state.

        Raises:
            ValueError: If the provided dictionary structure is invalid or incompatible with the editor.
            TypeError: If the input is not a dictionary

        Example:
            editor = Editor()
            sample_data = {
                "Start Time": "20250614065300",
                "End Time": "20250614070337",
                "What was done": "Improve documentation of the load_data()",
                "note": "converted to docstrings"
            }
            editor.load_data(sample_data)
        """
        if dict_data:
            self.d1 = dict_data
            # Enable editing of selected note
            self.first_line.pack(fill="x", padx=5, pady=5)  # Repack the frame (unhide)
            self._enable_widgets(self.first_line)
            self._enable_widgets(self.second_line)
            self._enable_widgets(self.date_control.first_line)
            # populate date control
            # - the timestamp is now controlled in the date_control
            # TODO when pressed unlock date, shall the time spins be disabled?
            # to secure only one part of timestamp changing
            note_timestamp = self.d1["Start Time"]
            self.date_control.set_date(note_timestamp)
            # populate times and task detail name
            self.set_name        (self.d1["What was done"])
            self.set_start_time  (self.d1["Start Time"])
            self.set_end_time    (self.d1["End Time"])
            ### it is not bad if the note text was not available, would be empty
            self.set_note(self.d1.get("note", ""))

            # TODO then we do not need the below code
            # set the note text
            #try:
            #    self.set_note    (self.d1["note"])
            #except IndexError:
            #    ### it is not bad if the note text was not available
            #    pass
            #except KeyError:
            #    ### it is not bad if the note text was not available
            #    pass

            self.note_loaded = True
        else:
            print("Placeholder Hit!")
            # Disable editing until note name created
            self.notes.config(state=tk.NORMAL)
            self.notes.insert("1.0", "Please give note a name ...")
            self.notes.config(state=tk.DISABLED)


    def get_data(self):
        # in case placeholder was hit,
        # we need to read back full data
        # created in the ttplus.on_table2_select()
        # and supplied via TaskDetailEditor.load_data()
        #
        if self.date_control.date_changed:
            # take changed timestamp
            d = self.date_control.get_date()[:8] # strftime("%Y%m%d%H%M%S")[:8]
            print(f"new fate {d}")
            # and add it to the start and end times
            self.d1["Start Time"]           = d + self.d1["Start Time"] [8:]
            self.d1["End Time"]             = d + self.d1["End Time"]   [8:]
        return self.d1

    def _on_change(self, event):
        # Determine which widget triggered the event
        widget = event.widget

        if not self.note_loaded:
            return  # Ignore the event

        if widget['state'] == tk.DISABLED:
            return  # Ignore the event

        # create dictionary of changed items to supply to the update callback
        d_new_details = {}
        if widget == self.task_detail:
            # print("Task name field changed:", self.get_name())
            d_new_details["What was done"]  = self.get_name()
            self.d1["What was done"]        = self.get_name()
        elif widget == self.notes:
            # print("Notes field changed:", self.get_note())
            d_new_details["note"]           = self.get_note()
            self.d1["note"]                 = self.get_note()
        elif widget == self.start_hour or widget == self.start_minute:
            # print("Start time changed:", self.get_start_time())
            d_new_details["Start Time"]     = self.get_start_time  ()
            self.d1["Start Time"]           = self.get_start_time  ()
        elif widget == self.end_hour or widget == self.end_minute:
            # print("End time changed:", self.get_end_time())
            d_new_details["End Time"]       = self.get_end_time    ()
            self.d1["End Time"]             = self.get_end_time    ()

        ##  TODO d_new_details is not used any more,
        # all details can be accessed using get_data()
        if self.callback:
            self.callback(d_new_details)

# Access methods for the task name (stored in self.task_detail)
    def get_name(self):
        return self.task_detail.get()

    def set_name(self, name):
        self.task_detail.delete(0, "end") # tk.END ?
        self.task_detail.insert(0, name)

    def clear_name(self):
        self.task_detail.delete(0, "end")

    # Access methods for the notes (stored in self.notes)
    def get_note(self):
        # "1.0" is the start, "end" includes the final newline
        return self.notes.get("1.0", "end").strip()

    def set_note(self, note):
        #print("set_note")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", note)
        self.notes.edit_reset()
        self._detect_and_tag_links()

    def clear_note(self):
        self.notes.delete("1.0", "end")

    # Access methods for start and end times
    def get_start_time(self):
        # Extract existing date from the stored timestamp
        d = self.timestamp[:8]  # YYYYMMDD
        h = self.start_hour.get()
        m = self.start_minute.get()
        #print(f"get_start_time return {d}{h}{m}00")
        return f"{d}{h}{m}00"

    def set_start_time(self, timestamp):
        self.timestamp = timestamp # remember for return path
        #print("self.timestamp = ",self.timestamp)
        # Extract hour and minute from the timestamp
        h = timestamp[8:10]
        m = timestamp[10:12]
        self.start_hour.delete(0, "end")
        self.start_hour.insert(0, h)
        self.start_minute.delete(0, "end")
        self.start_minute.insert(0, m)

    def get_end_time(self):
        d = self.timestamp[:8]  # YYYYMMDD
        h = self.end_hour.get()
        m = self.end_minute.get()
        return f"{d}{h}{m}00"

    def set_end_time(self, timestamp):
        """ Extract hour and minute from the timestamp """
        #print("set_end_time")
        #self.timestamp = timestamp # remember for return path - but this is done in the set_start_time
        h = timestamp[8:10]
        m = timestamp[10:12]
        self.end_hour.delete(0, "end")
        self.end_hour.insert(0, h)
        self.end_minute.delete(0, "end")
        self.end_minute.insert(0, m)

    def run_clock(self):
        """ Control of the automatic timer of the current active task. """
        self.count_time = True
        self.update_time()
    def stop_clock(self):
        """ Control of the automatic timer of the current active task. """
        self.count_time = False
    def update_time(self):
        """
        Updates the spinbox to show the current system time.
        
        Run set_end_time() for a started task note every minute.
        This automatically counts the time spent for the task.
        Only works for the task detail which was just created.
        The timer is stopped when the task is changed.
        """
        self.set_end_time( get_ts() )

        # Schedule the next update after 60 seconds
        if self.count_time:
            self.after(60000, self.update_time)

# Example Usage
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Task Detail Editor")
    editor = TaskDetailEditor(root)
    root.mainloop()
