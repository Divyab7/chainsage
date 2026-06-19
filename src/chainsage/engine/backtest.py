"""Long-only backtest for conviction-gated strategy."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from chainsage.config.load import apply_strategy_config
from chainsage.engine.metrics import summarize
from chainsage.signals.ensemble_strategy import get_decision_fn
from chainsage.signals.fusion import Decision
from chainsage.signals.thresholds import (
    IS_PERIOD_END,
    IS_PERIOD_START,
    OOS_PERIOD_END,
    OOS_PERIOD_START,
    ROUND_TRIP_COST,
)

DecisionFn = Callable[[pd.DataFrame, int, str], Decision]

IS_END = IS_PERIOD_END
OOS_START = OOS_PERIOD_START


def assert_no_is_oos_contamination(start: str, end: str) -> None:
    """CRITICAL: each backtest run must be wholly in-sample OR wholly out-of-sample."""
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    split = pd.Timestamp(OOS_START)
    is_end = pd.Timestamp(IS_END)

    in_is = end_ts <= is_end
    in_oos = start_ts >= split
    if not (in_is or in_oos):
        raise AssertionError(
            f"IS/OOS contamination! Period {start} → {end} crosses split at {OOS_START}"
        )


def load_market_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def filter_period(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    mask = (df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)
    return df.loc[mask].copy().reset_index(drop=True)


def run_backtest(
    df: pd.DataFrame,
    asset: str = "BNB",
    warmup: int = 35,
    fee_bps: float | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    mode: str = "aggressive",
    decision_fn: DecisionFn | None = None,
) -> dict[str, Any]:
    """
    Simulate: hold target_exposure fraction of capital when signal=long.
    Signal at day t applies to return from t to t+1 (no lookahead).
    Transaction costs: commission 10 bps + slippage 5 bps (fixed impact model).

    mode: aggressive | conservative | ensemble
    """
    if period_start and period_end:
        assert_no_is_oos_contamination(period_start, period_end)

    evaluator = decision_fn or get_decision_fn(mode)
    config_ctx = apply_strategy_config() if mode == "conservative" else nullcontext()

    fee = ROUND_TRIP_COST if fee_bps is None else fee_bps / 10_000
    exposures: list[float] = []
    decisions_log: list[dict] = []
    sub_strategy_counts: dict[str, int] = {}
    vol_regime_counts: dict[str, int] = {}

    with config_ctx:
        for i in range(len(df)):
            if i < warmup:
                exposures.append(0.0)
                continue
            decision = evaluator(df, i, asset=asset)
            exp = decision.target_exposure if decision.signal == "long" else 0.0
            exposures.append(exp)
            if decision.sub_strategy:
                sub_strategy_counts[decision.sub_strategy] = (
                    sub_strategy_counts.get(decision.sub_strategy, 0) + 1
                )
            ens = decision.layers.get("ensemble", {})
            for reason in ens.get("reasons", []):
                if reason.startswith("volatility_regime="):
                    regime = reason.split("=", 1)[1]
                    vol_regime_counts[regime] = vol_regime_counts.get(regime, 0) + 1
            if i == len(df) - 1 or i % max(1, len(df) // 20) == 0:
                decisions_log.append(decision.to_dict())

    df = df.copy()
    df["exposure"] = exposures
    df["market_return"] = df["close"].pct_change().fillna(0.0)
    df["exposure_shifted"] = df["exposure"].shift(1).fillna(0.0)
    df["turnover"] = df["exposure_shifted"].diff().abs().fillna(df["exposure_shifted"].abs())
    df["strategy_return"] = (
        df["exposure_shifted"] * df["market_return"] - df["turnover"] * fee
    )
    df["equity"] = (1 + df["strategy_return"]).cumprod()
    df["benchmark_equity"] = (1 + df["market_return"]).cumprod()

    strat = df["strategy_return"].iloc[warmup:]
    eq = df["equity"].iloc[warmup:]
    bench_eq = df["benchmark_equity"].iloc[warmup:]
    exp = df["exposure_shifted"].iloc[warmup:]

    label_start = period_start or str(df["timestamp"].iloc[warmup])[:10]
    label_end = period_end or str(df["timestamp"].iloc[-1])[:10]

    return {
        "asset": asset,
        "mode": mode,
        "metrics": summarize(strat, eq, exp),
        "benchmark_metrics": summarize(df["market_return"].iloc[warmup:], bench_eq),
        "equity_curve": [
            {
                "date": str(r.timestamp)[:10],
                "strategy": round(r.equity, 4),
                "benchmark": round(r.benchmark_equity, 4),
            }
            for r in df.iloc[warmup:].itertuples()
        ],
        "decisions_sample": decisions_log[-10:],
        "sub_strategy_counts": sub_strategy_counts,
        "volatility_regime_counts": vol_regime_counts,
        "period_start": label_start,
        "period_end": label_end,
        "period_label": _period_label(label_start, label_end),
    }


def _period_label(start: str, end: str) -> str:
    if end <= IS_END:
        return "in_sample"
    if start >= OOS_START:
        return "out_of_sample"
    return "full"


def run_backtest_period(
    df: pd.DataFrame,
    start: str,
    end: str,
    asset: str = "BNB",
    warmup: int = 35,
    mode: str = "aggressive",
    decision_fn: DecisionFn | None = None,
) -> dict[str, Any]:
    """Run backtest on a date window with IS/OOS contamination guard."""
    assert_no_is_oos_contamination(start, end)
    window = filter_period(df, start, end)
    if len(window) <= warmup:
        raise ValueError(f"Insufficient rows in {start}→{end} (need > {warmup})")
    return run_backtest(
        window,
        asset=asset,
        warmup=warmup,
        period_start=start,
        period_end=end,
        mode=mode,
        decision_fn=decision_fn,
    )


def run_is_oos_headline(
    df: pd.DataFrame,
    asset: str = "BNB",
    mode: str = "aggressive",
) -> dict[str, Any]:
    """Headline IS and OOS metrics for research / spec."""
    is_result = run_backtest_period(df, IS_PERIOD_START, IS_PERIOD_END, asset=asset, mode=mode)
    oos_result = run_backtest_period(df, OOS_PERIOD_START, OOS_PERIOD_END, asset=asset, mode=mode)
    return {
        "asset": asset,
        "mode": mode,
        "in_sample": is_result,
        "out_of_sample": oos_result,
        "is_period": f"{IS_PERIOD_START} to {IS_PERIOD_END}",
        "oos_period": f"{OOS_PERIOD_START} to {OOS_PERIOD_END}",
    }


def render_report(result: dict[str, Any]) -> str:
    m = result["metrics"]
    b = result["benchmark_metrics"]
    mode = result.get("mode", "aggressive")
    lines = [
        f"# ChainSage Backtest — {result['asset']} ({mode})",
        "",
        f"Period: {result['period_start']} → {result['period_end']}",
        f"Window: {result.get('period_label', 'full')}",
        "",
        "## Strategy vs Buy & Hold",
        "",
        "| Metric | ChainSage | Buy & Hold |",
        "|--------|----------:|-----------:|",
        f"| Total Return | {m['total_return']:.1%} | {b['total_return']:.1%} |",
        f"| Max Drawdown | {m['max_drawdown']:.1%} | {b['max_drawdown']:.1%} |",
        f"| Sharpe Ratio | {m['sharpe_ratio']:.2f} | {b['sharpe_ratio']:.2f} |",
        f"| Calmar Ratio | {m.get('calmar_ratio', 0):.2f} | — |",
        f"| Win Rate | {m['win_rate']:.1%} | — |",
        f"| Time in Market | {m.get('time_in_market', m['days_in_market_pct']):.1%} | 100% |",
        "",
        "## Philosophy",
        "",
        "ChainSage sits out when CMC-style data layers disagree. "
        "Lower drawdown matters more than chasing every rally.",
        "",
    ]
    return "\n".join(lines)
