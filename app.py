"""
Theme Desk — Tech Basket Monitor (v2)
Overhauled landing page: expandable basket cards with top/bottom performers.
"""

import json
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Theme Desk",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CONSTANTS ──────────────────────────────────────────────────────────────────
DEFAULT_BASKETS = {
    "Hyperscalers":       {"color": "#3b82f6", "tickers": ["MSFT", "AMZN", "GOOGL", "META", "ORCL"]},
    "Semis":              {"color": "#f59e0b", "tickers": ["NVDA", "AMD", "AVGO", "QCOM", "AMAT", "LRCX", "ASML"]},
    "SaaS":               {"color": "#8b5cf6", "tickers": ["CRM", "NOW", "SNOW", "DDOG", "MDB", "ZS", "HUBS"]},
    "AI Infrastructure":  {"color": "#10b981", "tickers": ["ARM", "SMCI", "DELL", "NET", "CDNS"]},
    "Cybersecurity":      {"color": "#ef4444", "tickers": ["CRWD", "PANW", "FTNT", "ZS", "S", "OKTA"]},
}

PALETTE = [
    "#3b82f6", "#f59e0b", "#8b5cf6", "#10b981", "#ef4444",
    "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
    "#14b8a6", "#a855f7", "#eab308", "#22c55e", "#0ea5e9",
]

Z_WINDOWS = {
    "63d  (Quarter)":      63,
    "126d (Semi-annual)": 126,
    "252d (Annual)":      252,
    "504d (Biennial)":    504,
}

FETCH_PERIOD = "5y"

# Extended intervals for expanded view (label, approx trading days)
INTERVALS = [
    ("1-Day",    1),
    ("5-Day",    5),
    ("20-Day",   20),
    ("3-Month",  63),
    ("6-Month",  126),
    ("12-Month", 252),
]


# ── CUSTOM CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Base dark theme */
[data-testid="stAppViewContainer"] { background: #030712; }
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
.stTabs [data-baseweb="tab-list"] { background: transparent; border-bottom: 1px solid #1e293b; gap: 0; }
.stTabs [data-baseweb="tab"] {
    background: transparent !important; color: #475569 !important;
    padding: 12px 20px; border: none !important;
    font-size: 12px; font-weight: 600; letter-spacing: 0.04em;
}
.stTabs [aria-selected="true"] { color: #f59e0b !important; border-bottom: 2px solid #f59e0b !important; }
.stTabs [data-baseweb="tab-panel"] { background: transparent; padding-top: 24px; }

/* Metric cards */
div[data-testid="metric-container"] {
    background: #080f1a !important;
    border: 1px solid #1e293b !important;
    border-radius: 8px;
    padding: 14px 18px !important;
}
div[data-testid="metric-container"] label { color: #475569 !important; font-size: 10px !important; letter-spacing: 0.06em; text-transform: uppercase; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace; font-size: 18px !important; }

/* Text */
h1, h2, h3, p, div { color: #e2e8f0; }
.stMarkdown p { color: #94a3b8; }

/* Buttons */
.stButton > button {
    background: #080f1a !important;
    border: 1px solid #1e293b !important;
    color: #94a3b8 !important;
    border-radius: 6px;
    font-size: 11px;
    transition: all 0.15s;
}
.stButton > button:hover { border-color: #334155 !important; color: #e2e8f0 !important; }

/* Selectbox / inputs */
[data-testid="stSelectbox"] > div > div { background: #080f1a !important; border: 1px solid #1e293b !important; }
.stTextInput > div > div > input { background: #080f1a !important; border: 1px solid #1e293b !important; color: #e2e8f0 !important; }
.stTextArea > div > div > textarea { background: #080f1a !important; border: 1px solid #1e293b !important; color: #e2e8f0 !important; }

/* Dataframe */
[data-testid="stDataFrame"] { border: 1px solid #1e293b; border-radius: 8px; }

/* Divider */
hr { border-color: #1e293b !important; }

/* Remove default padding */
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

/* Info boxes */
.info-box {
    background: #080f1a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 10px 16px;
    font-size: 11px;
    color: #475569;
    margin-bottom: 14px;
}
.live-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: #052010; border: 1px solid rgba(16,185,129,0.2);
    border-radius: 5px; padding: 4px 12px;
    font-size: 11px; color: #10b981; font-weight: 700;
}

/* Hide streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── SESSION STATE ──────────────────────────────────────────────────────────────
def _load_default_baskets():
    baskets_path = Path(__file__).parent / "baskets.json"
    if baskets_path.exists():
        try:
            with open(baskets_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {k: dict(v) for k, v in DEFAULT_BASKETS.items()}


def _save_baskets():
    """Auto-save current baskets to baskets.json in the app directory."""
    try:
        baskets_path = Path(__file__).parent / "baskets.json"
        with open(baskets_path, "w") as f:
            json.dump(st.session_state.baskets, f, indent=2)
    except Exception:
        pass  # silently fail if no write access

if "baskets" not in st.session_state:
    st.session_state.baskets = _load_default_baskets()
if "editing_basket" not in st.session_state:
    st.session_state.editing_basket = None
if "selected_basket" not in st.session_state:
    st.session_state.selected_basket = list(st.session_state.baskets.keys())[0]
if "z_window" not in st.session_state:
    st.session_state.z_window = 252
if "expanded_basket" not in st.session_state:
    st.session_state.expanded_basket = None  # None or basket name
if "display_mode" not in st.session_state:
    st.session_state.display_mode = "returns"  # "returns" or "zscore"
if "preview_period" not in st.session_state:
    st.session_state.preview_period = "5d"  # key into preview period options


# ── DATA FETCHING ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_prices(tickers: tuple, period: str = FETCH_PERIOD) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
    raw = yf.download(
        list(tickers), period=period, interval="1d",
        auto_adjust=True, progress=False, threads=True,
    )
    if raw.empty:
        return pd.DataFrame()
    close = raw["Close"] if "Close" in raw.columns else raw
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    close = close.dropna(how="all").ffill()
    return close


# ── COMPUTATION ───────────────────────────────────────────────────────────────
def ret_pct(prices: pd.Series, lookback: int) -> float:
    n = len(prices)
    if n < lookback + 1:
        return 0.0
    cur  = prices.iloc[-1]
    prev = prices.iloc[-(lookback + 1)]
    return ((cur - prev) / prev) * 100 if prev != 0 else 0.0


def rolling_return_series(prices: pd.Series, lookback: int) -> pd.Series:
    return prices.pct_change(lookback).dropna() * 100


def rolling_zscore(prices: pd.Series, lookback: int, z_window: int):
    # 1. Calculate daily returns to avoid autocorrelation
    daily_rets = prices.pct_change().dropna()
    
    if len(daily_rets) < z_window + lookback:
        return None
        
    # 2. Strict Out-of-Sample Window
    # If we are measuring a 5-day return today, the historical vol baseline 
    # must stop 5 days ago. Otherwise, the days making up our current return 
    # leak into the volatility baseline.
    historical_daily_rets = daily_rets.iloc[-(z_window + lookback) : -lookback]
    
    # 3. Calculate daily standard deviation (using sample std, ddof=1)
    daily_sigma = historical_daily_rets.std(ddof=1)
    
    if daily_sigma < 1e-8:
        return 0.0
        
    # 4. Scale volatility to the lookback period
    # Volatility scales with the square root of time
    period_sigma = daily_sigma * np.sqrt(lookback) * 100
    
    # 5. Get actual period return (The Observation)
    period_ret = ret_pct(prices, lookback)
    
    # 6. Calculate Z-score (assuming mu = 0 for momentum scaling)
    return float(period_ret / period_sigma)


def ytd_return(prices: pd.Series) -> float:
    """YTD % return — from last trading day of prior year to latest price."""
    if prices.empty:
        return 0.0
    current_year = prices.index[-1].year
    prior_year = prices[prices.index.year < current_year]
    if prior_year.empty:
        return 0.0
    prev = prior_year.iloc[-1]
    cur  = prices.iloc[-1]
    return ((cur - prev) / prev) * 100 if prev != 0 else 0.0


def build_stock_stats(prices_df: pd.DataFrame, baskets: dict, z_window: int) -> pd.DataFrame:
    primary = {}
    for name, cfg in baskets.items():
        for t in cfg["tickers"]:
            if t not in primary:
                primary[t] = name
    rows = []
    for ticker in prices_df.columns:
        s = prices_df[ticker].dropna()
        if len(s) < 25:
            continue
        row = {
            "ticker":  ticker,
            "basket":  primary.get(ticker, "Other"),
            "price":   round(float(s.iloc[-1]), 2),
            # Legacy columns (keep for rotation/momentum tabs)
            "ret1d":   round(ret_pct(s, 1),  2),
            "ret5d":   round(ret_pct(s, 5),  2),
            "ret20d":  round(ret_pct(s, 20), 2),
            "z1d":     rolling_zscore(s, 1,  z_window),
            "z5d":     rolling_zscore(s, 5,  z_window),
            "z20d":    rolling_zscore(s, 20, z_window),
            # YTD
            "ret_ytd": round(ytd_return(s), 2),
            "z_ytd":   rolling_zscore(s, min(len(s)-1, 252), z_window),  # approximate
        }
        # Extended interval columns
        for label, lb in INTERVALS:
            row[f"ret_{lb}"] = round(ret_pct(s, lb), 2)
            row[f"z_{lb}"]   = rolling_zscore(s, lb, z_window)
        rows.append(row)

    if not rows:
        cols = ["ticker","basket","price","ret1d","ret5d","ret20d","z1d","z5d","z20d","ret_ytd","z_ytd"]
        for _, lb in INTERVALS:
            cols += [f"ret_{lb}", f"z_{lb}"]
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)


def basket_stats(baskets: dict, stock_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, cfg in baskets.items():
        members = stock_df[stock_df["ticker"].isin(cfg["tickers"])]
        if members.empty:
            row = {"basket": name, "color": cfg["color"],
                   "tickers": cfg["tickers"], "n": 0,
                   "avg1d": 0, "avg5d": 0, "avg20d": 0,
                   "avgZ1d": 0, "avgZ5d": 0, "avgZ20d": 0,
                   "avg_ret_ytd": 0, "avgZ_ytd": 0}
            for _, lb in INTERVALS:
                row[f"avg_ret_{lb}"] = 0
                row[f"avgZ_{lb}"] = 0
            rows.append(row)
            continue
        z_rows = members.dropna(subset=["z1d","z5d","z20d"])
        row = {
            "basket":  name,
            "color":   cfg["color"],
            "tickers": cfg["tickers"],
            "n":       len(members),
            # Legacy columns
            "avg1d":   round(members["ret1d"].mean(),  2),
            "avg5d":   round(members["ret5d"].mean(),  2),
            "avg20d":  round(members["ret20d"].mean(), 2),
            "avgZ1d":  round(z_rows["z1d"].mean(),  3) if not z_rows.empty else 0,
            "avgZ5d":  round(z_rows["z5d"].mean(),  3) if not z_rows.empty else 0,
            "avgZ20d": round(z_rows["z20d"].mean(), 3) if not z_rows.empty else 0,
            # YTD
            "avg_ret_ytd": round(members["ret_ytd"].mean(), 2),
            "avgZ_ytd":    round(members["z_ytd"].dropna().mean(), 3) if not members["z_ytd"].dropna().empty else 0,
        }
        # Extended intervals
        for _, lb in INTERVALS:
            ret_col = f"ret_{lb}"
            z_col = f"z_{lb}"
            row[f"avg_ret_{lb}"] = round(members[ret_col].mean(), 2)
            z_valid = members[z_col].dropna()
            row[f"avgZ_{lb}"] = round(z_valid.mean(), 3) if not z_valid.empty else 0
        rows.append(row)
    return pd.DataFrame(rows)


# ── FORMAT HELPERS ─────────────────────────────────────────────────────────────
def _sign(v): return "▲" if v >= 0 else "▼"
def _color(v): return "#10b981" if v >= 0 else "#ef4444"

def pct_html(v, size=13):
    c = _color(v)
    return f'<span style="color:{c};font-family:\'IBM Plex Mono\',monospace;font-weight:700;font-size:{size}px">{_sign(v)} {abs(v):.2f}%</span>'

def z_html(v, size=13):
    if v is None:
        return '<span style="color:#334155">—</span>'
    c = _color(v)
    return f'<span style="color:{c};font-family:\'IBM Plex Mono\',monospace;font-weight:700;font-size:{size}px">{_sign(v)} {abs(v):.2f}σ</span>'


def _rgb(hex_color):
    """Convert hex to r,g,b tuple string."""
    h = hex_color.lstrip("#")
    return f"{int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)}"


# ── PLOTLY THEME ───────────────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="#080f1a",
    plot_bgcolor="#080f1a",
    font=dict(color="#94a3b8", family="IBM Plex Mono, monospace", size=10),
    margin=dict(l=50, r=30, t=30, b=50),
    showlegend=True,
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#1e293b", borderwidth=1),
    xaxis=dict(gridcolor="#1e293b", zerolinecolor="#334155", linecolor="#1e293b"),
    yaxis=dict(gridcolor="#1e293b", zerolinecolor="#334155", linecolor="#1e293b"),
)



# ── LANDING PAGE: SQUARE GRID CARDS ────────────────────────────────────────────
def _mini_row_html(ticker, val, show_z=False):
    """Ultra-compact performer row for square card."""
    if show_z:
        display = f"{abs(val):.1f}σ" if val is not None else "—"
        c = _color(val) if val is not None else "#334155"
    else:
        display = f"{abs(val):.1f}%"
        c = _color(val)
    sign = _sign(val) if val is not None else ""
    return f'<div style="display:flex;justify-content:space-between;padding:2px 0;font-size:10px"><span style="color:#94a3b8;font-family:\'IBM Plex Mono\',monospace">{ticker}</span><span style="color:{c};font-family:\'IBM Plex Mono\',monospace;font-weight:600">{sign}{display}</span></div>'


def render_landing_page(b_stats: pd.DataFrame, stock_df: pd.DataFrame, z_label: str):
    """Main landing page — universal controls + square grid cards + full-width expanded detail."""

    # ── Universal Control Bar ──
    # Preview period options: map label -> (ret_col, z_col, display_label)
    _PREVIEW_PERIODS = {
        "1d":  ("ret1d",  "z1d",  "1D"),
        "5d":  ("ret5d",  "z5d",  "5D"),
        "20d": ("ret20d", "z20d", "20D"),
        "3m":  ("ret_63", "z_63", "3M"),
        "6m":  ("ret_126","z_126","6M"),
        "12m": ("ret_252","z_252","12M"),
        "ytd": ("ret_ytd","z_ytd","YTD"),
    }

    ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 2])

    with ctrl1:
        period_keys = list(_PREVIEW_PERIODS.keys())
        period_labels = [_PREVIEW_PERIODS[k][2] for k in period_keys]
        cur_period = st.session_state.preview_period
        cur_idx = period_keys.index(cur_period) if cur_period in period_keys else 1
        new_idx = st.selectbox(
            "Period",
            range(len(period_keys)),
            index=cur_idx,
            format_func=lambda i: f"Period: {period_labels[i]}",
            key="preview_period_select",
            label_visibility="collapsed",
        )
        if period_keys[new_idx] != st.session_state.preview_period:
            st.session_state.preview_period = period_keys[new_idx]
            st.rerun()

    with ctrl2:
        z_options = list(Z_WINDOWS.keys())
        z_idx = z_options.index(z_label) if z_label in z_options else 2
        new_z_label = st.selectbox(
            "Z-Score Period",
            z_options,
            index=z_idx,
            key="landing_z_window",
            label_visibility="collapsed",
        )
        new_z_val = Z_WINDOWS[new_z_label]
        if new_z_val != st.session_state.z_window:
            st.session_state.z_window = new_z_val
            st.rerun()

    with ctrl3:
        mode_labels = {"returns": "Raw Returns %", "zscore": "Z-Score Momentum σ"}
        current_mode = st.session_state.display_mode
        toggled = st.button(
            f"Showing: {mode_labels[current_mode]}  ⇄",
            key="toggle_display_mode",
            use_container_width=True,
        )
        if toggled:
            st.session_state.display_mode = "zscore" if current_mode == "returns" else "returns"
            st.rerun()

    # Resolve preview columns
    pp = st.session_state.preview_period
    pp_ret_col, pp_z_col, pp_label = _PREVIEW_PERIODS[pp]

    mode_display = "RAW RETURNS %" if st.session_state.display_mode == "returns" else "Z-SCORE MOMENTUM σ"
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:14px">
        <div style="font-size:10px;font-weight:700;color:#94a3b8;letter-spacing:0.14em;text-transform:uppercase">
            ▌ Theme Baskets
        </div>
        <span style="font-size:9px;color:#475569;font-family:'IBM Plex Mono',monospace">
            z-window: {z_label} &nbsp;·&nbsp; {mode_display} &nbsp;·&nbsp; Period: {pp_label}
        </span>
    </div>
    """, unsafe_allow_html=True)

    baskets = st.session_state.baskets
    expanded = st.session_state.expanded_basket
    show_z = st.session_state.display_mode == "zscore"

    # ── Build card data ──
    card_data = []
    for basket_name, cfg in baskets.items():
        b_row = b_stats[b_stats["basket"] == basket_name]
        if b_row.empty:
            continue
        b_row = b_row.iloc[0]
        members = stock_df[stock_df["ticker"].isin(cfg["tickers"])]
        if members.empty:
            continue
        card_data.append((basket_name, cfg, b_row, members))

    if not card_data:
        st.info("No baskets with data. Add tickers in Settings.")
        return

    # ── Render square grid ──
    n_cards = len(card_data)
    cols_per_row = min(n_cards, 5)
    grid_cols = st.columns(cols_per_row)

    for i, (basket_name, cfg, b_row, members) in enumerate(card_data):
        color = cfg["color"]
        rgb = _rgb(color)
        is_exp = expanded == basket_name

        # Sort for top/bottom preview using selected period
        sort_col = pp_z_col if show_z else pp_ret_col
        sorted_m = members.dropna(subset=[sort_col]).sort_values(sort_col, ascending=False) if show_z else members.sort_values(sort_col, ascending=False)
        top3 = sorted_m.head(3)
        bot3 = sorted_m.tail(3).iloc[::-1]

        # Determine basket-level performance for the selected period for color coding
        if show_z:
            # Map period to basket-level z column
            _bz_map = {"1d":"avgZ1d","5d":"avgZ5d","20d":"avgZ20d",
                       "3m":"avgZ_63","6m":"avgZ_126","12m":"avgZ_252","ytd":"avgZ_ytd"}
            basket_perf = b_row.get(_bz_map.get(pp, "avgZ5d"), 0)
        else:
            _br_map = {"1d":"avg1d","5d":"avg5d","20d":"avg20d",
                       "3m":"avg_ret_63","6m":"avg_ret_126","12m":"avg_ret_252","ytd":"avg_ret_ytd"}
            basket_perf = b_row.get(_br_map.get(pp, "avg5d"), 0)
        try:
            basket_perf = float(basket_perf)
            if np.isnan(basket_perf):
                basket_perf = 0.0
        except (TypeError, ValueError):
            basket_perf = 0.0
        is_up = basket_perf >= 0

        top_html = ""
        for _, r in top3.iterrows():
            top_html += _mini_row_html(r["ticker"], r[sort_col], show_z)
        bot_html = ""
        for _, r in bot3.iterrows():
            bot_html += _mini_row_html(r["ticker"], r[sort_col], show_z)

        # Header metrics
        if show_z:
            m1_l, m1_v = "1D σ", z_html(b_row["avgZ1d"], 11)
            m2_l, m2_v = "5D σ", z_html(b_row["avgZ5d"], 11)
            m3_l, m3_v = "20D σ", z_html(b_row["avgZ20d"], 11)
        else:
            m1_l, m1_v = "1D", pct_html(b_row["avg1d"], 11)
            m2_l, m2_v = "5D", pct_html(b_row["avg5d"], 11)
            m3_l, m3_v = "20D", pct_html(b_row["avg20d"], 11)

        # Color-coded border based on period performance
        perf_color = "#10b981" if is_up else "#ef4444"
        perf_rgb = _rgb(perf_color)
        if is_exp:
            border = f"2px solid rgba({rgb},0.6)"
            bg = "#0a1120"
        else:
            border = f"1px solid rgba({perf_rgb},0.3)"
            bg = "#080f1a"
        indicator = f'<div style="width:6px;height:6px;border-radius:50%;background:{color};box-shadow:0 0 6px {color}"></div>' if is_exp else ""

        # Performance badge for the selected period
        perf_sign = "▲" if is_up else "▼"
        if show_z:
            perf_display = f"{abs(basket_perf):.2f}σ"
        else:
            perf_display = f"{abs(basket_perf):.2f}%"
        perf_badge = f'<span style="color:{perf_color};font-family:\'IBM Plex Mono\',monospace;font-weight:700;font-size:12px">{perf_sign} {perf_display}</span>'

        # Subtle left-edge glow
        glow_style = f"box-shadow:inset 3px 0 8px -4px {'rgba(16,185,129,0.3)' if is_up else 'rgba(239,68,68,0.3)'};"

        with grid_cols[i % cols_per_row]:
            st.html(f"""
            <div style="background:{bg};border:{border};border-radius:10px;padding:14px 16px;min-height:260px;display:flex;flex-direction:column;{glow_style}">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                    <div style="width:3px;height:22px;background:{color};border-radius:2px;flex-shrink:0"></div>
                    <div style="flex:1;min-width:0">
                        <div style="font-size:13px;font-weight:700;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{basket_name}</div>
                    </div>
                    {indicator}
                </div>
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
                    <span style="background:rgba({rgb},0.12);color:{color};border:1px solid rgba({rgb},0.25);border-radius:3px;padding:1px 6px;font-size:8px;font-weight:700">{b_row["n"]} STOCKS</span>
                    {perf_badge}
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #1e293b">
                    <div style="background:#0b1322;border-radius:5px;padding:6px 8px;text-align:center">
                        <div style="font-size:7px;color:#475569;font-weight:600;letter-spacing:0.06em;margin-bottom:2px">{m1_l}</div>
                        <div>{m1_v}</div>
                    </div>
                    <div style="background:#0b1322;border-radius:5px;padding:6px 8px;text-align:center">
                        <div style="font-size:7px;color:#475569;font-weight:600;letter-spacing:0.06em;margin-bottom:2px">{m2_l}</div>
                        <div>{m2_v}</div>
                    </div>
                    <div style="background:#0b1322;border-radius:5px;padding:6px 8px;text-align:center">
                        <div style="font-size:7px;color:#475569;font-weight:600;letter-spacing:0.06em;margin-bottom:2px">{m3_l}</div>
                        <div>{m3_v}</div>
                    </div>
                </div>
                <div style="margin-bottom:6px">
                    <div style="font-size:8px;font-weight:700;color:#10b981;letter-spacing:0.08em;margin-bottom:3px">▲ TOP 3 ({pp_label})</div>
                    {top_html}
                </div>
                <div style="flex:1">
                    <div style="font-size:8px;font-weight:700;color:#ef4444;letter-spacing:0.08em;margin-bottom:3px">▼ BOTTOM 3 ({pp_label})</div>
                    {bot_html}
                </div>
            </div>
            """)

            btn_label = f"▾ {basket_name}" if is_exp else f"▸ {basket_name}"
            if st.button(btn_label, key=f"expand_{basket_name}", use_container_width=True):
                if is_exp:
                    st.session_state.expanded_basket = None
                else:
                    st.session_state.expanded_basket = basket_name
                    st.session_state.selected_basket = basket_name
                st.rerun()

    # ── Expanded detail: full width BELOW the grid ──
    if expanded:
        exp_match = [(bn, c, br, m) for bn, c, br, m in card_data if bn == expanded]
        if exp_match:
            basket_name, cfg, b_row, members = exp_match[0]
            st.markdown("<div style='height:12px'/>", unsafe_allow_html=True)
            render_expanded_detail(basket_name, cfg, b_row, members)


# ── EXPANDED DETAIL VIEW ──────────────────────────────────────────────────────
def render_expanded_detail(basket_name, cfg, b_row, members_df):
    """Full detail view when a basket card is expanded — toggles between returns and z-score."""
    color = cfg["color"]
    rgb = _rgb(color)
    show_z = st.session_state.display_mode == "zscore"

    # ── Basket-level Metrics (single row based on mode) ──
    if show_z:
        st.markdown('<div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;border-bottom:1px solid #1e293b;padding-bottom:4px;margin-bottom:8px">Momentum Regime (Avg Z-Score)</div>', unsafe_allow_html=True)
        metric_cols = st.columns(len(INTERVALS) + 1)
        for i, (label, lb) in enumerate(INTERVALS):
            val = b_row[f"avgZ_{lb}"]
            metric_cols[i].metric(f"{label} σ", f"{'+'if val>=0 else ''}{val:.2f}σ")
        zytd_val = b_row["avgZ_ytd"]
        metric_cols[-1].metric("YTD σ", f"{'+'if zytd_val>=0 else ''}{zytd_val:.2f}σ")
    else:
        st.markdown('<div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;border-bottom:1px solid #1e293b;padding-bottom:4px;margin-bottom:8px">Basket Performance (Avg Raw %)</div>', unsafe_allow_html=True)
        metric_cols = st.columns(len(INTERVALS) + 1)
        for i, (label, lb) in enumerate(INTERVALS):
            val = b_row[f"avg_ret_{lb}"]
            metric_cols[i].metric(label, f"{'+'if val>=0 else ''}{val:.2f}%")
        ytd_val = b_row["avg_ret_ytd"]
        metric_cols[-1].metric("YTD", f"{'+'if ytd_val>=0 else ''}{ytd_val:.2f}%")

    st.markdown("<div style='height:12px'/>", unsafe_allow_html=True)

    # ── Full constituent table — single set of data columns based on mode ──
    col_headers = ""
    for label, lb in INTERVALS:
        short = label.replace("-", "")
        col_headers += f'<th style="text-align:right;padding:8px 10px;font-size:9px;font-weight:700;color:#475569;white-space:nowrap">{short}</th>'
    col_headers += '<th style="text-align:right;padding:8px 10px;font-size:9px;font-weight:700;color:#475569;white-space:nowrap">YTD</th>'

    n_data_cols = len(INTERVALS) + 1
    group_label = "Z-SCORE MOMENTUM (σ)" if show_z else "RAW RETURN %"

    rows_html = ""
    # Sort by 20-day z-score by default
    default_sort = "z_20" if show_z else "ret_20"
    for _, row in members_df.sort_values(default_sort, ascending=False, na_position="last").iterrows():
        data_cells = ""
        if show_z:
            for _, lb in INTERVALS:
                data_cells += f'<td style="padding:6px 10px;text-align:right">{z_html(row[f"z_{lb}"], 11)}</td>'
            data_cells += f'<td style="padding:6px 10px;text-align:right">{z_html(row["z_ytd"], 11)}</td>'
        else:
            for _, lb in INTERVALS:
                data_cells += f'<td style="padding:6px 10px;text-align:right">{pct_html(row[f"ret_{lb}"], 11)}</td>'
            data_cells += f'<td style="padding:6px 10px;text-align:right">{pct_html(row["ret_ytd"], 11)}</td>'

        rows_html += f"""
        <tr style="border-bottom:1px solid #0f172a">
            <td style="padding:6px 10px;font-weight:700;color:#e2e8f0;font-family:'IBM Plex Mono',monospace;font-size:11px;white-space:nowrap">{row["ticker"]}</td>
            <td style="padding:6px 10px;text-align:right;color:#94a3b8;font-family:'IBM Plex Mono',monospace;font-size:11px">${row["price"]:.2f}</td>
            {data_cells}
        </tr>"""

    st.html(f"""
    <div style="background:#080f1a;border:1px solid rgba({rgb},0.25);border-radius:8px;overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-size:11px">
            <thead>
                <tr style="border-bottom:1px solid #1e293b;background:#0f172a">
                    <th></th><th></th>
                    <th colspan="{n_data_cols}" style="text-align:center;padding:6px;font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.05em;border-left:1px solid #1e293b;border-right:1px solid #1e293b">{group_label}</th>
                </tr>
                <tr style="border-bottom:1px solid #1e293b">
                    <th style="text-align:left;padding:8px 10px;font-size:9px;font-weight:700;color:#475569;letter-spacing:0.08em">TICKER</th>
                    <th style="text-align:right;padding:8px 10px;font-size:9px;font-weight:700;color:#475569;letter-spacing:0.08em">PRICE</th>
                    {col_headers}
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """)

    st.markdown("<div style='height:16px'/>", unsafe_allow_html=True)


# ── ROTATION MAP TAB ───────────────────────────────────────────────────────────
def render_rotation(b_stats: pd.DataFrame, z_label: str):
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
        <div style="width:3px;height:20px;background:#f59e0b;border-radius:2px"></div>
        <span style="font-size:13px;font-weight:700;color:#e2e8f0">Thematic Rotation Map</span>
    </div>
    <div style="font-size:11px;color:#475569;margin-left:13px">Z-scored returns — each basket normalized by its own rolling vol</div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="info-box">
        <strong style="color:#f59e0b">σ</strong>&nbsp;
        Axes show <strong style="color:#94a3b8">z-scores</strong> — each basket's return divided by its own {z_label.split("(")[0].strip()} rolling std dev.
        Equal distances from origin are genuinely comparable across baskets regardless of vol regime.
    </div>
    """, unsafe_allow_html=True)

    q1, q2, q3, q4 = st.columns(4)
    quadrants = [
        ("LAGGING · DECEL",  "5d z < 0, 20d z < 0",  "#ef4444"),
        ("LAGGING · ACCEL",  "5d z > 0, 20d z < 0",  "#f59e0b"),
        ("LEADING · DECEL",  "5d z < 0, 20d z > 0",  "#8b5cf6"),
        ("LEADING · ACCEL",  "5d z > 0, 20d z > 0",  "#10b981"),
    ]
    for col, (q, desc, color) in zip([q1, q2, q3, q4], quadrants):
        col.markdown(f"""
        <div style="background:#080f1a;border:1px solid #1e293b;border-radius:6px;padding:8px 12px;font-size:10px">
            <span style="color:{color};font-weight:700">{q}</span><br>
            <span style="color:#475569">{desc}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:16px'/>", unsafe_allow_html=True)

    if b_stats.empty:
        st.info("No basket data available.")
        return

    fig = go.Figure()
    for x0, x1, y0, y1, col in [
        (-5, 0, -5,  0,  "rgba(239,68,68,0.04)"),     # bottom-left: lagging+decel
        ( 0, 5, -5,  0,  "rgba(245,158,11,0.04)"),     # bottom-right: lagging+accel
        (-5, 0,  0,  5,  "rgba(139,92,246,0.04)"),     # top-left: leading+decel
        ( 0, 5,  0,  5,  "rgba(16,185,129,0.04)"),     # top-right: leading+accel
    ]:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=col, line_width=0, layer="below")

    for _, row in b_stats.iterrows():
        x, y = row["avgZ5d"], row["avgZ20d"]
        color = row["color"]
        label = row["basket"][:7] + "…" if len(row["basket"]) > 7 else row["basket"]
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text", text=[label],
            textposition="middle center",
            textfont=dict(color=color, size=9, family="IBM Plex Mono"),
            marker=dict(
                size=48,
                color=f"rgba({_rgb(color)},0.13)",
                line=dict(color=color, width=1.5),
            ),
            hovertemplate=(
                f"<b style='color:{color}'>{row['basket']}</b><br>"
                f"5d z: {'+'if x>=0 else ''}{x:.2f}σ<br>"
                f"20d z: {'+'if y>=0 else ''}{y:.2f}σ<extra></extra>"
            ),
            name=row["basket"],
        ))

    fig.add_hline(y=0,  line=dict(color="#334155", dash="dash", width=1))
    fig.add_vline(x=0,  line=dict(color="#334155", dash="dash", width=1))
    fig.add_hline(y=1,  line=dict(color="#1e293b", dash="dot",  width=1))
    fig.add_hline(y=-1, line=dict(color="#1e293b", dash="dot",  width=1))
    fig.add_vline(x=1,  line=dict(color="#1e293b", dash="dot",  width=1))
    fig.add_vline(x=-1, line=dict(color="#1e293b", dash="dot",  width=1))

    layout = dict(**PLOTLY_LAYOUT)
    layout.update(
        height=420, showlegend=False,
        xaxis=dict(**PLOTLY_LAYOUT["xaxis"], title=dict(text="5d z-score (σ)", font=dict(color="#475569", size=10))),
        yaxis=dict(**PLOTLY_LAYOUT["yaxis"], title=dict(text="20d z-score (σ)",  font=dict(color="#475569", size=10))),
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Rotation summary table
    st.markdown("""
    <div style="font-size:9px;font-weight:700;color:#94a3b8;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:4px">Rotation Summary</div>
    """, unsafe_allow_html=True)

    def sort_key(row):
        return row["avgZ20d"] + (row["avgZ5d"] - row["avgZ20d"])
    sorted_rows = b_stats.iloc[b_stats.apply(sort_key, axis=1).argsort()[::-1]]

    rows_html = ""
    for _, row in sorted_rows.iterrows():
        color = row["color"]
        tickers_str = ", ".join(row["tickers"][:8]) + (f" +{len(row['tickers'])-8}" if len(row["tickers"]) > 8 else "")
        rows_html += f"""
        <tr style="border-bottom:1px solid #0f172a">
            <td style="padding:10px 14px">
                <div style="display:flex;align-items:center;gap:10px">
                    <div style="width:4px;height:32px;background:{color};border-radius:2px;flex-shrink:0"></div>
                    <div>
                        <div style="font-weight:700;font-size:13px;color:#e2e8f0">{row["basket"]}</div>
                        <div style="font-size:10px;color:#475569;margin-top:2px">{tickers_str}</div>
                    </div>
                </div>
            </td>
            <td style="padding:10px 14px;text-align:right"><div style="font-size:9px;color:#475569">5d σ</div>{z_html(row["avgZ5d"])}</td>
            <td style="padding:10px 14px;text-align:right"><div style="font-size:9px;color:#475569">20d σ</div>{z_html(row["avgZ20d"])}</td>
        </tr>"""

    st.html(f"""
    <div style="background:#080f1a;border:1px solid #1e293b;border-radius:8px;overflow:hidden">
        <table style="width:100%;border-collapse:collapse;font-size:12px">
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    """)


# ── MOMENTUM RANKS TAB ─────────────────────────────────────────────────────────
def render_momentum(stock_df: pd.DataFrame, b_stats: pd.DataFrame, z_label: str):
    col_hdr, col_mode = st.columns([3, 1])
    with col_hdr:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
            <div style="width:3px;height:20px;background:#f59e0b;border-radius:2px"></div>
            <span style="font-size:13px;font-weight:700;color:#e2e8f0">Cross-Basket Momentum Ranks</span>
        </div>
        """, unsafe_allow_html=True)
    with col_mode:
        mode = st.radio("Mode", ["1d", "5d", "20d"], horizontal=True, key="mom_mode", label_visibility="collapsed")

    z_col = "z1d" if mode == "1d" else ("z5d" if mode == "5d" else "z20d")
    valid_df = stock_df.dropna(subset=[z_col]).sort_values(z_col, ascending=False)

    if valid_df.empty:
        st.info("No z-score data yet.")
        return

    top5 = valid_df.head(5)
    bot5 = valid_df.tail(5).iloc[::-1]

    def rank_rows_html(df, is_top):
        rows = ""
        for rank, (_, row) in enumerate(df.iterrows(), 1):
            val   = row[z_col]
            color = st.session_state.baskets.get(row["basket"], {}).get("color", "#64748b")
            bar_w = min(100, abs(val) * 28)
            bar_color = "#10b981" if is_top else "#ef4444"
            bar_dir   = "left" if is_top else "right"
            rows += f"""
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                <span style="width:16px;font-size:9px;color:#475569;font-family:'IBM Plex Mono',monospace;text-align:right">{rank}</span>
                <span style="width:46px;font-size:11px;font-weight:700;color:#e2e8f0;font-family:'IBM Plex Mono',monospace">{row["ticker"]}</span>
                <div style="flex:1;background:#0f172a;border-radius:2px;height:14px;position:relative;overflow:hidden">
                    <div style="position:absolute;{bar_dir}:0;top:0;bottom:0;width:{bar_w}%;background:{bar_color};opacity:0.7;border-radius:2px"></div>
                </div>
                {z_html(val)}
                <span style="background:rgba({_rgb(color)},0.13);color:{color};border:1px solid rgba({_rgb(color)},0.27);border-radius:3px;padding:1px 6px;font-size:9px;font-weight:700">{row["basket"][:6]}</span>
            </div>"""
        return rows

    col_top, col_bot = st.columns(2)
    with col_top:
        st.html(f"""
        <div style="background:#080f1a;border:1px solid #1e293b;border-radius:8px;padding:20px">
            <div style="font-size:10px;font-weight:700;color:#10b981;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:14px">▲ Top z-score ({mode})</div>
            {rank_rows_html(top5, True)}
        </div>
        """)
    with col_bot:
        st.html(f"""
        <div style="background:#080f1a;border:1px solid #1e293b;border-radius:8px;padding:20px">
            <div style="font-size:10px;font-weight:700;color:#ef4444;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:14px">▼ Bottom z-score ({mode})</div>
            {rank_rows_html(bot5, False)}
        </div>
        """)

    st.markdown("<div style='height:20px'/>", unsafe_allow_html=True)

    bz_col = "avgZ1d" if mode == "1d" else ("avgZ5d" if mode == "5d" else "avgZ20d")
    sorted_baskets = b_stats.sort_values(bz_col, ascending=False)

    basket_rows = ""
    for rank, (_, row) in enumerate(sorted_baskets.iterrows(), 1):
        val   = row[bz_col]
        color = row["color"]
        bar_w = min(100, abs(val) * 28)
        bar_color = "#10b981" if val >= 0 else "#ef4444"
        bar_dir   = "left" if val >= 0 else "right"
        basket_rows += f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
            <span style="width:16px;font-size:9px;color:#475569;font-family:'IBM Plex Mono',monospace;text-align:right">{rank}</span>
            <span style="width:4px;height:24px;background:{color};border-radius:2px;flex-shrink:0"></span>
            <span style="width:110px;font-size:11px;font-weight:700;color:#e2e8f0">{row["basket"]}</span>
            <div style="flex:1;background:#0f172a;border-radius:2px;height:14px;position:relative;overflow:hidden">
                <div style="position:absolute;{bar_dir}:0;top:0;bottom:0;width:{bar_w}%;background:{bar_color};opacity:0.7;border-radius:2px"></div>
            </div>
            {z_html(val)}
        </div>"""

    st.html(f"""
    <div style="background:#080f1a;border:1px solid #1e293b;border-radius:8px;padding:20px">
        <div style="font-size:10px;font-weight:700;color:#f59e0b;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:14px">Basket z-score ({mode})</div>
        {basket_rows}
    </div>
    """)



# ── SETTINGS TAB ───────────────────────────────────────────────────────────────
def render_settings():
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:10px">Theme Baskets</div>', unsafe_allow_html=True)

        for name, cfg in st.session_state.baskets.items():
            col_sel, col_edit = st.columns([5, 1])
            with col_sel:
                is_sel = st.session_state.selected_basket == name
                if st.button(f"{'◆ ' if is_sel else '◇ '}{name}", key=f"sel_{name}", use_container_width=True):
                    st.session_state.selected_basket = name
                    st.session_state.editing_basket  = None
            with col_edit:
                if st.button("✎", key=f"edit_{name}", help=f"Edit {name}"):
                    st.session_state.editing_basket = name

        st.markdown("<div style='height:8px'/>", unsafe_allow_html=True)

        if st.button("＋ New Basket", use_container_width=True, key="new_basket_btn"):
            st.session_state.editing_basket = "__new__"

        editing = st.session_state.editing_basket
        if editing:
            st.divider()
            is_new   = editing == "__new__"
            existing = {} if is_new else st.session_state.baskets.get(editing, {})

            st.markdown(
                f'<div style="font-size:11px;font-weight:700;color:#e2e8f0;margin-bottom:12px">{"New Basket" if is_new else f"Edit · {editing}"}</div>',
                unsafe_allow_html=True,
            )

            with st.form(key="basket_form", clear_on_submit=True):
                new_name = st.text_input("Name", value="" if is_new else editing, placeholder="e.g. Fintech, EV…")
                color_idx = PALETTE.index(existing.get("color", PALETTE[0])) if existing.get("color") in PALETTE else 0
                new_color = st.selectbox("Color", PALETTE, index=color_idx, format_func=lambda c: c)
                tickers_default = ", ".join(existing.get("tickers", []))
                tickers_raw = st.text_area("Tickers (comma-separated)", value=tickers_default, height=80, placeholder="MSFT, AAPL, NVDA…")

                col_save, col_cancel = st.columns(2)
                with col_save:
                    submitted = st.form_submit_button("Save", use_container_width=True, type="primary")
                with col_cancel:
                    cancelled = st.form_submit_button("Cancel", use_container_width=True)

                if submitted:
                    name_clean    = new_name.strip()
                    ticker_list   = [t.strip().upper() for t in tickers_raw.replace("\n", ",").split(",") if t.strip()]
                    ticker_unique = list(dict.fromkeys(ticker_list))
                    dupes_removed = len(ticker_list) - len(ticker_unique)

                    if not name_clean:
                        st.error("Name is required")
                    elif not ticker_unique:
                        st.error("Add at least one ticker")
                    elif is_new and name_clean in st.session_state.baskets:
                        st.error("Name already exists")
                    else:
                        if dupes_removed:
                            st.warning(f"Removed {dupes_removed} duplicate ticker{'s' if dupes_removed > 1 else ''}")
                        if not is_new and editing != name_clean:
                            st.session_state.baskets.pop(editing)
                            if st.session_state.selected_basket == editing:
                                st.session_state.selected_basket = name_clean
                        st.session_state.baskets[name_clean] = {"color": new_color, "tickers": ticker_unique}
                        if is_new:
                            st.session_state.selected_basket = name_clean
                        st.session_state.editing_basket = None
                        _save_baskets()
                        st.rerun()

                if cancelled:
                    st.session_state.editing_basket = None
                    st.rerun()

            if not is_new:
                if st.button(f"🗑 Delete '{editing}'", key="delete_basket", use_container_width=True):
                    del st.session_state.baskets[editing]
                    remaining = list(st.session_state.baskets.keys())
                    st.session_state.selected_basket = remaining[0] if remaining else None
                    st.session_state.editing_basket  = None
                    _save_baskets()
                    st.rerun()

    with col_right:
        st.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px">Config</div>', unsafe_allow_html=True)

        basket_json = json.dumps(st.session_state.baskets, indent=2)
        st.download_button("⬇ Export baskets.json", data=basket_json, file_name="baskets.json", mime="application/json", use_container_width=True)

        uploaded = st.file_uploader("⬆ Import baskets.json", type="json", label_visibility="collapsed")
        if uploaded:
            try:
                imported = json.load(uploaded)
                st.session_state.baskets = imported
                st.session_state.selected_basket = list(imported.keys())[0]
                _save_baskets()
                st.success("Imported!")
                st.rerun()
            except Exception as e:
                st.error(f"Invalid file: {e}")

        st.markdown("<div style='height:24px'/>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:10px">Ticker Diagnostics</div>', unsafe_allow_html=True)

        baskets = st.session_state.baskets
        has_issues = False
        diag_html = ""

        for name, cfg in baskets.items():
            seen = {}
            for t in cfg["tickers"]:
                seen[t] = seen.get(t, 0) + 1
            dupes = {t: c for t, c in seen.items() if c > 1}
            if dupes:
                has_issues = True
                color = cfg.get("color", "#64748b")
                for t, c in dupes.items():
                    diag_html += f"""
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                        <span style="color:#ef4444;font-size:12px;font-weight:900">✕</span>
                        <span style="font-size:11px;color:#e2e8f0;font-family:'IBM Plex Mono',monospace;font-weight:700">{t}</span>
                        <span style="font-size:10px;color:#94a3b8">repeated {c}× in</span>
                        <span style="background:rgba({_rgb(color)},0.13);color:{color};border:1px solid rgba({_rgb(color)},0.27);border-radius:3px;padding:1px 6px;font-size:9px;font-weight:700">{name}</span>
                    </div>"""

        ticker_to_baskets = {}
        for name, cfg in baskets.items():
            for t in set(cfg["tickers"]):
                ticker_to_baskets.setdefault(t, []).append(name)
        cross_dupes = {t: bs for t, bs in ticker_to_baskets.items() if len(bs) > 1}

        if cross_dupes:
            has_issues = True
            for t, bs in sorted(cross_dupes.items()):
                tags = ""
                for b in bs:
                    color = baskets[b].get("color", "#64748b")
                    tags += f'<span style="background:rgba({_rgb(color)},0.13);color:{color};border:1px solid rgba({_rgb(color)},0.27);border-radius:3px;padding:1px 6px;font-size:9px;font-weight:700">{b}</span> '
                diag_html += f"""
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap">
                    <span style="color:#f59e0b;font-size:12px;font-weight:900">⚠</span>
                    <span style="font-size:11px;color:#e2e8f0;font-family:'IBM Plex Mono',monospace;font-weight:700">{t}</span>
                    <span style="font-size:10px;color:#94a3b8">appears in {len(bs)} baskets:</span>
                    {tags}
                </div>"""

        if has_issues:
            st.html(f'<div style="background:#080f1a;border:1px solid #1e293b;border-radius:8px;padding:16px">{diag_html}</div>')
        else:
            st.html('<div style="background:#080f1a;border:1px solid #1e293b;border-radius:8px;padding:16px;display:flex;align-items:center;gap:8px"><span style="color:#10b981;font-size:12px;font-weight:900">✓</span><span style="font-size:11px;color:#10b981;font-weight:600">All clean — no duplicate tickers found</span></div>')


# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    col_title, col_badge = st.columns([6, 1])
    with col_title:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:20px">
            <div style="width:36px;height:36px;background:linear-gradient(135deg,#f59e0b,#ef4444);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:900;color:#000">⬡</div>
            <div>
                <div style="font-size:20px;font-weight:700;letter-spacing:-0.02em;color:#e2e8f0">THEME DESK</div>
                <div style="font-size:10px;color:#475569;letter-spacing:0.1em;text-transform:uppercase">Tech Basket Monitor · Live via yfinance</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    baskets     = st.session_state.baskets
    z_window    = st.session_state.z_window
    z_label     = next(k for k, v in Z_WINDOWS.items() if v == z_window)
    all_tickers = tuple(sorted({t for cfg in baskets.values() for t in cfg["tickers"]}))

    with st.spinner("Fetching market data…"):
        prices_df = fetch_prices(all_tickers, FETCH_PERIOD)

    if prices_df.empty:
        st.error("Could not fetch price data. Check your internet connection.")
        return

    with col_badge:
        current_time = datetime.now().strftime("%H:%M")
        st.markdown(f"""
        <div style="text-align:right;margin-top:8px">
            <span class="live-badge">● Live · {current_time}</span>
        </div>
        """, unsafe_allow_html=True)

    stock_df = build_stock_stats(prices_df, baskets, z_window)
    b_stats  = basket_stats(baskets, stock_df)

    # Tabs — Overview replaced by landing page with expandable cards
    tab_baskets, tab_rot, tab_mom, tab_settings = st.tabs([
        "Baskets", "Rotation Map", "Momentum Ranks", "⚙ Settings"
    ])

    with tab_baskets:
        render_landing_page(b_stats, stock_df, z_label)

    with tab_rot:
        render_rotation(b_stats, z_label)

    with tab_mom:
        render_momentum(stock_df, b_stats, z_label)

    with tab_settings:
        render_settings()


if __name__ == "__main__":
    main()
