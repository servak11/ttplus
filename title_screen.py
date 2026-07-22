import tkinter as tk
from tkinter import ttk

from config import APP_TITLE, THEMES

from project import ProjectManagerScreen

# Model - View - Controller (MVC) Pattern:
#from mod_db import Database
from view    import TTPlusScreen
from control import TTPlusController


# --- Main Window / Screen Controller ---
class TTPlusWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("800x700+500+50")
        self.configure(bg="#1e1e1e")

        # Clean Flat ttk Scrollbar styling
        self.setup_ttk_styles()

        self.current_screen = None
        self.show_start_screen()

    def setup_ttk_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Minimalist Dark Scrollbar style
        style.configure(
            "TScrollbar",
            background="#3e3e3f",
            troughcolor="#2d2d2d",
            arrowcolor="#ffffff",
            relief="flat",
            borderwidth=0
        )
        style.map("TScrollbar", background=[("active", "#4e4e4f")])

        # Create a menu bar
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)
        menu_bar.add_command(label="About", command=self.show_about)

    def show_about(self):
        pass

    def show_start_screen(self):
        print("Switching to Project Manager Screen")
        if self.current_screen:
            self.current_screen.frame1.destroy()
            self.current_screen.destroy()
        print("Creating ProjectManagerScreen")
        self.current_screen = ProjectManagerScreen(self, on_open_callback=self.show_main_app)

    def show_main_app(self, filepath):
        """
        Model - View - Controller (MVC) Pattern:

        The Controller needs the screen instance (TTPlusScreen) to know where to insert the data.

        The Screen needs the Controller instance during __init__ to trigger the population.

        Architectural pattern: let the Controller act as the orchestrator.
        The controller
         - instantiate the screen,
          - save a reference to itself inside the screen,
           - then populate the tables.
        """
        if self.current_screen:
            self.current_screen.destroy()

        # Create Controller and Screen instances, passing references to each other
        self.current_controller = TTPlusController(filepath)
        self.current_screen = TTPlusScreen(
            self,
            self.current_controller,
            back_callback=self.show_start_screen
        )

if __name__ == "__main__":
    app = TTPlusWindow()
    app.mainloop()
