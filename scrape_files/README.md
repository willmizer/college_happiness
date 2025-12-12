**File Explanations**

review_scrape (Selenium)
-------------------------------

This script is a web scraper that automatically browses the Rate My Professors website using Selenium. It reads a list of school names from college_list.csv, searches for each one, and navigates to the school's review page. The main goal is to scrape and save the overall school ratings, categorical scores, and all available individual student reviews into two separate CSV files, school_ratings.csv and school_reviews.csv.

* * *

json_scrape (Requests/BeautifulSoup/JSON)
--------------------------------------------------

This script is another web scraper that collects detailed college profile data like admissions statistics, financial aid, and student demographics. It works by first reading a list of college names and URLs from college_list.csv. Instead of interacting with the webpage elements, it makes a request to the URL, finds a specific embedded JSON data block within the HTML source code, and extracts all the information directly from that structured JSON. The script supports a resume feature and appends all the newly scraped data to the all_colleges_data.csv file.


