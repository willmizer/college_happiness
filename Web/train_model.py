import pandas as pd
import numpy as np
import pickle
import json
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import MinMaxScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor

# 1. Load Data
try:
    df_raw = pd.read_csv('C:\\Users\\willm\\Desktop\\college_biz\\Data\\final_school_data.csv')
    print(f"Loaded CSV with {len(df_raw)} rows.")
    # Normalize columns to lowercase to prevent capitalization errors
    df_raw.columns = df_raw.columns.str.lower()
except FileNotFoundError:
    print("Error: 'final_school_data.csv' not found.")
    exit()

# 2. Clean Data
# FIX: I REMOVED "number_of_ratings" from this list so it gets saved!
drop_cols = [
    "rmp_school_id", "city", "overall_rating",
    "reputation", "campus_setting", "sat_median_total", "act_median_composite",
    "acceptance_rate", "avg_aid_awarded", "total_expenses_in_state",
    "total_expenses_out_state", "student_population_total", "student_to_faculty_ratio",
    "retention_rate_avg", "grad_rate_4yr",
]
# Only drop columns that actually exist
existing_drop_cols = [c for c in drop_cols if c in df_raw.columns]
df_raw = df_raw.drop(columns=existing_drop_cols)

# --- SAVE ANALYTICS DATASET (100% RAW) ---
print("Saving analysis_dataset.csv (Raw)...")
df_raw.to_csv('analysis_dataset.csv', index=False)

# --- SAVE METADATA (100% RAW) ---
print("Saving metadata.json (Raw)...")
school_data = {}
target = "happiness"

for index, row in df_raw.iterrows():
    s_name = row["school_name"]
    d = row.to_dict()
    if target in d: del d[target]
    school_data[s_name] = d

# Prepare Data for Model Training
df_train = df_raw.copy()

# Scale Target [1,5] -> [0,1]
df_train[target] = (df_train[target] - 1.0) / 4.0

# Drop non-numeric columns for training (Model doesn't need State/Name or Ratings count)
# We drop 'number_of_ratings' here because it's not a controllable feature for the slider
X = df_train.drop(columns=[target, "state", "school_name", "number_of_ratings"], errors='ignore')
y = df_train[target]

numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()

# 4. Train Model
preprocessor = ColumnTransformer(transformers=[("num", MinMaxScaler(), numeric_cols)])
rf_model = RandomForestRegressor(n_estimators=500, max_depth=10, min_samples_leaf=4, random_state=42, n_jobs=-1)
pipe = Pipeline([("preprocess", preprocessor), ("model", rf_model)])
pipe.fit(X, y)

# 5. Save Model
print("Saving model.pkl...")
with open('model.pkl', 'wb') as f:
    pickle.dump(pipe, f)

# Extract states for dropdown
states = sorted(df_raw['state'].dropna().unique().tolist())

metadata = {
    "numeric_cols": numeric_cols,
    "controllable_features": [c for c in numeric_cols],
    "school_defaults": school_data,
    "states": states
}

with open('metadata.json', 'w') as f:
    json.dump(metadata, f)

print("Done. 'number_of_ratings' preserved.")