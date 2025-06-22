"""
ttplus project - work time tracker

This module implements a date label widget with adjustment capabilities for the ttplus application.
The DateLabel widget combines a formatted date display with controls for locking and adjusting the date.

Key Features:
- Displays date in DD.MM.YYYY format
- Supports date locking with a toggle button
# Lock Button (toggle) that stays pressed when activated.
- Provides date adjustment via spinbox (-60 to +60 days)
- Includes tooltips for better user interaction

# API:
# def get_date(self):
# def set_date(self, timestamp):
"""

import tkinter as tk
from datetime import datetime, timedelta
from util.ts import *

class DateLabel(tk.Frame):
    """A specialized date label widget with lock and adjustment controls.

    This widget extends tk.Frame to provide a composite control that includes:
    - A formatted date label (DD.MM.YYYY)
    - A lock button that can be toggled to prevent date changes
    - A spinbox for adjusting the date within a -60 to +60 day range
    - Tooltip functionality for better user experience

    Attributes:
        _callback (Optional[Callable]): Optional callback function for date change events
        _date (datetime): Current date value stored in the widget
        lock_button (tk.Button): Button for toggling date lock
        spinbox (Optional[tk.Spinbox]): Spinbox for date adjustment (created on demand)
        spin_var (tk.IntVar): Variable controlling the spinbox value

    Args:
        parent (tk.Widget): Parent widget
        **kwargs: Additional keyword arguments passed to tk.Frame
    """
    def __init__(self, parent):
        # , timestamp
        super().__init__(parent)

        # Initialize instance variables
        self._callback = None
        # datetime of this control
        self._date = datetime.now()
        self.spinbox = None
        self.spin_var = tk.IntVar(value=0)
        # Create the control containing the date display and controls
        self._create_datelabel()

    def _create_datelabel(self):
        """Create and configure the main widget layout."""
        # Frame Container
        self.frm = tk.Frame(self)
        self.frm.pack(fill="x")

        # Date Label
        self.date_label = tk.Label(
            self.frm,
            text=get_ts(fmt=FMT_DATE), # short normal date
            width=10,  # Fixed width to prevent layout shifts
            font=("Verdana", 12))
        self.date_label.pack(side=tk.LEFT, padx=5)

        # Lock button
        self.lock_button = tk.Button(
            self.frm, 
            text="🔒", 
            relief=tk.RAISED,
            command=self.toggle_spinbox
        )
        self.lock_button.pack(side=tk.LEFT)
        self.lock_button.config(state=tk.DISABLED)

        # create tooltip for the lock button
        #self._create_tooltip(self.lock_button, "Lock")

        self.date_changed = False

        self.tooltip = ToolTip(self.lock_button, "Lock")  # Attach Tooltip

    def reset(self):
        """ Method to Reset the control needed if we change to a new task detail"""
        self.spin_var.set(0)
        # current_state = self.lock_button.cget("relief")
        self.lock_button.config(relief="raised")

    def get_date(self):
        """ Return the currently displayed date as a string in timestamp format FMT_LONG"""
        return get_ts(self._date) # convert to FMT_LONG

    def set_date(self, timestamp: str) -> None:
        """Set the date, given timestamp string.

        Args:
            timestamp (str): Timestamp string in format see util.ts FMT_LONG

        Raises:
            ValueError: If the timestamp string is not in the correct format
        """
        try:
            self._date = get_dt(timestamp) # parse "LONG" format
            self._update_date()
        except ValueError as e:
            raise ValueError(
                f"Invalid timestamp format."
                f"Expected FMT_LONG={FMT_LONG}, got {timestamp}"
            ) from e

    def set_callback(self, update_detail_date_method):
        """Set callback to update the date in the parent widget."""
        self._callback = update_detail_date_method

    def toggle_spinbox(self):
        """ Toggle spinbox visibility and update button state """
        if self.spinbox:
            self.spinbox.destroy()
            self.spinbox = None
            self.lock_button.config(relief=tk.RAISED)  # Reset button state
        else:
            # Create spinbox inline with label
            self.spinbox = tk.Spinbox(self.frm,
                from_=-60, to=60, width=4,
                textvariable=self.spin_var,
                command=self._update_date)
            self.spinbox.pack(side=tk.LEFT, padx=5)
            self.lock_button.config(relief=tk.SUNKEN)  # Set button to "pressed"

    def _update_date(self) -> None:
        """Update the date based on spinbox value
           update display and and trigger callback."""
        try:
            days_offset = int(self.spin_var.get())
            adjusted_date = self._date + timedelta(days=days_offset)
            # display date in the GUI control using FMT_DATE
            self.date_label.config(
                text=get_ts(adjusted_date, fmt=FMT_DATE)
            )
            self.date_changed = True
            if self._callback:
                self._callback(get_ts(adjusted_date))
        except ValueError:
            self.spin_var.set(0)


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
