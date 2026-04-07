"""Portfolio class — computes weighted returns from individual asset prices."""

import numpy as np
import pandas as pd


class Portfolio:
    """Represents a weighted portfolio of assets."""

    def __init__(self, prices: pd.DataFrame, weights: dict[str, float]):
        self.prices = prices
        self.weights = weights
        self.tickers = list(weights.keys())
        self._weight_array = np.array([weights[t] for t in self.tickers])
        self._validate()

    def _validate(self):
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total:.4f}")
        if any(w < 0 for w in self.weights.values()):
            raise ValueError("Negative weights are not allowed")
        missing = [t for t in self.tickers if t not in self.prices.columns]
        if missing:
            raise ValueError(f"Missing tickers in price data: {missing}")
        if len(self.prices) < 2:
            raise ValueError("Need at least 2 price observations")

    @property
    def daily_returns(self) -> pd.DataFrame:
        return self.prices[self.tickers].pct_change().dropna()

    @property
    def weighted_daily_returns(self) -> pd.Series:
        rets = self.daily_returns
        return (rets * self._weight_array).sum(axis=1)

    @property
    def cumulative_prices(self) -> pd.Series:
        """Portfolio value series normalized to start at 1."""
        wr = self.weighted_daily_returns
        return (1 + wr).cumprod()

    @property
    def asset_cumulative_returns(self) -> pd.Series:
        """Cumulative return of each asset over the period."""
        return self.prices[self.tickers].iloc[-1] / self.prices[self.tickers].iloc[0] - 1

    @property
    def covariance_matrix(self) -> pd.DataFrame:
        return self.daily_returns.cov() * 252

    @property
    def correlation_matrix(self) -> pd.DataFrame:
        return self.daily_returns.corr()
