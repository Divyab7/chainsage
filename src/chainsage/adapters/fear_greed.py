"""Fear & Greed historical data — CMC trial API + Alternative.me fallback."""

from __future__ import annotations

import os

import httpx
import pandas as pd

from chainsage.adapters.cmc import fetch_fear_greed_historical


def fetch_alternative_me_fg(limit: int = 0) -> pd.DataFrame:
    params: dict = {}
    if limit:
        params["limit"] = limit
    with httpx.Client(timeout=60.0) as client:
        r = client.get("https://api.alternative.me/fng/", params=params)
        r.raise_for_status()
        rows = r.json()["data"]

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="s", utc=True).dt.tz_localize(None)
    df["fear_greed"] = df["value"].astype(float)
    return df[["timestamp", "fear_greed"]].sort_values("timestamp")


def fetch_fg_history(days: int = 500) -> pd.DataFrame:
    """Prefer CMC historical F&G; fall back to Alternative.me."""
    try:
        if os.environ.get("CMC_API_KEY"):
            rows = fetch_fear_greed_historical(limit=min(days, 500))
            if rows:
                df = pd.DataFrame(rows)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                return df.sort_values("timestamp")
    except Exception:
        pass
    return fetch_alternative_me_fg(limit=days)
