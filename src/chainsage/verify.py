"""Verify headline numbers match committed backtest reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from chainsage.engine.backtest import load_market_csv, run_backtest
from chainsage.engine.event_study import run_event_study

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
README = ROOT / "README.md"

TOLERANCE = 0.002
SHARPE_TOL = 0.05


def verify_asset(asset: str) -> list[str]:
    errors: list[str] = []
    path = DATA / f"{asset.lower()}_daily.csv"
    if not path.exists():
        return [f"{asset}: missing {path}"]

    df = load_market_csv(path)
    result = run_backtest(df, asset=asset)
    json_path = REPORTS / f"{asset.lower()}_backtest.json"

    if json_path.exists():
        saved = json.loads(json_path.read_text())["metrics"]
        for key in ("total_return", "max_drawdown", "sharpe_ratio"):
            got = result["metrics"][key]
            want = saved[key]
            tol = SHARPE_TOL if key == "sharpe_ratio" else TOLERANCE
            if abs(got - want) > tol:
                errors.append(f"{asset}.{key}: got {got} want {want}")
    else:
        errors.append(f"{asset}: missing {json_path}")

    trades_path = REPORTS / f"{asset.lower()}_trades.csv"
    if not trades_path.exists():
        errors.append(f"{asset}: missing trade log {trades_path}")

    equity_path = REPORTS / f"{asset.lower()}_equity.html"
    if not equity_path.exists():
        errors.append(f"{asset}: missing equity report {equity_path}")

    return errors


def verify_readme_numbers() -> list[str]:
    """Check README table contains return % matching backtest JSON."""
    errors: list[str] = []
    if not README.exists():
        return errors

    text = README.read_text(encoding="utf-8")
    for asset in ("BNB", "CAKE", "TWT", "BTC"):
        json_path = REPORTS / f"{asset.lower()}_backtest.json"
        if not json_path.exists():
            continue
        ret = json.loads(json_path.read_text())["metrics"]["total_return"]
        pct = f"{ret * 100:.1f}%"
        if pct.replace("-", "−") not in text and pct not in text:
            # allow signed minus variants
            alt = pct.replace(".0%", "%") if pct.endswith(".0%") else pct
            if alt not in text and f"{ret:.1%}" not in text:
                errors.append(f"README missing return {asset} {pct}")
    return errors


def verify_event_study() -> list[str]:
    errors: list[str] = []
    path = REPORTS / "event_study.csv"
    if not path.exists():
        return ["missing reports/event_study.csv — run chainsage research"]
    return errors


def verify_walkforward() -> list[str]:
    path = REPORTS / "walkforward.csv"
    if not path.exists():
        return ["missing reports/walkforward.csv — run chainsage research"]
    return []


def write_manifest() -> None:
    """Write verify_manifest.json from current backtest results."""
    manifest: dict[str, dict] = {}
    for asset in ("BNB", "CAKE", "TWT", "BTC"):
        json_path = REPORTS / f"{asset.lower()}_backtest.json"
        if json_path.exists():
            manifest[asset] = json.loads(json_path.read_text())["metrics"]
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "verify_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    all_errors: list[str] = []
    for asset in ("BNB", "CAKE", "TWT", "BTC"):
        all_errors.extend(verify_asset(asset))
    all_errors.extend(verify_readme_numbers())
    all_errors.extend(verify_event_study())
    all_errors.extend(verify_walkforward())

    if all_errors:
        print("VERDICT: FAILED")
        for e in all_errors:
            print(f"  FAIL {e}")
        return 1

    print("VERDICT: VERIFIED — backtests, trade logs, equity reports, research artifacts OK")
    for asset in ("BNB", "CAKE", "TWT", "BTC"):
        m = json.loads((REPORTS / f"{asset.lower()}_backtest.json").read_text())["metrics"]
        print(f"  OK {asset} return={m['total_return']:.1%} maxDD={m['max_drawdown']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
