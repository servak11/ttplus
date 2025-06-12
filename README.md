## TTPlus - Yet Another Work Time Tracker

TKinter Application shall display two tables.

### Requirement 1: General GUI Setup

- **Table 1**: Displays the work tasks.
  - Columns: ID, Task Name, Total work time.
- **Textfield 1**: The textfield between the tables allows editing the task name.
- **Table 2**: Displays details of the work tasks.
  - Columns: Start Time, End Time, What was done.
- **Textfield 2**: The textfield below Table 2 allows editing the selected task detail ("What was done").

---

## Requirements Documentation

### General GUI Requirements

#### Requirement 1: Application Initialization
- At startup, a single entry exists in Table 1. This entry is shown in gray.
- Clicking on this entry allows editing in TextField 1, with the task ID defaulting to 1.

#### Requirement 2: Task Name Synchronization
- Editing the task name in TextField 1 updates the corresponding entry in Table 1.
- Task names are displayed in blue after editing.

#### Requirement 3: Task Details Display
- Selecting a task in Table 1 loads its details into Table 2.
- A placeholder "add detail ..." is appended to Table 2 for adding new entries.

#### Requirement 4: Task Detail Initialization
- When a new task is created, an initial detail entry is added to Table 2.
- This entry is shown in gray with the current time as the start time and the placeholder text "add detail ...".

#### Requirement 5: App Window Geometry
- The app's main window geometry is set to 800x500 pixels.
- Columns for ID, Start Time, and End Time are narrow, with time formatted as HH:MM.

#### Requirement 6: Note Detail Editor Initialization
- The Note Detail Editor is cleared and disabled when a new task is selected.
- The editor becomes enabled only when valid data is loaded for a task.

#### Requirement 7: Note Detail Editor Functionality
- The Note Detail Editor supports editing task notes, start time, end time, and task names.
- Unsaved changes in the editor prompt the user before clearing during task changes.

#### Requirement 8: Database Access
- A dedicated module encapsulates database interactions.
- Methods are provided for loading and saving data.

#### Requirement 9: Field Name Shortcuts
- To optimize database interaction, field name mappings are used:
  ```python
  db_field_shortnames = {
      "fti": "Full Task ID",
      "sti": "Short Task ID",
      "tnm": "Task Name",
      "twt": "Total Work Time"
  }
  ```

#### Requirement 10: User Feedback
- A "Help" menu provides options for "About," "Work Report," and "Detail Effort Report."

#### Requirement 11: Task Deletion
- A "Delete" button is provided next to TextField 1 for deleting tasks.

#### Requirement 12: Reporting
- Generate reports summarizing task details and time spent.
- Reports are sorted and formatted for clarity.

#### Requirement 13: Visual Styling
- Tasks are color-coded (e.g., gray for placeholders, blue for edited tasks).
- Consistent styling is applied to UI components (e.g., TreeView headers).

#### Requirement 14: Table Widget Module
- The table definition is implemented as a reusable class in a standalone Python module.
- The class derives from Tkinter's `TreeView` and supports general table operations like `insert_data`, `clear_table`, and `populate`.

#### Requirement 15: Database Access Module
- The database module encapsulates data handling logic.
- The module includes methods for `load_data` and `save_data`.

#### Requirement 16: Short Field Names
- To reduce database load, fields are named using shortcuts, as defined in a translation dictionary.

---

### Task Identification Requirements

#### Requirement 17: Task Placeholder
- The first task is displayed in gray in Table 1.
- Clicking on this placeholder allows editing in TextField 1.

#### Requirement 18: Task Detail Synchronization
- As the user types in TextField 1, the corresponding task name is updated in Table 1.

#### Requirement 19: Task Details Display
- When a task is selected in Table 1, its details are displayed in Table 2.
- Table 2 includes a placeholder "add detail ..." entry for adding new details.

#### Requirement 20: Task Detail Initialization
- When a new task is created, its first detail entry is automatically added to Table 2.
- This entry includes the current time as the start time and placeholder text "add detail ...".