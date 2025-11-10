import json
from datetime import datetime
from util.ts import *


# work with TimeTracking app or web to obtain tracking data via bridge
class TimeTracking:
    """
    Specification of Timetracking in TTPLUS.
    
    TTPLUS creates self.timetrack_deviation list of tuples during runtime
    using a thread started from contact_timetracking() function
    Two routines shall be performed periodically:
    - read table from timetracking website (run browse_data() from bridge)
    - run tw_report() as soon as note detail times change ... or new created
    
    The list self.timetrack_deviation shall contain tuples
    (dt1, closest_dt, time_diff_minutes)
    
    While loading task detail editor (TDE) using tde.load_data( d_entry )
    TTPLUS shall check for presence of self.timetrack_deviation list
    and try find the timestamp dt1 from the list 
    which matches the loaded task detail timestamp d_entry["Start Time"]
    Then is the time_diff_minutes is not 0 the red status shall be displayed
    using  status_bar.s_set( datetime.strptime( closest_dt, "%d.%m.%Y%H:%M") )
    
    """    
    #def __init__(self):
    #    """Initialize task tracking."""
    #    self.timetrack_deviation = []  # Dynamically created when tw_report() is called


    def tw_report(
            self,
            d_ttplus_db : dict,
            d_timetrack_list : dict,
            empty_project_only = False):
        """
        Process and store timekeeping data,
        generating a reference list of typles **self.timetrack_deviation**
        for comparison between the online timekeeping and ttplus entries.

        Each item in the list `self.timetrack_deviation` is a tuple containing:
            - The time-tracking entry's start datetime.
            - The closest ttplus task detail entry's start datetime.
            - The difference in minutes between the two entries.
            - The text of the ttplus task detail name.

        Goal: prepare data to fill the work report in the time-tracking tool

        When a note detail is opened, the method compares its start date to the reference data,
        finds the nearest timekeeping entry, and determines the activity status:
            - Yellow: no data available.
            - Green: start date and time match.
            - Red: start date and time mismatch (by minutes).

        Args:
            d_ttplus_db (dict):
                The ttplus database containing task details, loaded from JSON.
            d_timetrack_list(dict):
                The timetracking tool (online) database,
                which was by the way previously obtained and stored into local file
                TODO here check how sync of the data is solved!
            empty_project_only (bool, optional):
                If True, only timetrack entries with empty project fields
                are stored in the reference data. Defaults to False.

        Returns:
            datetime or None: The earliest date among records missing entries,
            or None if all records are complete.
        """

        #for row in d_timetrack_list:
        #    #for inf in row:
        #    if row[4] == "":
        #        print("  ".join(row))

        #print("  GET d_timetrack_list: ")
        #for row in d_timetrack_list:
        #    print("  ++ "+str(row))


        # Convert timetrack_list
        # - timetrack_list format see tw_data.json or mod_tt_bridge.py
        # Option to address only items with empty task (row[4] == "")
        # Convert date strings stored in column 2 and 3 (start and end time)
        #   to datetime objects (ignoring weekday "Mo, ")
        # Clean  start and end timestamps:
        # - convert dates to datetime objects for row[2] and row[3]
        d_timetrack_list_work_copy = []
        for row in d_timetrack_list:
            # format (Do, 22.05.2025)
            dd = row[1].split(", ")[1]
            d_timetrack_list_work_copy.append(
                list((
                    dd,                         # Remove weekday -> day
                    get_dt( dd+row[2], "%d.%m.%Y%H:%M"), # ts
                    get_dt( dd+row[3], "%d.%m.%Y%H:%M"), # ts
                    0,     # just for row[4] to keep index?
                    row[4], # str
                    row[5] # str
                ))
            )

        # extract dates only to sort the array
        # - option 1 - only empty timetrack records
        # - option 2 - all timetrack records
        dates = []
        if empty_project_only:
            # row[4] empty means project was not assigned to this timetrack
            dates = [
                get_dt( row[0], FMT_DATE)
                for row in d_timetrack_list_work_copy if row[5] == ""
            ]
        else:
            dates = [
                get_dt(row[0], FMT_DATE)
                for row in d_timetrack_list_work_copy
            ]

        # Find the earliest date
        if not [] == dates:
            dt_earliest = min(dates)
        else:
            dt_earliest = datetime. now()

        # prepare list of task details starting earliest date
        # shall contain
        # - start datetime
        # -   end datetime
        # - task detail name
        # - task id (?)
        # -
        td_report_list=[]
        for task_id, task_detail_list in d_ttplus_db.items():
            for detail_dict in task_detail_list:
                # shall take the timestamp and only output the task details
                # when the timestamp later than dt_earliest
                #sts = datetime.strptime(detail_dict["Start Time"], "%Y%m%d%H%M%S")
                #ets = datetime.strptime(detail_dict["End Time"], "%Y%m%d%H%M%S")
                try:
                    dt_sta = get_dt( detail_dict["Start Time"] )
                    #print("dta-"+str(dt_sta)+" - "+detail_dict["What was done"])
                    dt_end = get_dt( detail_dict["End Time"] )
                    if dt_sta > dt_earliest:
                        # in the dict of 4 items shall only take first 3
                        # of the values and place into list
                        # ALONG with task_id for backtrace
                        values_list = []
                        list(detail_dict.values())[:3]
                        values_list.append( dt_sta )
                        values_list.append( dt_end )
                        values_list.append( detail_dict["What was done"] )
                        values_list.append( task_id )
                        td_report_list.append( values_list )
                except ValueError:
                    print(f" bad dt_sta = get_dt( {detail_dict["Start Time"]} )")
                    print(f" bad dt_end = get_dt( {detail_dict["End Time"]} )")

        # Sort by First Column
        td_report_list. sort(key=lambda x: (x[1]))

        #print("TTPLUS notes starting "+str(dt_earliest))
        #for row in td_report_list:
        #    print(row)
        #print("*" * 30)
        # Now there are two lists
        # - timetracking list
        # -  note detail list
        # Below code shall match the lists against each other

        # compose list of dates which have records
        unique_dates = list(dict.fromkeys(dates))
        print("Date Range in the unique date list:\n", unique_dates)

        ################
        # main timetracking loop
        # - create list self.timetrack_deviation
        #
        # 2 lists of start datetime objects to compare directly
        # - using python list comprehension
        # - one line replaces 3 levels of "for" iterations
        # create two lists of working dates
        # - list1 for online dates
        # - list2 for TTPLUS dates
        # then find dates in list2 closest to those in list1
        if empty_project_only:
            # start date from online
            list1 = [row[1] for row in d_timetrack_list_work_copy if row[5] == ""]
        else:
            list1 = [row[1] for row in d_timetrack_list_work_copy]
        # 
        list2 = [(row[0], row[2]) for row in td_report_list]

        # (row[0], row[2]) tuple saves start time and task detail name
        # Find closest match for each datetime between the lists
        # self.timetrack_deviation is dynamically created class member variable ...
        # it is created when tw_report() was called
        self.timetrack_deviation = []   # create deviation list
        self.ts_note_dict = {}          # create start time note dictionary
        for dt1 in list1:
            # compare start time (item[0] from list2) with dt1 start time from list 1
            # and return both items from list2
            closest_dt, note_text = min(list2, key=lambda item2: abs(dt1 - item2[0]))
            time_diff_minutes = int((dt1 - closest_dt).total_seconds() / 60)
            self.timetrack_deviation.append(
                (dt1,                   # tiso online entry datetime
                 closest_dt,            # ttplus datetime matching closely dt1
                 time_diff_minutes,     # 
                 note_text)
             )
            print(f"self.ts_note_dict[{dt1}] = {note_text}")
            self.ts_note_dict[dt1] = note_text

        # convert dates back to strings to make them serializable again
        #for row in d_timetrack_list:
        #    row[2] = get_ts( row[2], "%H:%M")
        #    row[3] = get_ts( row[3], "%H:%M")

        return (dt_earliest)


    def print_timetrack_deviation(self):
        """Print results of this module's work - timetrack_deviation array"""
        print("TIMEKEEPING          ➝  TTPLUS  closest      | Difference - note")
        for original, closest, diff, note_text in self.timetrack_deviation:
            print(f"{original}  ➝  {closest}  | Difference: {diff:>4} minutes - {note_text}")
        print("TIMEKEEPING          ➝  TTPLUS  closest      | Difference - note")


    def check_deviation(self, d_entry):
        """
        Determine if the provided task detail entry has a matching time-tracking entry.

        This method checks whether the 'Start Time' of a given task detail 
        (`d_entry`) exists within the list `self.timetrack_deviation`,
        which is generated by the `tw_report` method.

        See tw_report() for details of `self.timetrack_deviation` tuple

        The method compares the 'Start Time' in `d_entry` (converted to a datetime object)
        with the matching value in the deviation list. If a match is found, the corresponding
        time-tracking datetime is returned. If no match is found or if the deviation list
        has not been generated, it returns None.

        Args:
            d_entry (dict): A dictionary representing a task detail from the ttplus database,
                            containing at least the key 'Start Time' (formatted as '%Y%m%d%H%M%S').

        Returns:
            datetime or None:
                The corresponding time-tracking entry's datetime if a match is found,
                or None if no matching entry exists or deviation data is unavailable.
        """
        
        # Ensure timetrack_deviation exists
        if not self.timetrack_deviation:
            return None  # No tracking data available

        # convert to datetime
        db_sts = get_dt(d_entry["Start Time"])

        # Find matching tuple for d_entry["Start Time"]
        # obtain datetimes and compare
        for track_ts, db_ds, _, _ in self.timetrack_deviation:
            #time_diff_minutes = int((track_ts - db_sts).total_seconds() / 60)
            #print(f"{track_ts}  ➝  {db_ds}  | Difference: {time_diff_minutes:>4} minutes")
            if db_ds == db_sts:
                return track_ts

        return None #"No matching entry found"  # Handle cases where no match exists


# Test
if __name__ == "__main__":

    from mod_db import Database

    db = Database()
    database = db.load_data()

    # Example usage.
    tracker = TimeTracking()
    tracker_db = Database("tw_data.json")
    tracker_database = tracker_db.load_data()

    # tw_report() constructs the `self.timetrack_deviation` list
    # and returns earliest_date in the history of deviations
    earliest_date = tracker.tw_report(
        database["task_details"],
        tracker_database["records"],
        empty_project_only=True
    )

    tracker.print_timetrack_deviation()

    print(
        "Timekeeping earliest date "
        + get_ts( earliest_date, fmt=FMT_DATE)
    )

    if 1: ### TEST ###
        def mod_timetrack_test(d_entry):
            # Find deviation returns datetime from tracker db
            track_ts = tracker.check_deviation(d_entry)
            # TODO this is wrong function to test on arbitrary data,
            # this will work only for timetracking datetimes
            if None == track_ts:
                return "No matching entry found"  # Handle cases where no match exists

            db_sts = datetime.strptime(d_entry["Start Time"], "%Y%m%d%H%M%S")
            time_diff_minutes = int((track_ts - db_sts).total_seconds() / 60)

            if time_diff_minutes != 0:
                return f"OVERDUE: {db_sts.strftime('%d.%m.%Y %H:%M')} ({time_diff_minutes})"
            else:
                return f"ON TIME: {db_sts.strftime('%d.%m.%Y %H:%M')}"

        def tostr(dt):
            return dt.strftime("%Y%m%d%H%M%S")

        print()
        print("*** Test 1. Check arbitrary date")
        # normally using the database this shall not happen
        # as deviation always calculated to the existing d entry
        # but this is the test
        d_entry = {"Start Time": tostr(datetime(2025, 6, 1, 10, 0))}
        print(d_entry)
        print("  -" + mod_timetrack_test(d_entry))


        print()
        print("*** Test 2. Check deviation date")
        d_entry = {"Start Time": tostr(datetime(2025, 6, 24, 6, 3, 16))}
        print("  -" + mod_timetrack_test(d_entry))


        print()
        print("*** Test 3. Check match date")
        d_entry = {"Start Time": tostr(datetime(2025, 6, 24, 16, 36))}
        print(d_entry)
        print("  -" + mod_timetrack_test(d_entry))

        print()
        print("*** Test 4. Large unmatch")

        d_entry = {"Start Time": tostr(datetime(2025, 5, 30, 8, 57, 38))}
        print(d_entry)
        print("  -" + mod_timetrack_test(d_entry))
