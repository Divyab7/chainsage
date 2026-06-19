"""Trade log extraction from backtest simulation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

from chainsage.signals.fusion import Decision
from chainsage.signals.ensemble_strategy import get_decision_fn

DecisionFn = Callable[[pd.DataFrame, int, str], Decision]


def extract_trades(
    df: pd.DataFrame,
    asset: str,
    warmup: int = 35,
    fee_bps: float = 10.0,
    mode: str = "aggressive",
    decision_fn: DecisionFn | None = None,
) -> pd.DataFrame:
    """Record exposure changes as trade events."""
    from contextlib import nullcontext

    from chainsage.config.load import apply_strategy_config

    fee = fee_bps / 10_000
    trades: list[dict[str, Any]] = []
    prev_exp = 0.0
    evaluator = decision_fn or get_decision_fn(mode)
    config_ctx = apply_strategy_config() if mode == "conservative" else nullcontext()

    with config_ctx:
        for i in range(warmup, len(df)):
            decision = evaluator(df, i, asset=asset)
            exp = decision.target_exposure if decision.signal == "long" else 0.0
            if abs(exp - prev_exp) < 1e-6:
                continue

            ts = str(df.iloc[i]["timestamp"])[:10]
            price = float(df.iloc[i]["close"])
            action = "enter" if exp > prev_exp else "exit"
            trades.append(
                {
                    "timestamp": ts,
                    "asset": asset,
                    "action": action,
                    "exposure_from": round(prev_exp, 3),
                    "exposure_to": round(exp, 3),
                    "price": round(price, 4),
                    "regime": decision.regime,
                    "conviction": round(decision.conviction, 3),
                    "sub_strategy": decision.sub_strategy or "",
                    "fee_bps": fee_bps,
                }
            )
            prev_exp = exp
            prev_exp = exp

    return pd.DataFrame(trades)


def write_trades_csv(df: pd.DataFrame, asset: str, out_dir: Path, suffix: str = "") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{asset.lower()}{suffix}_trades.csv"
    df.to_csv(path, index=False)
    return path
