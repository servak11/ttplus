import tkinter as tk
from tkinter import ttk

from config import APP_TITLE, THEMES

from project import ProjectManagerScreen

# Model - View - Controller (MVC) Pattern:
#from mod_db import Database
from view    import TTPlusScreen
from control import TTPlusController

from web.flask_server import NoteServer


# --- Main Window / Screen Controller ---
class TTPlusWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("800x700+500+50")
        self.configure(bg="#1e1e1e")

        # Single Flask note/kanban server for the whole application.
        # It binds one port, so it must be created and started only once and
        # then shared with every project controller.
        self.note_server = NoteServer()
        self.note_server.start()

        # Clean Flat ttk Scrollbar styling
        self.setup_ttk_styles()

        # Save the active project when the window is closed
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.current_screen = None
        self.current_controller = None
        # the Tisoware booking applet is a separate persistent window
        self.buchen_applet = None
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
            # destroying the frame destroys all of its child widgets
            self.current_screen.destroy()
        # the active project (if any) was already closed on the way back
        self.current_controller = None
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

        # Create Controller and Screen instances, passing references to each other.
        # The controller reuses the window's shared note server.
        self.current_controller = TTPlusController(filepath, note_server=self.note_server)
        self.current_screen = TTPlusScreen(
            self,
            self.current_controller,
            back_callback=self.show_start_screen
        )

    def show_buchen(self, json_database):
        """
        Open the Tisoware booking applet for the given project.

        A single persistent applet window is kept; if it is already open it is
        just raised and refocused. Imported lazily so the app can start without
        Selenium installed (only the applet needs it).
        """
        if self.buchen_applet is not None and self.buchen_applet.winfo_exists():
            self.buchen_applet.json_database = json_database
            self.buchen_applet.deiconify()
            self.buchen_applet.lift()
            self.buchen_applet.focus_force()
            return
        try:
            from mod_buchen import BuchenScreen
        except Exception as e:
            print("Cannot open Buchen applet:", e)
            return
        self.buchen_applet = BuchenScreen(self, json_database)

    def on_close(self):
        """Persist the active project (if one is open) and close the window."""
        if self.current_controller is not None:
            self.current_controller.close()
        self.destroy()

if __name__ == "__main__":
    app = TTPlusWindow()
    app.mainloop()
