"""Unit tests for metrics module."""

import numpy as np
import pandas as pd
import pytest

from core import metrics


@pytest.fixture
def simple_prices():
    """A simple price series: 100 -> 110 over 252 days (linear)."""
    dates = pd.bdate_range("2023-01-01", periods=253)
    values = np.linspace(100, 110, 253)
    return pd.Series(values, index=dates)


@pytest.fixture
def volatile_prices():
    """Price series with known volatility pattern."""
    np.random.seed(42)
    dates = pd.bdate_range("2023-01-01", periods=253)
    rets = np.random.normal(0.0004, 0.01, 252)
    prices = [100.0]
    for r in rets:
        prices.append(prices[-1] * (1 + r))
    return pd.Series(prices, index=dates)


@pytest.fixture
def long_volatile_prices():
    """Longer series for GARCH estimation (needs >100 obs)."""
    np.random.seed(99)
    dates = pd.bdate_range("2020-01-01", periods=600)
    rets = np.random.normal(0.0003, 0.012, 599)
    prices = [100.0]
    for r in rets:
        prices.append(prices[-1] * (1 + r))
    return pd.Series(prices, index=dates)


class TestCumulativeReturn:
    def test_positive(self, simple_prices):
        assert metrics.cumulative_return(simple_prices) == pytest.approx(0.10, abs=0.001)

    def test_flat(self):
        prices = pd.Series([100, 100, 100])
        assert metrics.cumulative_return(prices) == 0.0


class TestAnnualizedReturn:
    def test_one_year(self, simple_prices):
        cagr = metrics.annualized_return(simple_prices)
        assert cagr == pytest.approx(0.10, abs=0.005)


class TestVolatility:
    def test_zero_vol(self):
        prices = pd.Series([100.0, 100.0, 100.0, 100.0])
        assert metrics.annualized_volatility(prices) == 0.0

    def test_positive_vol(self, volatile_prices):
        vol = metrics.annualized_volatility(volatile_prices)
        assert 0.05 < vol < 0.30


class TestDrawdown:
    def test_no_drawdown(self):
        prices = pd.Series([100, 101, 102, 103])
        assert metrics.max_drawdown(prices) == 0.0

    def test_known_drawdown(self):
        prices = pd.Series([100, 110, 88, 95, 115])
        mdd = metrics.max_drawdown(prices)
        assert mdd == pytest.approx(-0.2, abs=0.001)

    def test_drawdown_duration(self):
        prices = pd.Series([100, 110, 88, 90, 95, 100, 110, 115])
        dur = metrics.max_drawdown_duration(prices)
        assert dur > 0


class TestSharpe:
    def test_sharpe_positive(self, simple_prices):
        sr = metrics.sharpe_ratio(simple_prices, risk_free_rate=0.03)
        assert sr > 0

    def test_sharpe_zero_vol(self):
        prices = pd.Series([100.0, 100.0, 100.0, 100.0])
        assert metrics.sharpe_ratio(prices) == 0.0


class TestVaR:
    def test_var95_negative(self, volatile_prices):
        var = metrics.var_95(volatile_prices)
        assert var < 0

    def test_var99_more_extreme(self, volatile_prices):
        var95 = metrics.var_95(volatile_prices)
        var99 = metrics.var_99(volatile_prices)
        assert var99 <= var95

    def test_cvar95_worse_than_var95(self, volatile_prices):
        var = metrics.var_95(volatile_prices)
        cvar = metrics.cvar_95(volatile_prices)
        assert cvar <= var

    def test_cvar99_worse_than_var99(self, volatile_prices):
        var = metrics.var_99(volatile_prices)
        cvar = metrics.cvar_99(volatile_prices)
        assert cvar <= var


class TestKupiec:
    def test_returns_dict(self, long_volatile_prices):
        result = metrics.kupiec_backtest(long_volatile_prices, confidence=0.95)
        assert "p_value" in result
        assert "model_adequate" in result
        assert "n_violations" in result
        assert "var_last" in result
        assert 0.0 <= result["p_value"] <= 1.0

    def test_out_of_sample(self, long_volatile_prices):
        result = metrics.kupiec_backtest(long_volatile_prices, confidence=0.95,
                                         window=252)
        # n_obs should be total - window, not total
        n_total = len(metrics.daily_returns(long_volatile_prices))
        assert result["n_obs"] == n_total - 252

    def test_99_fewer_violations_than_95(self, long_volatile_prices):
        r95 = metrics.kupiec_backtest(long_volatile_prices, confidence=0.95)
        r99 = metrics.kupiec_backtest(long_volatile_prices, confidence=0.99)
        assert r99["n_violations"] <= r95["n_violations"]


class TestGARCH:
    def test_garch_returns_dict(self, long_volatile_prices):
        result = metrics.fit_garch(long_volatile_prices)
        assert "alpha" in result
        assert "beta" in result
        assert "persistence" in result
        assert "conditional_vol" in result
        assert "forecast_vol_1d" in result

    def test_garch_persistence_bounded(self, long_volatile_prices):
        result = metrics.fit_garch(long_volatile_prices)
        assert 0 < result["persistence"] < 1.1

    def test_garch_alpha_positive(self, long_volatile_prices):
        result = metrics.fit_garch(long_volatile_prices)
        assert result["alpha"] >= 0

    def test_garch_forecast_positive(self, long_volatile_prices):
        result = metrics.fit_garch(long_volatile_prices)
        assert result["forecast_vol_1d"] > 0
        assert result["forecast_vol_5d"] > 0
        assert result["forecast_vol_10d"] > 0


class TestGJRGARCH:
    def test_gjr_returns_dict(self, long_volatile_prices):
        result = metrics.fit_gjr_garch(long_volatile_prices)
        assert "alpha" in result
        assert "gamma" in result
        assert "beta" in result
        assert "leverage_effect" in result
        assert "conditional_vol" in result

    def test_gjr_persistence_bounded(self, long_volatile_prices):
        result = metrics.fit_gjr_garch(long_volatile_prices)
        assert 0 < result["persistence"] < 1.1

    def test_gjr_gamma_exists(self, long_volatile_prices):
        result = metrics.fit_gjr_garch(long_volatile_prices)
        assert isinstance(result["gamma"], float)

    def test_gjr_forecast_positive(self, long_volatile_prices):
        result = metrics.fit_gjr_garch(long_volatile_prices)
        assert result["forecast_vol_1d"] > 0
        assert result["forecast_vol_5d"] > 0


class TestMarkovSwitching:
    def test_returns_dict(self, long_volatile_prices):
        result = metrics.fit_markov_switching(long_volatile_prices)
        assert "regimes" in result
        assert "calme" in result["regimes"]
        assert "stress" in result["regimes"]
        assert "filtered_proba_stress" in result
        assert "current_regime_proba" in result

    def test_probability_bounded(self, long_volatile_prices):
        result = metrics.fit_markov_switching(long_volatile_prices)
        p = result["current_regime_proba"]
        assert 0 <= p <= 1

    def test_stress_vol_higher_than_calm(self, long_volatile_prices):
        result = metrics.fit_markov_switching(long_volatile_prices)
        assert result["regimes"]["stress"]["vol_ann"] > result["regimes"]["calme"]["vol_ann"]

    def test_expected_durations_positive(self, long_volatile_prices):
        result = metrics.fit_markov_switching(long_volatile_prices)
        assert result["expected_duration_calm"] > 0
        assert result["expected_duration_stress"] > 0

    def test_filtered_series_length(self, long_volatile_prices):
        result = metrics.fit_markov_switching(long_volatile_prices)
        rets = metrics.daily_returns(long_volatile_prices)
        assert len(result["filtered_proba_stress"]) == len(rets)


class TestBeta:
    def test_self_beta(self, volatile_prices):
        b = metrics.beta(volatile_prices, volatile_prices)
        assert b == pytest.approx(1.0, abs=0.01)


class TestTrackingError:
    def test_self_tracking_error(self, volatile_prices):
        te = metrics.tracking_error(volatile_prices, volatile_prices)
        assert te == pytest.approx(0.0, abs=0.001)
