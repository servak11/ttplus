"""
This module provides a Tkinter status bar with two sections:
1. **Message Area** – Displays user messages.
2. **Activity Area** – Shows the current task match status.

We match agains tisoware - if the start time of the closest task in tisoware 
matches the time of the selected note detail, it is displayed in green
otherwise in red followed by offset in minutes

The `status(*args)` function updates the message area:
    - Converts all parameters to strings and creates a tuple.
    - Joins them into a single string for display.

The `update_activity(task_date)` function updates the activity area:
    - Displays a **green** message with the current date if the task is on time.
    - Displays a **red** message with the date if the task is **overdue**.

This module is useful for applications that require real-time status updates.
"""

import tkinter as tk
from datetime import datetime

class StatusBar(tk.Frame):
    """Custom status bar with message and activity areas."""

    def __init__(self, master):
        super().__init__(master, bd=1, relief=tk.SUNKEN)
        self.pack(side=tk.BOTTOM, fill=tk.X)

        # Message Area
        self.status_bar = tk.Label(self, text="Status: Ready", anchor="w")
        self.status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Activity Area
        self.activity_area = tk.Label(self, text="Task Status", anchor="e")
        self.activity_area.pack(side=tk.RIGHT)

    def s_set(self, *args):
        """Updates the message area of the status bar."""
        self.status_bar.config(text=" ".join(map(str, args)))

    # TODO
    # create python function which
    # - takes indefinite number of parameters,
    # - converts them all to strings,
    # - creates a tuple from the strings
    # - uses " ".join() method on the tuple
    # - returns the result!
    #def s_add(self, *args):
    # Convert all parameters to strings and create a tuple
    #    string_tuple = tuple(str(arg) for arg in args)
    #    """Appends the message to the text of the status bar."""
    #    t=status_bar.cget("text") + " -- "
    #    self.status_bar.config(text=" ".join(map(str, args)))

    # """Displays the status in green if the task is on time, red if overdue."""
    # @param task_date datetime ttplus
    # @param deviation_date datetime tracker tool
    def s_act(self, task_date, deviation_date):
        if not deviation_date:
            self.activity_area.config(text = "")
            return
        if task_date == deviation_date:
            self.activity_area.config(
                text = f"ON TIME: {task_date}",
                fg="green")  # Green for valid task
        else:
            time_diff_minutes = int(
                (deviation_date - task_date).total_seconds() / 60
            )
            self.activity_area.config(
                text = f"OVERDUE: {deviation_date}  ({time_diff_minutes})",
                fg="red")  # Red for overdue

# Example usage
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("400x100")
    
    status_bar = StatusBar(root)

    # Example calls
    status_bar.s_set("Welcome to the app!")
    status_bar.s_act("2025-05-30")

    root.mainloop()
 
