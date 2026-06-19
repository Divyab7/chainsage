"""Funding mean-reversion sub-strategy for high-volatility regimes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from chainsage.signals.fusion import Decision
from chainsage.signals.thresholds import IS_PERIOD_END, IS_PERIOD_START

# Relaxed static fallbacks (committed data rarely prints below -0.01%)
FUNDING_LONG_FALLBACK = -0.00005  # -0.005%
FUNDING_FLAT = 0.0003  # +0.03% — expensive to stay long
MR_TARGET_EXPOSURE = 0.6
IS_FUNDING_QUANTILE = 0.10

_long_threshold_cache: dict[str, float] = {}
_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


@dataclass
class FundingSignal:
    direction: str  # "LONG" | "FLAT"
    conviction: float
    target_exposure: float
    reason: str


def discover_funding_long_threshold(df: pd.DataFrame, asset: str) -> float:
    """
    IS-only funding floor (no OOS peeking): 10th percentile of in-sample prints.
    Calibrated from the full committed CSV, not the active backtest window.
    """
    if asset in _long_threshold_cache:
        return _long_threshold_cache[asset]

    cal_path = _DATA_ROOT / f"{asset.lower()}_daily.csv"
    if cal_path.exists():
        from chainsage.engine.backtest import load_market_csv

        cal_df = load_market_csv(cal_path)
    else:
        cal_df = df

    start, end = pd.Timestamp(IS_PERIOD_START), pd.Timestamp(IS_PERIOD_END)
    mask = (cal_df["timestamp"] >= start) & (cal_df["timestamp"] <= end)
    is_funding = cal_df.loc[mask, "funding_rate"].dropna()

    if len(is_funding) < 20:
        threshold = FUNDING_LONG_FALLBACK
    else:
        q10 = float(is_funding.quantile(IS_FUNDING_QUANTILE))
        threshold = min(q10, FUNDING_LONG_FALLBACK)

    _long_threshold_cache[asset] = threshold
    return threshold


def clear_threshold_cache() -> None:
    _long_threshold_cache.clear()


def funding_signal(
    funding_rate: float,
    regime: str,
    long_threshold: float,
) -> FundingSignal | None:
    """
    Mean-reversion leg — only active in high vol.
    Long when funding is at or below the IS-discovered cheap-funding floor.
    """
    if regime != "high":
        return None

    if funding_rate > FUNDING_FLAT:
        return FundingSignal(
            direction="FLAT",
            conviction=0.0,
            target_exposure=0.0,
            reason=f"funding {funding_rate:.4%} > 0.03% in high vol → flat",
        )

    is_cheap = (
        funding_rate < long_threshold
        if long_threshold < 0
        else funding_rate <= long_threshold
    )
    if is_cheap:
        conviction = min(max(abs(funding_rate) * 10_000, 0.4), 1.0)
        return FundingSignal(
            direction="LONG",
            conviction=conviction,
            target_exposure=MR_TARGET_EXPOSURE,
            reason=f"funding {funding_rate:.4%} < IS q10 ({long_threshold:.6f}) in high vol",
        )

    return None


class FundingMeanReversion:
    """Long crowded shorts / cheap funding in high-volatility regimes."""

    name = "funding_mean_reversion"

    def evaluate(
        self,
        df: pd.DataFrame,
        idx: int,
        asset: str = "BNB",
        volatility_regime: str = "high",
    ) -> Decision:
        row = df.iloc[idx]
        ts = str(row["timestamp"])[:10]
        funding = float(row.get("funding_rate", 0.0))
        long_threshold = discover_funding_long_threshold(df, asset)

        layers = {
            "mean_reversion": {
                "score": 0.0,
                "reasons": [
                    f"funding_rate={funding:.6f}",
                    f"is_long_threshold={long_threshold:.6f}",
                ],
            }
        }

        sig = funding_signal(funding, volatility_regime, long_threshold)
        if sig is None:
            return Decision(
                timestamp=ts,
                asset=asset,
                signal="flat",
                conviction=0.0,
                target_exposure=0.0,
                regime="high-vol-neutral",
                layers=layers,
                falsifiers=[],
                reasons=["no mean-reversion edge in high vol — flat"],
                sub_strategy=self.name,
            )

        if sig.direction == "LONG":
            return Decision(
                timestamp=ts,
                asset=asset,
                signal="long",
                conviction=sig.conviction,
                target_exposure=sig.target_exposure,
                regime="high-vol-mean-reversion",
                layers=layers,
                falsifiers=[],
                reasons=[sig.reason],
                sub_strategy=self.name,
            )

        return Decision(
            timestamp=ts,
            asset=asset,
            signal="flat",
            conviction=0.0,
            target_exposure=0.0,
            regime="high-vol-mean-reversion",
            layers=layers,
            falsifiers=[],
            reasons=[sig.reason],
            sub_strategy=self.name,
        )
