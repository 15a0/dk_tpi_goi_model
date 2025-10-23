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
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

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
driver.set_page_load_timeout(60)  # Set a 60-second page load timeout

# -----------------------------------------------------------------------------------
# Sanity check: open a page with retries for network flakiness
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        print(f"Attempting to load page (Attempt {attempt + 1}/{MAX_RETRIES})...")
        driver.get("https://www.hockey-reference.com/leagues/NHL_2026.html")
        print("Page loaded successfully.")
        break  # Exit the loop if successful
    except TimeoutException:
        print(f"Timeout loading page on attempt {attempt + 1}. Retrying...")
        if attempt + 1 == MAX_RETRIES:
            print("Failed to load page after multiple retries. Exiting.")
            driver.quit()
            exit(1)

# --- Handle Cookie Banner ---
try:
    # Wait for the cookie consent banner and click "Accept All"
    print("Looking for and closing cookie banner...")
    accept_button = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept All')]"))
    )
    accept_button.click()
    print("Cookie banner accepted.")
    time.sleep(1) # Give it a moment to disappear
except TimeoutException:
    # If the banner doesn't appear, just print a message and continue
    print("Cookie banner not found or already accepted.")

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# Helper function to wait for download and rename the file
def wait_for_download_and_rename(download_dir, new_filename, timeout=30):
    print(f"Waiting for download to complete...")
    seconds = 0
    while seconds < timeout:
        # Check for .crdownload files (Chrome's temporary download file)
        crdownload_files = [f for f in os.listdir(download_dir) if f.endswith('.crdownload')]
        if not crdownload_files:
            # No .crdownload files, so find the most recent .xlsx file
            time.sleep(1) # Give a moment for the file to be fully written
            files = sorted(
                [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.endswith('.xlsx')],
                key=os.path.getctime
            )
            if files:
                latest_file = files[-1]
                new_filepath = os.path.join(download_dir, new_filename)
                print(f"Download complete. Renaming '{os.path.basename(latest_file)}' to '{new_filename}'...")
                # If the target file already exists, remove it to prevent errors
                if os.path.exists(new_filepath):
                    os.remove(new_filepath)
                os.rename(latest_file, new_filepath)
                return True
        seconds += 1
        time.sleep(1)
    print("Error: Download did not complete in time.")
    return False

# -----------------------------------------------------------------------------------
# Main download logic
DOWNLOAD_DIR = r"C:\Downloads\NHL2026"

# Attempt to download the first Excel workbook
try:
    print("--- Starting Download 1: Team Statistics ---")
    wait = WebDriverWait(driver, 20)
    stats_table = wait.until(EC.presence_of_element_located((By.ID, 'div_stats')))
    share_button_span = stats_table.find_element(By.XPATH, ".//preceding-sibling::div//span[contains(text(), 'Share & Export')]")
    driver.execute_script("arguments[0].click();", share_button_span)
    time.sleep(1)
    excel_button = share_button_span.find_element(By.XPATH, ".//following-sibling::div//button[contains(text(), 'Get as Excel Workbook')]")
    driver.execute_script("arguments[0].click();", excel_button)
    wait_for_download_and_rename(DOWNLOAD_DIR, "team_statistics.xlsx")

except Exception as e:
    print(f"An error occurred during the download process for Team Statistics: {e}")
    driver.save_screenshot('debug_screenshot_stats.png')
    print("Saved screenshot to debug_screenshot_stats.png")

# Attempt to download the second Excel workbook (Team Analytics)
try:
    print("\n--- Starting Download 2: Team Analytics ---")
    analytics_table = wait.until(EC.presence_of_element_located((By.ID, 'div_stats_adv')))
    share_button_span_2 = analytics_table.find_element(By.XPATH, ".//preceding-sibling::div//span[contains(text(), 'Share & Export')]")
    driver.execute_script("arguments[0].click();", share_button_span_2)
    time.sleep(1)
    excel_button_2 = share_button_span_2.find_element(By.XPATH, ".//following-sibling::div//button[contains(text(), 'Get as Excel Workbook')]")
    driver.execute_script("arguments[0].click();", excel_button_2)
    wait_for_download_and_rename(DOWNLOAD_DIR, "team_analytics.xlsx")

except Exception as e:
    print(f"An error occurred during the download process for Team Analytics: {e}")
    driver.save_screenshot('debug_screenshot_analytics.png')
    print("Saved screenshot to debug_screenshot_analytics.png")

# -----------------------------------------------------------------------------------
# Optional: wait and close
driver.quit()
print("Session ended.")