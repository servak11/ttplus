## ttplus - work time tracker
#
# from mod_db import Database
#
import json
import os

class Database:
    def __init__(self, filename="tasks.json"):
        """
        Initialize the Database class.

        Parameters:
            filename: Name of the JSON file to store the database (default: tasks.json).
        """
        self.filename = filename

    def load_data(self):
        """
        Load data from the JSON file.

        Returns:
            A dictionary containing the database data.
        """
        if not os.path.exists(self.filename):
            # Return an empty structure if file doesn't exist
            return {"work_tasks": [], "task_details": {}}

        try:
            with open(self.filename, "r") as file:
                data = json.load(file)
            return data
        except (json.JSONDecodeError, FileNotFoundError):
            # Handle corrupted files or issues with file access
            return {"work_tasks": [], "task_details": {}}

    def save_data(self, data):
        """
        Save data to the JSON file.

        Parameters:
            data: A dictionary containing the data to be saved.
        """
        try:
            with open(self.filename, "w") as file:
                json.dump(data, file, indent=4)
        except Exception as e:
            print(f"Error saving data: {e}")
