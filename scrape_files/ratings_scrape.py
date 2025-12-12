from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
from urllib.parse import urlparse
import concurrent.futures 

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException,
)


START_ID = 1         # first RMP school id to try
MAX_ID = 50000           # last id to try 
INVALID_STREAK_LIMIT = 10000
MAX_WORKERS = 15        # number of parallel browser processes

ratings_csv_file = "school_ratings.csv"
school_ids_file = "school_ids.csv"

ratings_columns = [
    "rmp_school_id",
    "school_name",
    "state",
    "overall_rating",
    "number_of_ratings",
    "facilities",
    "location",
    "happiness",
    "opportunities",
    "clubs",
    "social",
    "safety",
    "reputation",
    "food",
    "internet",
]

school_id_columns = [
    "rmp_school_id",
    "school_name",
    "state",
]

RETRY_COUNT = 3
RETRY_DELAY = 1


# helpers 

def get_school_id_from_url(url: str) -> str | None:
    """Extract numeric id from a URL like https://www.ratemyprofessors.com/school/1299"""
    try:
        path = urlparse(url).path
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "school":
            return parts[1]
    except Exception:
        return None
    return None


def setup_driver() -> webdriver.Chrome:
    """Sets up a new, independent Chrome driver instance."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    options.add_argument("--no-sandbox")
    options.add_argument("--ignore-certificate-errors")
    options.page_load_strategy = "eager"
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")


    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.cookies": 2,
        "profile.managed_default_content_settings.javascript": 1,  
        "profile.managed_default_content_settings.plugins": 2,
        "profile.managed_default_content_settings.popups": 2,
        "profile.managed_default_content_settings.geolocation": 2,
        "profile.managed_default_content_settings.media_stream": 2,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    print("Initializing browser...")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    driver.set_page_load_timeout(30)
    return driver


def init_csvs():
    # ratings CSV
    with open(ratings_csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ratings_columns)
        writer.writeheader()

    # mapping CSV
    with open(school_ids_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=school_id_columns)
        writer.writeheader()


def is_valid_school_page(driver) -> bool:
    """
    Heuristic: a valid school page
    - URL still contains /school/
    - MiniStickyHeader__MiniNameWrapper exists
    """
    url = driver.current_url
    if "/school/" not in url:
        return False

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'div[class*="MiniStickyHeader__MiniNameWrapper"]')
            )
        )
        return True
    except TimeoutException:
        return False


def scrape_school_name(driver) -> str:
    try:
        el = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'div[class*="MiniStickyHeader__MiniNameWrapper"]')
            )
        )
        return el.text.strip()
    except TimeoutException:
        return ""


def _parse_state_from_city_state(text: str) -> str:
    """Given text like 'Bryn Athyn, PA' → 'Bryn Athyn, PA'. Returns 'N/A' if not found."""
    if not text:
        return "N/A"
        
    # clean and split the input string by comma
    parts = [p.strip() for p in text.split(",") if p.strip()]
    
    # check for the city, state format (at least two parts)
    if len(parts) >= 2:
        # check if the last part (potential state) is a two-letter abbreviation
        last = parts[-1]
        if len(last) == 2 and last.isalpha():
            # if the format is correct, return the original, non-empty input string
            return text.strip() 
            
    # if the text is empty, doesn't contain a comma, or the last part isn't a 2-letter state
    return "N/A"


def scrape_state_abbrev(driver) -> str:
    """Extracts state abbreviation."""
    try:
        el = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'div[class*="MiniStickyHeader__MiniLocationWrapper"]')
            )
        )
        text = el.text.strip()
        state = _parse_state_from_city_state(text)
        if state != "N/A":
            return state
    except TimeoutException:
        pass
    except Exception:
        pass

    try:
        el = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'span[class*="HeaderDescription__StyledCityState"]')
            )
        )
        text = el.text.strip()
        state = _parse_state_from_city_state(text)
        if state != "N/A":
            return state
    except TimeoutException:
        pass
    except Exception:
        pass

    return "N/A"


def scrape_ratings(driver, rmp_school_id: str, school_name: str, state: str) -> dict:
    """Scrape ratings + category grades. Missing fields -> 'N/A'."""
    school_data = {
        "rmp_school_id": rmp_school_id,
        "school_name": school_name,
        "state": state,
        "overall_rating": "N/A",
        "number_of_ratings": "N/A",
        "facilities": "N/A",
        "location": "N/A",
        "happiness": "N/A",
        "opportunities": "N/A",
        "clubs": "N/A",
        "social": "N/A",
        "safety": "N/A",
        "reputation": "N/A",
        "food": "N/A",
        "internet": "N/A",
    }

    try:
        school_data["overall_rating"] = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'div[class*="OverallRating__Number"]')
            )
        ).text
    except TimeoutException:
        pass

    try:
        school_data["number_of_ratings"] = (
            driver.find_element(
                By.CSS_SELECTOR,
                'div[class*="SchoolRatingsContainer__SchoolRatingsCount"]',
            )
            .text.replace(" Ratings", "")
            .strip()
        )
    except NoSuchElementException:
        pass

    for container in driver.find_elements(
            By.CSS_SELECTOR, 'div[class*="CategoryGradeContainer"]'):
        try:
            category_title = (
                container.find_element(
                    By.CSS_SELECTOR, 'div[class*="CategoryTitle"]'
                )
                .text.lower()
                .strip()
            )
            if category_title in school_data:
                school_data[category_title] = container.find_element(
                    By.CSS_SELECTOR, 'div[class*="GradeSquare"]'
                ).text
        except NoSuchElementException:
            continue

    return school_data


# concurrent scraping

def scrape_single_school(school_id: int) -> tuple:
    driver = None
    try:
        driver = setup_driver()
    except Exception as e:
        print(f"ERROR (id={school_id}): Driver init failed: {e}")
        return False, school_id, None, None

    ratings_data = None
    id_data = None
    url = f"https://www.ratemyprofessors.com/school/{school_id}"

    print(f"\n--- Visiting ID {school_id}: {url} ---")

    try:
        driver.get(url)

        if not is_valid_school_page(driver):
            print(f"ID {school_id}: Not a valid school page.")
            return False, school_id, None, None

        current_id = get_school_id_from_url(driver.current_url) or str(school_id)
        school_name = scrape_school_name(driver)
        state_abbrev = scrape_state_abbrev(driver)

        if not school_name:
            print(f"ID {current_id}: Could not find school name; skipping.")
            return False, school_id, None, None

        print(f"VALID SCHOOL FOUND: [{current_id}] {school_name} ({state_abbrev})")

        id_data = {
            "rmp_school_id": current_id,
            "school_name": school_name,
            "state": state_abbrev,
        }

        ratings_data = scrape_ratings(driver, current_id, school_name, state_abbrev)

        return True, school_id, id_data, ratings_data

    except Exception as e:
        print(f"ERROR (id={school_id}): Scraping failed: {e}")
        return False, school_id, None, None

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# main loop

def main():
    init_csvs()

    school_ids_to_check = range(START_ID, MAX_ID + 1)

    print(f"Starting concurrent scraping of {MAX_ID - START_ID + 1} IDs with {MAX_WORKERS} workers...")

    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor, \
            open(ratings_csv_file, "a", newline="", encoding="utf-8") as ratings_f, \
            open(school_ids_file, "a", newline="", encoding="utf-8") as ids_f:

        ratings_writer = csv.DictWriter(ratings_f, fieldnames=ratings_columns)
        ids_writer = csv.DictWriter(ids_f, fieldnames=school_id_columns)

        future_to_id = {
            executor.submit(scrape_single_school, school_id): school_id
            for school_id in school_ids_to_check
        }

        for future in concurrent.futures.as_completed(future_to_id):
            school_id = future_to_id[future]

            try:
                is_success, _, id_data, ratings_data = future.result()

                if is_success:
                    ids_writer.writerow(id_data)
                    ids_f.flush()

                    ratings_writer.writerow(ratings_data)
                    ratings_f.flush()

                    print(f"SAVED_RATINGS (id={id_data['rmp_school_id']}, name={id_data['school_name']})")

            except Exception as e:
                print(f"ERROR (id={school_id}): Worker failed to return result: {e}")

    print("\nID-based ratings scraping complete. All workers shut down.")


if __name__ == "__main__":
    main()
