## ttplus - work time tracker
#
## The Time Spin control
#
# class TimeSpinControl(ttk.Spinbox):
#   the spin control for editing hours or minutes shall allow changing the integer value it shows from 0 to a given maximum
#   with rollover to 0, after reaching that maximumm and spinning up
#   the spin control shall have width of 4
#   the text in all the control shall be confined to contain only 2 digits,
#   also when editing the text per keyboard,
#   if the number is less than 10, it shall display a leading 0, e.g. "01"
#   the text selection background color in all spin controls shall be lightblue

import tkinter as tk
from tkinter import ttk

class TimeSpinControl(ttk.Spinbox):
    def __init__(self, parent, max_value, **kwargs):
        super().__init__(parent, **kwargs)
        
        # Set the maximum and minimum values
        self.min_value = 0
        self.max_value = max_value
        
        # Configure the Spinbox
        self.configure(
            from_=self.min_value,
            to=self.max_value,
            wrap=True,
            width=4,
            justify="center",
            exportselection=0,  # Ensure selection works as expected
            font=("Verdana", 12)  # Use Verdana font, size 14
            #selectbackground="lightblue"  # Set the text selection background color
        )
        
        # Initialize value
        self.insert(0, "00")
        
        # Bind events for proper handling
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<Up>", self._increment)
        self.bind("<Down>", self._decrement)

    def _on_focus_out(self, event):
        """Ensure value is two-digit and within range when focus is lost."""
        self._validate_and_format()

    def _on_key_release(self, event):
        """Ensure value is formatted properly while typing."""
        self._validate_and_format()

    def _increment(self, event):
        """Handle the increment (Up arrow)."""
        current_value = int(self.get())
        next_value = current_value + 1 if current_value < self.max_value else self.min_value
        self.delete(0, "end")
        self.insert(0, f"{next_value:02d}")

    def _decrement(self, event):
        """Handle the decrement (Down arrow)."""
        current_value = int(self.get())
        next_value = current_value - 1 if current_value > self.min_value else self.max_value
        self.delete(0, "end")
        self.insert(0, f"{next_value:02d}")

    def _validate_and_format(self):
        """Ensure value is within range and properly formatted."""
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
