# The College Happiness Simulator & Analytics Platform

[![Live Demo](https://img.shields.io/badge/AWS-Live_Demo-FF9900?style=for-the-badge&logo=amazon-aws)](http://98.89.165.214/)

**A data-driven approach to quantifying student happiness.**
This project scrapes data from over 5,000 universities, analyzes the correlation between campus amenities and student happiness, and provides a simulation platform for university administrators to optimize budget allocation for maximum student well-being.

---

## Project Concept & Goals

Traditional college rankings often rely on prestige or endowment size. I wanted to understand **what actually makes students happy**.

**The Goal:** Build a full-stack ML application that allows users to:
1.  **Analyze:** View aggregated stats on facilities, safety, social life, and happiness across the US.
2.  **Simulate:** Take a specific school (e.g., *Florida Polytechnic University*) and determine: *"If we invest 10% more into Facilities vs. Food, which yields a higher return on student happiness?"*

---

## Data Pipeline

The dataset was constructed from scratch using a dual-scraping strategy to merge subjective reviews with objective university statistics.

### 1. Scraping (`bs4_scrape.py` & `ratings_scrape.py`)
* **Selenium:** Used to traverse *RateMyProfessors*, handling dynamic JavaScript loading to scrape subjective ratings (Happiness, Food, Safety, Clubs) for ~5,700 schools.
* **BeautifulSoup4:** Used to scrape *NCES College Navigator* for hard data (Tuition, Student Population, Retention Rates).
* **Concurrency:** Implemented `concurrent.futures` with 15 parallel workers to reduce scraping time from days to hours.

### 2. Data Cleaning (`clean_data.ipynb`)
* **Merging:** Joined datasets on fuzzy string matching (School Name + City/State).
* **Imputation:** Used `IterativeImputer` (MICE) to fill missing demographic data based on correlations with other features.
* **Filtering:** Removed outliers, closed institutions, and non-US territories (Guam, Puerto Rico) to ensure model stability.
* **Final Dataset:** ~3,200 viable institutions with 27 distinct features.

---

## Model Development & Testing

I tested three distinct regression models to predict the target variable: **Happiness Score (0.0 - 1.0)**.

### Model Performance (`model_testing.ipynb`)

| Model | Test R² | MAE | Analysis |
| :--- | :--- | :--- | :--- |
| **Random Forest** | **0.75** | **0.063** | **Best balance of accuracy and generalization.** |
| Linear Regression | 0.74 | 0.065 | Good baseline, but missed non-linear relationships. |
| XGBoost | 0.72 | 0.066 | Slight overfitting on the training set. |

### Cross Validation testing 

| Model | CV R² | Mean CV R² | std R² |
| :--- | :--- | :--- | :--- |
| **Random Forest** | **[0.80847141 0.71255238 0.76066599 0.70785308 0.73025952]** | **0.744** | **0.0372** |

### Key Insights
Feature importance analysis revealed that **Opportunities** and **Facilities** are the strongest predictors of student happiness, significantly outweighing **Food** or **Clubs**. Also, for **ML insights** these cross validation scores are excellent for my project goal.

*The final model (`model.pkl`) is a Random Forest Regressor integrated into a Scikit-Learn Pipeline with MinMaxScaler preprocessing.*

---

## The Application 

### Smart Weighting Algorithm (Analytics Page)
Ranking isn't just about the raw score; it's about confidence. I implemented a weighted ranking system:
$$\text{Score} = (0.85 \times \text{Feature Score}) + (0.15 \times \log(\text{Review Count}))$$
This ensures schools with 10,000 reviews have higher authority than schools with 5 reviews.

### Marginal Utility Engine
When a user adjusts the "Investment Slider" on the frontend:
1.  The backend generates **50+ perturbations** of the school's feature vector.
2.  It runs batch predictions to calculate the **marginal happiness gain** for every 1% increase in specific features (Safety, Internet, Location, etc.).
3.  **Result:** The app recommends the "Quickest Win" (*Fix the Internet first*) vs. "Long Term Strategic Investments" (*Improve Location/Opportunities*).

---

## Infrastructure & Deployment

The application is deployed on AWS using a budget friendly architecture designed for maximum performance on the Free Tier.

* **Instance:** AWS EC2 `t4g.micro` (ARM64/Graviton).
* **OS:** Ubuntu 24.04 LTS.
* **Web Server:** Nginx (Reverse Proxy) $\rightarrow$ Gunicorn (WSGI) $\rightarrow$ Flask.
* **Optimization:**
    * **Swap Space:** Allocated 2GB swap file to handle the memory overhead of Pandas/Scikit-Learn on a 1GB RAM instance.
    * **Systemd:** Configured as a background service for auto-healing/restarts.
    * **Network:** Custom VPC settings for secure HTTP traffic handling.

*See `aws_deployment.md` for full infrastructure documentation.*

---

## Local Installation

*Note: Source code is provided for educational purposes.*

1.  **Clone the Repo:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/college-happiness.git](https://github.com/YOUR_USERNAME/college-happiness.git)
    cd college-happiness
    ```

2.  **Create Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Server:**
    ```bash
    python server.py
    ```

---

## Future Work

* **User Accounts:** Allow university admins to save their simulation scenarios.
* **Cost Analysis:** Integrate cost-of-living API to correlate happiness with financial stress.
* **Sentiment Analysis:** Upgrade the scraper to parse the *text* of reviews (NLP) rather than just the numeric scores to find specific keywords ("small dorms" or "parking nightmare").
* **Feature Improvements and Engineering:** Upgrade the features used to try and account for more overall situations.


---

### License
This project is available for viewing and educational purposes only. All rights reserved.
