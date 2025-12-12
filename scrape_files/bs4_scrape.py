import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import re
import pandas as pd
from urllib.parse import urlparse, parse_qs
import time
import os
import random

BASE_URL = "https://nces.ed.gov/collegenavigator/"


session = requests.Session()
session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0 Safari/537.36"
        )
    }
)

retry_strategy = Retry(
    total=5,             # total retry attempts
    connect=5,
    read=5,
    backoff_factor=2.0,  # 0, 2, 4, 8, 16... seconds between retries
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS", "GET"],
    raise_on_status=False,
)

adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
session.mount("https://", adapter)
session.mount("http://", adapter)


def safe_get(url: str, timeout: int = 60):
    """
    Single-call GET using the global session with built-in retry/backoff.
    Returns response or None if all retries fail.
    """
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch URL after retries: {url}")
        print(f"        {type(e).__name__}: {e}")
        return None


# helper functions

def normalize(s: str) -> str:
    return s.strip().lower() if isinstance(s, str) else ""

def match_city_state(result_row: dict, target_city: str, target_state: str) -> bool:
    """
    Only requires the city to match (case-insensitive).
    State is ignored.
    """
    return normalize(result_row.get("city")) == normalize(target_city)


def get_srb_value(soup: BeautifulSoup, label_substring: str):
    td = soup.find(
        "td",
        class_="srb",
        string=lambda t: t and label_substring.lower() in t.lower(),
    )
    if not td:
        return None
    val = td.find_next_sibling("td")
    return val.get_text(" ", strip=True) if val else None


def get_table_value(soup: BeautifulSoup, label_text: str):
    td = soup.find("td", string=lambda t: t and label_text.lower() in t.lower())
    if not td:
        return None
    nxt = td.find_next_sibling("td")
    return nxt.get_text(" ", strip=True) if nxt else None


# search results scraper

def extract_all_school_data_bs(search_url: str):
    resp = safe_get(search_url, timeout=60)
    if resp is None:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    table = soup.find("table", id="ctl00_cphCollegeNavBody_ucResultsMain_tblResults")
    if not table:
        return results

    rows = table.find_all("tr", class_=lambda c: c and c.startswith("results"))

    for row in rows:
        try:
            link = row.find("a", href=re.compile(r"id="))
            if not link:
                continue

            name = link.get_text(strip=True)
            rel = link.get("href")
            full_url = requests.compat.urljoin(BASE_URL, rel)
            school_id = rel.split("id=")[-1].split("&")[0]

            td = link.find_parent("td")
            text_block = td.get_text("\n", strip=True)
            lines = [l.strip() for l in text_block.split("\n") if l.strip()]

            city, state = None, None
            if len(lines) >= 2 and "," in lines[-1]:
                c, s = lines[-1].split(",", 1)
                city = c.strip()
                state = s.strip()

            results.append(
                {
                    "name": name,
                    "city": city,
                    "state": state,
                    "id": school_id,
                    "url": full_url,
                }
            )

        except Exception:
            continue

    return results


# school detail scraper


def extract_school_details(school_url: str):
    resp = safe_get(school_url, timeout=60)
    # if request fails, return a dictionary of Nones which pandas will turn into N/A
    if resp is None:
        return {
            "campus_setting_raw": None,
            "student_population_total": None,
            "student_population_undergrad": None,
            "student_to_faculty_ratio": None,
            "retention_rate_avg": None,
            "acceptance_rate": None,
            "sat_median_total": None,
            "act_median_composite": None,
            "grad_rate_4yr": None,
            "avg_aid_awarded": None,
            "total_expenses_in_state": None,
            "total_expenses_out_state": None,
        }

    soup = BeautifulSoup(resp.text, "html.parser")

    # campus setting
    campus_setting_raw = get_srb_value(soup, "Campus setting:")
    # normalize campus setting to one of: Small, Midsize, Large, Remote
    campus_setting = None
    if campus_setting_raw:
        lower_val = campus_setting_raw.lower()
        for key in ["Small", "Midsize", "Large", "Remote"]:
            if key.lower() in lower_val:
                campus_setting = key
                break
    campus_setting_raw = campus_setting

    # student population
    student_pop_raw = get_srb_value(soup, "Student population:")
    student_population_total = None
    student_population_undergrad = None
    if student_pop_raw:
        mt = re.search(r"([\d,]+)", student_pop_raw)
        if mt:
            student_population_total = int(mt.group(1).replace(",", ""))
        mu = re.search(r"\(([\d,]+)\s*undergraduate", student_pop_raw, re.IGNORECASE)
        if mu:
            student_population_undergrad = int(mu.group(1).replace(",", ""))

    # student / faculty ratio
    ratio_raw = get_srb_value(soup, "Student-to-faculty ratio:")
    student_to_faculty_ratio = None
    if ratio_raw:
        mr = re.search(r"([\d\.]+)\s*to\s*1", ratio_raw)
        if mr:
            student_to_faculty_ratio = float(mr.group(1))

    # retention rates
    retention_rate_avg = None
    retention_full_time = None
    retention_part_time = None

    ret_th = soup.find("th", string=lambda t: t and "Retention Rates" in t)
    if ret_th:
        table = ret_th.find_parent("table")
        img = table.find("img", src=lambda s: s and "data=" in s) if table else None
        if img:
            qs = parse_qs(urlparse(img["src"]).query)
            data = qs.get("data")
            if data:
                parts = re.split(r"%3b|;", data[0])
                if len(parts) >= 1 and parts[0].isdigit():
                    retention_full_time = int(parts[0])
                if len(parts) >= 2 and parts[1].isdigit():
                    retention_part_time = int(parts[1])

    if retention_full_time and retention_part_time:
        retention_rate_avg = (retention_full_time + retention_part_time) / 2
    else:
        retention_rate_avg = retention_full_time or retention_part_time

    # acceptance rate
    acc_raw = get_table_value(soup, "Percent admitted")
    acceptance_rate = None  # percent, 57
    if acc_raw:
        m = re.search(r"([\d\.]+)", acc_raw)
        if m:
            acceptance_rate = float(m.group(1))

    # sat / act (median only)
    sat_ebrw_50 = sat_math_50 = act_comp_50 = None
    adm = soup.find("div", id="admsns")
    if adm:
        for table in adm.find_all("table", class_="tabular"):
            thead = table.find("thead")
            if not thead or "Test Scores" not in thead.get_text():
                continue
            tbody = table.find("tbody")
            if not tbody:
                continue

            for tr in tbody.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 4:
                    continue
                label = tds[0].get_text(strip=True).lower()
                median_match = re.search(r"\d+", tds[2].get_text())
                if not median_match:
                    continue
                median = int(median_match.group(0))

                if "reading" in label:
                    sat_ebrw_50 = median
                elif "sat math" in label:
                    sat_math_50 = median
                elif "act composite" in label:
                    act_comp_50 = median

    sat_median_total = (
        (sat_ebrw_50 + sat_math_50) if sat_ebrw_50 and sat_math_50 else None
    )
    act_median_composite = act_comp_50

    # graduation rate (4-year only)
    grad_rate_4yr = None
    grad_div = soup.find(
        "div",
        class_="tablenames",
        string=lambda t: t and "Bachelor's Degree Graduation Rates" in t,
    )
    if grad_div:
        table = grad_div.find_next("table", class_="graphtabs")
        img = table.find("img", src=lambda s: s and "data=" in s) if table else None
        if img:
            qs = parse_qs(urlparse(img["src"]).query)
            data = qs.get("data")
            if data:
                parts = re.split(r"%3b|;", data[0])
                if parts and parts[0].isdigit():
                    grad_rate_4yr = int(parts[0])

    # average aid awarded
    avg_aid_awarded = None
    aid_div = soup.find("div", id="finaid")
    aid_values = []

    if aid_div:
        for table in aid_div.find_all("table", class_="tabular"):
            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 5:
                    text = tds[-1].get_text(strip=True)
                    if "$" in text:
                        num = re.sub(r"[^\d]", "", text)
                        if num.isdigit():
                            aid_values.append(int(num))

    if aid_values:
        avg_aid_awarded = round(sum(aid_values) / len(aid_values), 2)

    # total expenses (On Campus, most recent year)
    total_expenses_in_state = None
    total_expenses_out_state = None

    exp = soup.find("div", id="expenses")
    if exp:
        total_td = exp.find("td", string=lambda t: t and "Total Expenses" in t)
        if total_td:
            table = total_td.find_parent("table")
            header_row = total_td.parent
            rows = list(header_row.find_next_siblings("tr"))

            last_year_idx = len(header_row.find_all("td")) - 2
            mode = None

            for tr in rows:
                first = tr.find("td")
                if not first:
                    continue
                txt = first.get_text(strip=True)

                if txt == "In-state":
                    mode = "in"
                    continue
                if txt == "Out-of-state":
                    mode = "out"
                    continue

                if txt == "On Campus" and mode:
                    tds = tr.find_all("td")
                    cell = tds[last_year_idx].get_text(strip=True)
                    num = re.sub(r"[^\d]", "", cell)
                    if num.isdigit():
                        if mode == "in":
                            total_expenses_in_state = int(num)
                        else:
                            total_expenses_out_state = int(num)
                    mode = None

    return {
        "campus_setting_raw": campus_setting_raw,
        "student_population_total": student_population_total,
        "student_population_undergrad": student_population_undergrad,
        "student_to_faculty_ratio": student_to_faculty_ratio,
        "retention_rate_avg": retention_rate_avg,
        "acceptance_rate": acceptance_rate,
        "sat_median_total": sat_median_total,
        "act_median_composite": act_median_composite,
        "grad_rate_4yr": grad_rate_4yr,
        "avg_aid_awarded": avg_aid_awarded,
        "total_expenses_in_state": total_expenses_in_state,
        "total_expenses_out_state": total_expenses_out_state,
    }


# main – csv driven

if __name__ == "__main__":
    df = pd.read_csv("school_ratings.csv")

    output_file = "school_numeric.csv"
    # if file already exists, remove it so we start fresh
    if os.path.exists(output_file):
        os.remove(output_file)

    total = len(df)

    for idx, row in df.iterrows():
        school_name = row["school_name"]
        city = row["city"]
        state = row["state"]

        search_url = f"{BASE_URL}?q={school_name}"
        results = extract_all_school_data_bs(search_url)

        # try to find a match where the city matches (state ignored)
        match = next(
            (r for r in results if match_city_state(r, city, state)),
            None,
        )

        # 2. if no city match is found AND there is exactly one result, use that
        if not match and len(results) == 1:
            match = results[0]

        if match:
            print(
                f"[INFO] {idx+1}/{total} Scraping {school_name} ({city}, {state})"
            )
            details = extract_school_details(match["url"])
        else:
            print(
                f"[WARN] {idx+1}/{total} No match found for {school_name} ({city}, {state})"
            )
            # if no match, populate details with Nones
            details = {
                "campus_setting_raw": None,
                "student_population_total": None,
                "student_population_undergrad": None,
                "student_to_faculty_ratio": None,
                "retention_rate_avg": None,
                "acceptance_rate": None,
                "sat_median_total": None,
                "act_median_composite": None,
                "grad_rate_4yr": None,
                "avg_aid_awarded": None,
                "total_expenses_in_state": None,
                "total_expenses_out_state": None,
            }

        # merge original school info + scraped details
        row_out = {
            "school_name": school_name,
            "city": city,
            "state": state,
        }
        row_out.update(details)

        # append this single row to CSV
        row_df = pd.DataFrame([row_out])
        write_header = idx == 0
        row_df.to_csv(
            output_file,
            mode="a",
            header=write_header,
            index=False,
            na_rep="N/A",
        )

        # small random delay to reduce throttling / timeouts
        time.sleep(random.uniform(0.3, 1.0))

    print(f"\n[DONE] Streamed all rows to {output_file}")
