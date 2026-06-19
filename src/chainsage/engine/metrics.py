"""Backtest metrics helpers."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min())


def sharpe_ratio(returns: pd.Series, periods_per_year: float = 252.0) -> float:
    if len(returns) < 2 or returns.std() == 0:
        return 0.0
    return float(np.sqrt(periods_per_year) * returns.mean() / returns.std())


def cagr(equity: pd.Series, periods_per_year: float = 252.0) -> float:
    if len(equity) < 2:
        return 0.0
    years = len(equity) / periods_per_year
    if years <= 0:
        return 0.0
    total = float(equity.iloc[-1] / equity.iloc[0])
    if total <= 0:
        return 0.0
    return float(total ** (1.0 / years) - 1.0)


def calmar_ratio(returns: pd.Series, equity: pd.Series, periods_per_year: float = 252.0) -> float:
    dd = abs(max_drawdown(equity))
    if dd < 1e-9:
        return 0.0
    return float(cagr(equity, periods_per_year) / dd)


def summarize(returns: pd.Series, equity: pd.Series, exposure: pd.Series | None = None) -> dict[str, float]:
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1) if len(equity) > 1 else 0.0
    wins = (returns > 0).sum()
    trades = (returns != 0).sum()
    win_rate = float(wins / trades) if trades > 0 else 0.0
    time_in_market = float(exposure.mean()) if exposure is not None and len(exposure) else float((returns != 0).mean())
    return {
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_drawdown(equity), 4),
        "sharpe_ratio": round(sharpe_ratio(returns), 3),
        "calmar_ratio": round(calmar_ratio(returns, equity), 3),
        "win_rate": round(win_rate, 3),
        "days_in_market_pct": round(float((returns != 0).mean()), 3),
        "time_in_market": round(time_in_market, 3),
    }


def _norm_ppf(p: float) -> float:
    """Inverse standard normal CDF — Acklam's approximation."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf

    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964538424692e-01,
        -2.400758277161838e00,
        -2.549507540312977e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]

    plow = 0.02425
    phigh = 1.0 - plow

    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )

    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def sharpe_variance(
    sharpe: float,
    n_observations: int,
    *,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Variance of Sharpe ratio estimator (Lo, 2002; Lopez de Prado, 2014)."""
    n = max(n_observations, 2)
    return (
        1.0
        + 0.5 * sharpe**2
        - skew * sharpe
        + ((kurtosis - 3.0) / 4.0) * sharpe**2
    ) / (n - 1)


def expected_max_sharpe(n_trials: int) -> float:
    """Expected maximum Sharpe under null across n independent trials."""
    n = max(n_trials, 1)
    if n == 1:
        return 0.0
    euler = 0.5772156649
    z1 = _norm_ppf(1.0 - 1.0 / n)
    z2 = _norm_ppf(1.0 - 1.0 / (n * math.e))
    return (1.0 - euler) * z1 + euler * z2


def deflated_sharpe(
    sharpe: float,
    n_trials: int = 3,
    n_observations: int = 252,
    *,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """
    Lopez de Prado (2014) — adjusts observed Sharpe for multiple strategy testing.

    Subtracts the expected maximum Sharpe (selection-bias threshold) scaled by
    the standard error of the Sharpe estimator.
    """
    if n_observations < 2:
        return round(max(0.0, sharpe), 2)

    e_max = expected_max_sharpe(max(n_trials, 1))
    sr_std = math.sqrt(max(sharpe_variance(sharpe, n_observations, skew=skew, kurtosis=kurtosis), 1e-12))
    threshold = e_max * sr_std
    return round(max(0.0, sharpe - threshold), 2)


def deflated_sharpe_probability(
    sharpe: float,
    n_trials: int = 3,
    n_observations: int = 252,
    *,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Probabilistic DSR: P(true Sharpe > 0) after multiple-testing correction."""
    if n_observations < 2:
        return 0.5

    e_max = expected_max_sharpe(max(n_trials, 1))
    sr_std = math.sqrt(max(sharpe_variance(sharpe, n_observations, skew=skew, kurtosis=kurtosis), 1e-12))
    if sr_std < 1e-12:
        return 1.0 if sharpe > e_max * sr_std else 0.0
    z = (sharpe - e_max * sr_std) / sr_std
    return round(_norm_cdf(z), 2)
