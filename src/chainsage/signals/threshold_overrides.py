"""Temporary threshold overrides for sensitivity analysis."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import chainsage.signals.thresholds as t

_SNAPSHOT: dict[str, object] = {}


def _snapshot() -> None:
    _SNAPSHOT.clear()
    for name in dir(t):
        if name.isupper() and not name.startswith("_"):
            val = getattr(t, name)
            if isinstance(val, (int, float, dict)):
                _SNAPSHOT[name] = (
                    dict(val) if isinstance(val, dict) else val
                )


def _restore() -> None:
    for name, val in _SNAPSHOT.items():
        setattr(t, name, val)


def _scale_tiers(tiers: dict[float, float], scale: float) -> None:
    for key in tiers:
        tiers[key] *= scale


@contextmanager
def apply_threshold_scale(
    *,
    funding: float = 1.0,
    holder: float = 1.0,
    narrative: float = 1.0,
    gates: float = 1.0,
) -> Iterator[None]:
    """Scale tier thresholds: >1.0 = stricter gates, <1.0 = looser."""
    _snapshot()
    try:
        if funding != 1.0:
            _scale_tiers(t.DERIVATIVES_TIERS, funding)
            t.FUNDING_HARD_STOP *= funding

        if holder != 1.0:
            _scale_tiers(t.ONCHAIN_TIERS, holder)

        if narrative != 1.0:
            t.SECTOR_RANK_STRONG_BULL = max(1, int(t.SECTOR_RANK_STRONG_BULL * narrative))
            t.SECTOR_RANK_MILD_BULL = max(1, int(t.SECTOR_RANK_MILD_BULL * narrative))
            t.FNG_STRONG_BULL = int(t.FNG_STRONG_BULL * narrative)
            t.FNG_MILD_BULL = int(t.FNG_MILD_BULL * narrative)

        if gates != 1.0:
            t.GATE_THRESHOLD = min(3.0, t.GATE_THRESHOLD * gates)
            t.CONFLICT_THRESHOLD = max(-1.0, t.CONFLICT_THRESHOLD * gates)

        yield
    finally:
        _restore()
