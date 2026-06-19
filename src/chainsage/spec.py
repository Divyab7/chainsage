"""Strategy spec export for Track 2 deliverable."""

from __future__ import annotations

from typing import Any

from chainsage.adapters.cmc import BSC_TOKENS
from chainsage.signals.fusion import Decision
from chainsage.signals.thresholds import (
    COMMISSION,
    GATE_THRESHOLD,
    HARD_STOP_FALSIFIERS,
    HELD_OUT_NOTE,
    IMPACT_MODEL,
    IS_PERIOD_END,
    IS_PERIOD_START,
    MAX_POSITION_SIZE,
    OOS_PERIOD_END,
    OOS_PERIOD_START,
    PERFORMANCE_TARGETS,
    SLIPPAGE,
    SOFT_WARNING_FALSIFIERS,
)


def _benchmark_comparison(backtest: dict[str, Any] | None, asset: str) -> dict[str, Any] | None:
    if not backtest:
        return None
    m = backtest.get("metrics", backtest)
    b = backtest.get("benchmark_metrics", {})
    if not m or not b:
        return None
    prefix = asset.lower()
    return {
        "strategy_return": round(m["total_return"], 4),
        f"{prefix}_buyhold_return": round(b["total_return"], 4),
        "strategy_sharpe": round(m["sharpe_ratio"], 3),
        f"{prefix}_sharpe": round(b["sharpe_ratio"], 3),
        "max_drawdown": round(m["max_drawdown"], 4),
        "benchmark_max_drawdown": round(b["max_drawdown"], 4),
        "time_in_market": round(m["days_in_market_pct"], 3),
    }


def build_strategy_spec(
    decision: Decision,
    backtest_summary: dict[str, Any] | None = None,
    cmc_sources: list[str] | None = None,
    mcp_tools: dict[str, Any] | None = None,
) -> dict[str, Any]:
    asset = decision.asset.upper()
    bsc = BSC_TOKENS.get(asset, {})

    spec: dict[str, Any] = {
        "name": "ChainSage Conviction Gate",
        "version": "0.5.0",
        "track": "BNB Hack Track 2 — Strategy Skills",
        "description": (
            "Only trade when derivatives, on-chain holder, and narrative layers align. "
            "Default to flat when they disagree."
        ),
        "universe": ["BNB", "CAKE", "TWT", "BTC"],
        "validation_methodology": {
            "is_period": f"{IS_PERIOD_START} to {IS_PERIOD_END}",
            "oos_period": f"{OOS_PERIOD_START} to {OOS_PERIOD_END}",
            "held_out_note": HELD_OUT_NOTE,
            "walk_forward": "6-month windows, expanding",
            "no_lookahead": "Signals computed only with data available at timestamp",
            "verify": "chainsage verify re-derives headline numbers from committed data/",
        },
        "performance_targets": PERFORMANCE_TARGETS,
        "transaction_costs": {
            "commission": COMMISSION,
            "slippage": SLIPPAGE,
            "impact_model": IMPACT_MODEL,
        },
        "scoring_rules": {
            "derivatives": {
                "score": (
                    "funding = get_global_crypto_derivatives_metrics().funding_rate; "
                    "if funding > 0.015%: +1.0; elif funding > 0.008%: +0.5; "
                    "elif funding < -0.015%: -1.0; elif funding < -0.008%: -0.5; else: 0.0"
                ),
            },
            "on_chain": {
                "score": (
                    "h = get_crypto_metrics().holder_change_7d; "
                    "if h > 3%: +1.0; elif h > 1.5%: +0.5; "
                    "elif h < -3%: -1.0; elif h < -1.5%: -0.5; else: 0.0"
                ),
            },
            "narrative": {
                "score": (
                    "rank = trending_crypto_narratives sector rank; fng = get_global_metrics_latest(); "
                    "if rank <= 5 AND fng >= 50: +1.0; elif rank <= 10 AND fng >= 40: +0.5; "
                    "elif fng < 15 OR rank > 50: -1.0; elif fng < 30 OR rank > 40: -0.5; else: 0.0"
                ),
            },
            "conviction_calculation": (
                "raw_score = sum(layer_scores); "
                "conviction = (raw_score + 3) / 6; "
                f"target_exposure = conviction * {MAX_POSITION_SIZE} when signal=long"
            ),
            "falsifiers": {
                "hard_stop": HARD_STOP_FALSIFIERS,
                "soft_warning": SOFT_WARNING_FALSIFIERS,
                "override": "ANY hard_stop triggers → immediate flat, conviction = 0",
            },
        },
        "ecosystem": {
            "chain": "BNB Smart Chain (BSC)",
            "focus_tokens": ["BNB", "CAKE", "TWT"],
            "data_layer": "CoinMarketCap AI Agent Hub (MCP)",
            "bsc_tokens": BSC_TOKENS,
            "execution_path_track1": {
                "signing": "Trust Wallet Agent Kit (TWAK) — self-custody local signing",
                "sdk": "BNB AI Agent SDK — PancakeSwap swap execution on BSC",
                "example": (
                    f"When signal=long on {asset}, TWAK agent swaps USDT → {asset} "
                    f"on {bsc.get('dex', 'PancakeSwap')} at target_exposure"
                ),
            },
        },
        "trust_wallet": {
            "action": "hold" if decision.signal == "long" else "cash",
            "target_token": asset,
            "target_exposure_pct": round(decision.target_exposure * 100, 1),
            "bsc_contract": bsc.get("contract"),
            "dex": bsc.get("dex", "PancakeSwap"),
            "note": "Skill emits allocation only — TWAK signs and executes on user rules",
        },
        "timeframe": "1D",
        "entry_rules": [
            f"sum(layer_scores) >= {GATE_THRESHOLD}",
            "No layer scores <= -0.5",
            "No hard_stop falsifier active",
            "All required CMC MCP tool payloads available",
        ],
        "exit_rules": [
            "Any layer turns <= -0.5",
            "Any hard_stop falsifier triggers",
            "CMC derivatives or metrics data becomes unavailable",
        ],
        "position_sizing": {
            "method": "conviction_scaled",
            "min_exposure": 0.0,
            "max_position_size": MAX_POSITION_SIZE,
            "formula": f"target_exposure = conviction * {MAX_POSITION_SIZE} when long",
            "example": "conviction 0.67 → target_exposure 0.536 (67% × 80%)",
        },
        "risk_limits": {
            "max_drawdown_gate": 0.25,
            "default_signal": "flat",
            "long_only": True,
        },
        "cmc_data_sources": cmc_sources
        or [
            "get_crypto_quotes_latest",
            "get_crypto_technical_analysis",
            "get_global_metrics_latest",
            "get_global_crypto_derivatives_metrics",
            "get_crypto_metrics",
            "trending_crypto_narratives",
        ],
        "current_decision": decision.to_dict(),
    }
    if mcp_tools:
        spec["mcp_tool_payloads"] = mcp_tools
    if backtest_summary:
        spec["backtest_summary"] = _benchmark_comparison(backtest_summary, asset) or backtest_summary
    return spec
