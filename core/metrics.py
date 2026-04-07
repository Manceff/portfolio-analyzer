"""Pure functions for portfolio metrics computation.

Each function takes numpy arrays / pandas Series and returns a scalar or array.
Organized by business question:
  1. Value creation (performance)
  2. Risk (including GARCH, VaR, Kupiec backtest)
  3. Risk-adjusted returns
"""

import numpy as np
import pandas as pd
from scipy import stats

TRADING_DAYS = 252


# --- 1. Value creation ---

def cumulative_return(prices: pd.Series) -> float:
    return prices.iloc[-1] / prices.iloc[0] - 1


def annualized_return(prices: pd.Series) -> float:
    n_days = len(prices) - 1
    if n_days <= 0:
        return 0.0
    cum = cumulative_return(prices)
    return (1 + cum) ** (TRADING_DAYS / n_days) - 1


def geometric_alpha(ptf_prices: pd.Series, bench_prices: pd.Series) -> float:
    r_ptf = annualized_return(ptf_prices)
    r_bench = annualized_return(bench_prices)
    if r_bench == -1:
        return 0.0
    return (1 + r_ptf) / (1 + r_bench) - 1


def rolling_returns(prices: pd.Series, window: int = TRADING_DAYS) -> pd.Series:
    return prices.pct_change(window).dropna()


# --- 2. Risk ---

def daily_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()


def annualized_volatility(prices: pd.Series) -> float:
    return daily_returns(prices).std() * np.sqrt(TRADING_DAYS)


def drawdown_series(prices: pd.Series) -> pd.Series:
    cummax = prices.cummax()
    return (prices - cummax) / cummax


def max_drawdown(prices: pd.Series) -> float:
    return drawdown_series(prices).min()


def max_drawdown_duration(prices: pd.Series) -> int:
    dd = drawdown_series(prices)
    is_underwater = dd < 0
    if not is_underwater.any():
        return 0
    groups = (~is_underwater).cumsum()
    underwater_groups = groups[is_underwater]
    if underwater_groups.empty:
        return 0
    durations = underwater_groups.groupby(underwater_groups).count()
    return int(durations.max())


# --- VaR / CVaR at multiple confidence levels ---

def var_historical(prices: pd.Series, confidence: float = 0.95) -> float:
    """Historical VaR at given confidence level (daily)."""
    rets = daily_returns(prices)
    return float(np.percentile(rets, (1 - confidence) * 100))


def cvar_historical(prices: pd.Series, confidence: float = 0.95) -> float:
    """Conditional VaR (Expected Shortfall) at given confidence level."""
    rets = daily_returns(prices)
    threshold = np.percentile(rets, (1 - confidence) * 100)
    tail = rets[rets <= threshold]
    return float(tail.mean()) if len(tail) > 0 else 0.0


# Keep backward-compatible aliases
def var_95(prices: pd.Series) -> float:
    return var_historical(prices, 0.95)


def cvar_95(prices: pd.Series) -> float:
    return cvar_historical(prices, 0.95)


def var_99(prices: pd.Series) -> float:
    return var_historical(prices, 0.99)


def cvar_99(prices: pd.Series) -> float:
    return cvar_historical(prices, 0.99)


# --- Kupiec backtest (Proportion of Failures test) ---

def kupiec_backtest(prices: pd.Series, confidence: float = 0.95,
                    window: int = 504) -> dict:
    """Kupiec POF test — out-of-sample with rolling window (Bâle III: 504j).

    For each day t >= window, the VaR is estimated on the trailing
    `window` observations [t-window, t-1] and the violation is checked
    at day t. Rolling (not expanding) so old shocks don't permanently
    inflate the VaR.

    H0: the VaR model is correctly specified.
    H1: the model is mis-specified.

    Returns dict with:
      - var_last: the most recent VaR estimate (trailing window)
      - expected_rate: 1 - confidence
      - observed_rate: actual fraction of out-of-sample violations
      - n_violations: count
      - n_obs: number of out-of-sample observations tested
      - lr_statistic: likelihood ratio (chi2, df=1)
      - p_value: p-value of the LR test
      - model_adequate: True if p >= 0.05
    """
    rets = daily_returns(prices)
    n_total = len(rets)
    p_expected = 1 - confidence
    percentile = (1 - confidence) * 100

    violations = 0
    n_tested = 0

    for t in range(window, n_total):
        # VaR estimated on trailing window [t-window, t-1], tested at t
        var_t = float(np.percentile(rets.iloc[t - window:t], percentile))
        if rets.iloc[t] < var_t:
            violations += 1
        n_tested += 1

    p_observed = violations / n_tested if n_tested > 0 else 0

    # Most recent VaR (trailing window)
    var_last = float(np.percentile(rets.iloc[-window:], percentile))

    # Likelihood ratio statistic
    if violations == 0 or violations == n_tested or n_tested == 0:
        lr_stat = 0.0
        p_value = 1.0
    else:
        lr_stat = -2 * (
            np.log((p_expected ** violations) * ((1 - p_expected) ** (n_tested - violations)))
            - np.log((p_observed ** violations) * ((1 - p_observed) ** (n_tested - violations)))
        )
        p_value = 1 - stats.chi2.cdf(lr_stat, df=1)

    return {
        "var_last": var_last,
        "expected_rate": p_expected,
        "observed_rate": p_observed,
        "n_violations": int(violations),
        "n_obs": n_tested,
        "lr_statistic": float(lr_stat),
        "p_value": float(p_value),
        "model_adequate": p_value >= 0.05,
    }


# --- GARCH(1,1) ---

def fit_garch(prices: pd.Series) -> dict:
    """Fit a GARCH(1,1) model on daily returns.

    Returns dict with:
      - omega, alpha, beta: GARCH parameters
      - persistence: alpha + beta (< 1 = mean-reverting, ~1 = IGARCH-like)
      - conditional_vol: Series of daily conditional volatility (decimal)
      - forecast_vol_1d: 1-day ahead daily vol
      - forecast_vol_5d: 5-day ahead daily vol (average of multi-step variances)
      - forecast_vol_10d: 10-day ahead daily vol (average of multi-step variances)
      - long_run_vol: unconditional (long-run) annualized volatility
    """
    from arch import arch_model

    rets = daily_returns(prices) * 100  # arch expects percentage returns

    model = arch_model(rets, vol="Garch", p=1, q=1, mean="Constant", dist="normal")
    result = model.fit(disp="off", show_warning=False)

    omega = result.params.get("omega", 0)
    alpha = result.params.get("alpha[1]", 0)
    beta_val = result.params.get("beta[1]", 0)
    persistence = alpha + beta_val

    # Conditional vol — kept in daily (no annualization)
    cond_vol_daily = result.conditional_volatility / 100  # decimal
    cond_vol_series = pd.Series(cond_vol_daily.values, index=rets.index,
                                name="GARCH Vol (daily)")

    # Multi-step forecasts — daily average vol over horizon
    forecast = result.forecast(horizon=10)
    variances = forecast.variance.iloc[-1] / 10000  # decimal daily variances

    fcast_vol_1d = float(np.sqrt(variances.iloc[0]))
    fcast_vol_5d = float(np.sqrt(variances.iloc[:5].mean()))
    fcast_vol_10d = float(np.sqrt(variances.iloc[:10].mean()))

    # Long-run unconditional vol (this one IS annualized — it's a structural parameter)
    if persistence < 1:
        long_run_var = (omega / 10000) / (1 - persistence)
        long_run_vol = np.sqrt(long_run_var) * np.sqrt(TRADING_DAYS)
    else:
        long_run_vol = float("nan")

    return {
        "omega": float(omega),
        "alpha": float(alpha),
        "beta": float(beta_val),
        "persistence": float(persistence),
        "conditional_vol": cond_vol_series,
        "forecast_vol_1d": fcast_vol_1d,
        "forecast_vol_5d": fcast_vol_5d,
        "forecast_vol_10d": fcast_vol_10d,
        "long_run_vol": float(long_run_vol),
    }


def fit_gjr_garch(prices: pd.Series) -> dict:
    """Fit a GJR-GARCH(1,1) model (Glosten-Jagannathan-Runkle, 1993).

    Captures the leverage effect: negative shocks increase volatility
    more than positive shocks of the same magnitude.

    Returns dict with:
      - omega, alpha, beta, gamma: GJR parameters
      - persistence: alpha + beta + gamma/2
      - conditional_vol: Series of daily conditional volatility (decimal)
      - forecast_vol_1d, 5d, 10d: daily vol forecasts (multi-step avg)
      - long_run_vol: unconditional annualized volatility
      - leverage_effect: bool, True if gamma > 0
    """
    from arch import arch_model

    rets = daily_returns(prices) * 100

    model = arch_model(rets, vol="Garch", p=1, o=1, q=1,
                       mean="Constant", dist="normal")
    result = model.fit(disp="off", show_warning=False)

    omega = result.params.get("omega", 0)
    alpha = result.params.get("alpha[1]", 0)
    gamma = result.params.get("gamma[1]", 0)
    beta_val = result.params.get("beta[1]", 0)
    persistence = alpha + beta_val + gamma / 2

    cond_vol_daily = result.conditional_volatility / 100
    cond_vol_series = pd.Series(cond_vol_daily.values, index=rets.index,
                                name="GJR Vol (daily)")

    forecast = result.forecast(horizon=10)
    variances = forecast.variance.iloc[-1] / 10000

    fcast_vol_1d = float(np.sqrt(variances.iloc[0]))
    fcast_vol_5d = float(np.sqrt(variances.iloc[:5].mean()))
    fcast_vol_10d = float(np.sqrt(variances.iloc[:10].mean()))

    if persistence < 1:
        long_run_var = (omega / 10000) / (1 - persistence)
        long_run_vol = np.sqrt(long_run_var) * np.sqrt(TRADING_DAYS)
    else:
        long_run_vol = float("nan")

    return {
        "omega": float(omega),
        "alpha": float(alpha),
        "gamma": float(gamma),
        "beta": float(beta_val),
        "persistence": float(persistence),
        "conditional_vol": cond_vol_series,
        "forecast_vol_1d": fcast_vol_1d,
        "forecast_vol_5d": fcast_vol_5d,
        "forecast_vol_10d": fcast_vol_10d,
        "long_run_vol": float(long_run_vol),
        "leverage_effect": gamma > 0,
    }


# --- Markov Regime Switching (Hamilton, 1989) ---

def fit_markov_switching(prices: pd.Series, k_regimes: int = 2) -> dict:
    """Fit a 2-regime Markov Switching model on daily returns.

    Each regime has its own mean and variance. The model identifies
    'calm' (low vol) and 'stress' (high vol) market regimes.

    Returns dict with:
      - regimes: dict per regime with mean_ann, vol_ann
      - stress_regime: index of the high-vol regime
      - transition_matrix: k x k transition probabilities
      - filtered_proba_stress: Series of P(stress) at each date
      - smoothed_proba_stress: Series of smoothed P(stress)
      - current_regime_proba: P(stress) at last observation
      - expected_duration_calm: expected days in calm regime
      - expected_duration_stress: expected days in stress regime
    """
    import warnings
    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

    rets = daily_returns(prices)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = MarkovRegression(
            rets, k_regimes=k_regimes, trend="c", switching_variance=True,
        )
        result = model.fit(maxiter=500, disp=False)

    # Identify which regime is stress (higher variance)
    regime_vars = []
    for i in range(k_regimes):
        regime_vars.append(result.params[f"sigma2[{i}]"])
    stress_idx = int(np.argmax(regime_vars))
    calm_idx = 1 - stress_idx

    # Regime characteristics
    regimes = {}
    for i in range(k_regimes):
        label = "stress" if i == stress_idx else "calme"
        mean_daily = result.params[f"const[{i}]"]
        var_daily = result.params[f"sigma2[{i}]"]
        regimes[label] = {
            "mean_ann": float(mean_daily * TRADING_DAYS),
            "vol_ann": float(np.sqrt(var_daily) * np.sqrt(TRADING_DAYS)),
        }

    # Transition matrix — shape is (k, k, 1), squeeze the last dim
    trans_raw = np.array(result.regime_transition, dtype=float).squeeze()
    # trans_raw[i, j] = P(from j -> to i), so transpose for P(from i -> to j)
    trans = trans_raw.T
    p_calm_calm = float(trans[calm_idx, calm_idx])
    p_stress_stress = float(trans[stress_idx, stress_idx])
    dur_calm = 1 / (1 - p_calm_calm) if p_calm_calm < 1 else float("inf")
    dur_stress = 1 / (1 - p_stress_stress) if p_stress_stress < 1 else float("inf")

    # Probabilities
    filtered = result.filtered_marginal_probabilities
    smoothed = result.smoothed_marginal_probabilities

    filtered_stress = pd.Series(
        filtered[stress_idx].values, index=rets.index, name="P(stress)"
    )
    smoothed_stress = pd.Series(
        smoothed[stress_idx].values, index=rets.index, name="P(stress) lissée"
    )

    return {
        "regimes": regimes,
        "stress_regime": stress_idx,
        "transition_matrix": [[float(trans[i][j]) for j in range(k_regimes)]
                              for i in range(k_regimes)],
        "filtered_proba_stress": filtered_stress,
        "smoothed_proba_stress": smoothed_stress,
        "current_regime_proba": float(filtered_stress.iloc[-1]),
        "expected_duration_calm": float(dur_calm),
        "expected_duration_stress": float(dur_stress),
    }


def tracking_error(ptf_prices: pd.Series, bench_prices: pd.Series) -> float:
    r_ptf = daily_returns(ptf_prices)
    r_bench = daily_returns(bench_prices)
    common = r_ptf.index.intersection(r_bench.index)
    diff = r_ptf.loc[common] - r_bench.loc[common]
    return float(diff.std() * np.sqrt(TRADING_DAYS))


def beta(ptf_prices: pd.Series, bench_prices: pd.Series) -> float:
    r_ptf = daily_returns(ptf_prices)
    r_bench = daily_returns(bench_prices)
    common = r_ptf.index.intersection(r_bench.index)
    r_ptf = r_ptf.loc[common]
    r_bench = r_bench.loc[common]
    cov = np.cov(r_ptf, r_bench)
    if cov[1, 1] == 0:
        return 0.0
    return float(cov[0, 1] / cov[1, 1])


# --- 3. Risk-adjusted returns ---

def sharpe_ratio(prices: pd.Series, risk_free_rate: float = 0.035) -> float:
    vol = annualized_volatility(prices)
    if vol == 0:
        return 0.0
    return (annualized_return(prices) - risk_free_rate) / vol


def sortino_ratio(prices: pd.Series, risk_free_rate: float = 0.035) -> float:
    rets = daily_returns(prices)
    daily_rf = (1 + risk_free_rate) ** (1 / TRADING_DAYS) - 1
    excess = rets - daily_rf
    # Downside deviation (Sortino & Price, 1994): sqrt(mean of squared negative deviations)
    # ALL observations count in the denominator — positive deviations contribute 0
    downside_sq = np.minimum(excess, 0) ** 2
    downside_dev = np.sqrt(downside_sq.mean()) * np.sqrt(TRADING_DAYS)
    if downside_dev == 0:
        return 0.0
    return (annualized_return(prices) - risk_free_rate) / downside_dev


def information_ratio(ptf_prices: pd.Series, bench_prices: pd.Series) -> float:
    te = tracking_error(ptf_prices, bench_prices)
    if te == 0:
        return 0.0
    alpha = geometric_alpha(ptf_prices, bench_prices)
    return alpha / te


def calmar_ratio(prices: pd.Series) -> float:
    mdd = max_drawdown(prices)
    if mdd == 0:
        return 0.0
    return annualized_return(prices) / abs(mdd)


def rolling_sharpe(prices: pd.Series, window: int = TRADING_DAYS,
                   risk_free_rate: float | pd.Series = 0.035) -> pd.Series:
    """Rolling Sharpe ratio.

    risk_free_rate can be a scalar (fixed) or a daily Series (time-varying).
    When time-varying, each rolling window uses the Rf at that date.
    """
    rets = daily_returns(prices)
    rolling_mean = rets.rolling(window).mean() * TRADING_DAYS
    rolling_std = rets.rolling(window).std() * np.sqrt(TRADING_DAYS)

    if isinstance(risk_free_rate, pd.Series):
        # Align Rf series to returns index, forward-fill
        rf_aligned = risk_free_rate.reindex(rets.index, method="ffill").fillna(0)
        result = (rolling_mean - rf_aligned) / rolling_std
    else:
        result = (rolling_mean - risk_free_rate) / rolling_std

    return result.dropna()
