## ttplus - work time tracker
#
# from mod_table import TableWidget
#
# TKinter table definition reusable class in a separate module.
# This class shall accept the columns definition structure such as
# (('Start Time', 20), ('End Time', 20), ('What was done', 500))
#
# The class shall be based on ttk.Treeview
# and use
# constant show_headings=True
# constant height=5
#

import tkinter as tk
from tkinter import ttk

"""
TableWidget class.

Parameters:
    parent: The parent Tkinter widget where the table will be placed.
    columns: A list of tuples [(column_name, column_width), ...].
"""
class TableWidget(ttk.Treeview):
    def __init__(self, parent, columns):
        self.parent = parent
        self.columns = columns
        self.si = 0 # start index to display data
        column_names = [col[0] for col in columns]  # Extract column names

        # Initialize the ttk.Treeview with predefined constants
        super().__init__(parent, columns=column_names, show="headings", height=5)

        # Configure columns dynamically
        for col_name, col_width in self.columns:
            self.heading(col_name, text=col_name)  # Set column heading
            self.column(col_name, width=col_width)  # Set column width

        # Pack the TreeView into the parent widget
        self.pack(fill="both", expand=True)

    """
    Insert a row of data into the table.

    Parameters:
        values: A list of values to populate the row (matches the column order).
        tags: Optional tags to style the row.
    """
    def insert_data(self, values, tags=None):
        self.insert("", "end", values=values, tags=tags)

    def clear_table(self):
        for row in self.get_children():
            self.delete(row)

    # supply dictionary of tasks
    def populate(self, d):
        for item in d.values():
            #print(item.__class__,item)
            # empty string means top level item in the tree
            # index="end" means attach at the end of the list
            #item_values = [i[1] for i in item]  # Extract column names
            # first item is full ID and we do not display that
            self.insert("", "end",
                values=list(item.values())[self.si:], tags=("blue",)
            )

    @staticmethod
    def _generate_short_id(full_task_id, length=5):
        """
        Generate a shorter, hashed version of the Task ID.

        Parameters:
            full_task_id: The full Task ID (e.g., timestamp).
            length: The number of characters to use from the hash.

        Returns:
            A short hash of the specified length.
        """
        import hashlib
        hash_object = hashlib.md5(full_task_id.encode())  # Use MD5 hashing
        return hash_object.hexdigest()[:length]           # Return the first `length` characters

if __name__ == "__main__":
    columns1 = (("ID",20), ("Task Name",400), ("Total work time",0))
    # Map short field names to their descriptive equivalents for display
    column_names = [col[0] for col in columns1]
    print (column_names)
    print ("_generate_short_id(20250404101919)=",TableWidget._generate_short_id("20250404101919"))
    print ("_generate_short_id(20250404111919)=",TableWidget._generate_short_id("20250404111919"))

