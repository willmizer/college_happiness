from flask import Flask, request, jsonify, render_template
import pickle
import pandas as pd
import numpy as np
import json
import os
import webbrowser
from threading import Timer

app = Flask(__name__)

# --- 1. LOAD MODEL & METADATA ---
print("Loading model and metadata...")
with open('model.pkl', 'rb') as f:
    pipe = pickle.load(f)

with open('metadata.json', 'r') as f:
    metadata = json.load(f)

scaler = pipe.named_steps['preprocess'].named_transformers_['num']

# --- 2. LOAD ANALYTICS DATASET ---
print("Loading analysis dataset...")
try:
    if os.path.exists('analysis_dataset.csv'):
        analytics_df = pd.read_csv('analysis_dataset.csv')
        
        if 'number_of_ratings' in analytics_df.columns:
            analytics_df['number_of_ratings'] = pd.to_numeric(analytics_df['number_of_ratings'], errors='coerce').fillna(0)
        
        if 'state' in analytics_df.columns:
            ALL_STATES = sorted(analytics_df['state'].dropna().unique().tolist())
        else:
            ALL_STATES = []
    else:
        analytics_df = pd.DataFrame()
        ALL_STATES = []

except Exception as e:
    print(f"Error loading analytics data: {e}")
    analytics_df = pd.DataFrame()
    ALL_STATES = []

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

# --- ANALYTICS API ---

@app.route('/api/states', methods=['GET'])
def get_states():
    return jsonify(ALL_STATES)

@app.route('/api/analytics/rank', methods=['POST'])
def rank_schools():
    """
    Returns:
    1. Top Schools (Ranked by 85% Quality / 15% Quantity)
    2. Top States (Ranked by WEIGHTED AVERAGE of schools)
    """
    data = request.json
    state = data.get("state", "All")
    feature = data.get("feature", "happiness")
    
    if analytics_df.empty:
        return jsonify({"error": "No data available"}), 500

    # --- HELPER: Smart Weighting Function ---
    def apply_weighting(df, feat_col):
        ratings = df['number_of_ratings']
        
        if not ratings.empty and ratings.max() > ratings.min():
            ratings_log = np.log1p(ratings)
            r_min, r_max = ratings_log.min(), ratings_log.max()
            
            # SCALE REVIEWS: 1.0 - 5.0
            scaled_reviews = 1 + 4 * (ratings_log - r_min) / (r_max - r_min)
        else:
            scaled_reviews = 1.0 
        
        # WEIGHTING: 85% Feature / 15% Reviews
        return (df[feat_col] * 0.85) + (scaled_reviews * 0.15)

    # ----------------------------------------
    # 1. GLOBAL STATE RANKING (WEIGHTED AVERAGE)
    # ----------------------------------------
    df_global = analytics_df.copy()
    if feature in df_global.columns:
        # A. Calculate individual school scores
        df_global['_weighted_score'] = apply_weighting(df_global, feature)
        
        # B. Calculate "Influence Weight" for each school
        # We use log(reviews) so a school with 10k reviews has more say than one with 10,
        # but doesn't completely drown it out.
        df_global['_influence'] = np.log1p(df_global['number_of_ratings'])
        
        # C. Calculate Weighted Average per State
        # Formula: Sum(Score * Influence) / Sum(Influence)
        def weighted_avg(x):
            if x['_influence'].sum() == 0:
                return 0
            return np.average(x['_weighted_score'], weights=x['_influence'])

        state_stats = df_global.groupby('state').apply(weighted_avg).sort_values(ascending=False).head(10)
        
        top_states = [{"state": s, "score": round(v, 2)} for s, v in state_stats.items()]
    else:
        top_states = []

    # ----------------------------------------
    # 2. SCHOOL RANKING
    # ----------------------------------------
    df_filtered = analytics_df.copy()
    
    if state != "All" and 'state' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['state'] == state]
    
    if feature not in df_filtered.columns:
        return jsonify({"top_schools": [], "top_states": [], "distribution": [], "average_score": 0})

    df_filtered['_weighted_score'] = apply_weighting(df_filtered, feature)
    df_sorted = df_filtered.sort_values(by='_weighted_score', ascending=False)
    
    # Display the weighted score
    df_sorted[feature] = df_sorted['_weighted_score'].round(2)
    
    top_schools = df_sorted.head(10)[['school_name', feature]].to_dict(orient='records')
    
    # Distribution Data
    vals = df_sorted[feature]
    bins = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.1]
    labels = ["1.0-1.5", "1.5-2.0", "2.0-2.5", "2.5-3.0", "3.0-3.5", "3.5-4.0", "4.0-4.5", "4.5-5.0"]
    
    if not vals.empty:
        hist_counts = pd.cut(vals, bins=bins, labels=labels, right=False).value_counts().sort_index()
        counts_list = hist_counts.tolist()
    else:
        counts_list = [0] * len(labels)
    
    distribution_data = {
        "labels": labels,
        "counts": counts_list
    }

    avg = df_sorted[feature].mean() if not df_sorted.empty else 0

    return jsonify({
        "top_schools": top_schools,
        "top_states": top_states, 
        "distribution": distribution_data,
        "school_count": len(df_filtered),
        "average_score": avg
    })

# --- SIMULATOR API ---

@app.route('/api/metadata', methods=['GET'])
def get_metadata():
    return jsonify({
        "schools": list(metadata["school_defaults"].keys()),
        "controllable": metadata["controllable_features"]
    })

@app.route('/api/school_profile_full', methods=['POST'])
def school_profile_full():
    data = request.json
    school_name = data.get("school_name")
    delta_scaled = float(data.get("delta", 0.2))

    if school_name not in metadata["school_defaults"]:
        return jsonify({"error": "School not found"}), 404

    base_row_dict = metadata["school_defaults"][school_name].copy()
    numeric_cols = metadata["numeric_cols"]
    controllable = metadata["controllable_features"]
    
    df_base = pd.DataFrame([base_row_dict])
    df_base_num = df_base[numeric_cols]
    base_pred = pipe.predict(df_base_num)[0]
    
    raw_numeric = df_base_num.values
    scaled_numeric = scaler.transform(raw_numeric)
    base_vec = scaled_numeric.flatten()

    batch_vectors = []
    meta_info = [] 

    for feat in controllable:
        idx = numeric_cols.index(feat)
        current_val = base_vec[idx]
        new_val = min(current_val + delta_scaled, 1.0)
        vec = base_vec.copy()
        vec[idx] = new_val
        batch_vectors.append(vec)
        meta_info.append(('ranking', feat))

    steps = list(range(51)) 
    for d_int in steps:
        d = d_int / 100.0
        for feat in controllable:
            idx = numeric_cols.index(feat)
            current_val = base_vec[idx]
            new_val = min(current_val + d, 1.0)
            vec = base_vec.copy()
            vec[idx] = new_val
            batch_vectors.append(vec)
            meta_info.append(('sweep', feat, d_int))

    batch_np = np.array(batch_vectors)
    batch_raw = scaler.inverse_transform(batch_np)
    df_batch = pd.DataFrame(batch_raw, columns=numeric_cols)
    all_preds = pipe.predict(df_batch)

    rankings_results = []
    sweep_data = {} 
    marginal_data = { f: {} for f in controllable }

    for i, info in enumerate(meta_info):
        pred = all_preds[i]
        gain = pred - base_pred
        
        if info[0] == 'ranking':
            feat = info[1]
            idx = numeric_cols.index(feat)
            new_raw = batch_raw[i, idx]
            rankings_results.append({
                "feature": feat,
                "current_value": base_row_dict[feat],
                "current_percent": base_vec[idx] * 100, 
                "new_value": new_raw,
                "gain": gain,
                "gain_percent": gain * 100
            })
        elif info[0] == 'sweep':
            feat = info[1]
            d_int = info[2]
            if d_int not in sweep_data: sweep_data[d_int] = {"gain": -1, "feat": None}
            if gain > sweep_data[d_int]["gain"]: sweep_data[d_int] = {"gain": gain, "feat": feat}
            marginal_data[feat][d_int] = pred

    rankings_results.sort(key=lambda x: x["gain"], reverse=True)

    sweep_results = []
    for d_int in sorted(sweep_data.keys()):
        item = sweep_data[d_int]
        if item["gain"] > 0:
            sweep_results.append({
                "delta": d_int,
                "best_feature": item["feat"],
                "gain_percent": item["gain"] * 100
            })

    marginal_results = []
    for feat in controllable:
        best_jump = -1
        best_delta = 0
        for s in range(1, 51):
            prev = marginal_data[feat][s-1]
            curr = marginal_data[feat][s]
            jump = curr - prev
            if jump > best_jump:
                best_jump = jump
                best_delta = s
        if best_jump > 0.0001:
            marginal_results.append({
                "feature": feat,
                "optimal_delta": best_delta,
                "jump_size": best_jump * 100
            })
    marginal_results.sort(key=lambda x: x["jump_size"], reverse=True)

    return jsonify({
        "baseline_happiness": base_pred * 100,
        "rankings": rankings_results,
        "sweep": sweep_results,
        "marginal": marginal_results
    })

if __name__ == '__main__':
    from threading import Timer
    import webbrowser

    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        def open_browser():
            webbrowser.open_new('http://127.0.0.1:5000/analytics')
        Timer(1, open_browser).start()

    app.run(debug=True, port=5000)