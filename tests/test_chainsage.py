"""Tests for ChainSage conviction gate and research pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from chainsage.adapters.indicators import compute_ta, macd_histogram, rsi
from chainsage.engine.backtest import load_market_csv, run_backtest
from chainsage.engine.event_study import run_event_study
from chainsage.engine.trades import extract_trades
from chainsage.signals.derivatives import score_derivatives
from chainsage.signals.fusion import evaluate_snapshot, compute_conviction, compute_target_exposure
from chainsage.signals.thresholds import GATE_THRESHOLD
from chainsage.signals.narrative import score_narrative
from chainsage.signals.onchain import score_onchain
from chainsage.spec import build_strategy_spec

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


@pytest.fixture
def bnb_df() -> pd.DataFrame:
    return load_market_csv(DATA / "bnb_daily.csv")


def test_evaluate_returns_flat_or_long(bnb_df: pd.DataFrame) -> None:
    d = evaluate_snapshot(bnb_df, 100, asset="BNB")
    assert d.signal in ("long", "flat")
    assert 0.0 <= d.conviction <= 1.0
    assert d.regime in ("aligned", "divergent", "risk-off", "data-incomplete")


def test_hard_stop_extreme_fear(bnb_df: pd.DataFrame) -> None:
    df = bnb_df.copy()
    df.loc[df.index[-1], "fear_greed"] = 10
    d = evaluate_snapshot(df, len(df) - 1, asset="BNB")
    assert d.signal == "flat"
    assert d.conviction == 0.0
    assert "fng < 15" in d.falsifiers


def test_backtest_has_equity_curve(bnb_df: pd.DataFrame) -> None:
    result = run_backtest(bnb_df, asset="BNB")
    assert len(result["equity_curve"]) > 50


def test_strategy_spec_has_trust_wallet(bnb_df: pd.DataFrame) -> None:
    decision = evaluate_snapshot(bnb_df, len(bnb_df) - 1, asset="CAKE")
    spec = build_strategy_spec(decision)
    assert "trust_wallet" in spec
    assert spec["trust_wallet"]["bsc_contract"]


def test_strategy_spec_serializable(bnb_df: pd.DataFrame) -> None:
    decision = evaluate_snapshot(bnb_df, len(bnb_df) - 1, asset="BNB")
    json.dumps(build_strategy_spec(decision))


def test_sample_data_columns() -> None:
    for asset in ("bnb", "cake", "twt", "btc"):
        df = pd.read_csv(DATA / f"{asset}_daily.csv")
        assert len(df) > 100
        for col in ("funding_rate", "fear_greed", "holder_trend", "narrative_score"):
            assert col in df.columns


def test_derivatives_score_bounded(bnb_df: pd.DataFrame) -> None:
    row = bnb_df.iloc[50]
    score, _ = score_derivatives(row, bnb_df.iloc[:51])
    assert -1.0 <= score <= 1.0


def test_onchain_score_bounded(bnb_df: pd.DataFrame) -> None:
    row = bnb_df.iloc[50]
    score, _ = score_onchain(row, bnb_df.iloc[:51])
    assert -1.0 <= score <= 1.0


def test_narrative_score_bounded(bnb_df: pd.DataFrame) -> None:
    row = bnb_df.iloc[50]
    score, _ = score_narrative(row, bnb_df.iloc[:51])
    assert -1.0 <= score <= 1.0


def test_gate_threshold_constant() -> None:
    assert GATE_THRESHOLD == 1.0


def test_trades_extracted(bnb_df: pd.DataFrame) -> None:
    trades = extract_trades(bnb_df, "BNB")
    assert "action" in trades.columns or trades.empty


def test_event_study_buckets(bnb_df: pd.DataFrame) -> None:
    es = run_event_study(bnb_df, "BNB")
    assert "buckets" in es
    assert len(es["rows"]) > 0


def test_event_study_no_lookahead(bnb_df: pd.DataFrame) -> None:
    es = run_event_study(bnb_df, "BNB")
    last_row_date = es["rows"][-1]["timestamp"]
    assert last_row_date < str(bnb_df["timestamp"].iloc[-30])[:10]


def test_rsi_range(bnb_df: pd.DataFrame) -> None:
    val = rsi(bnb_df["close"].iloc[:100])
    assert 0 <= val <= 100


def test_compute_ta_keys(bnb_df: pd.DataFrame) -> None:
    ta = compute_ta(bnb_df["close"].iloc[:100])
    assert "rsi14" in ta and "ema21" in ta


def test_macd_histogram_finite(bnb_df: pd.DataFrame) -> None:
    h = macd_histogram(bnb_df["close"].iloc[:100])
    assert pd.notna(h)


def test_backtest_metrics_keys(bnb_df: pd.DataFrame) -> None:
    m = run_backtest(bnb_df, "BNB")["metrics"]
    for k in ("total_return", "max_drawdown", "sharpe_ratio", "win_rate"):
        assert k in m


def test_decision_to_dict_roundtrip(bnb_df: pd.DataFrame) -> None:
    d = evaluate_snapshot(bnb_df, 200, asset="BNB")
    parsed = json.loads(json.dumps(d.to_dict()))
    assert parsed["signal"] == d.signal


def test_aligned_has_exposure_when_long(bnb_df: pd.DataFrame) -> None:
    for i in range(50, len(bnb_df)):
        d = evaluate_snapshot(bnb_df, i, asset="BNB")
        if d.signal == "long":
            assert d.target_exposure > 0
            return
    pytest.skip("no long signal in sample")


def test_conviction_formula() -> None:
    assert compute_conviction([0.5, 0.5, 0.0]) == 0.667
    assert compute_conviction([1.0, 1.0, 0.5]) == 0.917
    assert compute_target_exposure(0.667, "long") == round(0.667 * 0.8, 3)
    assert compute_target_exposure(0.667, "flat") == 0.0


def test_standard_falsifiers_in_spec(bnb_df: pd.DataFrame) -> None:
    decision = evaluate_snapshot(bnb_df, len(bnb_df) - 1, asset="BNB")
    spec = build_strategy_spec(decision)
    assert "fng < 15" in spec["scoring_rules"]["falsifiers"]["hard_stop"]
    assert spec["position_sizing"]["max_position_size"] == 0.8
    assert spec["validation_methodology"]["oos_period"].startswith("2024-07-01")


def test_falsifiers_on_divergence(bnb_df: pd.DataFrame) -> None:
    df = bnb_df.copy()
    idx = len(df) - 1
    df.loc[idx, "funding_rate"] = -0.01
    df.loc[idx, "holder_trend"] = 0.5
    d = evaluate_snapshot(df, idx, asset="BNB")
    if d.regime == "divergent":
        assert d.signal == "flat"


def test_spec_ecosystem_bsc_tokens() -> None:
    from chainsage.adapters.cmc import BSC_TOKENS

    assert "CAKE" in BSC_TOKENS
    assert BSC_TOKENS["CAKE"]["contract"].startswith("0x")


def test_is_oos_contamination_raises() -> None:
    import pytest
    from chainsage.engine.backtest import assert_no_is_oos_contamination

    assert_no_is_oos_contamination("2023-01-01", "2024-06-30")
    assert_no_is_oos_contamination("2024-07-01", "2026-06-01")
    with pytest.raises(AssertionError, match="IS/OOS contamination"):
        assert_no_is_oos_contamination("2024-01-01", "2025-01-01")


def test_is_oos_period_backtest(bnb_df: pd.DataFrame) -> None:
    from chainsage.engine.backtest import run_backtest_period
    from chainsage.signals.thresholds import IS_PERIOD_END, IS_PERIOD_START, OOS_PERIOD_END, OOS_PERIOD_START

    is_r = run_backtest_period(bnb_df, IS_PERIOD_START, IS_PERIOD_END, asset="BNB")
    oos_r = run_backtest_period(bnb_df, OOS_PERIOD_START, OOS_PERIOD_END, asset="BNB")
    assert is_r["period_label"] == "in_sample"
    assert oos_r["period_label"] == "out_of_sample"
    assert "calmar_ratio" in is_r["metrics"]


def test_sensitivity_runs(bnb_df: pd.DataFrame) -> None:
    from chainsage.engine.sensitivity import run_sensitivity_analysis

    out = run_sensitivity_analysis(bnb_df, "BNB")
    assert len(out["rows"]) == 4
    assert out["base_oos_sharpe"] is not None


def test_atr_pct_positive(bnb_df: pd.DataFrame) -> None:
    from chainsage.adapters.indicators import atr_pct

    val = atr_pct(bnb_df["close"].iloc[:100], 14)
    assert val >= 0.0


def test_volatility_regime_detect(bnb_df: pd.DataFrame) -> None:
    from chainsage.signals.regime import detect_volatility_regime

    regime, atr = detect_volatility_regime(bnb_df, 100)
    assert regime in ("high", "low", "normal")
    assert atr >= 0.0


def test_ensemble_selects_sub_strategy(bnb_df: pd.DataFrame) -> None:
    from chainsage.signals.ensemble_strategy import evaluate_snapshot_ensemble

    d = evaluate_snapshot_ensemble(bnb_df, 100, asset="BNB")
    assert d.sub_strategy in ("funding_mean_reversion", "momentum_gates")
    assert "ensemble" in d.layers


def test_conservative_config_loads() -> None:
    from chainsage.config.load import load_conservative_config

    cfg = load_conservative_config()
    assert cfg["GATE_THRESHOLD"] == 1.5


def test_conservative_backtest_oos(bnb_df: pd.DataFrame) -> None:
    from chainsage.engine.backtest import run_backtest_period
    from chainsage.signals.thresholds import OOS_PERIOD_END, OOS_PERIOD_START

    r = run_backtest_period(
        bnb_df, OOS_PERIOD_START, OOS_PERIOD_END, asset="BNB", mode="conservative"
    )
    assert r["mode"] == "conservative"
    assert "sharpe_ratio" in r["metrics"]


def test_mean_reversion_long_on_negative_funding(bnb_df: pd.DataFrame) -> None:
    from chainsage.signals.mean_reversion import FundingMeanReversion, clear_threshold_cache

    clear_threshold_cache()
    df = bnb_df.copy()
    idx = len(df) - 1
    df.loc[idx, "funding_rate"] = -0.0002
    d = FundingMeanReversion().evaluate(df, idx, asset="BNB", volatility_regime="high")
    assert d.signal == "long"
    assert d.sub_strategy == "funding_mean_reversion"
    assert d.target_exposure == 0.6


def test_mean_reversion_is_quantile_threshold(bnb_df: pd.DataFrame) -> None:
    from chainsage.signals.mean_reversion import (
        clear_threshold_cache,
        discover_funding_long_threshold,
        funding_signal,
    )

    clear_threshold_cache()
    th = discover_funding_long_threshold(bnb_df, "BNB")
    assert th <= -0.00005
    assert funding_signal(0.0, "high", th) is None
    sig = funding_signal(-0.0001, "high", th)
    assert sig is not None
    assert sig.direction == "LONG"


def test_signal_independent_of_future_data(bnb_df: pd.DataFrame) -> None:
    """Critical: signal at t must not change if we truncate future data."""
    from chainsage.signals.fusion import evaluate_snapshot

    idx = 200
    decision_full = evaluate_snapshot(bnb_df, idx, asset="BNB")
    truncated = bnb_df.iloc[: idx + 1].copy()
    decision_truncated = evaluate_snapshot(truncated, idx, asset="BNB")

    assert decision_full.signal == decision_truncated.signal
    assert decision_full.conviction == decision_truncated.conviction


def test_funding_signal_ignores_low_vol() -> None:
    from chainsage.signals.mean_reversion import funding_signal

    assert funding_signal(-0.001, "low", -0.00005) is None


def test_manifest_exists_after_backtest() -> None:
    manifest = ROOT / "reports" / "verify_manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert "BTC" in data or "BNB" in data


def test_deflated_sharpe_adjusts_for_trials() -> None:
    from chainsage.engine.metrics import deflated_sharpe

    base = deflated_sharpe(0.91, n_trials=1, n_observations=250)
    adjusted = deflated_sharpe(0.91, n_trials=3, n_observations=250)
    assert adjusted <= base
    assert adjusted < 0.91


def test_probability_of_overfitting_bounds(bnb_df: pd.DataFrame) -> None:
    from chainsage.engine.backtest import run_backtest_period
    from chainsage.engine.institutional import _strategy_returns_from_equity
    from chainsage.engine.validation import probability_of_overfitting
    from chainsage.signals.thresholds import IS_PERIOD_END, IS_PERIOD_START

    is_bt = run_backtest_period(bnb_df, IS_PERIOD_START, IS_PERIOD_END, "BNB")
    returns = _strategy_returns_from_equity(is_bt["equity_curve"])
    pbo = probability_of_overfitting(returns)
    assert 0.0 <= pbo <= 1.0


def test_analyze_decay() -> None:
    from chainsage.engine.decay import analyze_decay

    out = analyze_decay(
        {"metrics": {"sharpe_ratio": 0.91}},
        {"metrics": {"sharpe_ratio": 0.0}},
    )
    assert out["decay_ratio"] == 0.0
    assert out["interpretation"] == "regime_mismatch"


def test_walk_forward_analysis(bnb_df: pd.DataFrame) -> None:
    from chainsage.engine.walkforward import walk_forward_analysis

    wf = walk_forward_analysis(bnb_df, "BNB", max_windows=4)
    assert "n_windows" in wf
    assert "mean_sharpe" in wf
    assert wf["train_months"] == 6
