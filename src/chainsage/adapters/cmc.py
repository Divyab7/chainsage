"""CoinMarketCap REST adapter — Agent Hub MCP tools only (no third-party fallbacks)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
import pandas as pd

CMC_BASE = "https://pro-api.coinmarketcap.com"
CMC_TRIAL = f"{CMC_BASE}/trial-pro-api"

BSC_TOKENS = {
    "BNB": {"contract": "native", "dex": "PancakeSwap"},
    "CAKE": {"contract": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82", "dex": "PancakeSwap"},
    "TWT": {"contract": "0x4B0F1812e5Df2A09796481Ff14017e6005508003", "dex": "PancakeSwap"},
}

SYMBOL_IDS = {
    "BNB": 1839,
    "CAKE": 7186,
    "TWT": 5964,
    "BTC": 1,
    "ETH": 1027,
}

MCP_TOOLS = [
    "get_crypto_quotes_latest",
    "get_crypto_technical_analysis",
    "get_global_metrics_latest",
    "get_global_crypto_derivatives_metrics",
    "get_crypto_metrics",
    "trending_crypto_narratives",
]


def _headers() -> dict[str, str]:
    key = os.environ.get("CMC_API_KEY", "").strip()
    if not key or key == "your_coinmarketcap_api_key_here":
        return {"Accept": "application/json"}
    return {"X-CMC_PRO_API_KEY": key, "Accept": "application/json"}


def _get(path: str, params: dict | None = None, trial_ok: bool = False) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{CMC_BASE}{path}", headers=_headers(), params=params or {})
        if r.status_code == 200:
            return r.json()
        if trial_ok:
            r2 = client.get(f"{CMC_TRIAL}{path}", params=params or {})
            r2.raise_for_status()
            return r2.json()
        r.raise_for_status()
    return {}


def fetch_quotes_latest(symbol: str) -> dict[str, Any]:
    coin_id = SYMBOL_IDS.get(symbol.upper(), 1839)
    data = _get("/v1/cryptocurrency/quotes/latest", {"id": coin_id, "convert": "USD"})
    q = data["data"][str(coin_id)]["quote"]["USD"]
    return {
        "price": float(q["price"]),
        "volume_24h": float(q["volume_24h"]),
        "percent_change_7d": float(q.get("percent_change_7d") or 0),
        "percent_change_24h": float(q.get("percent_change_24h") or 0),
        "market_cap": float(q.get("market_cap") or 0),
    }


def fetch_fear_greed_latest() -> dict[str, Any]:
    data = _get("/v3/fear-and-greed/latest", trial_ok=True)
    d = data["data"]
    return {"value": float(d["value"]), "classification": d.get("value_classification", "")}


def fetch_global_metrics() -> dict[str, Any]:
    data = _get("/v1/global-metrics/quotes/latest", {"convert": "USD"}, trial_ok=True)
    q = data["data"]["quote"]["USD"]
    return {
        "total_market_cap": float(q.get("total_market_cap") or 0),
        "btc_dominance": float(data["data"].get("btc_dominance") or 0),
    }


def fetch_fear_greed_historical(limit: int = 400) -> list[dict[str, Any]]:
    data = _get("/v3/fear-and-greed/historical", {"limit": limit}, trial_ok=True)
    return [
        {
            "timestamp": datetime.fromtimestamp(int(r["timestamp"]), tz=timezone.utc).strftime("%Y-%m-%d"),
            "fear_greed": float(r["value"]),
        }
        for r in data.get("data", [])
    ]


def fetch_technical_analysis(symbol: str) -> dict[str, Any]:
    """Maps to get_crypto_technical_analysis — CMC REST only."""
    coin_id = SYMBOL_IDS.get(symbol.upper(), 1839)
    for path in (
        f"/v1/cryptocurrency/technical-analysis/latest?id={coin_id}",
        f"/v2/cryptocurrency/technical-analysis/latest?id={coin_id}",
    ):
        try:
            data = _get(path)
            if data.get("data"):
                block = data["data"]
                if isinstance(block, list):
                    block = block[0]
                indicators = block.get("indicators", block)
                return {
                    "source": "cmc_rest",
                    "rsi14": float(indicators.get("rsi", indicators.get("rsi14", 50))),
                    "macd_histogram": float(indicators.get("macd_histogram", 0)),
                    "ema21": float(indicators.get("ema21", indicators.get("ema_21", 0))),
                }
        except Exception:
            continue
    return {"source": "unavailable"}


def fetch_derivatives_metrics(symbol: str) -> dict[str, Any]:
    """Maps to get_global_crypto_derivatives_metrics — CMC only."""
    coin_id = SYMBOL_IDS.get(symbol.upper(), 1839)
    for path, params in (
        ("/v1/cryptocurrency/derivatives/latest", {"id": coin_id}),
        ("/v1/global-metrics/quotes/latest", {"convert": "USD"}),
    ):
        try:
            data = _get(path, params if params else None, trial_ok=path.endswith("latest"))
            if data.get("data"):
                d = data["data"]
                if isinstance(d, dict) and str(coin_id) in d:
                    deriv = d[str(coin_id)]
                    rate = deriv.get("funding_rate") or deriv.get("latest_funding_rate")
                    if rate is not None:
                        return {"source": "cmc_rest", "funding_rate": float(rate)}
        except Exception:
            continue
    return {"source": "unavailable"}


def fetch_crypto_metrics(symbol: str) -> dict[str, Any]:
    """Maps to get_crypto_metrics — CMC REST only."""
    coin_id = SYMBOL_IDS.get(symbol.upper(), 1839)
    try:
        data = _get(f"/v1/cryptocurrency/metrics/latest?id={coin_id}")
        if data.get("data"):
            m = data["data"]
            if isinstance(m, list):
                m = m[0]
            holder_chg = m.get("holder_change_7d") or m.get("holders_change_percentage_7d")
            concentration = m.get("holder_concentration") or m.get("top_holders_concentration")
            return {
                "source": "cmc_rest",
                "holder_change_7d": float(holder_chg or 0) / (100.0 if abs(float(holder_chg or 0)) > 1 else 1),
                "holder_concentration": float(concentration or 0),
            }
    except Exception:
        pass
    return {"source": "unavailable"}


def _sector_rank_from_narratives(narratives: list[dict], symbol: str) -> int:
    sym = symbol.upper()
    for i, n in enumerate(narratives, start=1):
        coins = [c.get("symbol", "").upper() for c in n.get("coins", [])]
        if sym in coins:
            return i
    return 60


def fetch_trending_narratives(symbol: str) -> dict[str, Any]:
    """Maps to trending_crypto_narratives — CMC REST only."""
    try:
        data = _get("/v1/cryptocurrency/narratives/trending")
        narratives = data.get("data", [])[:50]
        rank = _sector_rank_from_narratives(narratives, symbol)
        matched = rank <= 50
        return {
            "source": "cmc_rest",
            "sector_rank": rank,
            "matched": matched,
            "narrative_momentum": 0.5 if rank <= 10 else (0.0 if rank > 50 else 0.2),
        }
    except Exception:
        pass
    return {"source": "unavailable"}


def _cmc_complete(bundle: dict[str, Any]) -> bool:
    tools = bundle.get("mcp_tools", {})
    required = (
        "get_crypto_quotes_latest",
        "get_global_crypto_derivatives_metrics",
        "get_crypto_metrics",
        "trending_crypto_narratives",
    )
    for name in required:
        payload = tools.get(name, {})
        if payload.get("source") == "unavailable":
            return False
    return True


def fetch_live_bundle(symbol: str = "BNB") -> dict[str, Any]:
    symbol = symbol.upper()
    bundle: dict[str, Any] = {
        "symbol": symbol,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "mcp_tools": {},
        "sources": [],
        "errors": [],
    }

    try:
        quotes = fetch_quotes_latest(symbol)
        bundle["quotes"] = quotes
        bundle["mcp_tools"]["get_crypto_quotes_latest"] = quotes
        bundle["sources"].append("get_crypto_quotes_latest")
    except Exception as e:
        bundle["errors"].append(f"quotes: {e}")

    try:
        fg = fetch_fear_greed_latest()
        bundle["fear_greed"] = fg
        bundle["mcp_tools"]["get_global_metrics_latest"] = fg
        bundle["sources"].append("get_global_metrics_latest")
    except Exception as e:
        bundle["errors"].append(f"fear_greed: {e}")

    try:
        ta = fetch_technical_analysis(symbol)
        bundle["technical_analysis"] = ta
        bundle["mcp_tools"]["get_crypto_technical_analysis"] = ta
        if ta.get("source") == "cmc_rest":
            bundle["sources"].append("get_crypto_technical_analysis")
        else:
            bundle["errors"].append("technical_analysis: CMC unavailable")
    except Exception as e:
        bundle["errors"].append(f"technical_analysis: {e}")

    try:
        deriv = fetch_derivatives_metrics(symbol)
        bundle["derivatives"] = deriv
        bundle["mcp_tools"]["get_global_crypto_derivatives_metrics"] = deriv
        if deriv.get("source") == "cmc_rest":
            bundle["sources"].append("get_global_crypto_derivatives_metrics")
        else:
            bundle["errors"].append("derivatives: CMC funding unavailable for asset")
    except Exception as e:
        bundle["errors"].append(f"derivatives: {e}")

    try:
        metrics = fetch_crypto_metrics(symbol)
        bundle["crypto_metrics"] = metrics
        bundle["mcp_tools"]["get_crypto_metrics"] = metrics
        if metrics.get("source") == "cmc_rest":
            bundle["sources"].append("get_crypto_metrics")
        else:
            bundle["errors"].append("crypto_metrics: CMC unavailable")
    except Exception as e:
        bundle["errors"].append(f"crypto_metrics: {e}")

    try:
        narr = fetch_trending_narratives(symbol)
        bundle["narratives"] = narr
        bundle["mcp_tools"]["trending_crypto_narratives"] = narr
        if narr.get("source") == "cmc_rest":
            bundle["sources"].append("trending_crypto_narratives")
        else:
            bundle["errors"].append("narratives: CMC unavailable")
    except Exception as e:
        bundle["errors"].append(f"narratives: {e}")

    bundle["cmc_data_complete"] = _cmc_complete(bundle)
    bundle["sources"] = list(dict.fromkeys(bundle["sources"]))
    return bundle


def bundle_to_decision_row(bundle: dict[str, Any]) -> dict[str, Any]:
    quotes = bundle.get("quotes", {})
    close = float(quotes.get("price", 0))
    fg = float(bundle.get("fear_greed", {}).get("value", 50))

    deriv = bundle.get("derivatives", {})
    funding = float(deriv.get("funding_rate", 0.0)) if deriv.get("source") == "cmc_rest" else 0.0

    ta = bundle.get("technical_analysis", {})
    ema21 = float(ta.get("ema21", close)) if ta.get("source") == "cmc_rest" else close

    metrics = bundle.get("crypto_metrics", {})
    holder_chg = float(metrics.get("holder_change_7d", 0.0)) if metrics.get("source") == "cmc_rest" else 0.0
    concentration = float(metrics.get("holder_concentration", 0.0)) if metrics.get("source") == "cmc_rest" else 0.0

    narr = bundle.get("narratives", {})
    if narr.get("source") == "cmc_rest":
        sector_rank = int(narr.get("sector_rank", 60))
        narrative_score = float(narr.get("narrative_momentum", 0.0))
    else:
        sector_rank = 60
        narrative_score = 0.0

    return {
        "timestamp": bundle.get("fetched_at", "live")[:10],
        "close": close,
        "ema21": ema21,
        "volume_24h": float(quotes.get("volume_24h", 0)),
        "fear_greed": fg,
        "funding_rate": funding,
        "holder_change_7d": holder_chg,
        "holder_concentration": concentration,
        "sector_rank": sector_rank,
        "narrative_score": narrative_score,
        "cmc_data_complete": bool(bundle.get("cmc_data_complete")),
    }


def fetch_live_snapshot(symbol: str = "BNB") -> dict[str, Any]:
    bundle = fetch_live_bundle(symbol)
    quotes = bundle.get("quotes", {})
    fg = bundle.get("fear_greed", {})
    return {
        "symbol": symbol.upper(),
        "price": quotes.get("price", 0),
        "volume_24h": quotes.get("volume_24h", 0),
        "percent_change_7d": quotes.get("percent_change_7d", 0),
        "fear_greed": fg.get("value", 50),
        "source": "coinmarketcap_live",
        "cmc_sources": bundle.get("sources", []),
        "cmc_data_complete": bundle.get("cmc_data_complete", False),
    }
