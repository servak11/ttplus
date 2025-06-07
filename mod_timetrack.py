import json
from datetime import datetime

# work with TimeTracking app or web to obtain tracking data via bridge
class TimeTracking:
    
    #def __init__(self):
    #    """Initialize task tracking."""
    #    self.timetrack_deviation = []  # Dynamically created when tw_report() is called




    # obtain the timekeeping data
    # and store the list of reference data 
    # 
    # self.timetrack_deviation
    # - the reference array of tuples composed in this routine
    # - contains timetracking entry, the closest ttplus entry for it,
    #   the difference in minutes and the parent task of the ttplus entry
    #
    # when a note detail opened
    # compare its start date with the reference data
    # find nearest timekeeping entry
    # display the status in the activity status
    # - yellow no data
    # - green start date and time match
    # - red start date and time msmatch (by minutes)
    #
    # @param db json database from ttplus
    # @param empty_project_only if True, only stores the timetrack
    #       with empty project entry in the reference
    # @return earliest_date the records are missing entries
    def tw_report( self, db, empty_project_only = False):
        timetrack_list = []
        if 0:
            # use selenium to obtain the timekeeping data
            # TODO shall run in background thread ultimately
            #timetrack_list = browse_data()
            # save time tracking data to file
            with open("tw_data.json", "w") as json_file:
                json.dump(timetrack_list, json_file, indent=2)
        else:
            with open("tw_data.json", "r") as json_file:
                timetrack_list = json.load(json_file)

        #for row in timetrack_list:
        #    #for inf in row:
        #    if row[4] == "":
        #        print("  ".join(row))

        # address only items with empty task (row[4] == "")
        # Convert date strings stored in column 2
        # to datetime objects (ignoring weekday "Mo, ")
        # Updating the list with the cleaned dates.
        # converting dates to timestamps for row[2] and row[3] start and end ts
        for row in timetrack_list:
            row[1] = row[1].split(", ")[1]  # Remove weekday

            row[3] = datetime.strptime(row[1]+row[3], "%d.%m.%Y%H:%M")
            row[2] = datetime.strptime(row[1]+row[2], "%d.%m.%Y%H:%M")
        dates = []
        if empty_project_only:
            # row[4] empty means project was not assigned to this timetrack
            dates = [
                datetime.strptime(row[1], "%d.%m.%Y")
                for row in timetrack_list if row[4] == ""
            ]
        else:
            dates = [
                datetime.strptime(row[1], "%d.%m.%Y")
                for row in timetrack_list
            ]

        # Find the earliest date
        earliest_date = min(dates)

        # prepare list of task details starting earliest date
        td_report_list=[]
        for task_id, task_detail_list in db.items():
            for detail_dict in task_detail_list:
                # shall take the timestamp and only output the task details
                # when the timestamp later than earliest_date
                sts = datetime.strptime(detail_dict["Start Time"], "%Y%m%d%H%M%S")
                ets = datetime.strptime(detail_dict["End Time"], "%Y%m%d%H%M%S")
                if sts > earliest_date:
                    # in the dict of 4 items shall only take first 3
                    # of the values and place into list
                    # ALONG with task_id for backtrace
                    values_list = []
                    list(detail_dict.values())[:3]
                    values_list.append( sts )
                    values_list.append( ets )
                    values_list.append( detail_dict["What was done"] )
                    values_list.append( task_id )
                    td_report_list.append( values_list )
        # Sort by First Column
        td_report_list. sort(key=lambda x: (x[1]))
        #for row in td_report_list:
        #    print(row)
        # Now there are two lists
        # - timetracking list
        # - note detail list
        # Below code shall match the lists against each other

        # compose list of dates which have records
        unique_dates = list(dict.fromkeys(dates))
        #print("Date Range in this list:\n", unique_dates)

        # main timetracking loop
        # - for each working date
        # - check each task detail and calculate the delts
        # - between the timetracking start ts with task detail start ts
        # - (ts = python datetime object)
        if 0:
            # instead of looping through the list,
            # compare start date timestamps directly
            # -see below list1 and list2
            for d in unique_dates:
                for row in timetrack_list:
                    # ITEM   TYPE
                    # row[0] count string
                    # row[1] date string
                    # row[2] datetime start
                    # row[3] datetime end
                    # row[4-6] empty string (project, subp, )
                    if row[4] == "" :
                        if datetime.strptime(row[1], "%d.%m.%Y") == d :
                            #print(row)
                            for d_note in td_report_list:
                                # ITEM   TYPE
                                # d_note[0] datetime
                                # d_note[1] datetime
                                # d_note[2] note string
                                delta = d_note[0] - row[2]

        # 2 lists of start datetime objects to compare directly
        if empty_project_only:
            list1 = [row[2] for row in timetrack_list if row[4] == ""]
        else:
            list1 = [row[2] for row in timetrack_list]
        list2 = [(row[0], row[3]) for row in td_report_list]
        # (row[0], row[3]) tuple saves start time and task id
        # Find closest match for each datetime between the lists
        # self.timetrack_deviation is dynamically created class variable ...
        # it is created when tw_report() was called
        self.timetrack_deviation = []
        for dt1 in list1:
            # compare start time (item[0] from list2) with dt1 start time from list 1
            # and return both items from list2
            closest_dt, task_id = min(list2, key=lambda item2: abs(dt1 - item2[0]))
            time_diff_minutes = int((dt1 - closest_dt).total_seconds() / 60)
            self.timetrack_deviation.append((dt1, closest_dt, time_diff_minutes, task_id))
        # First check if self.timetrack_deviation variable exists
        # Given:
        # - list self.timetrack_deviation
        # - dict d_entry with task details
        # Find:
        #   the tuple from self.timetrack_deviation which d_entry["Start Time"]
        #   is equal to dt1 in the tuple
        #
        # Print results
        if 0:
            print("TIMEKEEPING          ➝  TTPLUS  closest      | Difference")
            for original, closest, diff, task_id in self.timetrack_deviation:
                print(f"{original}  ➝  {closest}  | Difference: {diff:>4} minutes")

        return (earliest_date)


        # Specification of Timetracking in TTPLUS.
        #
        # TTPLUS creates self.timetrack_deviation list of tuples during runtime
        # using a thread started from contact_timetracking() function
        # Two routines shall be performed periodically:
        # - read table from timetracking website (run browse_data() from bridge)
        # - run tw_report() as soon as note detail times change ... or new created
        #
        # The list self.timetrack_deviation shall contain tuples
        # (dt1, closest_dt, time_diff_minutes)
        # 
        # While loading task detail editor (TDE) using tde.load_data( d_entry )
        # TTPLUS shall check for presence of self.timetrack_deviation list
        # and try find the timestamp dt1 from the list 
        # which matches the loaded task detail timestamp d_entry["Start Time"]
        # Then is the time_diff_minutes is not 0 the red status shall be displayed
        # using  status_bar.s_set( datetime.strptime( closest_dt, "%d.%m.%Y%H:%M") )
        #
        #


    # the deviation list is composed from entries from the database
    # this means task detail is either in the list or does not have matching
    # timetracking task
    #
    # in this routine we detect if the task detail has a matching timetracking task
    #
    # @param d_entry dict entry from the ttplus database
    # @return datetime from deviation list corresponding to that entry
    #         None in error case
    def check_deviation(self, d_entry):
        """Checks if the task's 'Start Time' has a deviation."""
        # Ensure timetrack_deviation exists
        if not self.timetrack_deviation:
            return None  # No tracking data available

        # string to datetime
        db_sts = datetime.strptime(d_entry["Start Time"], "%Y%m%d%H%M%S")

        # Find matching tuple for d_entry["Start Time"]
        for track_ts, db_ds, time_diff_minutes, task_id in self.timetrack_deviation:
            #time_diff_minutes = int((track_ts - db_sts).total_seconds() / 60)
            #print(f"{track_ts}  ➝  {db_ds}  | Difference: {time_diff_minutes:>4} minutes")
            if db_ds == db_sts:
                return track_ts
                if time_diff_minutes != 0:
                    return f"OVERDUE: {db_ds.strftime('%d.%m.%Y %H:%M')} ({time_diff_minutes})"
                else:
                    return f"ON TIME: {db_ds.strftime('%d.%m.%Y %H:%M')}"
        
        return None #"No matching entry found"  # Handle cases where no match exists



# Test
if __name__ == "__main__":

    from mod_db import Database

    db = Database()
    database = db.load_data()

    tracker = TimeTracking()

    def mod_timetrack_test(d_entry):
        # Find deviation returns datetime from tracker db
        track_ts = tracker.check_deviation(d_entry)
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


    print(
        "Timekeeping earliest date " + # earliest_date
        tracker.tw_report(database["task_details"]).strftime('%d.%m.%Y')
    )

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
    d_entry = {"Start Time": tostr(datetime(2025, 5, 28, 6, 3, 16))}
    print("  -" + mod_timetrack_test(d_entry))


    print()
    print("*** Test 3. Check match date")
    d_entry = {"Start Time": tostr(datetime(2025, 5, 28, 9, 57))}
    print("  -" + mod_timetrack_test(d_entry))

    print()
    print("*** Test 4. Large unmatch")

    d_entry = {"Start Time": tostr(datetime(2025, 5, 30, 8, 57, 38))}
    print(d_entry)
    print("  -" + mod_timetrack_test(d_entry))
