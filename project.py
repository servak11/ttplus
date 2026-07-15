import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk
from mod_db import Database

from util.ts import get_ts, get_fts


class ProjectManagerScreen(tk.Frame):
    """ Start Screen display:
       - Project List (json file list)
       - Project Info Pane
    """
    def __init__(self, parent, on_open_callback):
        super().__init__(parent, bg="#1e1e1e")
        self.on_open_callback = on_open_callback
        self.pack(fill="both", expand=True)

        # Grid Configuration (Column 0: Sidebar, Column 1: Info Pane)
        self.grid_columnconfigure(0, weight=0, minsize=260)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------------- LEFT SIDEBAR (File List) ----------------
        self.sidebar_frame = tk.Frame(self, bg="#552526", width=500)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False) # Keep fixed width

        sidebar_title = tk.Label(
            self.sidebar_frame,
            text="Project Files",
            font=("Courier New", 14, "bold"),
            fg="white",
            bg="#552526"
        )
        sidebar_title.pack(pady=(20, 10), padx=7, anchor="w")

        # Container frame for styling Listbox border
        list_border_frame = tk.Frame(self.sidebar_frame, bg="#3e3e3f", bd=1)
        list_border_frame.pack(fill="both", expand=True, padx=7, pady=7)

        # Scrollbar and Listbox
        scrollbar = ttk.Scrollbar(list_border_frame)
        scrollbar.pack(side="right", fill="none")

        self.file_listbox = tk.Listbox(
            list_border_frame,
            yscrollcommand=scrollbar.set,
            bg="#2d2d2d",
            fg="#e0e0e0",
            selectbackground="#0f3c6d",
            selectforeground="white",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=("Courier New", 14),
            activestyle="none"
        )
        self.file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        # Bind double-click and single-click selection
        self.file_listbox.bind("<<ListboxSelect>>", self.on_select)

        # Do initial read
        self.populate_file_list()

        # ---------------- RIGHT PANE (Info & Action Buttons) ----------------
        self.right_pane = tk.Frame(self, bg="#3e1e1e", width=500)
        self.right_pane.grid(row=0, column=1, sticky="nsew", padx=7, pady=7)
        self.right_pane.grid_rowconfigure(0, weight=1)
        self.right_pane.grid_rowconfigure(1, weight=0)
        self.right_pane.grid_columnconfigure(0, weight=1)

        # Top: Information Card Frame
        self.info_card = tk.Frame(self.right_pane, bg="#252526", bd=1, relief="solid", highlightbackground="#333333")
        self.info_card.grid(row=0, column=0, sticky="nsew", pady=(0, 20))

        info_header = tk.Label(
            self.info_card,
            text="File Information",
            font=("Courier New", 13, "bold"),
            fg="white",
            bg="#252526"
        )
        info_header.pack(anchor="w", padx=20, pady=(20, 15))

        # Metadata UI Fields
        self.lbl_filename = self.create_info_row("Selected File:", "None")
        self.lbl_size = self.create_info_row("File Size:", "N/A")
        self.lbl_nodes = self.create_info_row("Root Nodes:", "N/A")
        self.lbl_created = self.create_info_row("Created Date:", "N/A")
        self.lbl_modified = self.create_info_row("Modified Date:", "N/A")

        # Bottom: Buttons Panel
        self.button_frame = tk.Frame(self.right_pane, bg="#1e1e1e")
        self.button_frame.grid(row=1, column=0, sticky="ew")

        # Modern Flat tk.Buttons (Using pure Tkinter for accurate dark theme button colors)
        self.btn_new = tk.Button(
            self.button_frame,
            text="➕ New",
            command=self.create_new_entry,
            bg="#2d2d2d",
            fg="white",
            activebackground="#3d3d3d",
            activeforeground="white",
            relief="flat",
            font=("Courier New", 13, "bold"),
            padx=20,
            pady=8,
            cursor="hand2"
        )
        self.btn_new.pack(side="left")

        self.btn_open = tk.Button(
            self.button_frame,
            text="📂 Open",
            command=self.open_selected_file,
            bg="#1f538d",
            fg="white",
            activebackground="#14375e",
            activeforeground="white",
            relief="flat",
            font=("Courier New", 13, "bold"),
            padx=20,
            pady=8,
            state="disabled",
            cursor="hand2"
        )
        self.btn_open.pack(side="right")

    def list_json_files(self):
        """Return list of .json files in current directory."""
        return [f for f in os.listdir('.') if f.lower().endswith('.json')]

    def create_info_row(self, label_text, default_value):
        row_frame = tk.Frame(self.info_card, bg="#252526")
        row_frame.pack(anchor="w", padx=20, pady=6, fill="x")

        lbl_title = tk.Label(row_frame, text=label_text, font=("Courier New", 12, "bold"), fg="#aaaaaa", bg="#252526", width=14, anchor="w")
        lbl_title.pack(side="left")

        lbl_val = tk.Label(row_frame, text=default_value, font=("Courier New", 12), fg="white", bg="#252526", anchor="w")
        lbl_val.pack(side="left", fill="x", expand=True)
        return lbl_val

    def populate_file_list(self):
        self.file_listbox.delete(0, tk.END)
        # Populate listbox
        for json_file in self.list_json_files():
            self.file_listbox.insert(tk.END, f"  📄 {json_file}") # Padded left for a clean look

    def on_select(self, event):
        """Handle selection of a file from the listbox."""
        selection = self.file_listbox.curselection()
        if not selection:
            return

        # Clean the filename string from extra display padding/icons
        raw_val = self.file_listbox.get(selection[0])
        filename = raw_val.replace("  📄 ", "").strip()

        self.select_file(filename)


    def select_file(self, filename):
        # Enable the Open button
        self.btn_open.config(state="normal", bg="#1f538d")

        # Get file info
        try:
            size = os.path.getsize(filename)
            at = os.path.getatime(filename)
            ct = os.path.getctime(filename)
            mt = os.path.getmtime(filename)

            #with open(filename, "r", encoding="utf-8") as f:
            #    lines = sum(1 for _ in f)
            #info_text.set(f"File: {filename}\nSize: {size} bytes\nLines: {lines}")

            # Load through Database Class
            db = Database(filename)
            database = db.load_data()

            # Populate the info panel
            self.lbl_filename.config(text=filename)
            self.lbl_size.    config(text=f"{size} bytes")
            self.lbl_nodes.   config(text=f"{len(database['work_tasks'])} tasks")
            german_date = get_fts(ct, "%d.%m.%Y %H:%M")
            self.lbl_created. config(text=f"{german_date}")
            german_date = get_fts(mt, "%d.%m.%Y %H:%M")
            self.lbl_modified.config(text=f"{german_date}")
        except Exception as e:
            self.lbl_filename.config(text=f"Error reading file:\n{e}")
            self.lbl_size.    config(text="")
            self.lbl_nodes.   config(text="")
            self.lbl_created. config(text="")
            self.lbl_modified.config(text="")

    def create_new_entry(self):
        # 1. Clear info panel visual details
        self.lbl_filename.config(text="[New File Draft]")
        self.lbl_size.config(text="0 KB")
        self.lbl_nodes.config(text="0")

        now_str = get_ts( None, "%Y-%m-%d %H:%M")
        self.lbl_created.config(text=now_str)
        self.lbl_modified.config(text=now_str)

        # 2. Append new mock file to list
        count = self.file_listbox.size()
        new_filename = f"new_project_{count+1}.json"
        self.file_listbox.insert(tk.END, f"  📄 {new_filename}")

        #self.populate_file_list()

        # 3. Focus and select the newly created item
        last_index = count
        self.file_listbox.select_clear(0, tk.END)
        self.file_listbox.select_set(last_index)
        self.file_listbox.see(last_index)

        # Trigger details reload
        self.select_file(new_filename)

    def open_selected_file(self):
        selection = self.file_listbox.curselection()
        if not selection:
            return

        raw_val = self.file_listbox.get(selection[0])
        selected_file = raw_val.replace("  📄 ", "").strip()

        # Load through Simulated Database Class
        db = Database(selected_file)
        result = db.load_data()

        self.on_open_callback(selected_file)
