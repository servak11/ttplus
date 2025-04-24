#
#
# Displays the "About Time Tracker Plus" information including version, copyright, and warning.
#
# Shows the icon img/time.png if the file exists, or displays a placeholder if not.

import tkinter as tk

class AboutDialog(tk.Toplevel):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.title("About Time Tracker Plus")
        self.resizable(False, False)

        # Load icon
        try:
            icon_image = tk.PhotoImage(file="img/time.png")
            icon_label = tk.Label(self, image=icon_image)
            icon_label.image = icon_image  # Keep a reference to avoid garbage collection
            icon_label.pack(pady=5)
        except tk.TclError:
            # Fallback if the icon is not found
            tk.Label(self, text="[Icon not found]").pack(pady=5)

        # Add details
        details = tk.Label(
            self,
            text="Time Tracker Plus\nVersion v.vv\nCopyright Andre Kovalev\n\nNo warranty, your data will be lost.",
            justify="center",
            font=("Verdana", 12)
        )
        details.pack(pady=10)

        # Close button
        close_button = tk.Button(self, text="Close", command=self.destroy)
        close_button.pack(pady=5)

def show_about():
    AboutDialog(master=root)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Time Tracker Plus")

    # Create a menu bar
    menu_bar = tk.Menu(root)
    root.config(menu=menu_bar)

    # Add the "Help" menu
    help_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_command(label="About", command=show_about)

    # Run the main application
    root.mainloop()
