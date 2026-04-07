"""Unit tests for Portfolio class."""

import numpy as np
import pandas as pd
import pytest

from core.portfolio import Portfolio


@pytest.fixture
def sample_prices():
    dates = pd.bdate_range("2023-01-01", periods=253)
    np.random.seed(123)
    data = {
        "A": 100 * np.cumprod(1 + np.random.normal(0.0003, 0.01, 253)),
        "B": 100 * np.cumprod(1 + np.random.normal(0.0001, 0.008, 253)),
    }
    return pd.DataFrame(data, index=dates)


class TestPortfolioCreation:
    def test_valid(self, sample_prices):
        p = Portfolio(sample_prices, {"A": 0.6, "B": 0.4})
        assert p.tickers == ["A", "B"]

    def test_invalid_weights(self, sample_prices):
        with pytest.raises(ValueError, match="sum to 1.0"):
            Portfolio(sample_prices, {"A": 0.5, "B": 0.3})

    def test_missing_ticker(self, sample_prices):
        with pytest.raises(ValueError, match="Missing tickers"):
            Portfolio(sample_prices, {"A": 0.5, "C": 0.5})


class TestPortfolioReturns:
    def test_daily_returns_shape(self, sample_prices):
        p = Portfolio(sample_prices, {"A": 0.6, "B": 0.4})
        assert len(p.daily_returns) == 252

    def test_cumulative_prices_starts_at_one(self, sample_prices):
        p = Portfolio(sample_prices, {"A": 0.6, "B": 0.4})
        assert p.cumulative_prices.iloc[0] == pytest.approx(1.0, abs=0.01)

    def test_correlation_bounded(self, sample_prices):
        p = Portfolio(sample_prices, {"A": 0.6, "B": 0.4})
        corr = p.correlation_matrix
        assert (corr.values >= -1).all()
        assert (corr.values <= 1).all()
