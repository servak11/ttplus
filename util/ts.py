"""
Time handling module

datetime  : datetime object
timestamp : str
"""

from datetime import datetime

FMT_LONG = "%Y%m%d%H%M%S"
FMT_DATE = "%d.%m.%Y"

def dm_hm(ts):
    """
    Return time in format suitable to display in the table 2

    Parameters:
        ts (str): timestamp

    Returns:
        str: date andtime in "DD.MM HH:MM" format
    """
    return ts[6:8] + "." + ts[4:6] +" "+ ts[8:10] + ":" + ts[10:12]

def get_dt(ts : str, fmt = FMT_LONG):
    """
    Return datetime object for the timestamp

    Parameters:
        ts (str): timestamp

    Returns:
        datetime: datetime object
    """
    return datetime.strptime( ts, fmt)

def get_ts( dt : datetime = None, fmt = FMT_LONG):
    """
    Return time in "long" format, a text timestamp

    Parameters:
        dt (datetime): datetime
        fmt (bool, optional): format string (FMT_LONG, FMT_DATE, ...).
            Default FMT_LONG

    Returns:
        str: date and time in selected format
    """
    if dt == None:
        dt = datetime.now()
    return dt.strftime(fmt)

if __name__ == "__main__":
    print("--- Timestamp Handling Module Demo ---")

    # 1. Capture current time in the standard "Long" format
    # Uses FMT_LONG by default: "%Y%m%d%H%M%S"
    current_ts = get_ts()
    print(f"Current TS (Generated): {current_ts}")

    # 2. Format for display (DD.MM HH:MM)
    # This is useful for the Kanban cards or tables
    display_time = dm_hm(current_ts)
    print(f"UI Display Format:     {display_time}")

    # 3. Convert the string timestamp back to a datetime object
    # Essential for calculating task duration (end_time - start_time)
    dt_object = get_dt(current_ts)
    print(f"Datetime Object:       {dt_object}")

    # 4. Get current time in Date-only format
    date_only = get_ts(fmt=FMT_DATE)
    print(f"Current Date:          {date_only}")

    # 5. Testing with a manual string to ensure slicing logic is consistent
    manual_ts = "20260407131530" # April 7, 2026, 13:15:30
    print(f"\nManual Test TS:        {manual_ts}")
    print(f"Manual UI Format:      {dm_hm(manual_ts)}")
