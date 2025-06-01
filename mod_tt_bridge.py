from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC

from dataclasses import dataclass
from typing import List

import json
import time
from datetime import datetime, timedelta

import re

ALLG_PATTERN = r"[Aa]llg\."
URL = 'http://menlogphost5.menlosystems.local/tisoware/twwebclient'

@dataclass
class Entry:
    from_time:  str
    to_time:    str
    project:    str
    activity:   str
    comment:    str

def browse_data(
        #date: str,
        #data: List[Entry],
        driver=None,
        url=None
    ):

    # Set up Edge options for headless mode (no visible window)
    edge_options = Options()
    edge_options.add_argument("--headless")
    # Improve performance
    edge_options.add_argument("--disable-gpu")  

    if driver is None:
        # Initialize WebDriver
        driver = webdriver.Edge(options=edge_options)
    if url is None:
        url = URL

    driver.get(URL)

    # Create a wait object (e.g., wait up to 10 seconds)
    wait = WebDriverWait(driver, 10)

    def E(id: str) -> WebElement:
        return wait.until(EC.presence_of_element_located((By.ID, id)))

    def wait_for_loaded():
        time.sleep(0.5)
        wait.until(lambda d: d.execute_script(
            """
            return document.readyState == "complete" && typeof spglNdNew == "function"
            """
            ))

    from config import u_r, p_d

    # Find the username and password fields and enter your credentials
    E("Uname").send_keys(u_r[:len(u_r)-3])
    E("PWD").send_keys(p_d[:len(p_d)-3])
    E("an").click()

    menujson_element = E("menujson")
    menujson = json.loads(menujson_element.get_attribute("innerHTML"))

    def trans_name_from_text(text: str):
        for e in menujson:
            if e["Text"] == text:
                return e["TransName"]

    def open_trans(text: str):
        name = trans_name_from_text(text)
        driver.execute_script(f'spglNdNew("{name}")')
        wait_for_loaded()

    open_trans("Erfassungsmappen")

    time.sleep(1)

    print(f"Opening PRZ Selector ...")
    #
    # if(checkPickerVoll(this.id)){
    #     setConfirmedChange(this.id, &quot;false&quot;);
    #     return false;
    # }else{
    #     setConfirmedChange(this.id, &quot;false&quot;);initWokSheet(this.id);}
    # }
    #
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
    # <option value="006" selected="selected"
    #     id="FromDate05.05.2025!&amp;!ToDate05.05.2025!&amp;!">003 -
    #     PRZ (Zeitspanne)</option>
    activity = E("wrksht")
    activities = activity.find_elements(By.TAG_NAME, "option")
    a = None
    for a in activities:
        v = a.get_attribute("value")
        #print(f"V: {v} = {a.text}")
        v = a.get_attribute("selected")
        #print(f"S: {v} = {a.text}")
        v = a.get_attribute("id")
        #print(f"ID: {v} = {a.text}")
    print(f"ID: {v} = {a.text}")
    print()

    date_range = "FromDate26.05.2025!&amp;!ToDate30.05.2025!&amp;!"

    # Locate the select dropdown "Mappe"
    dropdown = Select(driver.find_element("id", "wrksht"))
    dropdown.select_by_value("006")

    #time.sleep(3)

    # Calculate the date one week before today
    new_date = (datetime.today() - timedelta(weeks=1)).strftime("%d.%m.%Y")

    # the "to date" is today, so ok
    # now locate the input field for "from date" and delete content
    frdate = E("frD")
    #for k in range(10):
    #    input_field.send_keys(Keys.BACKSPACE)
    frdate.click()
    frdate.send_keys(Keys.CONTROL, "a")
    frdate.send_keys(new_date, Keys.TAB)

    # Verify the change
    print(f"Updated start date: {frdate.get_attribute('value')}")
    print()

    #time.sleep(1)

    # Button "OK" appears, type="submit" id="load" name="load"
    # Find the button and click it
    button = E("load")
    button.click()

    time.sleep(1)

    # button loads table into iframe
    # Switch to the iframe using its ID
    iframe = driver.find_element(By.ID, "tblfldfr")
    driver.switch_to.frame(iframe)

    # Now interact with elements inside the iframe
    #input_field = driver.find_element(By.ID, "tbl_12_1")
    #input_field.send_keys("NewValue")


    # Wait for the erfassung table to appear:
    table = wait.until(EC.presence_of_element_located((By.ID, "dvTblFLmain")))

    print("Table found:", table.id)
    # Find all rows inside the table
    rows = table.find_elements(By.TAG_NAME, "tr")    
    # Get the row count
    row_count = len(rows)
    print(f"Number of rows: {row_count}")
    text_inputs = rows[0].find_elements(By.CSS_SELECTOR, "input[type='text']")
    inpus_count = len(text_inputs)
    print(f"Number of text inputs: {inpus_count}")
    # Print the IDs of all found input fields
    ali = [10,20,30,40,50]
    for inf in text_inputs:
        print(inf.get_attribute("id") + ("-" * 15))
    k=1
    row_list = []
    for row in rows:
        text_inputs = row.find_elements(By.CSS_SELECTOR, "input[type='text']")
        inf_list = []
        inf_list = [f"{k:>5}:"]
        for inf in text_inputs:
            inf_list.append(inf.get_attribute("value"))
        #print("  ".join(inf_list))
        k=k+1
        select_elements = row.find_elements(By.CSS_SELECTOR, "select")
        #print(select_elements[1].get_attribute("id"))
        selected_option = Select(select_elements[1]).first_selected_option
        #print(selected_option.text)
        inf_list.append(selected_option.text)
        row_list.append(inf_list)

    return row_list

    toT = E("tbl_12_1")
    toT.click()
    toT.send_keys(Keys.CONTROL, "a")
    toT.send_keys("entry.to_time", Keys.TAB)

    time.sleep(11)
    return

    # Locate the parent div element
    parent_div = driver.find_element(By.ID, "inTable")

    # Find all input fields inside the div
    input_fields = parent_div.find_elements(By.TAG_NAME, "input")

    # Print the input fields
    for input_field in input_fields[:40]:
        name = input_field.get_attribute("name")
        if name[:6] == "tbl_12":
            print(name, input_field.get_attribute("value"), input_field.get_attribute("type"))
            b="{ bubbles: true }"
            c="{ key: 'a' }"
            d="{ key: 'x' }"
            # Attempt 1. Try javascriptm to write into "hidden" field.
            #  - focus
            #  - change text
            #  - send input and change events -
            script2 = (
                f'e=document.getElementById("{name}");e.focus();'
                f'e.value = "YourTextHere";'
                f'e.type="text";'
                f'e.dispatchEvent(new Event("input", {b}));'
                f'e.dispatchEvent(new Event("change", {b}));'
                f'e.blur();'
                f'let event = new KeyboardEvent("keydown", {c});'
                f'e.dispatchEvent(event);'
                f'event = new KeyboardEvent("keydown", {d});'
                f'e.dispatchEvent(event);'
                f'setInterval(() => {{document.getElementById("tbl_12_1").value = "YourTextHere";}}, 1000);'
            )

            #f'document.querySelector("shadow-host").shadowRoot.getElementById("{name}").value = "YourTextHere";'
            driver.execute_script(script2)
            print(name, input_field.get_attribute("value"), input_field.get_attribute("type"))
            # inspite type="text" field still not interactable
            #input_field.send_keys(Keys.CONTROL, "a")
            print()
            #driver.execute_script("arguments[0].click();", input_field)
            # 
            # on hidden elements selenium throws 
            # selenium.common.exceptions.ElementNotInteractableException: Message: element not interactable
            #input_field.click()
            #input_field.get_attribute
            #input_field.send_keys(Keys.CONTROL, "a")
            #input_field.send_keys(Keys.BACKSPACE)
            #input_field.send_keys("test")


    # Now list all fields which are to be filled in
    #wait_for_loaded()
    if 0:
        for k in range(5):
            id  = f"tbl_7_{k}"
            print(id)
            try:
                input_field = E( id )
                # Select all and delete text
                input_field.send_keys(Keys.CONTROL, "a")
                input_field.send_keys(Keys.BACKSPACE)
                input_field.send_keys("test")
            except:
                print("cannot load")
            id  = f"tbl_12_{k}"
            print(id)
            try:
                input_field = E( id )
                # Select all and delete text
                input_field.send_keys(Keys.CONTROL, "a")
                input_field.send_keys(Keys.BACKSPACE)
                input_field.send_keys("test")
            except:
                print("cannot load")
    time.sleep(15)

    if 0:

        driver.execute_script(f'transaktionObj.toBuchEdit("{date}")')
        wait_for_loaded()

        E("inf").send_keys("Excel Übertrag", Keys.TAB)

        buchungen = E("tblbuchaend")
        print("TABLE", buchungen)

        for entry in data:
            time.sleep(0.5)

            tbody = buchungen.find_element(By.CSS_SELECTOR, "tbody")
            rows = tbody.find_elements(By.XPATH, './*')

            last_row = rows[-1]
            time.sleep(0.5)

            last_row.click()
            time.sleep(0.5)

            E("wttext1").send_keys("010", Keys.TAB)
            time.sleep(0.5)

            try:
                confirmDialog = E("btnNein").click()
                time.sleep(0.5)
            except Exception as exc:
                print("failed to close dialog:", exc)

            frT = E("frT")
            frT.click()
            frT.send_keys(Keys.CONTROL, "a")
            frT.send_keys(entry.from_time, Keys.TAB)

            toT = E("toT")
            toT.click()
            toT.send_keys(Keys.CONTROL, "a")
            toT.send_keys(entry.to_time, Keys.TAB)

            pr = E("pr")
            pr.send_keys(entry.project, Keys.TAB)
            time.sleep(0.5)

            activity = E("activity")
            activities = activity.find_elements(By.TAG_NAME, "option")
            default_activity = None
            matching_activity = None
            for a in activities:
                v = a.get_attribute("value")
                print(f"ACTIVITY: {v} = {a.text}")

                if re.search(ALLG_PATTERN, a.text) is not None:
                    default_activity = v
                if "XXX" not in a.text and re.search(entry.activity, a.text) is not None:
                    matching_activity = v

            print(f"wanted activity: {entry.activity}")
            print(f"default_activity = {default_activity}")
            print(f"matching_activity = {matching_activity}")

            if matching_activity is None:
                matching_activity = default_activity

            if matching_activity is not None:
                activitytext = E("activitytext")
                activitytext.click()
                activitytext.send_keys(Keys.CONTROL, "a")
                activitytext.send_keys(str(matching_activity), Keys.TAB)

            comment = E("com")
            comment.click()
            comment.send_keys(Keys.CONTROL, "a")
            comment.send_keys(str(entry.comment), Keys.TAB)

            time.sleep(0.5)

            E("netblbuchaend").click()

if __name__ == "__main__":
    browse_data()
