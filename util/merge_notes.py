import json
import sys
import os

def merge_tasks(destination_file, source_file):
    """
    Merges task data from source_file into destination_file.
    Supports the TTPLUS structure: work_tasks and task_details.
    """
    # 1. Validation: Ensure both files exist
    if not os.path.exists(destination_file) or not os.path.exists(source_file):
        print(f"Error: One or both files not found.")
        return

    try:
        # 2. Load both JSON files
        with open(destination_file, 'r', encoding='utf-8') as f:
            dest_db = json.load(f)

        with open(source_file, 'r', encoding='utf-8') as f:
            src_db = json.load(f)

        # 3. Merge 'work_tasks' (The Headers)
        # Using .get() with an empty dict prevents crashes if a section is missing
        dest_work = dest_db.get('work_tasks', {})
        src_work = src_db.get('work_tasks', {})
        dest_work.update(src_work)
        dest_db['work_tasks'] = dest_work

        # 4. Merge 'task_details' (The Deep Notes/ADRs)
        dest_details = dest_db.get('task_details', {})
        src_details = src_db.get('task_details', {})
        dest_details.update(src_details)
        dest_db['task_details'] = dest_details

        # 5. Save the merged result back to the first file
        with open(destination_file, 'w', encoding='utf-8') as f:
            json.dump(dest_db, f, indent=4)

        print(f"Successfully merged {len(src_work)} tasks into {destination_file}.")

    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON. {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Check if user provided exactly two filenames
    if len(sys.argv) != 3:
        print("Usage: python merge_script.py <destination_json> <source_json>")
    else:
        file1 = sys.argv[1]
        file2 = sys.argv[2]
        merge_tasks(file1, file2)
