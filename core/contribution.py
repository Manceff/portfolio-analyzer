"""Contribution analysis — performance and risk attribution per asset."""

import numpy as np
import pandas as pd

from core.portfolio import Portfolio


def performance_contribution(portfolio: Portfolio) -> pd.Series:
    """Weight * cumulative return of each asset."""
    cum_rets = portfolio.asset_cumulative_returns
    weights = pd.Series(portfolio.weights)
    return weights * cum_rets


def risk_contribution(portfolio: Portfolio) -> pd.Series:
    """Marginal risk contribution of each asset to portfolio volatility.

    RC_i = w_i * (Cov @ w)_i / sigma_ptf
    """
    cov = portfolio.covariance_matrix.values
    w = portfolio._weight_array
    port_var = w @ cov @ w
    port_vol = np.sqrt(port_var)
    if port_vol == 0:
        return pd.Series(0.0, index=portfolio.tickers)
    marginal = cov @ w
    rc = w * marginal / port_vol
    return pd.Series(rc, index=portfolio.tickers)
