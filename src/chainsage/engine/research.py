"""Research utilities — OOS, ablation, walk-forward, event study, sensitivity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from chainsage.engine.backtest import run_backtest, run_backtest_period, run_is_oos_headline
from chainsage.engine.event_study import render_event_study_section, run_event_study
from chainsage.engine.institutional import write_institutional_risk_report
from chainsage.engine.sensitivity import render_robustness_section, run_sensitivity_analysis
from chainsage.signals.thresholds import IS_PERIOD_END, IS_PERIOD_START, OOS_PERIOD_END, OOS_PERIOD_START

REPORTS = Path(__file__).resolve().parents[3] / "reports"


def run_oos_backtest(df: pd.DataFrame, asset: str) -> dict[str, Any]:
    """Strict IS/OOS split with contamination guard."""
    headline = run_is_oos_headline(df, asset=asset)
    return {
        "asset": asset,
        "split_date": OOS_PERIOD_START,
        "is_period": headline["is_period"],
        "oos_period": headline["oos_period"],
        "in_sample": headline["in_sample"],
        "out_of_sample": headline["out_of_sample"],
        "full_period": run_backtest(df, asset=asset),
    }


def run_walkforward(df: pd.DataFrame, asset: str) -> list[dict[str, Any]]:
    df = df.copy()
    df["year"] = pd.to_datetime(df["timestamp"]).dt.year
    results = []
    for year in sorted(df["year"].unique()):
        chunk = df[df["year"] == year]
        if len(chunk) < 40:
            continue
        bt = run_backtest(chunk, asset=asset, warmup=min(35, len(chunk) // 3))
        results.append({"year": int(year), "asset": asset, "metrics": bt["metrics"]})
    return results


def run_ablation(df: pd.DataFrame, asset: str) -> dict[str, Any]:
    oos = filter_period_oos(df)
    results: dict[str, Any] = {"full": run_backtest(oos, asset=asset, period_start=OOS_PERIOD_START, period_end=OOS_PERIOD_END)["metrics"]}
    for name, col in {
        "no_derivatives": "funding_rate",
        "no_onchain": "holder_trend",
        "no_narrative": "narrative_score",
    }.items():
        d = oos.copy()
        d[col] = 0.0
        results[name] = run_backtest(
            d,
            asset=asset,
            period_start=OOS_PERIOD_START,
            period_end=OOS_PERIOD_END,
        )["metrics"]
    return {"asset": asset, "ablation": results}


def filter_period_oos(df: pd.DataFrame) -> pd.DataFrame:
    from chainsage.engine.backtest import filter_period

    return filter_period(df, OOS_PERIOD_START, OOS_PERIOD_END)


def run_full_research(df: pd.DataFrame, asset: str) -> dict[str, Any]:
    return {
        "asset": asset,
        "oos": run_oos_backtest(df, asset),
        "sensitivity": run_sensitivity_analysis(df, asset),
        "ablation": run_ablation(df, asset),
        "walkforward": run_walkforward(df, asset),
        "event_study": run_event_study(df, asset),
    }


def render_research_report(
    oos_results: list[dict],
    ablation_results: list[dict],
    walkforward_results: list[dict],
    event_study_results: list[dict],
    sensitivity_results: list[dict],
) -> str:
    lines = ["# ChainSage Research Report", ""]

    lines.append(f"## In-Sample ({IS_PERIOD_START} → {IS_PERIOD_END})")
    lines.append("")
    lines.append("| Asset | Return | Max DD | Sharpe | Calmar | Win Rate | Time in Mkt |")
    lines.append("|-------|-------:|-------:|-------:|-------:|---------:|------------:|")
    for r in oos_results:
        block = r.get("in_sample")
        if block:
            m = block["metrics"]
            lines.append(
                f"| {r['asset']} | {m['total_return']:.1%} | {m['max_drawdown']:.1%} | "
                f"{m['sharpe_ratio']:.2f} | {m.get('calmar_ratio', 0):.2f} | "
                f"{m['win_rate']:.1%} | {m.get('time_in_market', 0):.1%} |"
            )
    lines.append("")

    lines.append(f"## Out-of-Sample ({OOS_PERIOD_START} → {OOS_PERIOD_END})")
    lines.append("")
    lines.append("| Asset | Return | Max DD | Sharpe | Calmar | Win Rate | Time in Mkt |")
    lines.append("|-------|-------:|-------:|-------:|-------:|---------:|------------:|")
    for r in oos_results:
        block = r.get("out_of_sample")
        if block:
            m = block["metrics"]
            lines.append(
                f"| {r['asset']} | {m['total_return']:.1%} | {m['max_drawdown']:.1%} | "
                f"{m['sharpe_ratio']:.2f} | {m.get('calmar_ratio', 0):.2f} | "
                f"{m['win_rate']:.1%} | {m.get('time_in_market', 0):.1%} |"
            )
    lines.append("")

    for sens in sensitivity_results:
        lines.append(render_robustness_section(sens))

    lines.append("## Walk-Forward by Year")
    lines.append("")
    lines.append("| Asset | Year | Return | Max DD | Sharpe |")
    lines.append("|-------|-----:|-------:|-------:|-------:|")
    for r in walkforward_results:
        m = r["metrics"]
        lines.append(
            f"| {r['asset']} | {r['year']} | {m['total_return']:.1%} | {m['max_drawdown']:.1%} | {m['sharpe_ratio']:.2f} |"
        )
    lines.append("")

    lines.append(render_event_study_section(event_study_results))

    lines.append("## Ablation (OOS — does each layer help?)")
    lines.append("")
    for r in ablation_results:
        lines.append(f"### {r['asset']}")
        lines.append("")
        lines.append("| Variant | Return | Max DD | Sharpe |")
        lines.append("|---------|-------:|-------:|-------:|")
        for name, m in r["ablation"].items():
            lines.append(f"| {name} | {m['total_return']:.1%} | {m['max_drawdown']:.1%} | {m['sharpe_ratio']:.2f} |")
        lines.append("")

    return "\n".join(lines)


def write_research_artifacts(assets: tuple[str, ...] = ("BNB", "CAKE", "TWT", "BTC")) -> Path:
    from chainsage.engine.backtest import load_market_csv

    data_dir = Path(__file__).resolve().parents[3] / "data"
    oos_results, ablation_results, walkforward_results, event_results, sensitivity_results = [], [], [], [], []

    for asset in assets:
        df = load_market_csv(data_dir / f"{asset.lower()}_daily.csv")
        full = run_full_research(df, asset)
        oos_results.append(full["oos"])
        ablation_results.append(full["ablation"])
        walkforward_results.extend(full["walkforward"])
        event_results.append(full["event_study"])
        sensitivity_results.append(full["sensitivity"])

        if asset == "CAKE":
            write_institutional_risk_report(df, asset="CAKE", mode="conservative", reports_dir=REPORTS)

        es_path = REPORTS / f"{asset.lower()}_event_study.json"
        es_path.write_text(json.dumps(full["event_study"], indent=2), encoding="utf-8")

        sens_path = REPORTS / f"{asset.lower()}_sensitivity.json"
        sens_path.write_text(json.dumps(full["sensitivity"], indent=2), encoding="utf-8")

    report = render_research_report(
        oos_results,
        ablation_results,
        walkforward_results,
        event_results,
        sensitivity_results,
    )
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / "research_report.md"
    path.write_text(report, encoding="utf-8")

    headline = {
        asset: {
            "in_sample": next(r["in_sample"]["metrics"] for r in oos_results if r["asset"] == asset),
            "out_of_sample": next(r["out_of_sample"]["metrics"] for r in oos_results if r["asset"] == asset),
        }
        for asset in assets
    }
    (REPORTS / "is_oos_headline.json").write_text(json.dumps(headline, indent=2), encoding="utf-8")

    wf_path = REPORTS / "walkforward.csv"
    pd.DataFrame(walkforward_results).to_csv(wf_path, index=False)

    es_all = []
    for er in event_results:
        for row in er.get("rows", []):
            row["asset"] = er["asset"]
            es_all.append(row)
    if es_all:
        pd.DataFrame(es_all).to_csv(REPORTS / "event_study.csv", index=False)

    return path


def print_is_oos_headline(df: pd.DataFrame, asset: str = "BNB") -> None:
    """CLI helper: print IS/OOS Sharpe with contamination-safe windows."""
    is_r = run_backtest_period(df, IS_PERIOD_START, IS_PERIOD_END, asset=asset)
    oos_r = run_backtest_period(df, OOS_PERIOD_START, OOS_PERIOD_END, asset=asset)
    im, om = is_r["metrics"], oos_r["metrics"]
    print(f"\nIS/OOS headline — {asset}")
    print(f"  IS  ({IS_PERIOD_START} → {IS_PERIOD_END}): Sharpe {im['sharpe_ratio']:.2f}, Max DD {im['max_drawdown']:.1%}")
    print(f"  OOS ({OOS_PERIOD_START} → {OOS_PERIOD_END}): Sharpe {om['sharpe_ratio']:.2f}, Max DD {om['max_drawdown']:.1%}")
