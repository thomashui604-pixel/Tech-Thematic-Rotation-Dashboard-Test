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
from plotly.subplots import make_subplots
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
INTERVAL_KEYS = [f"ret_{lb}" for _, lb in INTERVALS]
Z_INTERVAL_KEYS = [f"z_{lb}" for _, lb in INTERVALS]


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

if "baskets" not in st.session_state:
    st.session_state.baskets = _load_default_baskets()
if "editing_basket" not in st.session_state:
    st.session_state.editing_basket = None
if "selected_basket" not in st.session_state:
    st.session_state.selected_basket = list(st.session_state.baskets.keys())[0]
if "z_window" not in st.session_state:
    st.session_state.z_window = 252


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
    rets = rolling_return_series(prices, lookback)
    if len(rets) < z_window:
        return None
    window_slice = rets.iloc[-z_window:]
    mu    = window_slice.mean()
    sigma = window_slice.std(ddof=0)
    if sigma < 1e-8:
        return 0.0
    return float((rets.iloc[-1] - mu) / sigma)


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

def signal_html(z):
    if z is None:
        return '<span style="color:#334155;font-size:10px">—</span>'
    if z > 1.5:
        return '<span style="color:#10b981;font-weight:700;font-size:10px;border:1px solid rgba(16,185,129,0.33);border-radius:3px;padding:2px 6px">ACCEL</span>'
    if z < -1.5:
        return '<span style="color:#ef4444;font-weight:700;font-size:10px;border:1px solid rgba(239,68,68,0.33);border-radius:3px;padding:2px 6px">FADE</span>'
    return '<span style="color:#64748b;font-weight:700;font-size:10px;border:1px solid rgba(100,116,139,0.33);border-radius:3px;padding:2px 6px">NEUTRAL</span>'


def rotation_label(z5d, z20d):
    pos   = "LEADING" if z20d >= 0 else "LAGGING"
    pos_c = "#10b981" if z20d >= 0 else "#ef4444"
    if z5d > z20d:
        dir_l, dir_c = "ACCEL", "#10b981"
    else:
        dir_l, dir_c = "DECEL", "#ef4444"
    return pos, pos_c, dir_l, dir_c


def rotation_label_html(z5d, z20d, size=9):
    pos, pos_c, dir_l, dir_c = rotation_label(z5d, z20d)
    return (
        f'<span style="font-size:{size}px;font-weight:700;font-family:\'IBM Plex Mono\',monospace">'
        f'<span style="color:{pos_c}">{pos}</span>'
        f'<span style="color:#334155"> · </span>'
        f'<span style="color:{dir_c}">{dir_l}</span>'
        f'</span>'
    )


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


# ── SIDEBAR ────────────────────────────────────────────────────────────────────
def render_settings():
    """Render settings content inside a tab (replaces sidebar)."""

    col_left, col_right = st.columns([1, 1], gap="large")

    # ── LEFT COLUMN: Z-window + Basket list + editor ──
    with col_left:
        st.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:6px">Z-Score Window</div>', unsafe_allow_html=True)
        z_label = st.selectbox(
            "z_window_select", list(Z_WINDOWS.keys()),
            index=list(Z_WINDOWS.values()).index(st.session_state.z_window),
            label_visibility="collapsed",
        )
        st.session_state.z_window = Z_WINDOWS[z_label]

        st.markdown("<div style='height:16px'/>", unsafe_allow_html=True)
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

        # ── Basket editor form ──
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
                new_color = st.selectbox("Color", PALETTE, index=color_idx,
                                         format_func=lambda c: c)

                tickers_default = ", ".join(existing.get("tickers", []))
                tickers_raw = st.text_area(
                    "Tickers (comma-separated)",
                    value=tickers_default,
                    height=80,
                    placeholder="MSFT, AAPL, NVDA…",
                )

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
                            old_data = st.session_state.baskets.pop(editing)
                            if st.session_state.selected_basket == editing:
                                st.session_state.selected_basket = name_clean

                        st.session_state.baskets[name_clean] = {
                            "color":   new_color,
                            "tickers": ticker_unique,
                        }
                        if is_new:
                            st.session_state.selected_basket = name_clean
                        st.session_state.editing_basket = None
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
                    st.rerun()

    # ── RIGHT COLUMN: Config export / import ──
    with col_right:
        st.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px">Config</div>', unsafe_allow_html=True)

        basket_json = json.dumps(st.session_state.baskets, indent=2)
        st.download_button(
            "⬇ Export baskets.json",
            data=basket_json,
            file_name="baskets.json",
            mime="application/json",
            use_container_width=True,
        )

        uploaded = st.file_uploader("⬆ Import baskets.json", type="json", label_visibility="collapsed")
        if uploaded:
            try:
                imported = json.load(uploaded)
                st.session_state.baskets = imported
                st.session_state.selected_basket = list(imported.keys())[0]
                st.success("Imported!")
                st.rerun()
            except Exception as e:
                st.error(f"Invalid file: {e}")

        # ── Ticker Diagnostics ──
        st.markdown("<div style='height:24px'/>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:10px">Ticker Diagnostics</div>', unsafe_allow_html=True)

        baskets = st.session_state.baskets
        has_issues = False
        diag_html = ""

        # Check for duplicates within a single basket
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
                        <span style="background:rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.13);color:{color};border:1px solid rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.27);border-radius:3px;padding:1px 6px;font-size:9px;font-weight:700">{name}</span>
                    </div>"""

        # Check for tickers shared across baskets
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
                    tags += f'<span style="background:rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.13);color:{color};border:1px solid rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.27);border-radius:3px;padding:1px 6px;font-size:9px;font-weight:700">{b}</span> '
                diag_html += f"""
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap">
                    <span style="color:#f59e0b;font-size:12px;font-weight:900">⚠</span>
                    <span style="font-size:11px;color:#e2e8f0;font-family:'IBM Plex Mono',monospace;font-weight:700">{t}</span>
                    <span style="font-size:10px;color:#94a3b8">appears in {len(bs)} baskets:</span>
                    {tags}
                </div>"""

        if has_issues:
            st.html(f"""
            <div style="background:#080f1a;border:1px solid #1e293b;border-radius:8px;padding:16px">
                {diag_html}
            </div>
            """)
        else:
            st.html("""
            <div style="background:#080f1a;border:1px solid #1e293b;border-radius:8px;padding:16px;display:flex;align-items:center;gap:8px">
                <span style="color:#10b981;font-size:12px;font-weight:900">✓</span>
                <span style="font-size:11px;color:#10b981;font-weight:600">All clean — no duplicate tickers found</span>
            </div>
            """)


# ── BASKET CARDS ROW ───────────────────────────────────────────────────────────
def render_basket_cards(b_stats: pd.DataFrame):
    st.markdown('<div style="font-size:9px;font-weight:700;color:#94a3b8;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:12px">▌ Theme Baskets — Raw % Returns</div>', unsafe_allow_html=True)

    n = len(b_stats)
    if n == 0:
        st.info("No baskets defined. Add one in the sidebar.")
        return

    cols = st.columns(min(n, 5))
    for i, (_, row) in enumerate(b_stats.iterrows()):
        if i >= len(cols):
            break
        color  = row["color"]
        avg1d  = row["avg1d"]
        avg5d  = row["avg5d"]
        avg20d = row["avg20d"]
        selected = st.session_state.selected_basket == row["basket"]

        border = f"2px solid {color}" if selected else "1px solid #1e293b"
        bg     = "#0f172a" if selected else "#080f1a"
        bar_w  = min(100, max(0, 50 + avg5d * 5))
        rot_html = rotation_label_html(row["avgZ5d"], row["avgZ20d"], size=9)

        with cols[i]:
            st.markdown(f"""
            <div onclick="" style="
                background:{bg};border:{border};border-radius:8px;
                padding:14px 16px;cursor:pointer;position:relative;overflow:hidden;
            ">
                <div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:6px">{row["basket"]}</div>
                <div style="display:inline-block;background:rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.13);color:{color};border:1px solid rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.27);border-radius:3px;padding:1px 7px;font-size:9px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:10px">{row["n"]} stocks</div>
                <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <div><div style="font-size:9px;color:#475569;margin-bottom:2px">1D</div>{pct_html(avg1d, 13)}</div>
                    <div style="text-align:center"><div style="font-size:9px;color:#475569;margin-bottom:2px">5D</div>{pct_html(avg5d, 13)}</div>
                    <div style="text-align:right"><div style="font-size:9px;color:#475569;margin-bottom:2px">20D</div>{pct_html(avg20d, 13)}</div>
                </div>
                <div style="margin-bottom:8px">{rot_html}</div>
                <div style="height:2px;background:#1e293b;border-radius:2px">
                    <div style="height:100%;width:{bar_w}%;background:linear-gradient(90deg,rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.33),{color});border-radius:2px"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Invisible button to handle clicks properly
            if st.button("Select", key=f"card_sel_{row['basket']}", use_container_width=True,
                         help=f"View {row['basket']}"):
                st.session_state.selected_basket = row["basket"]
                st.rerun()


# ── OVERVIEW TAB ───────────────────────────────────────────────────────────────
def render_overview(b_stats: pd.DataFrame, stock_df: pd.DataFrame, z_window: int, z_label: str):
    sel = st.session_state.selected_basket
    if not sel or sel not in st.session_state.baskets:
        st.info("Select a basket from the sidebar.")
        return

    cfg    = st.session_state.baskets[sel]
    b_row  = b_stats[b_stats["basket"] == sel]
    if b_row.empty:
        st.warning("No data yet for this basket.")
        return
    b_row = b_row.iloc[0]

    # ── HEADER & CONTROLS ──
    c_title, c_toggle = st.columns([4, 1])
    with c_title:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
            <div style="width:3px;height:20px;background:#f59e0b;border-radius:2px"></div>
            <span style="font-size:14px;font-weight:700;color:#e2e8f0">{sel}</span>
            <span style="font-size:11px;color:#475569">· {b_row["n"]} constituents · z-window: {z_label}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with c_toggle:
        sig_mode = st.selectbox("Signal Horizon", ["1d", "5d", "20d"], index=1, 
                               format_func=lambda x: f"{x} σ")
    
    z_col_map = {"1d": "z1d", "5d": "z5d", "20d": "z20d"}
    target_z_col = z_col_map[sig_mode]

    # ── SUMMARY METRICS (Grouped) ──
    # Group 1: Raw Performance
    st.markdown('<div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;border-bottom:1px solid #1e293b;padding-bottom:4px;margin-bottom:8px">Basket Performance (Raw %)</div>', unsafe_allow_html=True)
    c1, c2, c3, _ = st.columns([1, 1, 1, 3])
    c1.metric("Avg 1d %", f"{'+'if b_row['avg1d']>=0 else ''}{b_row['avg1d']:.2f}%")
    c2.metric("Avg 5d %", f"{'+'if b_row['avg5d']>=0 else ''}{b_row['avg5d']:.2f}%")
    c3.metric("Avg 20d %", f"{'+'if b_row['avg20d']>=0 else ''}{b_row['avg20d']:.2f}%")

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    # Group 2: Momentum Regime
    st.markdown('<div style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;border-bottom:1px solid #1e293b;padding-bottom:4px;margin-bottom:8px">Momentum Regime (Z-Score)</div>', unsafe_allow_html=True)
    c4, c5, c6, _ = st.columns([1, 1, 1, 3])
    c4.metric(f"Avg 1d σ", f"{'+'if b_row['avgZ1d']>=0 else ''}{b_row['avgZ1d']:.2f}σ")
    c5.metric(f"Avg 5d σ", f"{'+'if b_row['avgZ5d']>=0 else ''}{b_row['avgZ5d']:.2f}σ")
    c6.metric(f"Avg 20d σ", f"{'+'if b_row['avgZ20d']>=0 else ''}{b_row['avgZ20d']:.2f}σ")

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
    for _, row in members.sort_values(target_z_col, ascending=False, na_position="last").iterrows():
        rows_html += f"""
        <tr style="border-bottom:1px solid #0f172a">
            <td style="padding:8px 14px;font-weight:700;color:#e2e8f0;font-family:'IBM Plex Mono',monospace">{row["ticker"]}</td>
            <td style="padding:8px 14px;text-align:right;color:#94a3b8;font-family:'IBM Plex Mono',monospace">${row["price"]:.2f}</td>
            <td style="padding:8px 14px;text-align:right;background:rgba(255,255,255,0.015)">{pct_html(row["ret1d"])}</td>
            <td style="padding:8px 14px;text-align:right;background:rgba(255,255,255,0.015)">{pct_html(row["ret5d"])}</td>
            <td style="padding:8px 14px;text-align:right;background:rgba(255,255,255,0.015)">{pct_html(row["ret20d"])}</td>
            <td style="padding:8px 14px;text-align:right">{z_html(row["z1d"])}</td>
            <td style="padding:8px 14px;text-align:right">{z_html(row["z5d"])}</td>
            <td style="padding:8px 14px;text-align:right">{z_html(row["z20d"])}</td>
            <td style="padding:8px 14px;text-align:right">{signal_html(row[target_z_col])}</td>
        </tr>"""

    st.html(f"""
    <div style="background:#080f1a;border:1px solid rgba({rgb},0.25);border-radius:8px;overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-size:11px">
            <thead>
                <tr style="border-bottom:1px solid #1e293b;background:#0f172a">
                    <th></th>
                    <th></th>
                    <th colspan="3" style="text-align:center;padding:6px;font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.05em;border-left:1px solid #1e293b;border-right:1px solid #1e293b">RAW RETURN %</th>
                    <th colspan="3" style="text-align:center;padding:6px;font-size:9px;font-weight:700;color:#64748b;letter-spacing:0.05em;border-right:1px solid #1e293b">MOMENTUM REGIME (σ)</th>
                    <th></th>
                </tr>
                <tr style="border-bottom:1px solid #1e293b">
                    <th style="text-align:left;padding:8px 14px;font-size:10px;font-weight:700;color:#475569;letter-spacing:0.08em;text-transform:uppercase">Ticker</th>
                    <th style="text-align:right;padding:8px 14px;font-size:10px;font-weight:700;color:#475569;letter-spacing:0.08em;text-transform:uppercase">Price</th>
                    <th style="text-align:right;padding:8px 14px;font-size:10px;font-weight:700;color:#475569;background:rgba(255,255,255,0.015)">1D</th>
                    <th style="text-align:right;padding:8px 14px;font-size:10px;font-weight:700;color:#475569;background:rgba(255,255,255,0.015)">5D</th>
                    <th style="text-align:right;padding:8px 14px;font-size:10px;font-weight:700;color:#475569;background:rgba(255,255,255,0.015)">20D</th>
                    <th style="text-align:right;padding:8px 14px;font-size:10px;font-weight:700;color:#475569">1D</th>
                    <th style="text-align:right;padding:8px 14px;font-size:10px;font-weight:700;color:#475569">5D</th>
                    <th style="text-align:right;padding:8px 14px;font-size:10px;font-weight:700;color:#475569">20D</th>
                    <th style="text-align:right;padding:8px 14px;font-size:10px;font-weight:700;color:#f59e0b;letter-spacing:0.08em;text-transform:uppercase">SIGNAL ({sig_mode})</th>
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
                f"20d z: {'+'if x>=0 else ''}{x:.2f}σ<br>"
                f"5d z:  {'+'if y>=0 else ''}{y:.2f}σ<extra></extra>"
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
        rot_badge = rotation_label_html(row["avgZ5d"], row["avgZ20d"])
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
            <td style="padding:10px 14px;text-align:right">{rot_badge}</td>
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


# ── CORRELATION TAB ────────────────────────────────────────────────────────────


def render_correlations(prices_df: pd.DataFrame, baskets: dict):
    sel = st.session_state.selected_basket
    returns_df = prices_df.pct_change()

    basket_returns = {}
    basket_counts = {}
    for name, cfg in baskets.items():
        tickers = [t for t in cfg["tickers"] if t in returns_df.columns]
        if tickers:
            basket_returns[name] = returns_df[tickers].mean(axis=1)
            basket_counts[name] = returns_df[tickers].count(axis=1)

    basket_ret_df = pd.DataFrame(basket_returns).dropna(how='all')
    if basket_ret_df.empty:
        st.info("Insufficient data for correlation analysis.")
        return

    sel_tickers = [t for t in baskets[sel]["tickers"] if t in returns_df.columns]

    # ── Rolling Correlation Analysis ──
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
        <div style="width:3px;height:20px;background:#f59e0b;border-radius:2px"></div>
        <span style="font-size:13px;font-weight:700;color:#e2e8f0">Rolling Correlation History</span>
    </div>
    """, unsafe_allow_html=True)

    if sel not in basket_ret_df.columns:
        return

    other_baskets = [b for b in basket_ret_df.columns if b != sel]
    constituents  = sel_tickers

    rc1, rc2, rc3 = st.columns([1, 1, 2])
    with rc1:
        roll_target = st.selectbox("Compare Selected Basket vs...", ["Other Baskets", "Constituents"])
    with rc2:
        if roll_target == "Other Baskets":
            compare_to = st.selectbox("Select Target", other_baskets)
        else:
            compare_to = st.selectbox("Select Target", constituents)
    with rc3:
        roll_window = st.slider("Rolling Window (Trading Days)", 10, 252, 63)

    if roll_target == "Other Baskets":
        series_b = basket_ret_df[compare_to]
        line_color = baskets[compare_to].get("color", "#cbd5e1")
        series_a = basket_ret_df[sel]
        depth_series = basket_counts[sel].reindex(series_a.index)
    else:
        series_b = returns_df[compare_to]
        line_color = "#cbd5e1"
        is_constituent = compare_to in baskets[sel]["tickers"]
        if is_constituent:
            adj_tickers = [t for t in baskets[sel]["tickers"] if t != compare_to and t in returns_df.columns]
            if not adj_tickers:
                st.error(f"Cannot calculate: {compare_to} is the only stock in {sel}.")
                return
            series_a = returns_df[adj_tickers].mean(axis=1)
            depth_series = returns_df[adj_tickers].count(axis=1).reindex(series_a.index)
            st.caption(f"ℹ️ Excluded {compare_to} from {sel} basket return to prevent double-counting.")
        else:
            series_a = basket_ret_df[sel]
            depth_series = basket_counts[sel].reindex(series_a.index)

    rolling_corr = series_a.rolling(window=roll_window).corr(series_b).dropna()
    depth_series = depth_series.reindex(rolling_corr.index)

    fig_roll = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.7, 0.3])
    fig_roll.add_hline(y=0, line=dict(color="#334155", width=1, dash="dash"), row=1, col=1)
    fig_roll.add_hline(y=0.8, line=dict(color="#1e293b", width=1, dash="dot"), row=1, col=1)
    fig_roll.add_hline(y=-0.8, line=dict(color="#1e293b", width=1, dash="dot"), row=1, col=1)
    fig_roll.add_trace(go.Scatter(
        x=rolling_corr.index, y=rolling_corr.values, mode="lines",
        name=f"Corr({sel}, {compare_to})", line=dict(color=line_color, width=2)
    ), row=1, col=1)
    fig_roll.add_trace(go.Scatter(
        x=depth_series.index, y=depth_series.values, mode="lines",
        name="Active Constituents", fill='tozeroy',
        line=dict(color="#334155", width=1), hovertemplate="%{y} active stocks<extra></extra>"
    ), row=2, col=1)

    layout_roll = dict(**PLOTLY_LAYOUT)
    layout_roll.update(height=400, margin=dict(l=50, r=20, t=20, b=40), showlegend=True)
    fig_roll.update_layout(**layout_roll)
    fig_roll.update_yaxes(range=[-1.1, 1.1], gridcolor="#1e293b", zeroline=False, title=dict(text="Correlation", font=dict(size=10, color="#64748b")), row=1, col=1)
    fig_roll.update_yaxes(gridcolor="#1e293b", zeroline=False, title=dict(text="Count", font=dict(size=10, color="#64748b")), row=2, col=1)
    fig_roll.update_xaxes(gridcolor="#1e293b", zerolinecolor="#334155", linecolor="#1e293b", row=1, col=1)
    fig_roll.update_xaxes(title=dict(text=f"Date ({roll_window}d Rolling Window)", font=dict(size=10, color="#64748b")), gridcolor="#1e293b", zerolinecolor="#334155", linecolor="#1e293b", row=2, col=1)

    st.plotly_chart(fig_roll, use_container_width=True)

    latest_corr = rolling_corr.iloc[-1] if not rolling_corr.empty else 0
    avg_corr = rolling_corr.mean()
    min_corr = rolling_corr.min()
    max_corr = rolling_corr.max()
    st.markdown(f"""
    <div style="display:flex;gap:24px;background:#080f1a;border:1px solid #1e293b;padding:12px 20px;border-radius:6px;font-family:'IBM Plex Mono',monospace;font-size:11px">
        <div><span style="color:#64748b">Current:</span> <span style="color:#e2e8f0;font-weight:700">{latest_corr:.2f}</span></div>
        <div><span style="color:#64748b">Average:</span> <span style="color:#e2e8f0;font-weight:700">{avg_corr:.2f}</span></div>
        <div><span style="color:#64748b">Range:</span> <span style="color:#e2e8f0;font-weight:700">{min_corr:.2f}</span> to <span style="color:#e2e8f0;font-weight:700">{max_corr:.2f}</span></div>
    </div>
    """, unsafe_allow_html=True)


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
    tab_baskets, tab_rot, tab_mom, tab_corr, tab_settings = st.tabs([
        "Baskets", "Rotation Map", "Momentum Ranks", "Correlations", "⚙ Settings"
    ])

    with tab_baskets:
        render_landing_page(b_stats, stock_df, z_label)

    with tab_rot:
        render_rotation(b_stats, z_label)

    with tab_mom:
        render_momentum(stock_df, b_stats, z_label)

    with tab_corr:
        render_correlations(prices_df, baskets)

    with tab_settings:
        render_settings()


if __name__ == "__main__":
    main()