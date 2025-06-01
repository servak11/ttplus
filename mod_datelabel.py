import tkinter as tk
from datetime import datetime, timedelta

### Date Label displaying a formatted date.
# Controls:
# Lock Button (toggle) that stays pressed when activated.
# Tooltip showing “Lock” when hovered over.
# Spinbox allowing date adjustment between -60 and +60 days.
#
# API:
# def get_date(self):
# def set_date(self, timestamp):
class DateLabel(tk.Frame):
    def __init__(self, parent):
        # , timestamp
        super().__init__(parent)

        self.current_date2 = datetime.now().strftime("%d.%m.%Y")
        self.current_date1 = datetime.now().strftime("%Y%m%d%H%M%S")
        # Convert timestamp to datetime
        self.current_date = self.parse_timestamp(self.current_date1)
        #self.date_var = tk.StringVar(value=self.current_date.strftime("%d.%m.%Y"))

        self.date_changed = False

        # Header frame container
        self.first_line = tk.Frame(self)
        self.first_line.pack()

        # Date Label
        #self.date_label = tk.Label(self.first_line, textvariable=self.date_var, font=("Verdana", 12))
        self.date_label = tk.Label(self.first_line,
            text=self.current_date2,
            font=("Verdana", 12))
        self.date_label.pack(side=tk.LEFT, padx=5)

        # Lock Button (Toggle)
        self.lock_button = tk.Button(self.first_line, text="🔒", relief=tk.RAISED, command=self.toggle_spinbox)
        self.lock_button.pack(side=tk.LEFT)
        self.lock_button.config(state=tk.DISABLED)

        self.tooltip = ToolTip(self.lock_button, "Lock")  # Attach Tooltip

        self.spinbox = None  # Placeholder for the spin control
        self.spin_var = tk.IntVar(value=0)  # Controls spinbox value

    def set_callback(self, update_detail_date_method):
        self.callback = update_detail_date_method

    def parse_timestamp(self, timestamp):
        # Convert external timestamp into a datetime object
        return datetime.strptime(timestamp, "%Y%m%d%H%M%S")

    def get_date(self):
        # Return the currently displayed date to a string in timestamp format
        return self.current_date.strftime("%Y%m%d%H%M%S")

    def set_date(self, timestamp):
        # Set the date label from an external timestamp
        self.current_date = self.parse_timestamp(timestamp)
        #self.date_var.set(self.current_date.strftime("%d.%m.%Y"))
        self.date_label.config(text=self.current_date.strftime("%d.%m.%Y"))

    def toggle_spinbox(self):
        # Toggle spinbox visibility and update button state
        if self.spinbox:
            self.spinbox.destroy()
            self.spinbox = None
            self.lock_button.config(relief=tk.RAISED)  # Reset button state
        else:
            # Create spinbox inline with label
            self.spinbox = tk.Spinbox(self.first_line,
                from_=-60, to=60, width=5,
                textvariable=self.spin_var,
                command=self.update_date)
            self.spinbox.pack(side=tk.LEFT, padx=5)
            self.lock_button.config(relief=tk.SUNKEN)  # Set button to "pressed"

    def update_date(self):
        # spinbox command callback
        # - update the displayed date based on the spinbox value
        days_offset = self.spin_var.get()
        # A timedelta object represents a duration,
        # the difference between two datetime or date instances
        adjusted_date = self.current_date + timedelta(days=days_offset)
        #self.date_var.set(adjusted_date.strftime("%d.%m.%Y"))
        self.date_label.config(text=adjusted_date.strftime("%d.%m.%Y"))
        self.date_changed = True
        if self.callback:
            self.callback(adjusted_date.strftime("%Y%m%d"))

class ToolTip:
    """Tooltip handler for a widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None

        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        """Display the tooltip near the widget."""
        if self.tip_window:
            return

        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tip_window, text=self.text, background="#FFFFE0", relief=tk.SOLID, borderwidth=1)
        label.pack()

    def hide_tooltip(self, event):
        """Remove the tooltip when leaving the widget."""
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None
