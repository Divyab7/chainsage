"""Build committed market datasets from real public sources."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from chainsage.adapters.binance import fetch_daily_klines, fetch_funding_history
from chainsage.adapters.fear_greed import fetch_fg_history

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"

ASSETS = ("BNB", "CAKE", "TWT", "BTC")


def _holder_trend_proxy(df: pd.DataFrame) -> pd.Series:
    vol = df["volume_24h"]
    vol_ma = vol.rolling(14, min_periods=1).mean()
    z = (vol - vol_ma) / (vol.rolling(14, min_periods=1).std() + 1e-9)
    price_chg = df["close"].pct_change(7)
    return (z * 0.3 + price_chg * 5).clip(-0.5, 0.5).fillna(0.0)


def _narrative_proxy(df: pd.DataFrame, btc_df: pd.DataFrame) -> pd.Series:
    merged = df[["timestamp", "close"]].merge(
        btc_df[["timestamp", "close"]].rename(columns={"close": "btc_close"}),
        on="timestamp",
        how="left",
    )
    rel = (merged["close"].pct_change(7) - merged["btc_close"].pct_change(7)).clip(-0.3, 0.3)
    return (rel * 2).fillna(0.0)


def _sector_rank_from_score(narrative: float) -> int:
    if narrative > 0.5:
        return 5
    if narrative > 0.2:
        return 15
    if narrative < -0.2:
        return 55
    return 30


def build_asset_dataset(symbol: str, days: int = 500, btc_df: pd.DataFrame | None = None) -> pd.DataFrame:
    load_dotenv(ROOT / ".env")
    ohlcv = fetch_daily_klines(symbol, limit=days)
    funding = fetch_funding_history(symbol, limit=days * 3)
    fg = fetch_fg_history(days=days)

    df = ohlcv.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    funding["timestamp"] = pd.to_datetime(funding["timestamp"]).dt.normalize()
    fg["timestamp"] = pd.to_datetime(fg["timestamp"]).dt.normalize()

    df = df.merge(funding, on="timestamp", how="left")
    df = df.merge(fg, on="timestamp", how="left")
    df["funding_rate"] = df["funding_rate"].fillna(0.0)
    df["fear_greed"] = df["fear_greed"].ffill().bfill().fillna(50.0)
    df["holder_trend"] = _holder_trend_proxy(df)
    df["holder_change_7d"] = df["close"].pct_change(7).fillna(0.0)
    df["holder_concentration"] = 0.0
    df["oi_change_24h"] = df["volume_24h"].pct_change(1).fillna(0.0).abs()

    if symbol == "BTC":
        df["narrative_score"] = 0.0
        df["sector_rank"] = 30
    elif btc_df is not None:
        df["narrative_score"] = _narrative_proxy(df, btc_df)
        df["sector_rank"] = df["narrative_score"].apply(_sector_rank_from_score)
    else:
        df["narrative_score"] = 0.0
        df["sector_rank"] = 30

    return df


def fetch_all(assets: tuple[str, ...] = ASSETS, days: int = 1000) -> dict[str, Path]:
    DATA.mkdir(parents=True, exist_ok=True)
    btc = build_asset_dataset("BTC", days=days)
    paths: dict[str, Path] = {}
    row_counts: dict[str, int] = {}

    btc_out = DATA / "btc_daily.csv"
    btc.to_csv(btc_out, index=False)
    paths["BTC"] = btc_out
    row_counts["BTC"] = len(btc)
    print(f"Wrote {btc_out} ({len(btc)} rows)")

    for symbol in assets:
        if symbol == "BTC":
            continue
        df = build_asset_dataset(symbol, days=days, btc_df=btc)
        out = DATA / f"{symbol.lower()}_daily.csv"
        df.to_csv(out, index=False)
        paths[symbol] = out
        row_counts[symbol] = len(df)
        print(f"Wrote {out} ({len(df)} rows, {df['timestamp'].min().date()} → {df['timestamp'].max().date()})")

    manifest = {
        "sources": [
            "binance_spot_klines (price, volume)",
            "binance_futures_funding (derivatives layer)",
            "cmc_v3_fear_greed_or_alternative_me (sentiment)",
            "volume_trend_proxy (on-chain layer)",
            "relative_btc_momentum (narrative layer)",
        ],
        "assets": list(assets),
        "rows": row_counts,
    }
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return paths
