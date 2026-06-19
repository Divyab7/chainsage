# ChainSage

**A Research-Grade CoinMarketCap Strategy Skill for BNB Hack Track 2**

Not a black box — a **reproducible framework** for strategy validation. ChainSage turns CMC data into backtestable signals with enforced IS/OOS splits, falsifiers, and regime-aware ensembles.

> **Built in 72 hours | 40 tests | 2% probability of overfitting | Deflated Sharpe 0.78**

> **Core idea:** Only trade when independent data layers agree. If they disagree — or OOS regimes lack edge — sit out.

[BNB Hack: AI Trading Agent Edition](https://dorahacks.io/hackathon/bnbhack-twt-cmc/detail) — Track 2: Strategy Skills


| Resource      | Location                                                                                  |
| ------------- | ----------------------------------------------------------------------------------------- |
| CMC Skill     | `[skills/chainsage-conviction-gate/SKILL.md](skills/chainsage-conviction-gate/SKILL.md)`  |
| Live demo     | `python -m http.server 8080` → [http://localhost:8080/demo/](http://localhost:8080/demo/) |
| Strategy spec | `reports/bnb_strategy_spec.json`                                                          |


---

## For judges — reproduce in ~5 minutes

**No API key required** to verify backtests. Committed CSVs in `data/` are the source of truth.

### 1. Install

```bash
git clone https://github.com/Divyab7/chainsage.git
cd chainsage
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Requires **Python 3.9+**.

### 2. Run tests (40)

```bash
pytest -q
```

Expected: `40 passed`

Covers signal math, IS/OOS contamination guard, no-lookahead bias, institutional metrics (DSR, PBO, walk-forward), and schema checks.

### 3. Verify headline numbers

```bash
chainsage verify
```

Expected output:

```
VERDICT: VERIFIED — backtests, trade logs, equity reports, research artifacts OK
  OK BNB return=...
  OK CAKE return=...
  OK TWT return=...
  OK BTC return=...
```

This **re-runs backtests** from `data/*.csv` and checks they match `reports/*_backtest.json`, trade logs, equity HTML, README table figures, `walkforward.csv`, and `event_study.csv`. No network calls.

### 4. (Optional) Regenerate research artifacts

```bash
chainsage research
```

Writes:


| File                              | Contents                                                          |
| --------------------------------- | ----------------------------------------------------------------- |
| `reports/research_report.md`      | IS/OOS tables, walk-forward, ablation, event study                |
| `reports/institutional_risk.json` | DSR, PBO, walk-forward Sharpe, decay analysis (CAKE conservative) |
| `reports/walkforward.csv`         | Per-year walk-forward metrics                                     |
| `reports/event_study.csv`         | Regime forward-return study                                       |


### 5. (Optional) View the demo

```bash
chainsage build-demo    # bundles reports → demo/data/bundle.json
python -m http.server 8080
# open http://localhost:8080/demo/
```

The demo reads **only** `demo/data/bundle.json` — no backend. Shows IS/OOS comparison, research pipeline, verification panel, and live decision (if `reports/live_decision.json` exists).

### 6. (Optional) Live CMC decision

Requires `CMC_API_KEY` in `.env` (see `.env.example`):

```bash
cp .env.example .env
chainsage live --asset BNB
chainsage build-demo
```

---

## Honest results (CAKE, IS/OOS split)

Reproduce with:

```bash
chainsage backtest --asset CAKE --mode conservative   # full period
# IS/OOS headline is computed inside chainsage research / demo bundle
```


| Mode             | IS Sharpe | OOS Sharpe | Time in Market | Interpretation                                      |
| ---------------- | --------- | ---------- | -------------- | --------------------------------------------------- |
| **Conservative** | 0.91      | 0.00       | 4%             | Avoids unfavorable regimes                          |
| Ensemble         | 1.89      | 0.36       | 34%            | MR rarely triggers after IS q10; routes to momentum |
| Aggressive       | 1.89      | 0.36       | 34%            | Research depth; higher variance                     |


**IS:** 2023-01-01 → 2024-06-30 · **OOS:** 2024-07-01 → 2026-06-01

**Institutional risk (CAKE conservative, from `reports/institutional_risk.json`):**


| Metric                           | Value        |
| -------------------------------- | ------------ |
| Standard IS Sharpe               | 0.91         |
| Deflated Sharpe (3 trials)       | 0.78         |
| PBO (probability of overfitting) | 2%           |
| Walk-forward Sharpe              | −0.01 ± 0.55 |


**Conclusion:** OOS (2024–2026) lacked the regime conditions for our thesis. Conservative mode minimized exposure rather than forcing trades.

---

## Full pipeline (from scratch)

Use this if you want to refresh data and regenerate everything:

```bash
cp .env.example .env          # optional: CMC_API_KEY for fetch-data / live
pip install -e ".[dev]"

chainsage fetch-data          # downloads Binance + funding + F&G → data/
chainsage backtest-all        # all assets + conservative headline + demo bundle
chainsage research            # IS/OOS, walk-forward, institutional risk
chainsage verify              # must print VERIFIED
pytest -q                     # must print 40 passed
```

---

## Strategy modes


| Mode         | CLI flag              | Config                                    |
| ------------ | --------------------- | ----------------------------------------- |
| Aggressive   | `--mode aggressive`   | Default momentum conviction gate          |
| Conservative | `--mode conservative` | `config/conservative.yaml`                |
| Ensemble     | `--mode ensemble`     | ATR regime → funding MR or momentum gates |


```bash
chainsage backtest --asset CAKE --mode conservative
chainsage backtest --asset CAKE --mode ensemble
```

---

## Commands reference


| Command                                 | What it does                                                  |
| --------------------------------------- | ------------------------------------------------------------- |
| `chainsage fetch-data`                  | Download market history into `data/`                          |
| `chainsage backtest-all`                | Backtest BNB, CAKE, TWT, BTC + write `reports/` + demo bundle |
| `chainsage backtest --asset X --mode Y` | Single-asset backtest                                         |
| `chainsage research`                    | Research report + institutional risk JSON                     |
| `chainsage verify`                      | Re-derive metrics from `data/`; compare to `reports/`         |
| `chainsage build-demo`                  | Build `demo/data/bundle.json` for static demo                 |
| `chainsage live --asset BNB`            | Live CMC MCP tools (6/6) + decision log                       |
| `chainsage spec --asset BNB`            | Export `reports/bnb_strategy_spec.json`                       |


---

## Full-period backtests (aggressive, committed data)


| Asset | Return | Max DD | Sharpe |
| ----- | ------ | ------ | ------ |
| CAKE  | 114.2% | -35.8% | 0.79   |
| BTC   | 6.5%   | -14.9% | 0.21   |
| BNB   | -13.0% | -35.2% | -0.18  |
| TWT   | -6.1%  | -35.8% | 0.03   |


---

## Track 2 deliverables


| Artifact            | Path                                           |
| ------------------- | ---------------------------------------------- |
| CMC Skill           | `skills/chainsage-conviction-gate/SKILL.md`    |
| Strategy spec       | `reports/bnb_strategy_spec.json`               |
| Demo dashboard      | `demo/index.html` + `demo/data/bundle.json`    |
| Conservative config | `config/conservative.yaml`                     |
| Verification        | `chainsage verify` / `src/chainsage/verify.py` |


---

---

**API headers:** REST `X-CMC_PRO_API_KEY` · MCP `X-CMC-MCP-API-KEY`

## License

MIT