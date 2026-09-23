import json
import pickle

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="College Happiness Simulator", layout="wide")

st.markdown(
    """
    <style>
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] {
            flex-direction: column;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            width: 100% !important;
            flex: 1 1 100% !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

DATA_DIR = "Web"


@st.cache_resource
def load_model():
    with open(f"{DATA_DIR}/model.pkl", "rb") as f:
        return pickle.load(f)


@st.cache_resource
def load_metadata():
    with open(f"{DATA_DIR}/metadata.json") as f:
        return json.load(f)


@st.cache_data
def load_analytics_df():
    df = pd.read_csv(f"{DATA_DIR}/analysis_dataset.csv")
    df["number_of_ratings"] = pd.to_numeric(df["number_of_ratings"], errors="coerce").fillna(0)
    return df


pipe = load_model()
metadata = load_metadata()
analytics_df = load_analytics_df()
scaler = pipe.named_steps["preprocess"].named_transformers_["num"]
numeric_cols = metadata["numeric_cols"]
controllable = metadata["controllable_features"]
school_defaults = metadata["school_defaults"]
FEATURE_COLORS = {
    feat: px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]
    for i, feat in enumerate(controllable)
}
ALL_STATES = sorted(analytics_df["state"].dropna().unique().tolist())
FEATURE_COLS = [c for c in analytics_df.columns if c in numeric_cols or c == "happiness"]

st.title("The College Happiness Simulator")
st.caption(
    "A data-driven look at what actually makes students happy - analyze ~2,800 US "
    "colleges, then simulate how shifting a school's budget toward specific features "
    "moves predicted student happiness."
)

tab_analytics, tab_simulator = st.tabs(["Analytics", "Simulator"])


def apply_weighting(df: pd.DataFrame, feat_col: str) -> pd.Series:
    ratings = df["number_of_ratings"]
    if not ratings.empty and ratings.max() > ratings.min():
        ratings_log = np.log1p(ratings)
        r_min, r_max = ratings_log.min(), ratings_log.max()
        scaled_reviews = 1 + 4 * (ratings_log - r_min) / (r_max - r_min)
    else:
        scaled_reviews = pd.Series(1.0, index=df.index)
    return (df[feat_col] * 0.85) + (scaled_reviews * 0.15)


with tab_analytics:
    col_a, col_b = st.columns(2)
    with col_a:
        state_choice = st.selectbox("State", ["All"] + ALL_STATES, key="state_choice")
    with col_b:
        feature_choice = st.selectbox("Feature", sorted(FEATURE_COLS), index=sorted(FEATURE_COLS).index("happiness"))

    df_global = analytics_df.copy()
    df_global["_weighted_score"] = apply_weighting(df_global, feature_choice)
    df_global["_influence"] = np.log1p(df_global["number_of_ratings"])

    def weighted_avg(group: pd.DataFrame) -> float:
        if group["_influence"].sum() == 0:
            return 0.0
        return float(np.average(group["_weighted_score"], weights=group["_influence"]))

    state_stats = (
        df_global.groupby("state")
        .apply(weighted_avg, include_groups=False)
        .sort_values(ascending=False)
        .head(10)
    )

    df_filtered = analytics_df.copy()
    if state_choice != "All":
        df_filtered = df_filtered[df_filtered["state"] == state_choice]
    df_filtered["_weighted_score"] = apply_weighting(df_filtered, feature_choice)
    df_sorted = df_filtered.sort_values("_weighted_score", ascending=False)

    top_schools = df_sorted.head(10)[["school_name", "_weighted_score"]].rename(
        columns={"_weighted_score": feature_choice}
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Top 10 schools - {feature_choice}")
        st.dataframe(top_schools.set_index("school_name").round(2), use_container_width=True)
    with col2:
        feature_label = feature_choice.replace("_", " ").title()
        state_stats_asc = state_stats.sort_values(ascending=True).round(2)
        fig_states = px.bar(
            x=state_stats_asc.values,
            y=state_stats_asc.index,
            orientation="h",
            labels={"x": feature_label, "y": "State"},
            title=f"Top 10 States - {feature_label}",
        )
        st.plotly_chart(fig_states, use_container_width=True)

    st.subheader(f"Score distribution - {feature_choice}")
    bins = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.1]
    labels = ["1.0-1.5", "1.5-2.0", "2.0-2.5", "2.5-3.0", "3.0-3.5", "3.5-4.0", "4.0-4.5", "4.5-5.0"]
    vals = df_sorted["_weighted_score"]
    if not vals.empty:
        hist_counts = pd.cut(vals, bins=bins, labels=labels, right=False).value_counts().reindex(labels).fillna(0)
        fig = px.bar(x=labels, y=hist_counts.values, labels={"x": "Score range", "y": "Number of schools"})
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"{len(df_filtered)} schools · average score {vals.mean():.2f}")


with tab_simulator:
    school_names = sorted(school_defaults.keys())
    col1, col2 = st.columns([2, 1])
    with col1:
        school_name = st.selectbox("Select a university", school_names)
    with col2:
        delta_scaled = st.slider("Investment level (%)", 1, 50, 10) / 100.0

    base_row_dict = school_defaults[school_name].copy()
    df_base = pd.DataFrame([base_row_dict])[numeric_cols]
    base_pred = pipe.predict(df_base)[0]
    base_vec = scaler.transform(df_base).flatten()

    st.metric("Baseline projected happiness", f"{base_pred * 100:.1f}%")

    # ranking: bump each controllable feature by delta_scaled, holding others fixed
    ranking_vectors, ranking_feats = [], []
    for feat in controllable:
        idx = numeric_cols.index(feat)
        vec = base_vec.copy()
        vec[idx] = min(vec[idx] + delta_scaled, 1.0)
        ranking_vectors.append(vec)
        ranking_feats.append(feat)

    # sweep: delta 0..0.50 in 51 steps, per feature, to find marginal jumps
    steps = list(range(51))
    sweep_vectors, sweep_meta = [], []
    for feat in controllable:
        idx = numeric_cols.index(feat)
        for d_int in steps:
            d = d_int / 100.0
            vec = base_vec.copy()
            vec[idx] = min(vec[idx] + d, 1.0)
            sweep_vectors.append(vec)
            sweep_meta.append((feat, d_int))

    all_vectors = np.array(ranking_vectors + sweep_vectors)
    all_raw = scaler.inverse_transform(all_vectors)
    all_preds = pipe.predict(pd.DataFrame(all_raw, columns=numeric_cols))

    n_rank = len(ranking_feats)
    rank_preds = all_preds[:n_rank]
    sweep_preds = all_preds[n_rank:]

    rankings_results = []
    for feat, pred in zip(ranking_feats, rank_preds):
        gain = pred - base_pred
        rankings_results.append({"feature": feat, "gain_percent": gain * 100})
    rankings_results.sort(key=lambda x: x["gain_percent"], reverse=True)

    st.subheader(f"Best features to invest in (at +{delta_scaled*100:.0f}%)")
    rank_df = pd.DataFrame(rankings_results)
    fig_rank = px.bar(
        rank_df,
        x="feature",
        y="gain_percent",
        color="feature",
        color_discrete_map=FEATURE_COLORS,
        labels={"feature": "Feature", "gain_percent": "Happiness gain (pts)"},
    )
    fig_rank.update_layout(showlegend=False, xaxis_title="Feature", yaxis_title="Happiness gain (pts)")
    st.plotly_chart(fig_rank, use_container_width=True)
    st.caption("Colors match the feature legend in the marginal-gain chart below.")

    # marginal sweep per feature: happiness vs delta line chart + optimal jump table
    marginal_curve = pd.DataFrame(
        {"feature": [m[0] for m in sweep_meta], "delta": [m[1] for m in sweep_meta], "pred": sweep_preds}
    )
    fig2 = go.Figure()
    for feat in controllable:
        sub = marginal_curve[marginal_curve["feature"] == feat].sort_values("delta")
        fig2.add_trace(go.Scatter(
            x=sub["delta"], y=(sub["pred"] - base_pred) * 100, mode="lines", name=feat,
            line=dict(color=FEATURE_COLORS[feat]),
        ))
    fig2.update_layout(
        title="Marginal happiness gain vs. investment level, per feature",
        xaxis_title="Investment (%)",
        yaxis_title="Happiness gain (pts)",
    )
    st.plotly_chart(fig2, use_container_width=True)

    marginal_results = []
    for feat in controllable:
        sub = marginal_curve[marginal_curve["feature"] == feat].sort_values("delta")
        preds = sub["pred"].to_numpy()
        jumps = np.diff(preds)
        if len(jumps) and jumps.max() > 0.0001:
            best_i = int(np.argmax(jumps))
            marginal_results.append(
                {"feature": feat, "optimal_delta_%": best_i + 1, "jump_size_pts": jumps[best_i] * 100}
            )
    marginal_results.sort(key=lambda x: x["jump_size_pts"], reverse=True)

    st.subheader("Where's the sweet spot for each feature?")
    st.dataframe(pd.DataFrame(marginal_results).set_index("feature").round(3), use_container_width=True)
