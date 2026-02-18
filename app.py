# ── CORRELATION TAB ────────────────────────────────────────────────────────────
def plot_heatmap(corr_df: pd.DataFrame, title: str):
    """Generates a styled Plotly heatmap for correlations."""
    # Mask the upper triangle (optional, but cleaner for symmetric matrices)
    mask = np.triu(np.ones_like(corr_df, dtype=bool), k=1)
    
    # Custom text for the cells (only show 2 decimal places)
    text = np.around(corr_df.values, 2).astype(str)
    
    # Create Heatmap
    fig = go.Figure(data=go.Heatmap(
        z=corr_df.values,
        x=corr_df.columns,
        y=corr_df.index,
        text=text,
        texttemplate="%{text}",
        textfont={"size": 10, "color": "#e2e8f0"},
        colorscale="RdBu",  # Red (neg) to Blue (pos)
        zmin=-1, zmax=1,
        showscale=False,
        xgap=1, ygap=1,
    ))

    layout = dict(**PLOTLY_LAYOUT)
    layout.update(
        title=dict(text=title, font=dict(color="#e2e8f0", size=14)),
        height=500 + (len(corr_df) * 15), # dynamic height
        xaxis=dict(**PLOTLY_LAYOUT["xaxis"], side="bottom"),
        yaxis=dict(**PLOTLY_LAYOUT["yaxis"], autorange="reversed"), # Top-to-bottom
    )
    fig.update_layout(**layout)
    return fig

def render_correlations(prices_df: pd.DataFrame, baskets: dict):
    sel = st.session_state.selected_basket
    
    # Calculate daily returns for all stocks
    returns_df = prices_df.pct_change().dropna()
    
    # ── 1. CROSS-BASKET CORRELATION ──
    # Construct a dataframe of Basket Returns (Equal-Weighted)
    basket_returns = {}
    for name, cfg in baskets.items():
        tickers = [t for t in cfg["tickers"] if t in returns_df.columns]
        if tickers:
            # Mean return of the constituents for that day
            basket_returns[name] = returns_df[tickers].mean(axis=1)
    
    basket_ret_df = pd.DataFrame(basket_returns)
    
    if basket_ret_df.empty:
        st.info("Insufficient data for correlation analysis.")
        return

    # Lookback window slider
    col_ctrl, _ = st.columns([2, 3])
    with col_ctrl:
        lookback = st.select_slider(
            "Correlation Lookback",
            options=[20, 60, 120, 252],
            value=60,
            format_func=lambda x: f"{x} Days"
        )

    # Filter for the lookback window
    recent_basket_ret = basket_ret_df.tail(lookback)
    basket_corr = recent_basket_ret.corr()

    # ── 2. WITHIN-BASKET CORRELATION ──
    # Get constituents of the currently selected basket
    sel_tickers = [t for t in baskets[sel]["tickers"] if t in returns_df.columns]
    
    if len(sel_tickers) < 2:
        st.warning(f"Need at least 2 tickers in '{sel}' to calculate correlations.")
        stock_corr = pd.DataFrame()
    else:
        recent_stock_ret = returns_df[sel_tickers].tail(lookback)
        stock_corr = recent_stock_ret.corr()

    # ── RENDER ──
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f'<div style="font-size:12px;font-weight:700;color:#94a3b8;margin-bottom:8px">THEME CORRELATIONS ({lookback}d)</div>', unsafe_allow_html=True)
        if not basket_corr.empty:
            fig_b = plot_heatmap(basket_corr, "Cross-Basket Matrix")
            st.plotly_chart(fig_b, use_container_width=True)
            
    with col2:
        st.markdown(f'<div style="font-size:12px;font-weight:700;color:#94a3b8;margin-bottom:8px">{sel.upper()} CONSTITUENTS ({lookback}d)</div>', unsafe_allow_html=True)
        if not stock_corr.empty:
            fig_s = plot_heatmap(stock_corr, "Constituent Matrix")
            st.plotly_chart(fig_s, use_container_width=True)
            
    # Insight block
    st.markdown("""
    <div class="info-box">
        <strong style="color:#f59e0b">Interpret this:</strong> High correlation (>0.8) implies the basket trades as a single macro factor. 
        Low or negative correlation between baskets suggests true diversification benefits.
    </div>
    """, unsafe_allow_html=True)
