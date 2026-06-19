# DoraHacks Submission — ChainSage

## Project Name
ChainSage — Conviction-Gated CMC Strategy Skill

## Track
Track 2: Strategy Skills

## One-Line Summary
A CoinMarketCap Skill that only recommends trades when derivatives, on-chain holder, and narrative data layers align — defaulting to flat when they disagree.

## Problem
Most crypto strategies trade too often in confusing markets. They fuse signals into a buy score without checking whether independent data sources actually agree.

## Solution
ChainSage scores three independent CMC data planes, applies a conviction gate, and exports a backtestable strategy spec with explicit falsifiers (conditions that invalidate the thesis).

## CMC Tools Used
- `get_crypto_quotes_latest`
- `get_crypto_technical_analysis`
- `get_global_metrics_latest`
- `get_global_crypto_derivatives_metrics`
- `get_crypto_metrics`
- `trending_crypto_narratives`

## How to Reproduce
```bash
pip install -e .
python scripts/generate_sample_data.py
chainsage backtest-all
chainsage spec --asset BNB
```

## Key Results (committed sample data)
- **BTC:** Max drawdown -4.9% vs buy-and-hold -34.1%
- **BNB:** Max drawdown -18.0% vs buy-and-hold -31.4%

## What We Do NOT Do
- No wallet connection
- No live trade execution
- No private keys
- No token launch

## Links
- GitHub: (your repo URL)
- Demo: `demo/index.html` or deployed URL
- Video: (your YouTube/Loom link)

## Team
(Add your name/handle)
