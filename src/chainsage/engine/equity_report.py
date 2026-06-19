"""Self-contained HTML equity curve report."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def render_equity_html(result: dict[str, Any]) -> str:
    asset = result["asset"]
    curve = result.get("equity_curve", [])
    if not curve:
        return f"<html><body><p>No equity data for {asset}</p></body></html>"

    dates = [p["date"] for p in curve]
    strat = [p["strategy"] for p in curve]
    bench = [p["benchmark"] for p in curve]
    m = result["metrics"]
    b = result["benchmark_metrics"]

    def poly(vals: list[float], w: int = 800, h: int = 220) -> str:
        lo, hi = min(vals + bench), max(vals + bench)
        span = hi - lo or 1
        pts = []
        for i, v in enumerate(vals):
            x = i / max(len(vals) - 1, 1) * w
            y = h - (v - lo) / span * h
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    def poly_bench(vals: list[float], w: int = 800, h: int = 220) -> str:
        lo, hi = min(strat + vals), max(strat + vals)
        span = hi - lo or 1
        pts = []
        for i, v in enumerate(vals):
            x = i / max(len(vals) - 1, 1) * w
            y = h - (v - lo) / span * h
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/><title>ChainSage Equity — {asset}</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0b0f14;color:#e8edf4;padding:2rem;max-width:900px;margin:auto}}
h1{{color:#f0b90b}} .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin:1rem 0}}
.card{{background:#141b24;border:1px solid #243044;border-radius:8px;padding:1rem}}
svg{{background:#141b24;border-radius:8px;width:100%;max-width:800px}}
</style></head><body>
<h1>ChainSage — {asset}</h1>
<p>{result['period_start']} → {result['period_end']}</p>
<div class="grid">
  <div class="card"><div>Return</div><strong>{m['total_return']:.1%}</strong> vs {b['total_return']:.1%}</div>
  <div class="card"><div>Max DD</div><strong>{m['max_drawdown']:.1%}</strong> vs {b['max_drawdown']:.1%}</div>
  <div class="card"><div>Sharpe</div><strong>{m['sharpe_ratio']:.2f}</strong> vs {b['sharpe_ratio']:.2f}</div>
  <div class="card"><div>In Market</div><strong>{m['days_in_market_pct']:.0%}</strong></div>
</div>
<svg viewBox="0 0 800 240" xmlns="http://www.w3.org/2000/svg">
  <polyline fill="none" stroke="#8b9bb4" stroke-width="2" points="{poly_bench(bench)}"/>
  <polyline fill="none" stroke="#f0b90b" stroke-width="2.5" points="{poly(strat)}"/>
</svg>
<p style="color:#8b9bb4;font-size:0.85rem">Gold = ChainSage · Gray = buy &amp; hold · {len(dates)} daily points</p>
</body></html>"""


def write_equity_html(result: dict[str, Any], out_dir: Path, suffix: str = "") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    asset = result["asset"].lower()
    mode = result.get("mode", "aggressive")
    file_suffix = suffix or (f"_{mode}" if mode != "aggressive" else "")
    path = out_dir / f"{asset}{file_suffix}_equity.html"
    path.write_text(render_equity_html(result), encoding="utf-8")
    return path
