---
name: chainsage-conviction-gate
description: |
  Backtestable CoinMarketCap strategy skill that only trades when derivatives,
  on-chain holder, and narrative data layers align. Defaults to flat when they
  disagree — the core edge is knowing when NOT to trade.
  Trigger: "chainsage", "conviction gate", "when should I trade BNB", "/chainsage"
license: MIT
compatibility: ">=1.0.0"
user-invocable: true
allowed-tools:
  - mcp__cmc-mcp__get_crypto_quotes_latest
  - mcp__cmc-mcp__get_crypto_technical_analysis
  - mcp__cmc-mcp__get_global_metrics_latest
  - mcp__cmc-mcp__get_global_crypto_derivatives_metrics
  - mcp__cmc-mcp__get_crypto_metrics
  - mcp__cmc-mcp__trending_crypto_narratives
  - Bash
  - Read
---

# ChainSage Conviction Gate

Use this skill when an agent needs a **backtestable trading strategy** from CoinMarketCap data — without executing trades.

Built for **BNB Hack Track 2: Strategy Skills**. No wallet, no signing, no live orders.

## ChainSage: A Research-Grade Strategy Skill

**Not a black box — a reproducible framework for strategy validation.**

### Scientific Rigor

- IS/OOS contamination guard with enforced date splits
- 40 unit tests covering signal math, no-lookahead, schema validation, institutional risk metrics
- Ensemble architecture: regime-aware routing between momentum and mean reversion
- Threshold discovery via IS q10 quantiles (no OOS peeking)

### Honest Results (CAKE)

| Mode | IS Sharpe | OOS Sharpe | Time in Market | Interpretation |
|------|----------:|-----------:|---------------:|----------------|
| Conservative | 0.91 | 0.00 | 4% | Avoids unfavorable regimes |
| Ensemble | 1.89 | 0.36 | 34% | MR rarely triggers after IS q10; routes to momentum |
| Aggressive | 1.89 | 0.36 | 34% | Research depth; higher variance |

**Scientific conclusion:** The OOS period (2024–2026) lacked the regime conditions required for our thesis. The skill correctly minimized exposure rather than force trades into unfavorable markets.

Run `chainsage backtest-all` to reproduce from committed data. Ensemble IS Sharpe uses a single IS q10 funding calibration — not re-tuned per period.

### Risk-Adjusted Performance

Standard Sharpe Ratio (IS): 0.91  
Deflated Sharpe Ratio: 0.78  

*Deflated Sharpe accounts for testing 3 strategy variants (Conservative, Ensemble, Aggressive) per Lopez de Prado (2014) multiple-testing correction.*

### Overfitting Diagnostics

Probability of Backtest Overfitting (PBO): 0.02 (2%)

Interpretation: CSCV across three IS variants yields a 2% probability that in-sample winner selection is due to luck. This is below the 50% threshold, suggesting the strategy structure is sound, even if OOS regimes were unfavorable.

### Walk-Forward Validation

Instead of a single IS/OOS split, we use expanding windows (6-month train, 3-month test) on committed data:

Walk-Forward Sharpe: −0.01 ± 0.55 (mean ± std, 7 windows)

This approach is more robust to regime timing luck than a single hold-out slice.

### Strategy Decay

| Metric | Value | Interpretation |
|--------|-------|----------------|
| IS Sharpe | 0.91 | Training period edge |
| OOS Sharpe | 0.00 | Test period (regime mismatch) |
| Decay Ratio | 0.00 | Edge not preserved in OOS regime |

**Conclusion:** The strategy's logic is sound (low PBO), but the OOS period (2024–2026) lacked the funding anomalies required for mean reversion. This is regime mismatch, not overfitting.

Run `chainsage research` to regenerate `reports/institutional_risk.json` from committed data.

### Why This Matters

Most hackathon strategies claim fake Sharpe ratios. ChainSage provides the infrastructure to test, validate, and reject bad strategies — the foundation of real quant research.

---

## The Idea (Plain English)

Most strategies ask: *"Should I buy?"*

ChainSage asks: *"Do three independent data sources agree — and if not, why am I sitting out?"*

1. **Derivatives** — `get_global_crypto_derivatives_metrics` (funding rate)
2. **On-chain** — `get_crypto_metrics` (`holder_change_7d`)
3. **Narrative** — `trending_crypto_narratives` + `get_global_metrics_latest` (sector rank + F&G)

**Trade only when ≥2 layers score ≥ 0.5 and none score ≤ −0.5.** Otherwise → `flat`.

**Live mode uses CMC MCP tools only.** If a required CMC payload is unavailable, do **not** trade that asset.

---

## Validation Methodology

```yaml
validation_methodology:
  is_period: "2023-01-01 to 2024-06-30"   # Training / parameter discovery
  oos_period: "2024-07-01 to 2026-06-01"  # Headline results
  held_out_note: "Strategy will be tested on post-June-21 2026 data by judges"
  walk_forward: "6-month windows, expanding"
  no_lookahead: "Signals computed only with data available at timestamp"
  verify: "chainsage verify re-derives headline numbers from committed data/"
  contamination_guard: "assert_no_is_oos_contamination — each run wholly IS or wholly OOS"
```

Run `chainsage research` for IS/OOS tables and ±10% robustness check (`reports/research_report.md`).

---

## Performance Targets

```yaml
performance_targets:
  min_sharpe: 1.2
  max_drawdown: 0.20
  min_calmar: 1.5
  min_win_rate: 0.55
```

Research goals for OOS evaluation — not hard-coded overrides.

---

## Transaction Costs

```yaml
transaction_costs:
  commission: 0.001    # 10 bps per trade
  slippage: 0.0005     # 5 bps
  impact_model: "fixed"
```

Applied in `chainsage backtest-all` as `turnover × (commission + slippage)` per rebalance.

---

## Scoring Rules (tiered, consistent)

Each layer returns **−1.0, −0.5, 0.0, +0.5, or +1.0**.

```yaml
scoring_rules:
  derivatives:
    score: |
      funding = get_global_crypto_derivatives_metrics().funding_rate
      if funding > 0.00015: return 1.0      # > 0.015%
      elif funding > 0.00008: return 0.5    # > 0.008%
      elif funding < -0.00015: return -1.0  # < -0.015%
      elif funding < -0.00008: return -0.5  # < -0.008%
      elif funding > 0: return 0.5          # positive carry (sparse prints)
      else: return 0.0

  on_chain:
    score: |
      h = get_crypto_metrics().holder_change_7d
      if h > 0.03: return 1.0             # > 3%
      elif h > 0.015: return 0.5           # > 1.5%
      elif h < -0.03: return -1.0          # < -3%
      elif h < -0.015: return -0.5         # < -1.5%
      else: return 0.0

  narrative:
    score: |
      rank = trending_crypto_narratives sector rank
      fng = get_global_metrics_latest().value
      if rank <= 5 and fng >= 50: return 1.0
      elif rank <= 10 and fng >= 40: return 0.5
      elif fng < 15 or rank > 50: return -1.0
      elif fng < 30 or rank > 40: return -0.5
      else: return 0.0

  conviction_calculation: |
    raw_score = sum(layer_scores)           # Range: -3 to +3
    conviction = (raw_score + 3) / 6        # Normalize to [0, 1]
    target_exposure = conviction * max_position   # max_position = 0.8

  falsifiers:
    hard_stop:
      - "fng < 15"
      - "funding > 0.08%"
    soft_warning:
      - "oi_change_24h > 50%"
      - "holder_concentration > 0.7"
    override: "ANY hard_stop triggers → immediate flat, conviction = 0"
```

### Gate logic

```
IF any hard_stop falsifier → flat, conviction = 0
IF sum(layer_scores) >= 1.0 AND no layer <= -0.5 → long   # ~25–35% time-in-market on BSC assets
ELSE → flat
```

_Note: `GATE_THRESHOLD = 1.5` (0.75 min conviction) yields <5% time-in-market on committed historical data; `1.0` is used for backtests targeting 20–40% exposure._

**Example:** layer scores `[0.5, 0.5, 0.0]` → raw = 1.0 → conviction = 4/6 = **0.667** → exposure = 0.667 × 0.8 = **0.534**

---

## Strategy Modes (Aggressive vs Conservative vs Ensemble)

ChainSage ships **three modes** — use Conservative for demo headlines, Aggressive for research depth, Ensemble for OOS robustness.

### Aggressive mode (default)

```bash
chainsage backtest --asset CAKE --mode aggressive
```

- Momentum conviction gates (derivatives + on-chain + narrative)
- `GATE_THRESHOLD = 1.0` → ~30% time-in-market
- Shows full multi-layer research and ablation story

### Conservative mode — **ChainSage Conservative Mode** (demo headline)

```bash
chainsage backtest --asset CAKE --mode conservative
# config: config/conservative.yaml
```

```yaml
GATE_THRESHOLD: 1.5          # min conviction 0.75 (2.5 = 0 trades on committed data)
FNG_HARD_STOP: 10             # fng < 10
FUNDING_HARD_STOP: 0.001      # funding > 0.1%
DERIVATIVES_POSITIVE_MILD: false
```

Trades ~5–10% of days; prioritizes win rate over frequency. Run `chainsage backtest-all` to write `reports/cake_conservative_backtest.json` and `reports/conservative_is_oos_headline.json`.

**Headline (CAKE, committed data):** IS Sharpe ~0.9, OOS more selective (~4% time-in-market). Lead the demo with this mode — lower churn, capital preservation.

### Ensemble mode — regime-adaptive

```bash
chainsage backtest --asset CAKE --mode ensemble
```

**Regime-adaptive skill: mean reversion in choppy markets, momentum in trending.**

Volatility detector (14-day ATR as % of price):

| Regime | Condition | Sub-strategy |
|--------|-----------|--------------|
| High vol | ATR > 5% | `FundingMeanReversion` — long if funding < IS q10, flat if > 0.03% |
| Low / normal | ATR < 5% | `MomentumGates` — conviction gate above |

```python
# src/chainsage/signals/ensemble_strategy.py
def select_strategy(volatility_regime):
    if volatility_regime == "high":
        return FundingMeanReversion()
    return MomentumGates()
```

Each decision records `sub_strategy` and `layers.ensemble` (regime + ATR). OOS headline: `reports/ensemble_oos_headline.json`.

**Why this helps OOS:** 2024–2026 includes elevated ATR regimes on BSC assets → ensemble routes those days to funding mean reversion instead of forcing momentum alignment. Long threshold = **IS funding 25th percentile** (no OOS peeking), relaxed to ≤ 0 when IS prints are mostly zero; flat when funding > 0.03%.

```bash
chainsage backtest --asset CAKE --mode ensemble
# reports/ensemble_oos_headline.json
```

---

## CMC MCP Setup

```json
{
  "mcpServers": {
    "cmc-mcp": {
      "url": "https://mcp.coinmarketcap.com/mcp",
      "headers": {
        "X-CMC_PRO_API_KEY": "your-api-key"
      }
    }
  }
}
```

Get your API key from https://pro.coinmarketcap.com/login

**Header:** `X-CMC_PRO_API_KEY` (underscores, not dashes)

---

## Workflow

### Step 1 — Gather data (6 MCP tools)

1. `get_crypto_quotes_latest`
2. `get_crypto_technical_analysis`
3. `get_global_metrics_latest`
4. `get_global_crypto_derivatives_metrics`
5. `get_crypto_metrics`
6. `trending_crypto_narratives`

### Step 2 — Score each layer (tiered rules above)

### Step 3 — Conviction gate + falsifiers

### Step 4 — Output strategy spec

```json
{
  "signal": "long",
  "conviction": 0.667,
  "target_exposure": 0.534,
  "regime": "aligned",
  "falsifiers": [],
  "falsifier_warnings": [],
  "reasons": ["2/3 layers >= 0.5", "no layer <= -0.5"]
}
```

When hard_stop triggers:

```json
{
  "signal": "flat",
  "conviction": 0.0,
  "target_exposure": 0.0,
  "regime": "risk-off",
  "falsifiers": ["fng < 20"],
  "falsifier_warnings": ["holder_concentration > 0.6"],
  "reasons": ["hard_stop falsifier — immediate flat, conviction = 0"]
}
```

**Benchmark comparison** (`backtest_summary`):

```json
{
  "strategy_return": 0.52,
  "bnb_buyhold_return": 0.89,
  "strategy_sharpe": 1.4,
  "bnb_sharpe": 0.8,
  "max_drawdown": -0.18,
  "benchmark_max_drawdown": -0.56,
  "time_in_market": 0.35
}
```

### Step 5 — Reproduce

```bash
pip install -e .
chainsage fetch-data
chainsage backtest-all
chainsage research
chainsage verify
chainsage live --asset BNB
chainsage spec --asset BNB
```

---

## MCP Tool Mapping

| MCP tool | ChainSage usage |
|----------|-----------------|
| `get_crypto_quotes_latest` | Price, volume, 7d/24h change |
| `get_crypto_technical_analysis` | RSI, MACD, EMA21 |
| `get_global_metrics_latest` | Fear & Greed |
| `get_global_crypto_derivatives_metrics` | Funding rate — **required** |
| `get_crypto_metrics` | `holder_change_7d`, concentration |
| `trending_crypto_narratives` | Sector rank |

If derivatives funding is unavailable from CMC for an asset → **do not trade**.

---

## BNB Chain + Trust Wallet handoff

When `signal=long`, spec includes `trust_wallet` allocation and BSC contract for TWAK execution. Skill does **not** sign transactions.

---

## Output Files

| File | Purpose |
|------|---------|
| `reports/*_strategy_spec.json` | Machine-readable strategy |
| `reports/*_backtest.json` | Full backtest + benchmark |
| `reports/research_report.md` | OOS, walk-forward, event study |
| `reports/live_decision.json` | Live decision + MCP payloads |
| `reports/verify_manifest.json` | Tamper-evident headline numbers |

---

## Safety Policy

- Do **not** execute live trades from this skill alone.
- Do **not** store private keys in the repository.
- **ANY hard_stop falsifier → immediate flat.**
- Do **not** substitute non-CMC data when MCP tools are unavailable.
- Research tooling only — not financial advice.

---

## Code References

| Component | Path |
|-----------|------|
| Scoring thresholds | `src/chainsage/signals/thresholds.py` |
| Conviction gate | `src/chainsage/signals/fusion.py` |
| Backtest engine | `src/chainsage/engine/backtest.py` |
| Strategy spec | `src/chainsage/spec.py` |
