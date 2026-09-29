"""Shared visual theme for the Streamlit apps: palette, CSS, and Plotly styling.

Presentation only. Nothing in here touches app logic or data.
"""
import streamlit as st

# palette
ACCENT = "#3B4CCA"
BG = "#F7F7F5"
CARD = "#FFFFFF"
BORDER = "#E3E3DE"
TEXT = "#1F2430"
MUTED = "#6B7280"
GRID = "#ECECE8"

BLUE = "#2F6FDE"    # Democrat / male
RED = "#D64545"     # Republican / negative
GREEN = "#3DA35D"   # positive
COLORWAY = ["#3B4CCA", "#1B9AAA", "#E9A23B", "#E4572E", "#3DA35D", "#8E5BD0", "#64748B", "#D6467F"]

_FONT_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');"

_CSS = f"""
{_FONT_IMPORT}
html, body, [class*="css"], .stApp, button, input, textarea, select {{
    font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif !important;
}}
.stApp {{ background: {BG}; color: {TEXT}; }}
h1, h2, h3, h4, h5, h6, p, label, li, a, .hero *, .rec-title, .rec-year, .stats, .stats *, .chip, [data-testid="stMetricLabel"] *, [data-testid="stMetricValue"] *,
[data-baseweb="tab"] *, [data-testid="stCaptionContainer"] * {{ font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif !important; }}

/* hide Streamlit chrome */
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stDeployButton"],
[data-testid="stStatusWidget"] {{ display: none !important; visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* page */
.block-container {{ padding-top: 4rem; padding-bottom: 3rem; }}
h1 {{ font-weight: 700; letter-spacing: -0.02em; font-size: 2rem; line-height: 1.25; padding: .25rem 0 .25rem; }}
h2, h3 {{ font-weight: 600; letter-spacing: -0.01em; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: {MUTED}; }}
hr {{ border-color: {BORDER}; margin: 1.25rem 0; }}

/* metric cards */
[data-testid="stMetric"] {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px;
    padding: 12px 12px; box-shadow: 0 1px 2px rgba(16,24,40,.04);
}}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-size: clamp(.68rem, .95vw, .8rem); font-weight: 500; overflow-wrap: normal; word-break: normal; }}
[data-testid="stMetricValue"] {{ font-weight: 650; font-size: 1.6rem; font-variant-numeric: tabular-nums; }}
[data-testid="stMetricLabel"] p, [data-testid="stMetricValue"] div {{ white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }}
[data-testid="stMetricValue"] div {{ font-size: clamp(1rem, 1.45vw, 1.6rem); }}

/* tabs */
[data-baseweb="tab-list"] {{ gap: 1.25rem; border-bottom: 1px solid {BORDER}; }}
[data-baseweb="tab"] {{ padding-left: 0; padding-right: 0; }}
[data-baseweb="tab"] p {{ font-weight: 600; }}
[data-baseweb="tab-highlight"] {{ background-color: {ACCENT}; height: 3px; border-radius: 3px; }}
button[aria-selected="true"] p {{ color: {ACCENT}; }}

/* inputs, buttons */
div[data-baseweb="select"] > div, div[data-baseweb="input"], div[data-baseweb="base-input"],
[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input {{ border-radius: 10px !important; }}
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
    border-radius: 10px; font-weight: 600; min-height: 2.6rem; transition: all .15s ease;
}}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ transform: translateY(-1px); }}

/* containers */
[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 12px; overflow: hidden; background: {CARD}; }}
[data-testid="stExpander"] {{ border: 1px solid {BORDER}; border-radius: 12px; background: {CARD}; }}
[data-testid="stAlert"] {{ border-radius: 12px; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 14px; }}
[data-testid="stPlotlyChart"] {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; padding: 8px; }}
[data-testid="stSidebar"] {{ background: {CARD}; border-right: 1px solid {BORDER}; }}
"""

_STACK = """
@media (max-width: 768px) {
    div[data-testid="stHorizontalBlock"] { flex-direction: column; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] { width: 100% !important; flex: 1 1 100% !important; }
}
"""

_MOBILE = f"""
@media (max-width: 640px) {{
    .block-container {{ padding: 3.5rem .85rem 2rem; }}
    h1 {{ font-size: 1.65rem !important; }}
    [data-testid="stMetricValue"] {{ font-size: 1.35rem; }}
}}
"""


def apply_theme(stack_columns=True, max_width=None, extra_css=""):
    """Inject the shared CSS. stack_columns=True stacks st.columns vertically on phones."""
    width = f".block-container {{ max-width: {max_width}; }}" if max_width else ""
    css = _CSS + width + _MOBILE + (_STACK if stack_columns else "") + extra_css
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def style_fig(fig):
    """Apply the shared Plotly look (fonts, transparent bg, light grid, palette)."""
    fig.update_layout(
        font=dict(family="Inter, -apple-system, Segoe UI, sans-serif", color=TEXT, size=13),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=COLORWAY,
        title_font=dict(size=15, color=TEXT, family="Inter, -apple-system, Segoe UI, sans-serif"),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="white", font_size=13, bordercolor=BORDER),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=BORDER, ticks="")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=BORDER, ticks="")
    return fig
