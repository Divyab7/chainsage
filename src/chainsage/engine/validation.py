"""Overfitting diagnostics — CSCV probability of backtest overfitting (PBO)."""

from __future__ import annotations

import itertools
from typing import Sequence

import numpy as np
import pandas as pd

from chainsage.engine.metrics import sharpe_ratio


def probability_of_overfitting(
    returns: pd.Series,
    n_partitions: int = 8,
    trial_returns: Sequence[pd.Series] | None = None,
) -> float:
    """
    CSCV method (Bailey & Lopez de Prado, 2014).

    With multiple ``trial_returns`` (e.g. Conservative / Ensemble / Aggressive),
    estimates the probability that the in-sample winner underperforms out-of-sample
    relative to the trial universe — the standard PBO for multiple testing.

    With a single return series, uses half-sample IS/OOS Sharpe degradation rate.
    Values below 0.50 suggest robust structure; above 0.50 suggest overfitting risk.
    """
    if trial_returns and len(trial_returns) > 1:
        return _pbo_multiple_trials(trial_returns, n_partitions)

    r = returns.dropna().astype(float)
    if len(r) < n_partitions * 8:
        return 0.5

    groups = np.array_split(r.values, n_partitions)
    half = n_partitions // 2
    if half < 1:
        return 0.5

    degradations = 0
    total = 0

    for is_idx in itertools.combinations(range(n_partitions), half):
        oos_idx = [i for i in range(n_partitions) if i not in is_idx]
        is_ret = np.concatenate([groups[i] for i in is_idx])
        oos_ret = np.concatenate([groups[i] for i in oos_idx])
        if len(is_ret) < 10 or len(oos_ret) < 10:
            continue
        is_sr = sharpe_ratio(pd.Series(is_ret))
        oos_sr = sharpe_ratio(pd.Series(oos_ret))
        if is_sr > oos_sr:
            degradations += 1
        total += 1

    if total == 0:
        return 0.5
    return round(degradations / total, 2)


def _pbo_multiple_trials(trial_returns: Sequence[pd.Series], n_partitions: int = 8) -> float:
    """CSCV PBO across strategy variants tested on the same IS window."""
    aligned = [r.dropna().astype(float).reset_index(drop=True) for r in trial_returns]
    min_len = min(len(s) for s in aligned)
    if min_len < n_partitions * 8:
        return 0.5

    matrix = np.column_stack([s.iloc[:min_len].values for s in aligned])
    groups = [matrix[i::n_partitions] for i in range(n_partitions)]
    # Re-split contiguous blocks instead of strided for time-series respect
    groups = np.array_split(matrix, n_partitions, axis=0)
    half = n_partitions // 2
    if half < 1:
        return 0.5

    underperform = 0
    total = 0

    for is_idx in itertools.combinations(range(n_partitions), half):
        oos_idx = [i for i in range(n_partitions) if i not in is_idx]
        is_block = np.vstack([groups[i] for i in is_idx])
        oos_block = np.vstack([groups[i] for i in oos_idx])
        if len(is_block) < 10 or len(oos_block) < 10:
            continue

        is_sharpes = [sharpe_ratio(pd.Series(is_block[:, j])) for j in range(matrix.shape[1])]
        oos_sharpes = [sharpe_ratio(pd.Series(oos_block[:, j])) for j in range(matrix.shape[1])]
        winner = int(np.argmax(is_sharpes))
        oos_rank = sum(1 for s in oos_sharpes if s > oos_sharpes[winner])
        # IS winner below median OOS rank → overfitting signal
        if oos_rank >= len(oos_sharpes) / 2:
            underperform += 1
        total += 1

    if total == 0:
        return 0.5
    return round(underperform / total, 2)
