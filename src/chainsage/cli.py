"""ChainSage CLI — backtest, live scan, spec export, fetch-data, verify."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from chainsage.engine.backtest import load_market_csv, render_report, run_backtest, run_is_oos_headline
from chainsage.engine.equity_report import write_equity_html
from chainsage.engine.research import write_research_artifacts
from chainsage.engine.trades import extract_trades, write_trades_csv
from chainsage.signals.fusion import evaluate_snapshot
from chainsage.spec import build_strategy_spec
from chainsage.verify import write_manifest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


def _ensure_data() -> bool:
    if not (DATA / "bnb_daily.csv").exists():
        print("No data found. Run: chainsage fetch-data")
        return False
    return True


def cmd_fetch_data(args: argparse.Namespace) -> int:
    load_dotenv(ROOT / ".env")
    from chainsage.data.fetch import fetch_all

    print("Fetching real market data (Binance + F&G + funding)...")
    fetch_all(days=args.days)
    print("\nDone. Run: chainsage backtest-all")
    return 0


def _write_backtest_artifacts(df: pd.DataFrame, asset: str, result: dict, mode: str = "aggressive") -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    asset_l = asset.lower()
    suffix = f"_{mode}" if mode != "aggressive" else ""
    (REPORTS / f"{asset_l}{suffix}_backtest.md").write_text(render_report(result), encoding="utf-8")
    (REPORTS / f"{asset_l}{suffix}_backtest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_trades_csv(extract_trades(df, asset, mode=mode), asset, REPORTS, suffix=suffix)
    write_equity_html(result, REPORTS, suffix=suffix)


def cmd_backtest(args: argparse.Namespace) -> int:
    if not _ensure_data():
        return 1
    asset = args.asset.upper()
    mode = getattr(args, "mode", "aggressive")
    df = load_market_csv(DATA / f"{asset.lower()}_daily.csv")
    result = run_backtest(df, asset=asset, mode=mode)
    _write_backtest_artifacts(df, asset, result, mode=mode)

    m, b = result["metrics"], result["benchmark_metrics"]
    print(f"\nChainSage backtest — {asset} [{mode}]")
    print(f"  Period: {result['period_start']} → {result['period_end']}")
    print(f"  Return:      {m['total_return']:>7.1%}  (buy & hold {b['total_return']:.1%})")
    print(f"  Max DD:      {m['max_drawdown']:>7.1%}  (buy & hold {b['max_drawdown']:.1%})")
    print(f"  Sharpe:      {m['sharpe_ratio']:>7.2f}  (buy & hold {b['sharpe_ratio']:.2f})")
    print(f"  In market:   {m['days_in_market_pct']:>7.1%}")
    print(f"  Artifacts:   {asset.lower()}_trades.csv, {asset.lower()}_equity.html")
    return 0


def cmd_backtest_all(args: argparse.Namespace) -> int:
    from chainsage.engine.ensemble_stats import write_ensemble_headline
    from chainsage.engine.research import print_is_oos_headline, write_research_artifacts

    mode = getattr(args, "mode", "aggressive")
    for asset in ("BNB", "CAKE", "TWT", "BTC"):
        if cmd_backtest(argparse.Namespace(asset=asset, mode=mode)) != 0:
            return 1

    # Conservative headline for demo (lead variant)
    for asset in ("CAKE", "BNB"):
        df = load_market_csv(DATA / f"{asset.lower()}_daily.csv")
        cons = run_backtest(df, asset=asset, mode="conservative")
        _write_backtest_artifacts(df, asset, cons, mode="conservative")
        is_oos = run_is_oos_headline(df, asset, mode="conservative")
        is_m = is_oos["in_sample"]["metrics"]
        oos_m = is_oos["out_of_sample"]["metrics"]
        print(
            f"\nConservative Mode — {asset}: "
            f"IS Sharpe {is_m['sharpe_ratio']:.2f} ({is_m['days_in_market_pct']:.1%} in market), "
            f"OOS Sharpe {oos_m['sharpe_ratio']:.2f} ({oos_m['days_in_market_pct']:.1%} in market)"
        )

    ensemble_headline = write_ensemble_headline()
    (REPORTS / "ensemble_oos_headline.json").write_text(
        json.dumps(ensemble_headline, indent=2), encoding="utf-8"
    )

    conservative_is_oos: dict[str, Any] = {}
    for asset in ("CAKE", "BNB"):
        df = load_market_csv(DATA / f"{asset.lower()}_daily.csv")
        conservative_is_oos[asset] = run_is_oos_headline(df, asset, mode="conservative")
    (REPORTS / "conservative_is_oos_headline.json").write_text(
        json.dumps(conservative_is_oos, indent=2), encoding="utf-8"
    )

    if "CAKE" in ensemble_headline:
        h = ensemble_headline["CAKE"]
        print(
            f"\nEnsemble OOS — CAKE: high-vol regime {h.get('high_vol_pct', 0):.0%} of days, "
            f"mean-reversion Sharpe {h.get('mean_reversion_oos_sharpe', 0):.2f}, "
            f"ensemble Sharpe {h.get('ensemble_oos_sharpe', 0):.2f}"
        )

    write_manifest()
    write_research_artifacts()
    df = load_market_csv(DATA / "bnb_daily.csv")
    print_is_oos_headline(df, "BNB")
    cmd_build_demo(argparse.Namespace())
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    load_dotenv(ROOT / ".env")
    asset = args.asset.upper()
    path = DATA / f"{asset.lower()}_daily.csv"
    source = "coinmarketcap_live"
    cmc_sources: list[str] = []
    mcp_tools: dict = {}

    if not path.exists():
        print(f"No history file at {path} (optional for live append).")

    try:
        from chainsage.adapters.cmc import bundle_to_decision_row, fetch_live_bundle

        bundle = fetch_live_bundle(asset)
        if not bundle.get("cmc_data_complete"):
            print(f"CMC MCP incomplete for {asset} — signal forced FLAT (no third-party fallbacks).")
            for err in bundle.get("errors", []):
                print(f"  · {err}")
        row = bundle_to_decision_row(bundle)
        cmc_sources = bundle.get("sources", [])
        mcp_tools = bundle.get("mcp_tools", {})
        quotes = bundle.get("quotes", {})
        fg = bundle.get("fear_greed", {})
        print(f"Live CMC for {asset}: ${quotes.get('price', 0):,.2f}, F&G={fg.get('value', '?')}")
        print(f"CMC MCP tools ({len(cmc_sources)}/6): {', '.join(cmc_sources)}")
        source = "coinmarketcap_live"
    except Exception as e:
        print(f"Live CMC required but unavailable: {e}")
        print("Set CMC_API_KEY in .env — this skill does not fall back to non-CMC data sources.")
        return 1

    if path.exists():
        history = load_market_csv(path)
        row_df = pd.DataFrame([{**row, "timestamp": pd.Timestamp.utcnow().normalize()}])
        history = pd.concat([history, row_df], ignore_index=True)
    else:
        history = pd.DataFrame([row])

    decision = evaluate_snapshot(history, len(history) - 1, asset=asset)
    spec = build_strategy_spec(decision, cmc_sources=cmc_sources, mcp_tools=mcp_tools)
    spec["data_source"] = source

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "live_decision.json"
    out.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    log_path = REPORTS / "decision_log.jsonl"
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "asset": asset, "source": source, "decision": decision.to_dict()}
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"\nSignal:     {decision.signal.upper()}")
    print(f"Regime:     {decision.regime}")
    print(f"Conviction: {decision.conviction:.0%}")
    print(f"Exposure:   {decision.target_exposure:.0%}")
    print(f"Reasons:    {', '.join(decision.reasons)}")
    if decision.falsifiers:
        print(f"Falsifiers: {', '.join(decision.falsifiers)}")
    print(f"\nWrote {out}")
    return 0


def cmd_spec(args: argparse.Namespace) -> int:
    if not _ensure_data():
        return 1
    asset = args.asset.upper()
    df = load_market_csv(DATA / f"{asset.lower()}_daily.csv")
    decision = evaluate_snapshot(df, len(df) - 1, asset=asset)
    result = run_backtest(df, asset=asset)
    is_oos = run_is_oos_headline(df, asset)
    spec = build_strategy_spec(
        decision,
        backtest_summary={**result, "is_oos": is_oos},
    )
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"{asset.lower()}_strategy_spec.json"
    out.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"Strategy spec written to {out}")
    return 0


def cmd_research(_: argparse.Namespace) -> int:
    if not _ensure_data():
        return 1
    path = write_research_artifacts()
    print(path.read_text(encoding="utf-8"))
    print(f"\nWrote {path}")
    print("Also: reports/walkforward.csv, reports/event_study.csv")
    return 0


def cmd_build_demo(_: argparse.Namespace) -> int:
    from chainsage.demo_build import build_demo_bundle

    path = build_demo_bundle()
    print(f"Wrote {path} ({path.stat().st_size // 1024} KB)")
    print("Serve: python -m http.server 8080 → http://localhost:8080/demo/")
    return 0


def cmd_verify(_: argparse.Namespace) -> int:
    from chainsage.verify import main as verify_main

    return verify_main()


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="ChainSage — conviction-gated CMC strategy skill")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch-data", help="Download real Binance + F&G + funding data")
    p_fetch.add_argument("--days", type=int, default=1000)
    p_fetch.set_defaults(func=cmd_fetch_data)

    p_bt = sub.add_parser("backtest", help="Run backtest on committed data")
    p_bt.add_argument("--asset", default="BNB")
    p_bt.add_argument(
        "--mode",
        default="aggressive",
        choices=("aggressive", "conservative", "ensemble"),
        help="aggressive=momentum gates, conservative=strict 4-gate, ensemble=regime-adaptive",
    )
    p_bt.set_defaults(func=cmd_backtest)

    p_all = sub.add_parser("backtest-all", help="Backtest all assets + conservative headline")
    p_all.add_argument(
        "--mode",
        default="aggressive",
        choices=("aggressive", "conservative", "ensemble"),
    )
    p_all.set_defaults(func=cmd_backtest_all)

    p_live = sub.add_parser("live", help="Live CMC scan + decision log")
    p_live.add_argument("--asset", default="BNB")
    p_live.set_defaults(func=cmd_live)

    p_spec = sub.add_parser("spec", help="Export strategy spec JSON")
    p_spec.add_argument("--asset", default="BNB")
    p_spec.set_defaults(func=cmd_spec)

    sub.add_parser("research", help="OOS + ablation + walk-forward + event study").set_defaults(func=cmd_research)
    sub.add_parser("build-demo", help="Bundle reports into demo/data/bundle.json").set_defaults(func=cmd_build_demo)
    sub.add_parser("verify", help="Verify all artifacts").set_defaults(func=cmd_verify)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
