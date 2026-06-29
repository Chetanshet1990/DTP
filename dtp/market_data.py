from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from urllib.error import URLError
from urllib.request import urlopen
import json

import pandas as pd


# REVIEW EXPLANATION:
# This file brings current market context into the cost twin. Steel price and
# USD/INR FX influence material cost, so the app can explain why current fair
# price may move away from old ERP purchase history.

FRED_STEEL_INDEX_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=WPU101"
FRANKFURTER_USD_INR_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=INR"
DEFAULT_BASE_STEEL_INDEX = 280.0
DEFAULT_BASE_USD_INR = 83.0


@dataclass(frozen=True)
class MarketAdjustment:
    """Container for live/fallback market values used by the cost model."""
    steel_index: float
    steel_index_date: str
    usd_inr: float
    fx_date: str
    base_steel_index: float = DEFAULT_BASE_STEEL_INDEX
    base_usd_inr: float = DEFAULT_BASE_USD_INR
    source_status: str = "live"

    @property
    def steel_index_factor(self) -> float:
        """Current steel index divided by the baseline steel index."""
        return self.steel_index / self.base_steel_index

    @property
    def fx_factor(self) -> float:
        """Current USD/INR divided by the baseline USD/INR."""
        return self.usd_inr / self.base_usd_inr

    @property
    def material_rate_factor(self) -> float:
        """Combined multiplier applied to base steel rate per kg."""
        return self.steel_index_factor * self.fx_factor


def _read_url(url: str, timeout: int = 10) -> str:
    """Small wrapper around urlopen so fetch functions stay readable."""
    with urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8")


def fetch_latest_steel_index() -> tuple[float, str]:
    """Fetch FRED WPU101 iron and steel producer price index."""
    raw_csv = _read_url(FRED_STEEL_INDEX_URL)
    data = pd.read_csv(StringIO(raw_csv))
    data["WPU101"] = pd.to_numeric(data["WPU101"], errors="coerce")
    latest = data.dropna(subset=["WPU101"]).iloc[-1]
    return float(latest["WPU101"]), str(latest["observation_date"])


def fetch_usd_inr_rate() -> tuple[float, str]:
    """Fetch latest USD to INR exchange rate from Frankfurter API."""
    payload = json.loads(_read_url(FRANKFURTER_USD_INR_URL))
    return float(payload["rates"]["INR"]), str(payload["date"])


def get_market_adjustment(
    base_steel_index: float = DEFAULT_BASE_STEEL_INDEX,
    base_usd_inr: float = DEFAULT_BASE_USD_INR,
) -> MarketAdjustment:
    """Fetch live market data; fall back to baseline values if APIs fail."""
    try:
        steel_index, steel_index_date = fetch_latest_steel_index()
        usd_inr, fx_date = fetch_usd_inr_rate()
        return MarketAdjustment(
            steel_index=steel_index,
            steel_index_date=steel_index_date,
            usd_inr=usd_inr,
            fx_date=fx_date,
            base_steel_index=base_steel_index,
            base_usd_inr=base_usd_inr,
        )
    except (KeyError, IndexError, ValueError, URLError, TimeoutError, OSError):
        # Demo must keep running during review even if internet/API access fails.
        # The source_status flag tells the UI and confidence logic this is fallback.
        return MarketAdjustment(
            steel_index=base_steel_index,
            steel_index_date=datetime.utcnow().date().isoformat(),
            usd_inr=base_usd_inr,
            fx_date=datetime.utcnow().date().isoformat(),
            base_steel_index=base_steel_index,
            base_usd_inr=base_usd_inr,
            source_status="fallback",
        )
