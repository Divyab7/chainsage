# ChainSage Research Report

## In-Sample (2023-01-01 → 2024-06-30)

| Asset | Return | Max DD | Sharpe | Calmar | Win Rate | Time in Mkt |
|-------|-------:|-------:|-------:|-------:|---------:|------------:|
| BNB | 6.4% | -20.8% | 0.41 | 0.31 | 37.9% | 17.3% |
| CAKE | 91.0% | -11.7% | 1.89 | 7.98 | 46.9% | 17.9% |
| TWT | -3.1% | -23.3% | -0.02 | -0.13 | 38.6% | 14.1% |
| BTC | 1.8% | -12.8% | 0.20 | 0.14 | 36.6% | 14.9% |

## Out-of-Sample (2024-07-01 → 2026-06-01)

| Asset | Return | Max DD | Sharpe | Calmar | Win Rate | Time in Mkt |
|-------|-------:|-------:|-------:|-------:|---------:|------------:|
| BNB | -13.6% | -18.8% | -0.44 | -0.29 | 38.8% | 12.5% |
| CAKE | 17.8% | -32.8% | 0.36 | 0.20 | 35.9% | 14.4% |
| TWT | 12.9% | -26.4% | 0.32 | 0.18 | 40.4% | 11.7% |
| BTC | 4.0% | -11.9% | 0.22 | 0.12 | 36.5% | 10.6% |

## Robustness Check

OOS window: 2024-07-01 to 2026-06-01 · Asset: BNB

| Parameter Change | OOS Sharpe | Impact |
|------------------|----------:|--------|
| Base case | -0.44 | — |
| Funding threshold +10% | -0.44 | +0% |
| Holder threshold -10% | -0.44 | +0% |
| All gates +10% | -0.19 | +58% |

Strategy is fragile to threshold perturbation (OOS Sharpe < 1.0).

## Robustness Check

OOS window: 2024-07-01 to 2026-06-01 · Asset: CAKE

| Parameter Change | OOS Sharpe | Impact |
|------------------|----------:|--------|
| Base case | 0.36 | — |
| Funding threshold +10% | 0.36 | +0% |
| Holder threshold -10% | 0.36 | +0% |
| All gates +10% | 0.00 | -100% |

Strategy is fragile to threshold perturbation (OOS Sharpe < 1.0).

## Robustness Check

OOS window: 2024-07-01 to 2026-06-01 · Asset: TWT

| Parameter Change | OOS Sharpe | Impact |
|------------------|----------:|--------|
| Base case | 0.32 | — |
| Funding threshold +10% | 0.32 | +0% |
| Holder threshold -10% | 0.32 | +0% |
| All gates +10% | 0.18 | -44% |

Strategy is fragile to threshold perturbation (OOS Sharpe < 1.0).

## Robustness Check

OOS window: 2024-07-01 to 2026-06-01 · Asset: BTC

| Parameter Change | OOS Sharpe | Impact |
|------------------|----------:|--------|
| Base case | 0.22 | — |
| Funding threshold +10% | 0.22 | +0% |
| Holder threshold -10% | 0.22 | +0% |
| All gates +10% | -0.42 | -292% |

Strategy is fragile to threshold perturbation (OOS Sharpe < 1.0).

## Walk-Forward by Year

| Asset | Year | Return | Max DD | Sharpe |
|-------|-----:|-------:|-------:|-------:|
| BNB | 2023 | -2.8% | -9.8% | -0.47 |
| BNB | 2024 | 6.4% | -23.4% | 0.35 |
| BNB | 2025 | 3.1% | -12.2% | 0.25 |
| BNB | 2026 | -6.0% | -7.6% | -1.45 |
| CAKE | 2023 | 61.7% | -10.7% | 3.17 |
| CAKE | 2024 | 76.0% | -13.9% | 1.62 |
| CAKE | 2025 | 3.5% | -26.7% | 0.24 |
| CAKE | 2026 | -12.5% | -12.5% | -2.52 |
| TWT | 2023 | 10.5% | -15.3% | 1.18 |
| TWT | 2024 | -7.5% | -34.6% | -0.15 |
| TWT | 2025 | 8.1% | -19.5% | 0.36 |
| TWT | 2026 | -1.9% | -6.9% | -0.37 |
| BTC | 2023 | 0.7% | -3.0% | 0.35 |
| BTC | 2024 | 27.3% | -12.8% | 1.53 |
| BTC | 2025 | -0.1% | -6.1% | 0.02 |
| BTC | 2026 | -5.0% | -7.3% | -1.33 |

## Event Study (forward returns by regime)

When layers align (`aligned`), forward returns should beat `divergent` / `risk-off` buckets.

| Asset | Regime | Days | 7d mean | 7d hit% | 30d mean | 30d hit% |
|-------|--------|-----:|--------:|--------:|---------:|---------:|
| BNB | aligned | 238 | 0.7% | 48% | 4.7% | 52% |
| BNB | divergent | 670 | 1.2% | 55% | 4.3% | 61% |
| BNB | risk-off | 27 | -0.1% | 44% | 2.6% | 78% |
| CAKE | aligned | 261 | 1.4% | 44% | -0.2% | 44% |
| CAKE | divergent | 647 | 1.2% | 47% | 2.6% | 49% |
| CAKE | risk-off | 27 | 0.1% | 44% | 3.0% | 74% |
| TWT | aligned | 214 | -0.3% | 41% | -2.3% | 35% |
| TWT | divergent | 694 | 0.1% | 48% | -0.7% | 40% |
| TWT | risk-off | 27 | -3.4% | 19% | -8.1% | 22% |
| BTC | aligned | 208 | 0.6% | 55% | 4.9% | 55% |
| BTC | divergent | 700 | 0.9% | 55% | 2.6% | 55% |
| BTC | risk-off | 27 | 0.2% | 44% | 2.8% | 70% |

## Ablation (OOS — does each layer help?)

### BNB

| Variant | Return | Max DD | Sharpe |
|---------|-------:|-------:|-------:|
| full | -13.6% | -18.8% | -0.44 |
| no_derivatives | -14.4% | -18.8% | -0.48 |
| no_onchain | 0.0% | 0.0% | 0.00 |
| no_narrative | -16.1% | -20.2% | -0.53 |

### CAKE

| Variant | Return | Max DD | Sharpe |
|---------|-------:|-------:|-------:|
| full | 17.8% | -32.8% | 0.36 |
| no_derivatives | 18.1% | -32.6% | 0.36 |
| no_onchain | -3.5% | -7.9% | -0.17 |
| no_narrative | 15.2% | -32.1% | 0.33 |

### TWT

| Variant | Return | Max DD | Sharpe |
|---------|-------:|-------:|-------:|
| full | 12.9% | -26.4% | 0.32 |
| no_derivatives | 13.0% | -26.4% | 0.32 |
| no_onchain | 7.3% | -4.0% | 0.38 |
| no_narrative | 2.9% | -25.0% | 0.15 |

### BTC

| Variant | Return | Max DD | Sharpe |
|---------|-------:|-------:|-------:|
| full | 4.0% | -11.9% | 0.22 |
| no_derivatives | 5.3% | -11.1% | 0.28 |
| no_onchain | 0.0% | 0.0% | 0.00 |
| no_narrative | 4.0% | -11.9% | 0.22 |
