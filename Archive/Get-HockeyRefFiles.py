print("starting script")

import os
import time
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoAlertPresentException

# -----------------------------------------------------------------------------------
# Timestamp overlay
start_time = time.time()
start_datetime = datetime.datetime.fromtimestamp(start_time)
start_formatted = start_datetime.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
print("Start time:", start_formatted)

# -----------------------------------------------------------------------------------
# Chrome options with download preferences
chrome_options = Options()
chrome_options.add_argument("--headless=new")  # Use new headless mode
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

chrome_options.add_experimental_option("prefs", {
    "download.default_directory": r"C:\Downloads\NHL2026",
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True
})

# -----------------------------------------------------------------------------------
# WebDriver setup
os.environ['PATH'] += r';C:\Program Files\Chromedriver\chromedriver-win64\chromedriver-win64'
chrome_driver_path = r'C:\Program Files\Chromedriver\chromedriver-win64\chromedriver-win64\chromedriver.exe'

if not os.path.exists(chrome_driver_path):
    print(f"Chromedriver not found at: {chrome_driver_path}. Exiting...")
    exit(1)

chrome_service = Service(chrome_driver_path)
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

# -----------------------------------------------------------------------------------
# Sanity check: open a page
driver.get("https://www.hockey-reference.com/leagues/NHL_2026.html")
print("Chrome session launched and page loaded.")

# Optional: wait and close
time.sleep(2)
driver.quit()
print("Session ended.")