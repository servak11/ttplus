import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk

from config import APP_TITLE, THEMES
from mod_db import Database

from util.ts import get_ts

from project import ProjectManagerScreen

from controls.statusbar import StatusBar
from controls.tasktable import TableWidget
from mod_detaileditor import TaskDetailEditor

from control import TTPlusController

class TTPlusScreen(tk.Frame):
    def __init__(self, parent, controller:TTPlusController, back_callback):
        super().__init__(parent, bg="#1e1e1e")
        self.pack(fill="both", expand=True)

        self.root = parent  # Reference to the main window
        self.back_callback = back_callback
        self.current_theme = "dark"  # Default theme    , TODO place into settings

        # --- UI Element References for Redrawing ---
        self.frames_to_color = []
        self.entries_to_color = []
        self.buttons_to_color = []

        # This is my controller!
        # Pass reference to the view so it can populate the tables after initialization
        self.controller = controller
        self.controller.set_view(self)

        # Build the initial layout elements
        self.create_widgets()

        # Apply the current theme colors immediately
        self.apply_theme(self.current_theme)

    def create_widgets(self):
        # Table 1 (Work Tasks)
        self.frame1 = ttk.LabelFrame(self, text="Work Tasks", style="Modern.TLabelframe")
        self.frame1.pack(fill="both", padx=8, pady=8)

        columns1 = (("ID", 20), ("Task Name", 400), ("Total work time", 0))
        self.table1 = TableWidget(self.frame1, columns1)
        self.table1.bind("<<TreeviewSelect>>", self.controller.on_table1_select)
        self.table1.si = 1 # column 0 is timestamp, start display from 1


        # Must reference the controller to populate the table after the screen is created
        # Latest shall be done here
        self.controller.set_view(self)
        self.controller.populate_table1()


        # Editor Row
        # Frame for Textfield 1 and Delete Button
        self.frame_task_editor = tk.Frame(self)
        self.frame_task_editor.pack(pady=8)
        self.frames_to_color.append(self.frame_task_editor)

        self.textfield_task_name = tk.Entry(
            self.frame_task_editor,
            width=50,
            relief="flat",
            font=("Tahoma", 12),
            bd=4
        )
        self.textfield_task_name.pack(side="left", padx=4)
        self.entries_to_color.append(self.textfield_task_name)
        self.textfield_task_name.bind("<KeyRelease>", self.controller.update_task_name)


        # Delete Button
        # plain U+1F5D1 without the U+FE0F variation selector: Tk has no glyph
        # for the selector and draws it as a second, empty cell, which made the
        # button twice as wide with the icon pushed to the left
        self.delete_button = tk.Button(
            self.frame_task_editor,
            text="\N{WASTEBASKET}",
            font=("Tahoma", 11),
            relief="flat",
            bd=0,
            command=self.controller.delete_task
        )
        self.delete_button.pack(side="left")
        self.buttons_to_color.append(self.delete_button)


        # Table 2 (Task Details)
        # frame2 is a ttk widget: it is themed through the "Modern.TLabelframe"
        # ttk style in apply_theme(), NOT via .configure(bg=...) which ttk
        # widgets reject ("unknown option -bg"). So keep it out of the
        # entries_to_color / frames_to_color lists.
        self.frame2 = ttk.LabelFrame(self, text="Task Details", style="Modern.TLabelframe")
        self.frame2.pack(fill="both", padx=5, pady=5)

        columns2 = (("Start Time", 20), ("End Time", 20), ("What was done", 500))
        self.table2 = TableWidget(self.frame2, columns2)
        self.table2.bind("<<TreeviewSelect>>", self.controller.on_table2_select)

        self.tde=TaskDetailEditor(self)
        self.tde.pack(pady=5)
        self.tde.set_callback(self.controller.update_task_details)

        # parent the status bar to this frame (not the window) so it is
        # destroyed together with the screen and does not leak onto the
        # Project Manager after navigating back
        self.status_bar = StatusBar(self)


    def build_menu(self, colors):
        """Rebuilds the top menu bar to show current selections and colors smoothly"""
        # Create a menu bar
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        # Add the "Help" menu
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_command(label="About", command=self.controller.show_about)
        menu_bar.add_command(label="Work Report", command=self.controller.show_report)
        menu_bar.add_command(label="Detail Effort Report", command=self.controller.show_task_report)
        menu_bar.add_command(label="Test", command=self.controller.tt_test_action)
        #menu_bar.add_command(label="TW", command=tw_report)
        menu_bar.add_command(label="View Note in Browser", command=self.controller.push_note_to_browser)
        menu_bar.add_command(label="Show Kanban", command=self.controller.show_kanban)

        # 2. Setup standard wrapper for the back callback to strip menus
        def go_back_cleanly():
            #self.root.config(menu="") # Remove the menu bar completely when leaving
            #self.back_callback()
            # Persist the project and stop timers before tearing the screen down
            self.controller.close()
            # Defer removing the menu and destroying the frame by 10ms
            self.root.after(10, lambda: self.root.config(menu=""))
            self.root.after(20, self.back_callback)

        menu_bar.add_command(label="Project Manager", command=go_back_cleanly)

        # --- Tools Cascading Menu ---
        self.tools_menu = tk.Menu(menu_bar, tearoff=0)
        self.tools_menu.add_command(
            label="Move Task Detail",
            command=self.controller.move_task_detail
        )
        self.tools_menu.add_command(
            label="Cancel Move",
            command=self.controller.cancel_move_task_detail
        )
        menu_bar.add_cascade(label="Tools", menu=self.tools_menu)
        self.update_tools_menu()

        # --- Theme Switcher Cascading Menu ---
        theme_menu = tk.Menu(menu_bar, tearoff=0)
        theme_menu.add_command(
            label="🌙 Dark Mode" if self.current_theme == "dark" else "   Dark Mode",
            command=lambda: self.apply_theme("dark")
        )
        theme_menu.add_command(
            label="☀️ Bright Mode" if self.current_theme == "bright" else "   Bright Mode",
            command=lambda: self.apply_theme("bright")
        )
        menu_bar.add_cascade(label="🎨 Themes", menu=theme_menu)

    def update_tools_menu(self):
        """Sync the Tools menu with the controller's pending move state."""
        label, enabled = self.controller.move_menu_state()
        self.tools_menu.entryconfigure(
            0, label=label, state="normal" if enabled else "disabled"
        )
        self.tools_menu.entryconfigure(
            1, state="normal" if self.controller.move_armed() else "disabled"
        )

    def apply_theme(self, theme_name):
        """
        Dynamically applies light or dark visual mappings to all elements

        Also build menu
        """
        self.current_theme = theme_name
        colors = THEMES[theme_name]

        # 1. Rebuild Menu configuration with updated checkboxes/emojis
        self.build_menu(colors)

        # 2. Update Standard Tkinter backgrounds
        self.configure(bg=colors["bg_main"])

        for frame in self.frames_to_color:
            frame.configure(bg=colors["bg_main"])

        for entry in self.entries_to_color:
            entry.configure(
                bg=colors["bg_input"],
                fg=colors["fg_main"],
                insertbackground=colors["fg_main"] # Text caret color
            )

        for button in self.buttons_to_color:
            button.configure(
                bg=colors["bg_input"],
                fg=colors["fg_main"],
                activebackground=colors["accent"],
                activeforeground=colors["fg_main"],
                highlightbackground=colors["bg_main"]
            )

        # 3. Update TTK Style Definitions
        style = ttk.Style()
        style.theme_use("clam")

        # LabelFrames
        style.configure("Modern.TLabelframe", background=colors["bg_main"], relief="flat")
        style.configure(
            "Modern.TLabelframe.Label",
            background=colors["bg_main"],
            foreground=colors["fg_muted"],
            font=("Arial", 10, "bold")
        )

        # Treeview Tables
        style.configure(
            "Treeview",
            background=colors["bg_input"],
            fieldbackground=colors["bg_input"],
            foreground=colors["fg_main"],
            rowheight=24
        )
        style.configure(
            "Treeview.Heading",
            background=colors["tree_header"],
            foreground=colors["fg_main"],
            relief="flat",
            font=("Arial", 10, "bold")
        )
        style.map("Treeview.Heading", background=[("active", colors["accent"])])

        # Color the tag selections inside your custom TableWidgets
        accent_color = colors["accent"]
        style.map("Treeview", background=[("selected", accent_color)])

        # Update text item tags inside the tables dynamically
        gray_color = "#888888" if theme_name == "dark" else "#555555"

        for table in (self.table1, self.table2):
            table.tag_configure("grey", foreground=gray_color)
            table.tag_configure("blue", foreground=colors["link"])

        # 4. The Detail Editor colours its own controls
        self.tde.apply_theme(colors)

    def apply_custom_styles(self):
        style = ttk.Style()

        # Style the TTK LabelFrames to integrate with the dark palette
        style.configure(
            "Modern.TLabelframe",
            background="#1e1e1e",
            relief="groove"
        )
        style.configure(
            "Modern.TLabelframe.Label",
            background="#1e1e1e",
            foreground="#aaaaaa",
            font=("Arial", 10, "bold")
        )

        # Style the Treeview headers and rows cleanly
        style.configure(
            "Treeview",
            background="#2d2d2d",
            fieldbackground="#2d2d2d",
            foreground="white",
            rowheight=24
        )
        style.configure(
            "Treeview.Heading",
            background="#3a3a3a",
            foreground="white",
            relief="flat",
            font=("Arial", 10, "bold")
        )
        # Prevent row header flashing an ugly white background on selection
        style.map("Treeview.Heading", background=[("active", "#4a4a4a")])
