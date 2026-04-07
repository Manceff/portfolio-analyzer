"""Data loader adapter — abstracts the data source (yFinance, ECB API)."""

import io

import numpy as np
import pandas as pd
import yfinance as yf
import requests


def fetch_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Fetch adjusted close prices for a list of tickers."""
    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)

    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"]
    else:
        prices = data[["Close"]].rename(columns={"Close": tickers[0]})

    prices = prices.dropna(how="all").ffill()
    return prices


def fetch_benchmark(ticker: str, start: str, end: str) -> pd.Series:
    """Fetch adjusted close prices for a single benchmark ticker."""
    data = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        series = data["Close"].iloc[:, 0]
    else:
        series = data["Close"]
    series = series.dropna().ffill()
    series.name = ticker
    return series


# ── Taux sans risque USD (Yahoo Finance) ────────────────

US_TREASURY_TICKERS = {
    "3 mois": "^IRX",
    "5 ans": "^FVX",
    "10 ans": "^TNX",
}


def fetch_us_risk_free(maturity: str, start: str, end: str) -> pd.Series:
    """Fetch US Treasury yield from yFinance.

    yFinance returns yields in percentage points (e.g. 4.25 = 4.25%).
    We convert to decimal (0.0425).
    """
    ticker = US_TREASURY_TICKERS[maturity]
    data = yf.download(ticker, start=start, end=end, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        series = data["Close"].iloc[:, 0]
    else:
        series = data["Close"]
    series = series.dropna().ffill() / 100.0
    series.name = f"US Treasury {maturity}"
    return series


# ── Taux sans risque EUR (API BCE — Yield Curve AAA) ────
#
# Source : ECB Statistical Data Warehouse
# Dataset : YC (Euro area yield curves)
# Courbe : Obligations souveraines AAA, modèle Svensson, zéro-coupon
# https://data.ecb.europa.eu/data/datasets/YC
#
# Avantage vs approximation par paliers :
#   - Données daily exactes (pas d'interpolation)
#   - Inclut la prime de terme réelle (pas un spread fixe)
#   - Toutes maturités disponibles

_ECB_YC_MATURITIES = {
    "1 an (AAA spot)": "SR_1Y",
    "5 ans (AAA spot)": "SR_5Y",
    "10 ans (AAA spot)": "SR_10Y",
}

_ECB_API_URL = (
    "https://data-api.ecb.europa.eu/service/data/YC/"
    "B.U2.EUR.4F.G_N_A.SV_C_YM.{maturity_code}"
)


def fetch_eur_risk_free(maturity: str, start: str, end: str) -> pd.Series:
    """Fetch EUR AAA yield curve spot rate from the ECB API.

    Returns a daily Series of annualized yields in decimal (e.g. 0.0212).
    Source: ECB Yield Curve — AAA-rated sovereign bonds, Svensson model.
    """
    maturity_code = _ECB_YC_MATURITIES[maturity]
    url = _ECB_API_URL.format(maturity_code=maturity_code)
    params = {
        "startPeriod": start,
        "endPeriod": end,
        "format": "csvdata",
    }

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text))
    df = df[["TIME_PERIOD", "OBS_VALUE"]].copy()
    df["TIME_PERIOD"] = pd.to_datetime(df["TIME_PERIOD"])
    df = df.set_index("TIME_PERIOD").sort_index()
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna()

    # ECB returns rates in percentage (2.12 = 2.12%), convert to decimal
    series = df["OBS_VALUE"] / 100.0
    series = series.ffill()
    series.name = f"EUR {maturity}"
    return series
