from webdriver_manager.chrome import ChromeDriverManager
import time
import csv
import string
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
    ElementNotInteractableException,
)
import random

# CSV file setup for input and output
input_csv_file = "colleges.csv"
ratings_csv_file = "school_ratings.csv"
reviews_csv_file = "school_reviews.csv"

ratings_columns = [
    "school_name",
    "state",           # state column in output
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
reviews_columns = ["school_name", "date", "review_score", "review_comment"]

RETRY_COUNT = 3
RETRY_DELAY = 1

# ---------- NAME MATCHING HELPERS ----------

PUNCT_TABLE = str.maketrans("", "", string.punctuation)
STOPWORDS = {
    "university",
    "college",
    "institute",
    "school",
    "of",
    "the",
    "at",
    "state",
    "and",
    "for",
}

# basic US state mapping for state-aware filtering
STATE_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}


def _tokens_for_match(name: str):
    """Normalize and tokenize a school name for fuzzy comparison."""
    if not name:
        return set()
    # handle & before stripping punctuation
    name = name.lower().replace("&", " and ")
    name = name.translate(PUNCT_TABLE)
    tokens = [t for t in name.split() if t and t not in STOPWORDS]
    return set(tokens)


def names_match(csv_name: str, page_name: str) -> bool:
    """
    Fuzzy name match between CSV school name and RMP page name.
    - token-based subset / Jaccard
    - explicit Virginia Tech special-case
    """
    if not csv_name or not page_name:
        return False

    csv_lower = csv_name.lower()
    page_lower = page_name.lower()

    # --- Hard special-cases for Virginia Tech ---
    if "virginia polytechnic institute and state university" in csv_lower and "virginia tech" in page_lower:
        return True
    if "virginia tech" in csv_lower and "virginia polytechnic" in page_lower:
        return True

    # --- General token-based matching ---
    csv_tokens = _tokens_for_match(csv_name)
    page_tokens = _tokens_for_match(page_name)

    if not csv_tokens or not page_tokens:
        return False

    # Exact token set equality
    if csv_tokens == page_tokens:
        return True

    # Subset match: allow the CSV tokens to be a subset
    # of page tokens (handles cases like "University of X" vs "X")
    if csv_tokens.issubset(page_tokens):
        return True

    # Jaccard similarity
    overlap = len(csv_tokens & page_tokens)
    union = len(csv_tokens | page_tokens)
    jaccard = overlap / union if union else 0.0
    if jaccard >= 0.6:
        return True

    # Old Virginia Tech special-case still as a fallback
    if "virginia" in csv_tokens and "tech" in page_tokens:
        return True

    return False

def location_matches_state(csv_state: str, loc_text: str) -> bool:
    """
    Use the CSV state to filter out obviously wrong search cards.
    Example: CSV state 'Florida' should NOT match a card whose location says 'Bayamon, PR'.
    """
    if not csv_state or not loc_text:
        return False

    csv_state_norm = csv_state.strip().lower()
    loc_lower = loc_text.lower()

    # direct match on full state name
    if csv_state_norm in loc_lower:
        return True

    # try abbreviation
    abbr = STATE_ABBR.get(csv_state_norm)
    if abbr and abbr.lower() in loc_lower:
        return True

    return False


# ---------- READ INPUT SCHOOLS (WITH STATE) ----------

schools = []  # list of dicts: {"name": ..., "state": ...}
try:
    with open(input_csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "Name of Institution" not in reader.fieldnames:
            raise ValueError("CSV file must contain 'Name of Institution' column")

        # Handle either "State Name" or "State" as the state column
        if "State Name" in reader.fieldnames:
            state_col = "State Name"
        elif "State" in reader.fieldnames:
            state_col = "State"
        else:
            raise ValueError(
                "CSV file must contain a state column named either 'State Name' or 'State'"
            )

        for row in reader:
            name = row["Name of Institution"].strip()
            state = row[state_col].strip() if row.get(state_col) is not None else ""
            if name:
                schools.append({"name": name, "state": state})
except FileNotFoundError:
    print(f"ERROR: {input_csv_file} not found.")
    exit(1)
except ValueError as e:
    print(f"ERROR: {e}")
    exit(1)

if not schools:
    print("ERROR: No schools found in the CSV file.")
    exit(1)

print(f"Loaded {len(schools)} schools")
print("First few:", [s["name"] for s in schools[:5]])

# ---------- CHROME SETUP ----------

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
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_page_load_timeout(30)

try:
    # CSV Header Setup
    with open(ratings_csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ratings_columns)
        writer.writeheader()
    with open(reviews_csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=reviews_columns)
        writer.writeheader()

    # Loop through schools
    for school in schools:
        school_name = school["name"]
        state = school["state"]

        print(f"\n--- Processing School: {school_name} ({state}) ---")

        try:
            # Construct and navigate to search URL
            search_query = school_name.replace(" ", "%20")
            search_url = f"https://www.ratemyprofessors.com/search/schools?q={search_query}"
            driver.get(search_url)

            # Wait for search results
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'a[class*="SchoolCard__StyledSchoolCard"]')
                    )
                )
            except TimeoutException:
                print(f"ERROR ({school_name}): Search results not found.")
                continue

            # Collect all school cards and their review counts + location
            school_cards = driver.find_elements(
                By.CSS_SELECTOR, 'a[class*="SchoolCard__StyledSchoolCard"]'
            )
            if not school_cards:
                print(f"ERROR ({school_name}): No school cards found in search results.")
                continue

            school_list = []
            for card in school_cards:
                try:
                    card_name = card.get_attribute("aria-label").replace(
                        "Link to school page for ", ""
                    )
                    review_count_text = card.find_element(
                        By.CSS_SELECTOR,
                        'div[class*="CardNumRating__CardNumRatingCount"]',
                    ).text
                    review_count = int(
                        review_count_text.replace(" ratings", "").replace(",", "")
                    )
                    school_url = card.get_attribute("href")
                    try:
                        loc_text = card.find_element(
                            By.CSS_SELECTOR,
                            'div[class*="CardSchoolLocation"]'
                        ).text
                    except NoSuchElementException:
                        loc_text = ""

                    school_list.append(
                        {
                            "name": card_name,
                            "review_count": review_count,
                            "url": school_url,
                            "location": loc_text,
                        }
                    )
                except (NoSuchElementException, ValueError) as e:
                    print(f"WARN ({school_name}): Failed to parse a school card: {e}")
                    continue

            if not school_list:
                print(f"ERROR ({school_name}): No valid school cards processed.")
                continue

            # ---------- STATE-AWARE FILTERING ----------
            # Prefer only cards whose location matches the CSV state
            state_filtered = [
                s for s in school_list
                if location_matches_state(state, s.get("location", ""))
            ]
            if state_filtered:
                school_list = state_filtered
                print(
                    f"INFO ({school_name}): Using {len(school_list)} candidates filtered by state."
                )
            else:
                print(
                    f"INFO ({school_name}): No candidates matched state '{state}'. "
                    f"Falling back to all {len(school_list)} candidates."
                )

            # Sort schools by review count (descending)
            school_list.sort(key=lambda x: x["review_count"], reverse=True)

            selected_school = None
            csv_display_name = school_name  # keep original for logs

            # Try each school in order of review count
            for school_info in school_list:
                driver.get(school_info["url"])
                try:
                    WebDriverWait(driver, 15).until(EC.url_contains("/school/"))

                    page_school_name = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, 'div[class*="MiniStickyHeader__MiniNameWrapper"]')
                        )
                    ).text

                    if names_match(csv_display_name, page_school_name):
                        selected_school = school_info
                        print(
                            f"SUCCESS ({school_name}): Name verified.\n"
                            f"  CSV:  {csv_display_name}\n"
                            f"  Page: {page_school_name}\n"
                            f"  Location: {school_info.get('location','')}\n"
                            f"  Reviews: {school_info['review_count']}"
                        )
                        break
                    else:
                        print(
                            f"WARN ({school_name}): Name mismatch.\n"
                            f"  CSV:  {csv_display_name}\n"
                            f"  Page: {page_school_name}\n"
                            f"  Location: {school_info.get('location','')}\n"
                            f"  Reviews: {school_info['review_count']}. "
                            f"Trying next school."
                        )
                        driver.get(search_url)
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, 'a[class*="SchoolCard__StyledSchoolCard"]')
                            )
                        )
                except TimeoutException:
                    print(
                        f"ERROR ({school_name}): School name element not found for "
                        f"{school_info['name']}."
                    )
                    driver.get(search_url)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, 'a[class*="SchoolCard__StyledSchoolCard"]')
                        )
                    )
                    continue

            if not selected_school:
                print(
                    f"ERROR ({school_name}): No matching school found after checking all search results."
                )
                continue

            print(
                f"SUCCESS ({school_name}): Selected {selected_school['name']} "
                f"with {selected_school['review_count']} reviews "
                f"({selected_school.get('location','')})."
            )

            # ---------- SCRAPE RATINGS ----------
            school_data = {
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
                By.CSS_SELECTOR, 'div[class*="CategoryGradeContainer"]'
            ):
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

            with open(ratings_csv_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=ratings_columns)
                writer.writerow(school_data)
            print(f"SAVED_RATINGS ({school_name})")

            # ---------- SCRAPE REVIEWS (your original loop, unchanged) ----------
            reviews_batch, processed_review_elements, total_reviews_saved = [], set(), 0

            while True:
                all_review_containers = driver.find_elements(
                    By.CSS_SELECTOR, 'div[class*="SchoolRatingContainer"]'
                )
                new_containers = [
                    el for el in all_review_containers if el not in processed_review_elements
                ]
                if not new_containers:
                    break

                for container in new_containers:
                    for attempt in range(RETRY_COUNT):
                        try:
                            score, comment, date = "N/A", "N/A", "N/A"
                            date = container.find_element(
                                By.CSS_SELECTOR, 'div[class*="TimeStamp"]'
                            ).text
                            try:
                                score = container.find_element(
                                    By.CSS_SELECTOR, 'div[class*="GradeSquare"]'
                                ).text
                                comment = container.find_element(
                                    By.CSS_SELECTOR, 'div[class*="RatingComment"]'
                                ).text
                            except NoSuchElementException:
                                score = container.find_element(
                                    By.CSS_SELECTOR,
                                    'div[class*="CardNumRating__CardNumRatingNumber"]',
                                ).text
                                comment = container.find_element(
                                    By.CSS_SELECTOR, 'div[class*="Comments__StyledComments"]'
                                ).text

                            if not date.strip() and not score.strip():
                                raise NoSuchElementException(
                                    "Validation failed: Scraped data was empty."
                                )

                            reviews_batch.append(
                                {
                                    "school_name": school_name,
                                    "date": date,
                                    "review_score": score,
                                    "review_comment": comment,
                                }
                            )
                            processed_review_elements.add(container)
                            break
                        except NoSuchElementException:
                            if attempt < RETRY_COUNT - 1:
                                time.sleep(RETRY_DELAY)
                    else:
                        print(
                            f"FAIL ({school_name}): Failed to process a review "
                            f"after {RETRY_COUNT} attempts."
                        )

                if len(reviews_batch) >= 10:
                    with open(reviews_csv_file, "a", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=reviews_columns)
                        writer.writerows(reviews_batch)
                    total_reviews_saved += len(reviews_batch)
                    print(
                        f"SAVED_REVIEWS ({school_name}): Batch of {len(reviews_batch)}. "
                        f"Total: {total_reviews_saved}"
                    )
                    reviews_batch.clear()

                # Close any popup
                try:
                    close_button = driver.find_element(
                        By.CSS_SELECTOR, 'button[class*="StyledCloseButton"]'
                    )
                    close_button.click()
                    time.sleep(0.5)
                except (NoSuchElementException, ElementNotInteractableException):
                    pass

                # Try to click "Show More"
                try:
                    show_more_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//button[text()='Show More']")
                        )
                    )
                    for click_attempt in range(RETRY_COUNT):
                        review_count_before = len(
                            driver.find_elements(
                                By.CSS_SELECTOR, 'div[class*="SchoolRatingContainer"]'
                            )
                        )
                        driver.execute_script("arguments[0].click();", show_more_button)
                        try:
                            WebDriverWait(driver, 10).until(
                                lambda d: len(
                                    d.find_elements(
                                        By.CSS_SELECTOR,
                                        'div[class*="SchoolRatingContainer"]',
                                    )
                                )
                                > review_count_before
                            )
                            break
                        except TimeoutException:
                            print(
                                f"WARN ({school_name}): 'Show More' click failed. "
                                f"Attempt {click_attempt + 1}/{RETRY_COUNT}."
                            )
                            time.sleep(1)
                    else:
                        print(f"ERROR ({school_name}): All 'Show More' click attempts failed.")
                        break
                except TimeoutException:
                    print(f"INFO ({school_name}): No more 'Show More' button found.")
                    break

            if reviews_batch:
                with open(reviews_csv_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=reviews_columns)
                    writer.writerows(reviews_batch)
                total_reviews_saved += len(reviews_batch)
                print(
                    f"SAVED_REVIEWS ({school_name}): Final batch of {len(reviews_batch)}. "
                    f"Total: {total_reviews_saved}"
                )

            print(
                f"--- Finished School: {school_name}. "
                f"Saved {total_reviews_saved} reviews. ---"
            )

        except Exception as e:
            print(f"A critical error occurred while processing {school_name}: {e}")
            continue

finally:
    print("\nAll scraping tasks complete. Shutting down.")
    if "driver" in locals() and driver:
        driver.quit()
