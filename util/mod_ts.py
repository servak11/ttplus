"""
Time handling module

datetime  : datetime object
timestamp : str
"""

from datetime import datetime

FMT_LONG = "%Y%m%d%H%M%S"

def dm_hm(ts):
    """
    Return time in format suitable to display in the table 2 

    Parameters:
        ts (str): timestamp

    Returns:
        str: date andtime in "DD.MM HH:MM" format
    """
    return ts[6:8] + "." + ts[4:6] +" "+ ts[8:10] + ":" + ts[10:12]

def get_dt(ts):
    """
    Return datetime object for the timestamp

    Parameters:
        ts (str): timestamp

    Returns:
        datetime: datetime object
    """
    return datetime.strptime( ts, FMT_LONG)

def get_ts(dt=None):
    """
    Return time in "long" format, a text timestamp

    Parameters:
        ts (str): timestamp

    Returns:
        str: date andtime in FMT_LONG
    """
    if dt == None:
        dt = datetime.now()
    return dt.strftime(FMT_LONG)
