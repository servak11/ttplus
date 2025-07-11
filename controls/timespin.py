"""
ttplus project - work time tracker

## The Time Spin control

This module implements a specialized spin control for time input in the ttplus application.
It provides a TimeSpinControl class that extends ttk.Spinbox to handle time input with
specific formatting and validation requirements.

Location:
    ./controls/timespin.py - Part of the controls package for ttplus UI components

Key Features:
- Two-digit display with leading zeros (e.g. "01" for 1)
- Value wrapping when reaching maximum/minimum
- Keyboard and arrow key navigation
- Automatic value validation and formatting
- Configurable maximum value (typically 23 for hours, 59 for minutes)
- The spin control shall have width of 4
"""

import tkinter as tk
from tkinter import ttk

class TimeSpinControl(ttk.Spinbox):
    """A specialized Spinbox control for time input (hours/minutes).

    This control enforces two-digit display with leading zeros and implements
    wrapping behavior when incrementing/decrementing values.

    Attributes:
        min_value (int): Minimum allowed value (always 0)
        max_value (int): Maximum allowed value (23 for hours, 59 for minutes)

    Args:
        parent: The parent widget
        max_value (int): Maximum value for the control (23 for hours, 59 for minutes)
        **kwargs: Additional keyword arguments passed to ttk.Spinbox
    """
    def __init__(self, parent, max_value, **kwargs):
        """Initialize the TimeSpinControl.

        Args:
            parent: The parent widget
            max_value (int):    Maximum value for the spinbox
                                (typically 23 for hours or 59 for minutes)
            **kwargs: Additional configuration options passed to ttk.Spinbox

        Raises:
            ValueError: If max_value is not a positive integer
        """
        if not isinstance(max_value, int) or max_value <= 0:
            raise ValueError("max_value must be a positive integer")
        super().__init__(parent, **kwargs)
        
        # Set the maximum and minimum values
        self.min_value = 0
        self.max_value = max_value
        
        # Configure the Spinbox
        self.configure(
            from_   = self.min_value,
            to      = self.max_value,
            wrap    = True,
            width   = 4,
            justify = "center",
            exportselection = 0,
            font    = ("Verdana", 12),
            background = "lightblue"
        )

        # Bind events for proper handling
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<KeyRelease>", self._on_key_release)


    def _on_focus_out(self, event):
        """Ensure value is two-digit and within range when focus is lost."""
        self._validate_and_format()
        # assume finished editing because focus out
        value = self.get()
        if len(value) < 1:
            self.insert(0, "00") # convert empty to 0
        else:
            if len(value) < 2:
                self.insert(0, "0") # insert leading 0

    def _on_key_release(self, event):
        """Ensure value is formatted properly while typing."""
        self._validate_and_format()

    def _validate_and_format(self):
        """Ensure value is within range and properly formatted."""
        value = self.get()
        if not value.isdigit():
            self.delete(0, "end")
        if value.isdigit():
            if len(value) > 2: # 3rd digit 
                # when 2 digits already entered, then third typed digit would appear
                # assume the new number shall be entred, so remove old number
                # and leave only 1 new digit
                self.delete(0, "end")
                self.insert(0, value[2:] ) # display last digit, assuming user enters new number
        value = self.get()
        if value.isdigit():
            value = int(value)
            if value < self.min_value:
                value = self.min_value
            elif value > self.max_value:
                value = self.max_value
        else:
            value = self.min_value
        # Ensure two-digit formatting
        if not value < 10:
            self.delete(0, "end")
            self.insert(0, f"{value:02d}")

# Example usage
if __name__ == "__main__":
    root = tk.Tk()
    root.title("TimeSpinControl Example")
    
    # Create a frame for layout
    frame = tk.Frame(root, padx=10, pady=10)
    frame.pack()

    # Hour Spin Control (0-23)
    hour_spin = TimeSpinControl(frame, max_value=23)
    hour_spin.pack(side="left", padx=5)

    # Minute Spin Control (0-59)
    minute_spin = TimeSpinControl(frame, max_value=59)
    minute_spin.pack(side="left", padx=5)

    root.mainloop()
