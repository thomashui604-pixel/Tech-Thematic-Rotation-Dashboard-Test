# Theme Desk — Tech Basket Monitor

Live thematic momentum tracker for tech stocks. Deployed via Streamlit Community Cloud — no local installs required.

---

## Deploy in 5 minutes

### 1. Create a GitHub repo

Create a **new public (or private) repo** and add these two files:
```
your-repo/
├── app.py
└── requirements.txt
```

### 2. Deploy to Streamlit Community Cloud

1. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub
2. Click **"New app"**
3. Select your repo, branch (`main`), and set the **Main file path** to `app.py`
4. Click **"Deploy"**

Streamlit will install dependencies and launch the app. You'll get a permanent URL like:
```
https://your-app-name.streamlit.app
```

That's it. Accessible from any browser, no Python or Node required.

---

## Saving your basket config

Basket changes (add/edit/delete) persist **for your current session only** on Streamlit Cloud (the server is stateless).

To save your baskets permanently:

1. Click **"⬇ Export baskets.json"** in the sidebar
2. Commit the downloaded `baskets.json` to your repo
3. In `app.py`, change the `DEFAULT_BASKETS` loader to read from the file:

```python
import json, os

def load_default_baskets():
    if os.path.exists("baskets.json"):
        with open("baskets.json") as f:
            return json.load(f)
    return DEFAULT_BASKETS

# Then in session state init:
if "baskets" not in st.session_state:
    st.session_state.baskets = load_default_baskets()
```

Commit that change and your baskets will be pre-loaded on every new session.

---

## Features

| Feature | Details |
|---|---|
| **Live data** | yfinance pulls 2 years of adjusted daily closes, cached 5 min |
| **Basket cards** | Raw % returns (5d / 20d) per basket |
| **Overview tab** | Per-stock table with raw % + z-scores + signal (ACCEL / FADE / NEUTRAL) |
| **Rotation Map** | Z-scored scatter plot — 5d z (Y) vs 20d z (X), quadrant analysis |
| **Momentum Ranks** | Top/bottom 5 stocks by z-score across all baskets |
| **Z-score windows** | 63d / 126d / 252d / 504d (quarter / semi / annual / biennial) |
| **Basket management** | Create, rename, recolor, edit tickers, delete — all in sidebar |
| **Config export/import** | Download/upload `baskets.json` to persist across sessions |

---

## Local development (optional)

If you want to run it locally:

```bash
pip install streamlit yfinance pandas numpy plotly
streamlit run app.py
```
