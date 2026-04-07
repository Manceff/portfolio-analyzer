"""Chart functions — all Plotly visualizations.

Transparent backgrounds, no hardcoded text colors — works with any Streamlit theme.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from core import metrics
from core.portfolio import Portfolio
from core.contribution import performance_contribution, risk_contribution

# High-contrast palette — readable on both light and dark
C_PTF = "#2E75B6"
C_BENCH = "#FF6B35"
C_POS = "#2ECC71"
C_NEG = "#E74C3C"
C_PURPLE = "#9B59B6"
C_TEAL = "#1ABC9C"
C_NEUTRAL = "#95A5A6"

ASSET_PALETTE = [
    "#2E75B6", "#FF6B35", "#2ECC71", "#E74C3C", "#9B59B6",
    "#1ABC9C", "#F1C40F", "#E91E63", "#3498DB", "#E67E22",
]

_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, -apple-system, sans-serif", size=12),
    margin=dict(l=50, r=20, t=70, b=40),
    hovermode="x unified",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="right", x=1),
)


def _layout(**kw):
    return {**_LAYOUT, **kw}


# ── 1. Performance cumulée ──────────────────────────────

def chart_cumulative_performance(ptf_prices, bench_prices):
    ptf = ptf_prices / ptf_prices.iloc[0] * 100
    bench = bench_prices / bench_prices.iloc[0] * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ptf.index, y=ptf.values, name="Portefeuille",
                             line=dict(color=C_PTF, width=2.5)))
    fig.add_trace(go.Scatter(x=bench.index, y=bench.values, name="Benchmark",
                             line=dict(color=C_BENCH, width=2, dash="dash")))
    fig.update_layout(**_layout(
        title=dict(text="Performance cumulée (base 100)", font_size=15),
        yaxis_title="Valeur",
    ))
    return fig


# ── 2. Drawdown ─────────────────────────────────────────

def chart_drawdown(ptf_prices, bench_prices):
    dd_ptf = metrics.drawdown_series(ptf_prices)
    dd_bench = metrics.drawdown_series(bench_prices)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd_ptf.index, y=dd_ptf.values, fill="tozeroy",
        name="Portefeuille", line=dict(color=C_NEG, width=1),
        fillcolor="rgba(231,76,60,0.15)",
    ))
    fig.add_trace(go.Scatter(
        x=dd_bench.index, y=dd_bench.values, name="Benchmark",
        line=dict(color=C_NEUTRAL, width=1, dash="dash"),
    ))
    fig.update_layout(**_layout(
        title=dict(text="Drawdown", font_size=15),
        yaxis_title="Drawdown", yaxis_tickformat=".0%",
    ))
    return fig


# ── 3. Rolling Sharpe ───────────────────────────────────

def chart_rolling_sharpe(ptf_prices, bench_prices, risk_free_rate):
    rs_ptf = metrics.rolling_sharpe(ptf_prices, risk_free_rate=risk_free_rate)
    rs_bench = metrics.rolling_sharpe(bench_prices, risk_free_rate=risk_free_rate)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rs_ptf.index, y=rs_ptf.values, name="Portefeuille",
                             line=dict(color=C_PTF, width=2)))
    fig.add_trace(go.Scatter(x=rs_bench.index, y=rs_bench.values, name="Benchmark",
                             line=dict(color=C_BENCH, width=1.5, dash="dash")))
    fig.add_hline(y=0, line_dash="dot", line_color=C_NEUTRAL, opacity=0.5)
    fig.update_layout(**_layout(
        title=dict(text="Rolling Sharpe (1 an)", font_size=15),
        yaxis_title="Sharpe",
    ))
    return fig


# ── 4. Contribution à la performance ────────────────────

def chart_performance_contribution(portfolio):
    contrib = performance_contribution(portfolio).fillna(0).sort_values()

    base = "rgba(46, 117, 182, {alpha})"
    neg = "rgba(149, 165, 166, {alpha})"
    vals = np.array([float(v) if np.isfinite(v) else 0.0 for v in contrib.values])
    max_abs = max(np.max(np.abs(vals)), 1e-9)
    colors = []
    for v in vals:
        alpha = 0.35 + 0.65 * (abs(v) / max_abs)
        colors.append(base.format(alpha=f"{alpha:.2f}") if v >= 0
                      else neg.format(alpha=f"{alpha:.2f}"))

    fig = go.Figure(go.Bar(
        x=contrib.values, y=contrib.index, orientation="h",
        marker_color=colors,
        text=[f"{v:+.2%}" for v in contrib.values],
        textposition="outside", textfont_size=11,
    ))
    # Marges élargies des deux côtés pour que les labels ne soient jamais croppés
    v_min = min(vals.min(), 0)
    v_max = max(vals.max(), 0)
    padding = max(abs(v_min), abs(v_max), 0.01) * 0.5
    fig.update_layout(**_layout(
        title=dict(text="Contribution à la performance", font_size=15),
        xaxis_title="Contribution", xaxis_tickformat=".1%",
        xaxis_range=[v_min - padding, v_max + padding],
        margin=dict(l=80, r=80, t=70, b=40),
        showlegend=False,
    ))
    return fig


# ── 5. Matrice de corrélation ───────────────────────────

def chart_correlation_heatmap(portfolio):
    corr = portfolio.correlation_matrix
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=corr.columns, y=corr.index,
        colorscale="RdBu_r", zmin=-1, zmax=1,
        text=np.round(corr.values, 2), texttemplate="%{text}",
        textfont=dict(size=13),
    ))
    fig.update_layout(**_layout(
        title=dict(text="Matrice de corrélation", font_size=15),
        width=550, height=480, showlegend=False,
    ))
    return fig


# ── 6. Distribution + VaR ──────────────────────────────

def chart_return_distribution(ptf_prices, bench_prices):
    rets_ptf = metrics.daily_returns(ptf_prices)
    rets_bench = metrics.daily_returns(bench_prices)
    var95 = metrics.var_95(ptf_prices)
    cvar95 = metrics.cvar_95(ptf_prices)
    var99 = metrics.var_99(ptf_prices)

    fig = go.Figure()
    fig.add_trace(go.Histogram(x=rets_ptf.values, nbinsx=80, name="Portefeuille",
                               marker_color=C_PTF, opacity=0.7))
    fig.add_trace(go.Histogram(x=rets_bench.values, nbinsx=80, name="Benchmark",
                               marker_color=C_BENCH, opacity=0.3))

    # Annotations positionnées manuellement pour éviter le chevauchement
    for val, label, color, dash, yref in [
        (var95, f"VaR 95% : {var95:.2%}", C_NEG, "dash", 0.95),
        (var99, f"VaR 99% : {var99:.2%}", C_PURPLE, "dash", 0.82),
        (cvar95, f"CVaR 95% : {cvar95:.2%}", C_NEG, "dot", 0.69),
    ]:
        fig.add_vline(x=val, line_dash=dash, line_color=color, line_width=1.5)
        fig.add_annotation(
            x=val, y=yref, yref="paper", xanchor="left", xshift=6,
            text=label, font=dict(size=10, color=color),
            showarrow=False, bgcolor="rgba(255,255,255,0.8)",
        )

    fig.update_layout(**_layout(
        title=dict(text="Distribution des rendements (1 jour)", font_size=15),
        xaxis_title="Rendement", yaxis_title="Fréquence",
        xaxis_tickformat=".1%", barmode="overlay",
    ))
    return fig


# ── 7. Décomposition du risque ──────────────────────────

def chart_risk_contribution(portfolio):
    rc = risk_contribution(portfolio).abs()

    max_rc = rc.max() if rc.max() > 0 else 1
    colors = [f"rgba(46, 117, 182, {0.3 + 0.7 * (v / max_rc):.2f})" for v in rc.values]

    fig = go.Figure(go.Pie(
        labels=rc.index, values=rc.values, hole=0.45,
        marker=dict(colors=colors,
                    line=dict(width=1.5, color="rgba(255,255,255,0.6)")),
        textinfo="label+percent", textfont_size=11,
    ))
    fig.update_layout(**_layout(
        title=dict(text="Décomposition du risque", font_size=15),
        showlegend=False,
    ))
    return fig


# ── 8. Volatilité GARCH(1,1) ───────────────────────────

def chart_garch_volatility(garch_ptf, garch_bench):
    vol_ptf = garch_ptf["conditional_vol"]
    vol_bench = garch_bench["conditional_vol"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=vol_ptf.index, y=vol_ptf.values,
                             name="Portefeuille", line=dict(color=C_PTF, width=2)))
    fig.add_trace(go.Scatter(x=vol_bench.index, y=vol_bench.values,
                             name="Benchmark", line=dict(color=C_BENCH, width=1.5, dash="dash")))

    last_date = vol_ptf.index[-1]
    fig.add_trace(go.Scatter(
        x=[last_date], y=[garch_ptf["forecast_vol_1d"]],
        mode="markers",
        marker=dict(size=10, color=C_TEAL, symbol="diamond",
                    line=dict(width=1.5, color="white")),
        name=f"Prévision J+1 ({garch_ptf['forecast_vol_1d']:.2%})",
    ))

    fig.update_layout(**_layout(
        title=dict(text="Volatilité conditionnelle GARCH(1,1)", font_size=15,
                   y=0.95, x=0.5, xanchor="center"),
        yaxis_title="Vol daily", yaxis_tickformat=".2%",
        margin=dict(l=50, r=20, t=90, b=40),
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5),
    ))
    return fig


# ── 9. Volatilité GJR-GARCH ────────────────────────────

def chart_gjr_garch_volatility(gjr_ptf, gjr_bench):
    vol_ptf = gjr_ptf["conditional_vol"]
    vol_bench = gjr_bench["conditional_vol"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=vol_ptf.index, y=vol_ptf.values,
                             name="Portefeuille (GJR)",
                             line=dict(color="#0F9ED5", width=2)))
    fig.add_trace(go.Scatter(x=vol_bench.index, y=vol_bench.values,
                             name="Benchmark (GJR)",
                             line=dict(color=C_BENCH, width=1.5, dash="dash")))

    last_date = vol_ptf.index[-1]
    fig.add_trace(go.Scatter(
        x=[last_date], y=[gjr_ptf["forecast_vol_1d"]],
        mode="markers",
        marker=dict(size=10, color=C_TEAL, symbol="diamond",
                    line=dict(width=1.5, color="white")),
        name=f"Prévision J+1 ({gjr_ptf['forecast_vol_1d']:.2%})",
    ))

    fig.update_layout(**_layout(
        title=dict(text="Volatilité conditionnelle GJR-GARCH(1,1)", font_size=15,
                   y=0.95, x=0.5, xanchor="center"),
        yaxis_title="Vol daily", yaxis_tickformat=".2%",
        margin=dict(l=50, r=20, t=90, b=40),
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5),
    ))
    return fig


# ── 10. Markov Regime Switching ─────────────────────────

def chart_regime_probabilities(ms_result: dict, ptf_prices) -> go.Figure:
    """Probabilité filtrée du régime stress + performance cumulée en fond."""
    filtered = ms_result["filtered_proba_stress"]
    smoothed = ms_result["smoothed_proba_stress"]

    from plotly.subplots import make_subplots
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Performance cumulée en fond (axe secondaire)
    ptf_norm = ptf_prices / ptf_prices.iloc[0] * 100
    common = filtered.index.intersection(ptf_norm.index)
    fig.add_trace(
        go.Scatter(x=common, y=ptf_norm.loc[common].values,
                   name="Portefeuille (base 100)",
                   line=dict(color=C_NEUTRAL, width=1),
                   opacity=0.4),
        secondary_y=True,
    )

    # Probabilité filtrée (zone remplie)
    fig.add_trace(
        go.Scatter(x=filtered.index, y=filtered.values,
                   fill="tozeroy", name="P(stress) filtrée",
                   line=dict(color=C_NEG, width=1.5),
                   fillcolor="rgba(231, 76, 60, 0.15)"),
        secondary_y=False,
    )

    # Probabilité lissée
    fig.add_trace(
        go.Scatter(x=smoothed.index, y=smoothed.values,
                   name="P(stress) lissée",
                   line=dict(color="#0F9ED5", width=1.5, dash="dash")),
        secondary_y=False,
    )

    fig.add_hline(y=0.5, line_dash="dot", line_color=C_NEUTRAL, opacity=0.4,
                  annotation_text="50%", annotation_position="bottom right",
                  annotation_font_size=9)

    fig.update_yaxes(title_text="P(stress)", range=[0, 1],
                     tickformat=".0%", secondary_y=False)
    fig.update_yaxes(title_text="Portefeuille (base 100)", secondary_y=True)

    fig.update_layout(**_layout(
        title=dict(text="Détection de régime — Markov Switching", font_size=15,
                   y=0.95, x=0.5, xanchor="center"),
        margin=dict(l=50, r=50, t=90, b=50),
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5),
    ))
    return fig
