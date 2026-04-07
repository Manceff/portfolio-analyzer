"""Sidebar — configuration du portefeuille."""

from datetime import date, timedelta

import streamlit as st


def render_sidebar() -> dict:
    """Affiche la sidebar et retourne la configuration."""

    st.sidebar.markdown("**Portefeuille**")

    tickers_input = st.sidebar.text_input(
        "Tickers",
        value="AAPL, MSFT, VTI, BND",
        help="Yahoo Finance — séparés par des virgules",
    )
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

    equal_w = round(100 / len(tickers), 2) if tickers else 0
    weights_input = st.sidebar.text_input(
        "Poids (%)",
        value=", ".join([str(equal_w)] * len(tickers)),
    )
    try:
        weights_raw = [float(w.strip()) for w in weights_input.split(",") if w.strip()]
    except ValueError:
        weights_raw = [100 / len(tickers)] * len(tickers)

    if len(weights_raw) != len(tickers):
        st.sidebar.warning("Nombre de poids ≠ tickers. Équipondération appliquée.")
        weights_raw = [100 / len(tickers)] * len(tickers)

    weights_sum = sum(weights_raw)
    if abs(weights_sum - 100) > 0.5:
        st.sidebar.caption(f"Somme = {weights_sum:.0f}% — normalisé à 100%.")
        weights_raw = [w / weights_sum * 100 for w in weights_raw]

    weights = {t: w / 100.0 for t, w in zip(tickers, weights_raw)}

    st.sidebar.divider()
    st.sidebar.markdown("**Benchmark & Période**")

    benchmark = st.sidebar.text_input(
        "Benchmark",
        value="SPY",
        help="SPY, ACWI, QQQ...",
    ).strip().upper()

    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input(
        "Début",
        value=date(2020, 1, 1),
        max_value=date.today() - timedelta(days=30),
    )
    end_date = col2.date_input(
        "Fin",
        value=date.today(),
        min_value=start_date + timedelta(days=30),
    )

    st.sidebar.divider()
    st.sidebar.markdown("**Taux sans risque**")
    st.sidebar.caption("Utilisé pour le Sharpe, Sortino et Rolling Sharpe.")

    rf_mode = st.sidebar.radio(
        "Zone",
        ["USD (US Treasury)", "EUR (API BCE)", "Fixe"],
        index=0,
        label_visibility="collapsed",
    )

    rf_config = {"mode": rf_mode}

    if rf_mode == "USD (US Treasury)":
        maturity = st.sidebar.selectbox(
            "Maturité",
            ["3 mois", "5 ans", "10 ans"],
            index=2,
            help="10 ans recommandé pour un horizon de placement > 3 ans",
        )
        rf_config["maturity"] = maturity

    elif rf_mode == "EUR (API BCE)":
        maturity = st.sidebar.selectbox(
            "Maturité",
            ["1 an (AAA spot)", "5 ans (AAA spot)", "10 ans (AAA spot)"],
            index=2,
            help="Courbe des taux zéro-coupon AAA (Svensson) — source BCE",
        )
        rf_config["maturity"] = maturity

    else:
        risk_free_rate = st.sidebar.number_input(
            "Rf annuel (%)",
            min_value=0.0, max_value=15.0,
            value=3.5, step=0.25,
        ) / 100.0
        rf_config["fixed_rate"] = risk_free_rate

    return {
        "tickers": tickers,
        "weights": weights,
        "benchmark": benchmark,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "rf_config": rf_config,
    }
