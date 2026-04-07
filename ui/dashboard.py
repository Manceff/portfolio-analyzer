"""Dashboard — layout principal avec navigation par onglets."""

import streamlit as st
import pandas as pd

from core.portfolio import Portfolio
from core import metrics
from core.contribution import performance_contribution, risk_contribution
from core.export import generate_excel
from core.export_pptx import generate_pptx
from ui import charts


def _render_performance(ptf_prices, bench_aligned):
    """Onglet 1 : Création de valeur."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        ptf_cum = metrics.cumulative_return(ptf_prices)
        bench_cum = metrics.cumulative_return(bench_aligned)
        st.metric("Rendement cumulé", f"{ptf_cum:.2%}",
                  delta=f"Bench : {bench_cum:.2%}", delta_color="off")
    with col2:
        ptf_cagr = metrics.annualized_return(ptf_prices)
        bench_cagr = metrics.annualized_return(bench_aligned)
        st.metric("CAGR", f"{ptf_cagr:.2%}",
                  delta=f"Bench : {bench_cagr:.2%}", delta_color="off")
    with col3:
        alpha = metrics.geometric_alpha(ptf_prices, bench_aligned)
        st.metric("Alpha géométrique", f"{alpha:.2%}")
    with col4:
        b = metrics.beta(ptf_prices, bench_aligned)
        st.metric("Bêta", f"{b:.2f}")

    st.plotly_chart(
        charts.chart_cumulative_performance(ptf_prices, bench_aligned),
        use_container_width=True,
    )


def _render_risk_tab(ptf_prices, bench_aligned, kupiec_95, kupiec_99):
    """Onglet 2 : Mesure du risque."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        vol_ptf = metrics.annualized_volatility(ptf_prices)
        vol_bench = metrics.annualized_volatility(bench_aligned)
        st.metric("Volatilité ann.", f"{vol_ptf:.2%}",
                  delta=f"Bench : {vol_bench:.2%}", delta_color="off")
    with col2:
        mdd_ptf = metrics.max_drawdown(ptf_prices)
        mdd_bench = metrics.max_drawdown(bench_aligned)
        st.metric("Max Drawdown", f"{mdd_ptf:.2%}",
                  delta=f"Bench : {mdd_bench:.2%}", delta_color="off")
    with col3:
        dd_dur = metrics.max_drawdown_duration(ptf_prices)
        st.metric("Durée drawdown max", f"{dd_dur} j")
    with col4:
        te = metrics.tracking_error(ptf_prices, bench_aligned)
        st.metric("Tracking Error", f"{te:.2%}")

    st.plotly_chart(
        charts.chart_drawdown(ptf_prices, bench_aligned),
        use_container_width=True,
    )

    st.markdown("---")
    st.markdown("##### Value at Risk (horizon 1 jour)")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("VaR 95%", f"{metrics.var_95(ptf_prices):.2%}")
    with col2:
        st.metric("CVaR 95%", f"{metrics.cvar_95(ptf_prices):.2%}")
    with col3:
        st.metric("VaR 99%", f"{metrics.var_99(ptf_prices):.2%}")
    with col4:
        st.metric("CVaR 99%", f"{metrics.cvar_99(ptf_prices):.2%}")

    st.markdown("##### Backtesting de Kupiec (POF) — rolling 504j")
    st.caption(
        "VaR estimée sur fenêtre glissante de 504 jours (standard Bâle III), "
        "violations comptées hors échantillon. H0 : modèle correct. p < 5% = **rejeté**."
    )

    bt_data = {
        "Niveau": ["VaR 95%", "VaR 99%"],
        "Seuil VaR": [f"{kupiec_95['var_last']:.2%}", f"{kupiec_99['var_last']:.2%}"],
        "Violations att.": [
            f"{kupiec_95['expected_rate']:.1%} ({int(kupiec_95['n_obs'] * kupiec_95['expected_rate'])})",
            f"{kupiec_99['expected_rate']:.1%} ({int(kupiec_99['n_obs'] * kupiec_99['expected_rate'])})",
        ],
        "Violations obs.": [
            f"{kupiec_95['observed_rate']:.1%} ({kupiec_95['n_violations']})",
            f"{kupiec_99['observed_rate']:.1%} ({kupiec_99['n_violations']})",
        ],
        "LR (chi²)": [f"{kupiec_95['lr_statistic']:.3f}", f"{kupiec_99['lr_statistic']:.3f}"],
        "p-value": [f"{kupiec_95['p_value']:.4f}", f"{kupiec_99['p_value']:.4f}"],
        "Verdict": [
            "Adéquat" if kupiec_95["model_adequate"] else "REJETÉ",
            "Adéquat" if kupiec_99["model_adequate"] else "REJETÉ",
        ],
    }
    st.dataframe(pd.DataFrame(bt_data).set_index("Niveau"), use_container_width=True)

    for label, result in [("VaR 95%", kupiec_95), ("VaR 99%", kupiec_99)]:
        if not result["model_adequate"]:
            st.warning(
                f"**{label} rejeté** (p = {result['p_value']:.4f}). "
                f"Violations : {result['observed_rate']:.1%} vs {result['expected_rate']:.1%} attendues."
            )

    st.plotly_chart(
        charts.chart_return_distribution(ptf_prices, bench_aligned),
        use_container_width=True,
    )


def _render_garch_tab(ptf_prices, bench_aligned,
                      garch_ptf, garch_bench, gjr_ptf, gjr_bench):
    """Onglet 3 : GARCH(1,1) & GJR-GARCH."""

    # --- GARCH(1,1) ---
    st.markdown("##### GARCH(1,1)")
    st.caption(
        "Volatilité conditionnelle (Bollerslev, 1986). "
        "Prévisions en vol **daily** — moyenne des variances multi-step sur l'horizon."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("α (réaction)", f"{garch_ptf['alpha']:.4f}")
    with col2:
        st.metric("β (persistance)", f"{garch_ptf['beta']:.4f}")
    with col3:
        persistence = garch_ptf["persistence"]
        st.metric("α + β", f"{persistence:.4f}")
    with col4:
        if not pd.isna(garch_ptf["long_run_vol"]):
            st.metric("Vol long terme (ann.)", f"{garch_ptf['long_run_vol']:.2%}")
        else:
            st.metric("Vol long terme", "N/A (IGARCH)")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Vol daily J+1", f"{garch_ptf['forecast_vol_1d']:.3%}")
    with col2:
        st.metric("Vol daily J+5 (moy.)", f"{garch_ptf['forecast_vol_5d']:.3%}")
    with col3:
        st.metric("Vol daily J+10 (moy.)", f"{garch_ptf['forecast_vol_10d']:.3%}")

    st.plotly_chart(
        charts.chart_garch_volatility(garch_ptf, garch_bench),
        use_container_width=True,
    )

    # --- GJR-GARCH ---
    st.markdown("---")
    st.markdown("##### GJR-GARCH(1,1)")
    st.caption(
        "Glosten-Jagannathan-Runkle (1993). Capture l'effet de levier : "
        "un choc négatif augmente davantage la volatilité qu'un choc positif "
        "de même amplitude. Le coefficient γ mesure cette asymétrie."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("α (réaction)", f"{gjr_ptf['alpha']:.4f}")
    with col2:
        st.metric("γ (levier)", f"{gjr_ptf['gamma']:.4f}")
    with col3:
        st.metric("β (persistance)", f"{gjr_ptf['beta']:.4f}")
    with col4:
        gjr_pers = gjr_ptf["persistence"]
        st.metric("α + β + γ/2", f"{gjr_pers:.4f}")

    if gjr_ptf["leverage_effect"]:
        st.success(
            f"**Effet de levier confirmé** (γ = {gjr_ptf['gamma']:.4f} > 0). "
            "Les baisses amplifient la volatilité plus que les hausses. "
            "GJR-GARCH est plus pertinent que GARCH(1,1) pour ce portefeuille."
        )
    else:
        st.info(
            f"Pas d'effet de levier détecté (γ = {gjr_ptf['gamma']:.4f} ≤ 0). "
            "GARCH(1,1) symétrique suffit."
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Vol daily J+1 (GJR)", f"{gjr_ptf['forecast_vol_1d']:.3%}")
    with col2:
        st.metric("Vol daily J+5 (GJR)", f"{gjr_ptf['forecast_vol_5d']:.3%}")
    with col3:
        st.metric("Vol daily J+10 (GJR)", f"{gjr_ptf['forecast_vol_10d']:.3%}")

    st.plotly_chart(
        charts.chart_gjr_garch_volatility(gjr_ptf, gjr_bench),
        use_container_width=True,
    )

    # Comparison table
    st.markdown("##### Comparaison GARCH vs GJR-GARCH (daily)")
    comp = {
        "": ["Persistance", "Vol long terme (ann.)",
             "Vol J+1", "Vol J+5", "Vol J+10"],
        "GARCH(1,1)": [
            f"{garch_ptf['persistence']:.4f}",
            f"{garch_ptf['long_run_vol']:.2%}" if not pd.isna(garch_ptf["long_run_vol"]) else "N/A",
            f"{garch_ptf['forecast_vol_1d']:.3%}",
            f"{garch_ptf['forecast_vol_5d']:.3%}",
            f"{garch_ptf['forecast_vol_10d']:.3%}",
        ],
        "GJR-GARCH": [
            f"{gjr_ptf['persistence']:.4f}",
            f"{gjr_ptf['long_run_vol']:.2%}" if not pd.isna(gjr_ptf["long_run_vol"]) else "N/A",
            f"{gjr_ptf['forecast_vol_1d']:.3%}",
            f"{gjr_ptf['forecast_vol_5d']:.3%}",
            f"{gjr_ptf['forecast_vol_10d']:.3%}",
        ],
    }
    st.dataframe(pd.DataFrame(comp).set_index(""), use_container_width=True)


def _render_regimes_tab(ptf_prices, bench_aligned, ms_ptf, ms_bench):
    """Onglet 4 : Détection de régime — Markov Switching."""
    st.caption(
        "Modèle de Markov à 2 régimes (Hamilton, 1989). Chaque régime a sa propre "
        "moyenne et variance. Le régime « stress » est celui avec la volatilité la plus élevée."
    )

    # Current regime probability
    current_p = ms_ptf["current_regime_proba"]
    if current_p >= 0.7:
        regime_label = "STRESS"
        regime_color = "red"
    elif current_p <= 0.3:
        regime_label = "CALME"
        regime_color = "green"
    else:
        regime_label = "TRANSITION"
        regime_color = "orange"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("P(stress) aujourd'hui", f"{current_p:.1%}")
    with col2:
        st.metric("Régime actuel", regime_label)
    with col3:
        bench_p = ms_bench["current_regime_proba"]
        st.metric("P(stress) benchmark", f"{bench_p:.1%}")

    # Regime characteristics
    st.markdown("##### Caractéristiques des régimes")
    calm = ms_ptf["regimes"]["calme"]
    stress = ms_ptf["regimes"]["stress"]

    regime_data = {
        "Régime": ["Calme", "Stress"],
        "Rendement ann.": [f"{calm['mean_ann']:.2%}", f"{stress['mean_ann']:.2%}"],
        "Volatilité ann.": [f"{calm['vol_ann']:.2%}", f"{stress['vol_ann']:.2%}"],
        "Durée moyenne (j)": [
            f"{ms_ptf['expected_duration_calm']:.0f}",
            f"{ms_ptf['expected_duration_stress']:.0f}",
        ],
    }
    st.dataframe(pd.DataFrame(regime_data).set_index("Régime"), use_container_width=True)

    # Transition matrix
    st.markdown("##### Matrice de transition")
    st.caption("P(passer du régime ligne au régime colonne) en un jour.")
    trans = ms_ptf["transition_matrix"]
    stress_idx = ms_ptf["stress_regime"]
    calm_idx = 1 - stress_idx
    trans_df = pd.DataFrame(
        [[trans[calm_idx][calm_idx], trans[calm_idx][stress_idx]],
         [trans[stress_idx][calm_idx], trans[stress_idx][stress_idx]]],
        index=["Calme", "Stress"],
        columns=["→ Calme", "→ Stress"],
    )
    st.dataframe(
        trans_df.style.format("{:.4f}"),
        use_container_width=True,
    )

    # Chart
    st.plotly_chart(
        charts.chart_regime_probabilities(ms_ptf, ptf_prices),
        use_container_width=True,
    )

    # Interpretation
    st.markdown("##### Interprétation")
    dur_calm = ms_ptf["expected_duration_calm"]
    dur_stress = ms_ptf["expected_duration_stress"]
    vol_ratio = stress["vol_ann"] / calm["vol_ann"] if calm["vol_ann"] > 0 else 0

    st.markdown(
        f"- En régime **calme**, la volatilité est de **{calm['vol_ann']:.1%}** "
        f"avec un rendement annualisé de **{calm['mean_ann']:.1%}**. "
        f"Durée moyenne : **{dur_calm:.0f} jours**.\n"
        f"- En régime **stress**, la volatilité monte à **{stress['vol_ann']:.1%}** "
        f"(**×{vol_ratio:.1f}**) avec un rendement de **{stress['mean_ann']:.1%}**. "
        f"Durée moyenne : **{dur_stress:.0f} jours**.\n"
        f"- La probabilité actuelle d'être en régime stress est de **{current_p:.1%}**."
    )


def _render_ratios(ptf_prices, bench_aligned, risk_free_rate, rf_series):
    """Onglet 5 : Ratios ajustés du risque."""
    st.caption(f"Sharpe et Sortino calculés avec Rf actuel = {risk_free_rate:.2%}")

    ratios_data = {
        "Ratio": ["Sharpe", "Sortino", "Information Ratio", "Calmar"],
        "Portefeuille": [
            f"{metrics.sharpe_ratio(ptf_prices, risk_free_rate):.2f}",
            f"{metrics.sortino_ratio(ptf_prices, risk_free_rate):.2f}",
            f"{metrics.information_ratio(ptf_prices, bench_aligned):.2f}",
            f"{metrics.calmar_ratio(ptf_prices):.2f}",
        ],
        "Benchmark": [
            f"{metrics.sharpe_ratio(bench_aligned, risk_free_rate):.2f}",
            f"{metrics.sortino_ratio(bench_aligned, risk_free_rate):.2f}",
            "—",
            f"{metrics.calmar_ratio(bench_aligned):.2f}",
        ],
    }

    st.dataframe(
        pd.DataFrame(ratios_data).set_index("Ratio"),
        use_container_width=True,
    )

    # Rolling Sharpe uses time-varying Rf if available
    rf_for_rolling = rf_series if rf_series is not None else risk_free_rate
    st.plotly_chart(
        charts.chart_rolling_sharpe(ptf_prices, bench_aligned, rf_for_rolling),
        use_container_width=True,
    )
    if rf_series is not None:
        st.caption("Rolling Sharpe calculé avec Rf time-varying (taux du jour à chaque point).")


def _render_contribution(portfolio):
    """Onglet 5 : Analyse de contribution."""
    col_left, col_right = st.columns(2)
    with col_left:
        st.plotly_chart(
            charts.chart_performance_contribution(portfolio),
            use_container_width=True,
        )
    with col_right:
        st.plotly_chart(
            charts.chart_risk_contribution(portfolio),
            use_container_width=True,
        )

    st.plotly_chart(
        charts.chart_correlation_heatmap(portfolio),
        use_container_width=True,
    )


def render_dashboard(portfolio: Portfolio, bench_prices: pd.Series,
                     risk_free_rate: float, rf_series=None, rf_desc: str = ""):
    """Rendu du dashboard complet avec onglets."""
    ptf_prices = portfolio.cumulative_prices

    common_idx = ptf_prices.index.intersection(bench_prices.index)
    ptf_prices = ptf_prices.loc[common_idx]
    bench_aligned = bench_prices.loc[common_idx]

    # Barre de synthèse
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Rendement", f"{metrics.cumulative_return(ptf_prices):.2%}")
        c2.metric("Volatilité", f"{metrics.annualized_volatility(ptf_prices):.2%}")
        c3.metric("Max DD", f"{metrics.max_drawdown(ptf_prices):.2%}")
        c4.metric("Sharpe", f"{metrics.sharpe_ratio(ptf_prices, risk_free_rate):.2f}")
        c5.metric("Alpha", f"{metrics.geometric_alpha(ptf_prices, bench_aligned):.2%}")

    # Onglets
    tabs = st.tabs([
        "Performance",
        "Risque & VaR",
        "GARCH & GJR",
        "Régimes de marché",
        "Ratios ajustés",
        "Contribution",
        "Export",
    ])
    tab_perf, tab_risk, tab_garch, tab_regimes, tab_ratios, tab_contrib, tab_export = tabs

    # Pré-calcul des modèles lourds (partagés entre onglets)
    with st.spinner("Estimation des modèles (GARCH, GJR, Markov Switching)..."):
        garch_ptf = metrics.fit_garch(ptf_prices)
        garch_bench = metrics.fit_garch(bench_aligned)
        gjr_ptf = metrics.fit_gjr_garch(ptf_prices)
        gjr_bench = metrics.fit_gjr_garch(bench_aligned)
        ms_ptf = metrics.fit_markov_switching(ptf_prices)
        ms_bench = metrics.fit_markov_switching(bench_aligned)
    kupiec_95 = metrics.kupiec_backtest(ptf_prices, 0.95)
    kupiec_99 = metrics.kupiec_backtest(ptf_prices, 0.99)

    with tab_perf:
        _render_performance(ptf_prices, bench_aligned)

    with tab_risk:
        _render_risk_tab(ptf_prices, bench_aligned, kupiec_95, kupiec_99)

    with tab_garch:
        _render_garch_tab(ptf_prices, bench_aligned,
                          garch_ptf, garch_bench, gjr_ptf, gjr_bench)

    with tab_regimes:
        _render_regimes_tab(ptf_prices, bench_aligned, ms_ptf, ms_bench)

    with tab_ratios:
        _render_ratios(ptf_prices, bench_aligned, risk_free_rate, rf_series)

    with tab_contrib:
        _render_contribution(portfolio)

    with tab_export:
        col_xl, col_pptx = st.columns(2)

        with col_xl:
            st.markdown("##### Rapport Excel")
            st.caption(
                "8 onglets avec données, métriques et graphiques natifs Excel."
            )
            excel_bytes = generate_excel(
                portfolio, bench_aligned, risk_free_rate,
                garch_ptf, garch_bench, kupiec_95, kupiec_99,
                ms_ptf,
            )
            st.download_button(
                label="Télécharger Excel (.xlsx)",
                data=excel_bytes,
                file_name="portfolio_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )

        with col_pptx:
            st.markdown("##### Rapport PowerPoint")
            st.caption(
                "9 slides : Performance, Drawdown, VaR, GARCH, Régimes, Ratios, Contribution, Corrélation."
            )
            try:
                pptx_bytes = generate_pptx(
                    portfolio, bench_aligned, risk_free_rate,
                    rf_series, rf_desc,
                    garch_ptf, garch_bench, gjr_ptf,
                    kupiec_95, kupiec_99, ms_ptf,
                )
                st.download_button(
                    label="Télécharger PowerPoint (.pptx)",
                    data=pptx_bytes,
                    file_name="portfolio_report.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    type="primary",
                )
            except Exception:
                st.info(
                    "L'export PowerPoint nécessite kaleido (rendu d'images). "
                    "Non disponible sur Streamlit Cloud — disponible en exécution locale."
                )

    # ── Méthodologie détaillée en bas de page ──
    st.divider()
    with st.container(border=True):
        st.markdown("##### Méthodologie")
        st.caption("Description détaillée des choix méthodologiques, sources de données et modèles utilisés.")

        st.markdown("---")

        # 1. Données
        st.markdown("**1. Données de marché**")
        st.markdown(
            "Les prix de clôture ajustés (dividendes réinvestis, splits corrigés) sont téléchargés "
            "via l'API Yahoo Finance. Les données manquantes sont comblées par forward-fill. "
            "Les rendements quotidiens sont calculés en rendements arithmétiques simples : "
            "`r(t) = P(t) / P(t-1) - 1`. Le portefeuille est construit par pondération linéaire "
            "des rendements quotidiens de chaque actif (rééquilibrage quotidien implicite vers les poids cibles)."
        )

        st.markdown("---")

        # 2. Taux sans risque
        st.markdown("**2. Taux sans risque**")
        if "US Treasury" in rf_desc:
            st.markdown(
                f"**Source : {rf_desc}**\n\n"
                "Téléchargé via Yahoo Finance (tickers `^IRX` pour le 3 mois, `^FVX` pour le 5 ans, "
                "`^TNX` pour le 10 ans). Le Rf utilisé pour le **Sharpe** et le **Sortino** est le "
                "**dernier taux disponible** (taux actuel), conformément à la pratique de calcul du Sharpe "
                "à date. Le **Rolling Sharpe** utilise le **taux du jour correspondant** à chaque point "
                "(Rf time-varying), ce qui reflète fidèlement le coût d'opportunité du cash à chaque instant."
            )
        elif "EUR" in rf_desc:
            st.markdown(
                f"**Source : {rf_desc}**\n\n"
                "Téléchargé via l'**API publique de la BCE** (ECB Statistical Data Warehouse). "
                "Il s'agit de la courbe des taux zéro-coupon des obligations souveraines de la zone euro "
                "notées AAA, estimée par le modèle de Svensson. "
                "Dataset : `YC.B.U2.EUR.4F.G_N_A.SV_C_YM`. "
                "Données quotidiennes exactes (pas d'approximation). "
                "Le Sharpe et le Sortino utilisent le dernier taux disponible. "
                "Le Rolling Sharpe utilise le taux du jour à chaque point."
            )
        else:
            st.markdown(
                f"**Source : {rf_desc}**\n\n"
                "Taux fixe défini manuellement par l'utilisateur. "
                "Appliqué uniformément sur toute la période d'analyse."
            )

        st.markdown("---")

        # 3. Métriques de performance
        st.markdown("**3. Métriques de performance**")
        st.markdown(
            "- **Rendement cumulé** : `(P_final / P_initial) - 1`\n"
            "- **CAGR** (rendement annualisé) : `(1 + R_cum)^(252/n_jours) - 1`, "
            "où 252 est le nombre conventionnel de jours de trading par an\n"
            "- **Alpha géométrique** : `(1 + R_ptf) / (1 + R_bench) - 1` — "
            "mesure la surperformance composée du portefeuille par rapport au benchmark\n"
            "- **Bêta** : `Cov(R_ptf, R_bench) / Var(R_bench)` — "
            "sensibilité du portefeuille aux mouvements du marché"
        )

        st.markdown("---")

        # 4. Métriques de risque
        st.markdown("**4. Métriques de risque**")
        st.markdown(
            "- **Volatilité annualisée** : écart-type des rendements quotidiens × √252 "
            "(écart-type échantillon, ddof=1)\n"
            "- **Maximum Drawdown** : pire perte entre un plus haut et le point le plus bas qui suit. "
            "Formule : `min((P - cummax(P)) / cummax(P))`\n"
            "- **Durée du drawdown max** : nombre de jours de trading passés sous le plus haut historique "
            "dans la plus longue période de perte\n"
            "- **Tracking Error** : écart-type annualisé de la différence des rendements quotidiens "
            "portefeuille vs benchmark"
        )

        st.markdown("---")

        # 5. Value at Risk
        st.markdown("**5. Value at Risk & Backtesting**")
        st.markdown(
            "- **VaR historique** (horizon 1 jour) : percentile empirique des rendements quotidiens. "
            "VaR 95% = percentile 5%, VaR 99% = percentile 1%\n"
            "- **CVaR (Expected Shortfall)** : moyenne des rendements au-delà du seuil VaR. "
            "Plus conservatrice que la VaR, elle mesure la perte moyenne dans les pires scénarios\n"
            "- **Backtesting de Kupiec** (Proportion of Failures, 1995) : "
            "pour chaque jour t, la VaR est estimée sur une **fenêtre glissante de 504 jours** "
            "(2 ans, standard Bâle III) et la violation est vérifiée hors échantillon au jour t. "
            "Le test du rapport de vraisemblance (chi², 1 ddl) compare le taux de violations observé "
            "au taux théorique. H0 = modèle correctement spécifié. "
            "**p < 5% → modèle rejeté** (le modèle sous-estime ou surestime le risque)"
        )

        st.markdown("---")

        # 6. Ratios ajustés
        st.markdown("**6. Ratios ajustés du risque**")
        st.markdown(
            "- **Sharpe** : `(R_ann - Rf) / σ_ann` — rendement excédentaire par unité de risque total. "
            "Au-dessus de 1 = bon, au-dessus de 1.5 = très bon\n"
            "- **Sortino** (Sortino & Price, 1994) : `(R_ann - Rf) / DD` où DD = downside deviation. "
            "La DD est calculée comme `√(moyenne des min(r_i - rf_daily, 0)²)` sur **toutes** les observations "
            "(les jours positifs contribuent 0 au numérateur mais comptent dans le dénominateur). "
            "Ne pénalise que la volatilité baissière\n"
            "- **Information Ratio** : `Alpha_géométrique / Tracking_Error` — "
            "Sharpe de la surperformance active\n"
            "- **Calmar** : `CAGR / |Max_Drawdown|` — rendement par unité de pire perte"
        )

        st.markdown("---")

        # 7. GARCH
        st.markdown("**7. Modèles de volatilité conditionnelle**")
        st.markdown(
            "- **GARCH(1,1)** (Bollerslev, 1986) : `σ²(t) = ω + α·ε²(t-1) + β·σ²(t-1)`. "
            "Capture le *volatility clustering* (les périodes de forte volatilité se regroupent). "
            "Persistance = α + β. Si < 1, la variance revient vers sa moyenne de long terme\n"
            "- **GJR-GARCH(1,1)** (Glosten-Jagannathan-Runkle, 1993) : "
            "`σ²(t) = ω + α·ε²(t-1) + γ·ε²(t-1)·I(ε<0) + β·σ²(t-1)`. "
            "Le coefficient γ capture l'**effet de levier** : un choc négatif augmente la volatilité "
            "plus qu'un choc positif de même amplitude. Si γ > 0, l'effet de levier est confirmé "
            "et GJR-GARCH est plus pertinent que GARCH symétrique\n"
            "- **Prévisions** : volatilité conditionnelle **quotidienne** (pas d'annualisation, "
            "qui serait incohérente avec la nature time-varying du modèle). "
            "Les prévisions J+5 et J+10 sont la moyenne des variances multi-step "
            "(propagation récursive de σ², pas d'approximation √T)\n"
            "- **Estimation** : via la librairie `arch`, maximum de vraisemblance, "
            "distribution normale, moyenne constante"
        )

        st.markdown("---")

        # 8. Markov Switching
        st.markdown("**8. Détection de régime — Markov Switching**")
        st.markdown(
            "Modèle à 2 régimes de Markov (Hamilton, 1989). Chaque régime possède sa propre "
            "moyenne et variance de rendements. Le régime **stress** est identifié automatiquement "
            "comme celui ayant la variance la plus élevée.\n\n"
            "- **Matrice de transition** : probabilité de passer d'un régime à l'autre en 1 jour\n"
            "- **Durée espérée** d'un régime : `1 / (1 - p_ii)` où `p_ii` est la probabilité "
            "de rester dans le même régime (distribution géométrique)\n"
            "- **Probabilité filtrée** : P(être en régime stress au jour t | information jusqu'à t)\n"
            "- **Probabilité lissée** : idem mais en utilisant toute l'information de l'échantillon\n"
            "- **Estimation** : via `statsmodels.MarkovRegression`, maximum de vraisemblance"
        )

        st.markdown("---")

        # 9. Contribution
        st.markdown("**9. Analyse de contribution**")
        st.markdown(
            "- **Contribution à la performance** : `poids_i × rendement_cumulé_i` pour chaque actif. "
            "La somme des contributions approxime le rendement total du portefeuille "
            "(attribution buy-and-hold)\n"
            "- **Contribution au risque** (décomposition d'Euler) : "
            "`RC_i = w_i × (Σ·w)_i / σ_ptf` où Σ est la matrice de covariance annualisée. "
            "Propriété : la somme des RC_i = volatilité du portefeuille. "
            "Un actif peut peser 10% du portefeuille mais représenter 40% du risque\n"
            "- **Matrice de corrélation** : corrélations des rendements quotidiens entre actifs. "
            "Corrélation > 0.8 = risque de concentration (colorée en rouge), "
            "< 0.3 = diversification effective (colorée en vert)"
        )

        st.markdown("---")

        st.caption("Projet initié par Ferrah Mancef — Analyse quantitative de portefeuille.")
