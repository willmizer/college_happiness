# Data Scraper Documentation

This project uses two separate scripts to build the final dataset. The first script finds the schools and student opinions, while the second script adds the official statistics.

---

## 1. `ratings_scrape.py` 
**Goal:** Discover schools and collect student opinions.

This script acts like a robot browsing the web. Since we don't know every school's ID number, it uses a "brute force" method to find them.
* **What it does:** Tries every ID number from `1` to `50,000` on the *RateMyProfessors* website.
* **How it works:** It opens **15 invisible Chrome browsers** in parallel to work faster.
* **Data Collected:** If it finds a valid school, it saves the data: Happiness, Food Quality, Safety, Social Life, and Internet Speed.
* **Output:** Saves everything to `school_ratings.csv`.

---

## 2. `bs4_scrape.py` 
**Goal:** Add official government statistics to the schools we found.

This script takes the list of schools found by the first script and looks up their official records on the *National Center for Education Statistics (NCES)* website.
* **What it does:** Reads `school_ratings.csv` to get the school names.
* **How it works:** Searches for each specific school name on the government database.
* **Data Collected:** Grabs the "hard" numbers: Tuition Costs, SAT/ACT Scores, Acceptance Rates, and Student Population size.
* **Output:** Combines the ratings from step 1 with the stats from step 2 into the final file: `school_numeric.csv`.
