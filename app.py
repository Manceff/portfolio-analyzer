"""Portfolio Analyzer — Point d'entrée Streamlit."""

import streamlit as st

st.set_page_config(
    page_title="Portfolio Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        border-right: 3px solid #2E75B6;
    }
    div[data-testid="stMetric"] {
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-radius: 8px;
        padding: 0.8rem 1rem;
        border-left: 3px solid #2E75B6;
    }
    div[data-testid="stMetric"] label {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        opacity: 0.7;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-weight: 700 !important;
        font-size: 1.3rem !important;
    }
    button[data-baseweb="tab"] {
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }
    .stDownloadButton button {
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    .stPlotlyChart {
        border-radius: 8px;
        overflow: hidden;
    }
    .stDataFrame {
        border-radius: 6px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

from core.data_loader import (
    fetch_prices, fetch_benchmark, fetch_us_risk_free, fetch_eur_risk_free,
)
from core.portfolio import Portfolio
from ui.sidebar import render_sidebar
from ui.dashboard import render_dashboard


def _resolve_risk_free(rf_config: dict, start: str, end: str) -> tuple[float, pd.Series | None, str]:
    """Resolve risk-free config into (current_rate, daily_series_or_None, description).

    - current_rate: dernier taux disponible (pour Sharpe métrique)
    - daily_series: série time-varying (pour Rolling Sharpe), None si fixe
    """
    mode = rf_config["mode"]

    if mode == "USD (US Treasury)":
        maturity = rf_config["maturity"]
        try:
            rf_series = fetch_us_risk_free(maturity, start, end)
            current = float(rf_series.iloc[-1])
            return current, rf_series, f"US Treasury {maturity} ({current:.2%} actuel)"
        except Exception:
            return 0.035, None, "US Treasury (fallback 3.5%)"

    elif mode == "EUR (API BCE)":
        maturity = rf_config["maturity"]
        try:
            rf_series = fetch_eur_risk_free(maturity, start, end)
            current = float(rf_series.iloc[-1])
            return current, rf_series, f"EUR {maturity} ({current:.2%} actuel)"
        except Exception:
            return 0.025, None, "EUR BCE (fallback 2.5%)"

    else:
        rate = rf_config["fixed_rate"]
        return rate, None, f"Fixe ({rate:.2%})"


def main():
    params = render_sidebar()

    st.markdown("### Analyse de portefeuille — Projet étudiant")
    st.caption(
        "Projet initié par Ferrah Mancef, proposant une analyse quantitative de portefeuille "
        "en vue de contribuer à la prise de décision, avec des options d'export vers Excel et PowerPoint."
    )

    if st.sidebar.button("Lancer l'analyse", type="primary", use_container_width=True):
        st.session_state["params"] = params
        st.session_state["run"] = True

    if not st.session_state.get("run"):
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            with st.container(border=True):
                st.markdown("**1. Configurez**")
                st.caption("Tickers, poids, benchmark et période dans le panneau latéral.")
        with col2:
            with st.container(border=True):
                st.markdown("**2. Analysez**")
                st.caption("Métriques de performance, risque, GARCH et VaR backtesting.")
        with col3:
            with st.container(border=True):
                st.markdown("**3. Exportez**")
                st.caption("Rapport Excel professionnel avec graphiques natifs.")

        st.markdown("")
        with st.container(border=True):
            st.markdown("**Piste d'évolution — Gestion dynamique des positions**")
            st.caption(
                "Dans sa version actuelle, l'outil analyse un portefeuille à allocation fixe. "
                "En contexte opérationnel d'asset management, l'étape suivante serait de permettre "
                "l'import d'un fichier CSV de positions datées (date, ticker, poids), afin d'analyser "
                "un portefeuille dont l'allocation a évolué dans le temps — reflétant les décisions "
                "réelles du gérant et permettant une attribution de performance dynamique (Brinson-Fachler)."
            )
        return

    params = st.session_state["params"]

    with st.spinner("Téléchargement des données de marché..."):
        try:
            prices = fetch_prices(
                params["tickers"],
                params["start_date"],
                params["end_date"],
            )
            bench_prices = fetch_benchmark(
                params["benchmark"],
                params["start_date"],
                params["end_date"],
            )
        except Exception as e:
            st.error(f"Erreur de téléchargement : {e}")
            return

    try:
        portfolio = Portfolio(prices, params["weights"])
    except ValueError as e:
        st.error(str(e))
        return

    risk_free_rate, rf_series, rf_desc = _resolve_risk_free(
        params["rf_config"], params["start_date"], params["end_date"],
    )
    st.sidebar.caption(f"Rf : {rf_desc}")

    render_dashboard(portfolio, bench_prices, risk_free_rate, rf_series, rf_desc)


if __name__ == "__main__":
    main()
