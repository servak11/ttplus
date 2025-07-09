from selenium import webdriver
from selenium.webdriver.common.by       import By
from selenium.webdriver.common.keys     import Keys
from selenium.webdriver.chrome.options  import Options
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui      import WebDriverWait
from selenium.webdriver.support.ui      import Select
from selenium.webdriver.support import expected_conditions as EC

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
    def __init__(self, url = None ):
        if 0:
            # Set up Edge options for headless mode (no visible window)
            edge_options = Options()
            edge_options.add_argument("--headless")
            # Improve performance
            edge_options.add_argument("--disable-gpu")  
            driver = webdriver.Edge(options=edge_options)

        #from selenium import webdriver
        edge_options = webdriver.EdgeOptions()
        #edge_options.add_argument("--headless")

        # Improve performance
        edge_options.add_argument("--disable-gpu")  
        edge_options.add_argument("--disable-features=EdgeIdentity")

        self.driver = webdriver.Edge(options=edge_options)
        self.driver = webdriver.Edge()

        if url is None:
            url = URL

        # Create a wait object (e.g., wait up to 10 seconds)
        self.wait = WebDriverWait(self.driver, 10)

        self.driver.get(url)

    def get_buttons(self):
        return self.driver.find_elements(By.TAG_NAME, "button")

    def open(self, url):
        self.driver.get(url)

    def E(self, id: str) -> WebElement:
        return self.wait.until(EC.presence_of_element_located((By.ID, id)))

    def wait_for_loaded(self):
        time.sleep(0.5)
        self.wait.until(lambda d: d.execute_script(
            """
            return document.readyState == "complete" && typeof spglNdNew == "function"
            """
            ))

    def browse_data(
            #date: str,
            #data: List[Entry],
            #driver=None,
            url=None
        ):
        pass

class Tiso(MyBrowser):
    def __init__(self, url = None ):
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
        name = self.trans_name_from_text(text)
        self.driver.execute_script(f'spglNdNew("{name}")')
        self.wait_for_loaded()
    def login(self):
        from config import u_r, p_d
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

    def select_ze(self):
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
        """
        first_of_month_str = get_ts(
            datetime.today().replace(day=1),
            fmt = FMT_DATE
        )

        # the "to date" is today, leave as is
        # locate the input field for "from date"
        # select content (Ctrl-a), send new date there, Tab to update value
        frdate = self.E("frD")
        frdate.click()
        frdate.send_keys( Keys.CONTROL, "a")
        frdate.send_keys( first_of_month_str, Keys.TAB)

        # Verify the change
        print(f"Updated start date: {frdate.get_attribute('value')}")
        print()
        #time.sleep(1)

        # Button "OK" appears, type="submit" id="load" name="load"
        # Find the button and click it
        button = self.E("load")
        button.click()
        time.sleep(1)

        """
        # 3. The timetracking sheet would now be loaded into an IFRAME !
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
        # <iframe frameborder="0" id="tblfldfr" style="width: 692.478px; height: 485.115px; overflow: hidden; border: none;" src="../tisowareClient/0b6436d9657672fa53b2c26e73b0cd3e19c1f4ad86f7c7132fed37b0f151184d/inff1079215197.html" name="tblfldfr" scrolling="no" class="inbindresize"></iframe>
        #  tblfldfr
        #
        # Need to SWITCH to the iframe using its ID !
        """
        iframe = d.find_element(By.ID, "tblfldfr")
        d.switch_to.frame(iframe)

        # Wait for the erfassung table to appear:
        table = self.wait.until(EC.presence_of_element_located((By.ID, "dvTblFLmain")))

        print("Table found:", table.id)
        # Find all rows inside the table
        rows = table.find_elements(By.TAG_NAME, "tr")
        # Get the row count
        row_count = len(rows)
        print(f"Number of rows: {row_count}")
        text_inputs = rows[0].find_elements(By.CSS_SELECTOR, "input[type='text']")
        inpus_count = len(text_inputs)
        # Print the IDs of all found input fields
        inf_list = []
        for inf in text_inputs:
            #print(inf.get_attribute("id") + ("-" * 15))
            inf_list.append( inf.get_attribute("id") )
        print(f"Reading {inpus_count} text inputs: {inf_list}")
        k=1
        row_list = []
        for row in rows:
            # find all input elements in selected row and add them to info row
            text_inputs = row.find_elements(By.CSS_SELECTOR, "input[type='text']")
            inf_list = []
            inf_list = [f"{k:>5}:"]  # row number
            for inf in text_inputs:  # get all values
                inf_list.append(inf.get_attribute("value"))
            #print("  ".join(inf_list))
            k=k+1
            # find the select element for "type of work" -- 2nd selector
            select_elements = row.find_elements(By.CSS_SELECTOR, "select")
            #print(select_elements[1].get_attribute("id"))
            selected_option = Select(select_elements[1]).first_selected_option
            #print(selected_option.text)
            inf_list.append(selected_option.text) # add option to the list
            row_list.append(inf_list)

        return row_list

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
    row_list = t.select_ze()
    #
    # works 09.07.2025
    #
    #print(row_list)

    time.sleep(13)
