import selenium
from selenium import webdriver
from selenium.webdriver.common.by       import By
from selenium.webdriver.common.keys     import Keys
from selenium.webdriver.chrome.options  import Options
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui      import WebDriverWait
from selenium.webdriver.support.ui      import Select
from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import (
    NoSuchElementException,
    InvalidSessionIdException,
    WebDriverException
)

import json
import time
from datetime import datetime, timedelta

from util.ts import *

URL = 'http://menlogphost5.menlosystems.local/tisoware/twwebclient'


# connect to the webpage given by the url
# select PRZ sheet
# select and display the span of the date from 1.st of this month until today
# return all inputs relevant for user from that sheet
#
# @return list of lists
# - each list contains values of row elements
#   row #
#   WeekDay, Date DD.MM.YYYY
#   TT:MM start
#   TT:MM end
#   project
#   comment
#   project item - note last item in the list,
#   because added from selector element in the end
class MyBrowser:
    """
    Wrapper around Selenium Edge driver features:
     - auto-restart on session expiration.
     - get by element id
    """
    def __init__(self, url = None ):
        self.edge_options = webdriver.EdgeOptions()

        # Set up Edge options for headless mode (no visible window)
        #edge_options.add_argument("--headless")

        # Improve performance
        self.edge_options.add_argument("--disable-gpu")  
        self.edge_options.add_argument("--disable-features=EdgeIdentity")
        self.edge_options.add_argument("--disable-sync")
        self.edge_options.add_argument("--log-level=3")
        # Apply geometry via options - no jerking
        self.edge_options.add_argument("--window-size=800,700")
        self.edge_options.add_argument("--window-position=100,50")

        self.driver = self._start_driver()

        # Move window to x=100, y=50
        #self.driver.set_window_position(100, 50)
        # Resize window to width=1200, height=800
        #self.driver.set_window_size(800, 700)

        # Apply geometry in one call
        #self.driver.set_window_rect(x=x, y=y, width=w, height=h)


        if url is None:
            url = URL


        # Create a wait object (e.g., wait up to 10 seconds)
        self.wait = WebDriverWait(self.driver, 10)

        self.driver.get(url)


    """
    Init driver
    """
    def _start_driver(self):
        print("---------- session create")
        return webdriver.Edge(options=self.edge_options)

    """
    Re-Init driver when session expired
    """
    def restart(self):
        try:
            self.driver.quit()
        except Exception:
            pass
        self.driver = self._start_driver()


    def get_driver(self):
        return self.driver

    def is_alive(self):
        try:
            _ = self.driver.title
            return True
        except InvalidSessionIdException:
            return False
        except WebDriverException:
            # covers "chrome not reachable", "disconnected", etc.
            return False

    """
    Returns element or None.
    Automatically restarts driver if session expired.
    """
    def get_byid(self, element_id):
        try:
            return self.driver.find_element(By.ID, element_id)
        except InvalidSessionIdException:
            print("Session expired — restarting driver")
            self.restart()
            return None
        except NoSuchElementException:
            print(f"Element {element_id} not found")
            return None
        except WebDriverException as e:
            print(f"Unexpected webdriver error: {e}")
            return None


    def get_buttons(self):
        return self.driver.find_elements(By.TAG_NAME, "button")

    def open(self, url):
        self.driver.get(url)

    # get element by id when present
    def E(self, id: str) -> WebElement:
        return self.wait.until(EC.presence_of_element_located((By.ID, id)))

    # get element when clickable
    # 28.01.2026> the Tiso interface changed to more fancy one
    def EW(self, id: str) -> WebElement:
        elem = None
        try:
            elem = self.wait.until(
                EC.element_to_be_clickable((By.ID, id))
            )
        except selenium.common.exceptions.TimeoutException:
            elem = None
        return elem


    def wait_for_loaded(self):
        time.sleep(0.5)
        self.wait.until(lambda d: d.execute_script(
            """
            return document.readyState == "complete" && typeof spglNdNew == "function"
            """
            ))



class Tiso(MyBrowser):
    """
    extension of the selenium driver container to the tisoware application browser

    inherits self.driver
    """
    def __init__(self, url = None ):
        """
        automate login into timetracking system
        """
        super().__init__(URL)
        self.menujson = None
        self.login()

    def trans_name_from_text(self, text: str):
        """
        return name of the menu of that app
        """
        for e in self.menujson:
            if e["Text"] == text:
                return e["TransName"]

    def open_trans(self, text: str):
        """
        open the page corresponding to the menu of the menu in that app
        """
        try:
            name = self.trans_name_from_text(text)
            if self.is_alive():
                #print("---------- session valid")
                pass
            else:
                print("---------- session is expired as it seems")
            self.driver.execute_script(f'spglNdNew("{name}")')
            self.wait_for_loaded()
            return 1
        except selenium.common.exceptions.JavascriptException:
            return 0

    def login(self):
        """
        decode the password and login into timetracking system
        """
        if self.is_already_logged_in():
            print ("Already Logged in !")
            return

        from config import u_r, p_d

        # 28.01.2026> the Tiso interface changed to more fancy one
        # Even though the <input id="Uname"> is in the DOM,
        # the UI may animate, fade in, or be covered by a loading overlay.
        elem = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "Uname"))
        )

        # Find the username and password fields and enter credentials
        self.E("Uname").send_keys(u_r[:len(u_r)-3])
        self.E("PWD").send_keys(p_d[:len(p_d)-3])

        # .click() generates error in headless mode
        # selenium.common.exceptions.ElementClickInterceptedException:
        # button is not clickable at point (250, 419)
        #E("an").click()
        self.driver.execute_script("arguments[0].click();", self.E("an"))
        menujson_element = self.E("menujson")
        self.menujson = json.loads(menujson_element.get_attribute("innerHTML"))
        # debug the json config of the tisoware menu
        #print("self.menujson")
        #print(self.menujson)

    def is_login_screen_present(self):
        try:
            e = self.driver.find_element(By.ID, "Uname")
            return e.is_displayed()
        except NoSuchElementException:
            return False

    def is_already_logged_in(self):
        """
        the home page has a stable element (the menu - id=toggleMenu)
        check for it and detect if login was needed
        """
        try:
            self.driver.find_element(By.ID, "toggleMenu")
            return True
        except:
            return False

    def _sample_PRZ_entry(self):
        #self.open_trans("Erfassungsmappen")
        #time.sleep(1)
        #print(f"Opening PRZ Selector ...")
        #
        # if(checkPickerVoll(this.id)){
        #     setConfirmedChange(this.id, &quot;false&quot;);
        #     return false;
        # }else{
        #     setConfirmedChange(this.id, &quot;false&quot;);initWokSheet(this.id);}
        # }
        """
        # onchange="{ if(checkPickerVoll(this.id))
        # {setConfirmedChange(this.id, &quot;false&quot;);
        # return false;}else{setConfirmedChange(this.id, &quot;false&quot;);initWokSheet(this.id);}}">
        #
        # <option value="0"> </option>
        # <option value="004"
        #     id="FromDate05.05.2025!&amp;!ToDate05.05.2025!&amp;!">002 -
        #     BDE</option>
        # <option value="005"
        #     id="FromDate05.05.2025!&amp;!ToDate05.05.2025!&amp;!">003 -
        #     PRZ (kumuliert)</option>
        """
        print()


    def read_timetrack_list(self):
        """
        Tiso browser function which opens the PRZ
        and reads the list of timetracking records
        from the table created in the webpage.

        The table has the following columns:
        Restzeit - Datum - Von-Zeit - Bis-Zeit - Projekt - Projektvorgang - Kommentar

        some first record does not contain all fields, so check to not cause error when reading them later

        """
        d = self.driver
        """
        # 1. Select Zeiterfassungs Mappe - timetracking sheet
        #
        # Locate the select dropdown "Mappe", select value 006 for PRZ
        # <option value="006" selected="selected"
        #     id="FromDate05.05.2025!&amp;!ToDate05.05.2025!&amp;!">003 -
        #     PRZ (Zeitspanne)</option>
        """
        dropdown = Select(d.find_element("id", "wrksht"))
        dropdown.select_by_value("006")
        #time.sleep(1)
        """
        # 2. Select the date range from the 1st of the month

        1.st of month because that app does not allow
        to edit content of previous month, all records must be done
        within the current one

        # 3. Return all inputs relevant for user from that sheet

        Return: list of lists
        - each list contains values of row elements
          row #
          WeekDay, Date DD.MM.YYYY
          TT:MM start
          TT:MM end
          project
          comment
          project item - note last item in the list,
          because added from selector element in the end
        """
        first_of_month_str = get_ts(
            datetime.today().replace(day=20),
            fmt = FMT_DATE
        )

        USE_TO_DATE = False
        if USE_TO_DATE: # debug date - once the last date did not work
            todate = get_ts(
                datetime.today().replace(day=24),
                fmt = FMT_DATE
            )

        # the "to date" is today, leave as is
        # locate the input field for "from date"
        # select content (Ctrl-a), send new date there, Tab to update value
        date_select = self.EW("frD")
        #date_select.click()
        date_select.send_keys( Keys.CONTROL, "a")
        date_select.send_keys( first_of_month_str, Keys.TAB)

        # Verify the change
        print(f"Updated start date: {date_select.get_attribute('value')}")
        print()
        #time.sleep(1)

        if USE_TO_DATE: # debug date - once the last date did not work
            date_select = self.EW("toD")
            #date_select.click()
            date_select.send_keys( Keys.CONTROL, "a")
            date_select.send_keys( todate, Keys.TAB)

            # Verify the change
            print(f"Updated end date: {date_select.get_attribute('value')}")
            print()
            #time.sleep(1)

        # Button "OK" appears, type="submit" id="load" name="load"
        # Find the button and click it
        button = self.EW("load")
        button.click()
        time.sleep(1)

        """
        # IFRAME tblfldfr:
        #   The timetracking sheet would now be loaded into an IFRAME !!!
        #
        # Hierarchy
        # mainWinTable
        # - class content-main
        # -- reitermain
        # --- divAll
        # ---- div_tblfldfr
        # ----- .. table
        # ----- .. table
        # ----- .. td(iframe nmfrfrrest) td(id tren_tbl) td (iframe tblfldfr)
        # This is timetracking iframe
        # <iframe frameborder="0" id="tblfldfr" name="tblfldfr"
        #   style="width: 692.478px; height: 485.115px; overflow: hidden; border: none;"
        #   src="../tisowareClient/0b6436d9657672fa53b2c26e73b0cd3e19c1f4ad86f7c7132fed37b0f151184d/inff1079215197.html"
        #   scrolling="no" class="inbindresize">
        # </iframe>
        #
        # Need to SWITCH to the iframe using its ID !
        #
        #
        # 28.01.2026> the Tiso interface changed to more fancy one
        # No more IFRAME!!

        """
        if 0:
            try :
                iframe = d.find_element(By.ID, "tblfldfr")
                d.switch_to.frame(iframe)
            except NoSuchElementException:
                print("Error: cannot find IFRAME tblfldfr")
                return []
            # Wait for the erfassung table to appear:
            table = self.wait.until(EC.presence_of_element_located((By.ID, "dvTblFLmain")))
        # 28.01.2026> the Tiso interface changed to more fancy one
        table = self.EW("TBFL")

        print("---------- read_timetrack_list(): select Zeiterfassung")
        #print("dvTblFLmain Table found:", table.id)
        # Find all rows inside the table
        rows = table.find_elements(By.TAG_NAME, "tr")
        # Get the row count
        row_count = len(rows)
        print(f"Number of rows: {row_count}")
        if 0: # here exactlly lookign at the first row which is short and not filled - skip
            text_inputs = rows[0].find_elements(By.CSS_SELECTOR, "input[type='text']")
            inpus_count = len(text_inputs)
            # Print the IDs of all found input fields
            if 1:
                inf_list = []
                for inf in text_inputs:
                   #print(inf.get_attribute("id") + ("-" * 15))
                   inf_list.append( inf.get_attribute("id") )
                print(f"Reading {inpus_count} text inputs: {inf_list}")
        ### compose the read_timetrack_list
        k=1
        row_list = []
        for row in rows:
            #print(f"Processing row {k:>4} ...")
            # find all input elements in selected row and add them to info row
            text_inputs = row.find_elements(By.CSS_SELECTOR, "input")
            #print("- Row inputs found:", len(text_inputs))
            if len(text_inputs) < 8:
                # this is assert to avoid error when procesing rows
                #print("  -- skip row, not enough inputs")
                continue
            inf_list = []
            inf_list = [f"{k:>5}:"]  # row number
            k=k+1
            for inf in text_inputs:  # get all values
                inf_list.append(inf.get_attribute("value"))
            #print("  ".join(inf_list))
            # find the select element for "type of work" -- 2nd selector
            select_elements = row.find_elements(By.CSS_SELECTOR, "select")
            #print("- Row select_elements found:", len(select_elements))
            if len(select_elements) > 1:
                selected_option = Select(select_elements[1]).first_selected_option
                inf_list.append(selected_option.text) # add option to the list
            row_list.append(inf_list)

        return row_list


    def update_timetracking( self, tracker ):
        """
        Fill in the timetracking form.

        Note. In the browser - shoud have ALREADY SWITCHED to the IFRAME using its ID !

        This function loops through the displayed timetracking page
        and fills in the table with the form with the missing details.

        Args:
            tracker
                - the timetracking module used to compare
                  the Tiso timetracking against the ttplus data
                - tracker.tw_report the deviation list of the tracker
                  created in the timetracking.tw_report()
                  is needed for filling the form from its notes
        """
        #d = self.driver
        #if None == d:
        #    return

        # Wait for the erfassung table to appear:
        # only self.wait represents here the connection to the webpage
        # then we receive the table element with its children
        if 0:    # 28.01.2026> the Tiso interface changed to more fancy one
            try:
                table = self.wait.until(
                    EC.presence_of_element_located(
                        (By.ID, "dvTblFLmain")
                    )
                )
            except selenium.common.exceptions.TimeoutException:
                print("Error: cannot find timetracking table dvTblFLmain")
                return
        # 28.01.2026> the Tiso interface changed to more fancy one
        table = self.EW("TBFL")

        print("---------- update_timetracking()")
        if table is None:
            print("Error: cannot find timetracking table TBFL")
            return
        #print("dvTblFLmain Table found:", table.id)
        # Find all rows inside the table
        rows = table.find_elements( By.TAG_NAME, "tr")
        # Get the row count
        row_count = len(rows)
        print(f"Zeiterfassung HTML loaded. Number of rows: {row_count}")

        # always book to this project
        project_key = "9300_2025_Fs-DCP"
        # key 
        # Allg. Aufgaben 2026
        project_key = "9577"

        # iterate through all rows in the Zeiterfassung HTML table
        row_number = 1
        for row in rows:
            # find all input elements - put into a list
            #(old)text_inputs = row.find_elements(By.CSS_SELECTOR, "input[type='text']")
            text_inputs = row.find_elements(By.CSS_SELECTOR, "input")
            if len(text_inputs) < 8:
                # this is assert to avoid error when procesing rows
                print(f"  -- skip row {row_number}, not enough inputs")
                continue
            project_text = text_inputs[3].get_attribute("value")
            #comment_text = text_inputs[4].get_attribute("value") # must be empty
            #if "" == comment_text:
            if "" == project_text:
                #for original, closest, diff, note_text in self.timetrack_deviation:
                #    print(f"{original}  ➝  {closest}  | Difference: {diff:>4} minutes - {note_text}")
                # found empty project field, get its timestamp
                date_text = text_inputs[0].get_attribute("value")
                time_text = text_inputs[1].get_attribute("value")
                ts_key = date_text.split(", ")[1]  # Remove weekday
                # string key
                ts_key = ts_key + time_text
                # convert to datetime key - did this in tracker!
                ts_key = get_dt( ts_key, "%d.%m.%Y%H:%M")
                # timestamp is the combination of date and start time
                # in its webpage formats ("%d.%m.%Y%H:%M")
                # tracker already uses that as a key to detail name
                if 1: # debug timestamp
                    ts_dbg = date_text + "--" + time_text
                    print(f"  -- row {row_number:>4}:{ts_dbg}")
                if "" == project_text:
                    text_inputs[3].send_keys( project_key )
                try:
                    note_text = tracker.ts_note_dict[ts_key]
                    text_inputs[4].send_keys( note_text )
                except KeyError as ke:
                    print("Error: cannot get note for ", ts_key)
                # after the project was selected,
                # the select control below will be populated
                # find the select element for "type of work" -- 2nd selector
                # select.select_by_index(len(select.options) - 1)
                select_elements = row.find_elements(By.CSS_SELECTOR, "select")
                # now depending on the selector options, select either the last one
                #select_elements[1].send_keys(Keys.END) # select last option
                # or the first one
                select_elements[1].send_keys(Keys.ARROW_DOWN) # select first option
                
            row_number += 1



if __name__ == "__main__":

    print("My Browser!")
    b = MyBrowser("http://www.google.com")

    time.sleep(1)

    # Find all <button> elements and input[type=submit] (some buttons are inputs)
    buttons = b.get_buttons( )
    #inputs  = self.driver.find_elements(By.CSS_SELECTOR, "input[type='submit']")

    # Combine and print button texts
    print("Buttons found on the page:")
    for btn in buttons:
        label = btn.get_attribute("value") or btn.text
        print("-", label.strip())
        if 'Alle ablehnen' == label.strip():
            print (label.strip() + ' - found')
            break

    # click away cookies
    btn.click()

    time.sleep(3)

    b.open("http://www.bbc.com")

    buttons = b.get_buttons( )
    #inputs  = self.driver.find_elements(By.CSS_SELECTOR, "input[type='submit']")

    # Combine and print button texts
    print("Buttons found on the page:")
    for btn in buttons:
        label = btn.get_attribute("value") or btn.text
        print("-", label.strip())
        if 'Alle ablehnen' == label.strip():
            print (label.strip() + ' - found')
            break

    time.sleep(3)

    t=Tiso()
    t.open_trans("Erfassungsmappen")
    row_list = t.read_timetrack_list()
    #
    # works 09.07.2025
    #
    #print(row_list)

    time.sleep(13)
