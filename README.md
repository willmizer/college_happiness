# College Happiness Simulator & Analytics Platform

[![Live Demo](https://img.shields.io/badge/Streamlit-Live_Demo-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://collegehappiness.streamlit.app/)

**A data-driven simulator for what actually makes college students happy.**

Traditional college rankings lean on prestige or endowment size. This project scrapes data from over 5,000 universities, models the relationship between campus amenities and student happiness, and lets a user simulate "what if we invested more in Facilities vs. Food?" for any specific school.

---

## Overview

- **Analyze:** view aggregated stats on facilities, safety, social life, and happiness across the US, ranked by state or school.
- **Simulate:** pick a school (e.g. *Florida Polytechnic University*) and a hypothetical investment level, and see which feature (Safety, Internet, Location, Opportunities, etc.) yields the biggest happiness gain per dollar.
- Built on a scraped dataset of ~3,000 institutions with 27 features, after cleaning ~5,700 raw scraped records and removing duplicate/ambiguous school listings.

## Tech Stack

- **App:** Python, Streamlit, Plotly
- **Modeling:** scikit-learn (Random Forest Regressor in a Pipeline with `MinMaxScaler` preprocessing)
- **Data Collection:** Selenium, BeautifulSoup4, `concurrent.futures`
- **Data Cleaning:** pandas, scikit-learn `IterativeImputer` (MICE)

## Data Pipeline

### 1. Scraping (`scrape_files/bs4_scrape.py`, `scrape_files/ratings_scrape.py`)
- **Selenium** traverses *RateMyProfessors*, handling dynamic JS loading to scrape subjective ratings (Happiness, Food, Safety, Clubs) for ~5,700 schools.
- **BeautifulSoup4** scrapes *NCES College Navigator* for objective data (tuition, student population, retention rates).
- 15 parallel workers via `concurrent.futures` cut scraping time from days to hours.

### 2. Data Cleaning (`clean_data.ipynb`)
- Merged datasets on fuzzy string matching (school name + city/state).
- Imputed missing demographic data with `IterativeImputer` (MICE), using correlations with other features.
- Removed outliers, closed institutions, and non-US territories to keep the model stable.
- **Deduplicated RateMyProfessors listings:** RMP has multiple listings for some schools (real branch campuses, e.g. FSU Panama City, and outright duplicate/mislabeled entries). Same-city duplicates were collapsed to the higher-review-count listing; genuine branch campuses were disambiguated by name (e.g. "Austin Community College (Round Rock)"); anywhere city data was too unreliable to tell the two apart, the smaller listing was dropped rather than guessed at.
- Final dataset: ~3,000 viable institutions, 27 features.

### 3. Modeling (`model_testing.ipynb`)
Three regression models were tested to predict a **Happiness Score (0.0–1.0)**:

| Model | Test R² | MAE | Notes |
| :--- | :--- | :--- | :--- |
| **Random Forest** | **0.75** | **0.063** | Best balance of accuracy and generalization, used in the app. |
| Linear Regression | 0.74 | 0.065 | Good baseline, missed non-linear relationships. |
| XGBoost | 0.72 | 0.066 | Slight overfitting on the training set. |

5-fold cross-validation on the Random Forest model: mean R² **0.744** (std 0.037).

Feature importance showed **Opportunities** and **Facilities** are the strongest predictors of happiness, well ahead of Food or Clubs.

### 4. The Application (`app.py`)
- **Smart Weighting (Analytics tab):** school scores are weighted `0.85 × feature score + 0.15 × log-scaled review count`, so schools with 10,000 reviews carry more authority than ones with 5.
- **Marginal Utility Engine (Simulator tab):** for a chosen school and investment delta, the app generates 50+ perturbations of its feature vector, batch-predicts happiness for each, and surfaces both the single biggest "quickest win" and the full marginal-gain curve per feature.

## Key Results

- Random Forest model: **R² 0.75**, MAE **0.063** on held-out test data.
- **Opportunities** and **Facilities** dominate the happiness prediction, far more than Food or Clubs.
- Review-count weighting meaningfully changes rankings versus raw averages, preventing low-sample schools from dominating leaderboards.

## Project Structure

```
college_biz/
├── app.py                        # Streamlit app (Analytics + Simulator tabs)
├── clean_data.ipynb              # Scraped-data cleaning & merging
├── model_testing.ipynb           # Model comparison & cross-validation
├── requirements.txt
├── scrape_files/
│   ├── bs4_scrape.py             # NCES College Navigator scraper
│   ├── ratings_scrape.py         # RateMyProfessors scraper (Selenium)
│   └── README.md
└── Web/
    ├── model.pkl                 # Trained Random Forest pipeline
    ├── metadata.json             # School defaults + controllable features
    ├── analysis_dataset.csv      # Cleaned, scraped dataset
    └── train_model.py            # Training script (documents model provenance)
```

## Run Locally

```bash
git clone https://github.com/willmizer/college_happiness.git
cd college_happiness
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

This launches both the Analytics and Simulator views (as tabs) at `http://localhost:8501`.

## Previously Hosted on AWS

This app was originally deployed as a Flask app on AWS instead of Streamlit. It worked, but keeping a paid EC2 instance running around the clock wasn't worth it for a portfolio demo that just needs to be reachable when someone clicks the link, so it moved to Streamlit Community Cloud's free hosting instead.

The original setup, briefly:
- **Instance:** AWS EC2 `t4g.micro` (ARM64/Graviton), Ubuntu 24.04 LTS.
- **Stack:** Nginx (reverse proxy) in front of Gunicorn (WSGI) running the Flask app.
- **Memory:** a 2GB swap file to cover pandas/scikit-learn's overhead on the instance's 1GB of RAM.
- **Process management:** a systemd service so the app auto-restarted on crash or reboot.
- **Domain:** a free DuckDNS subdomain pointed at the instance's public IP.

## Future Improvements

- **User accounts:** let university admins save their simulation scenarios.
- **Cost analysis:** integrate a cost-of-living API to correlate happiness with financial stress.
- **Sentiment analysis:** parse review *text* (NLP) rather than just numeric scores, to surface specific keywords ("small dorms," "parking nightmare").
- **Feature engineering:** expand the feature set to capture more of what drives student happiness.

## License

This project is shared for portfolio and educational purposes. Feel free to explore the code, but please reach out before reusing it commercially.

© 2026 Will Mizer
