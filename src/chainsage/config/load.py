"""Load strategy mode configs (conservative.yaml) and apply threshold overrides."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import chainsage.signals.thresholds as t

ROOT = Path(__file__).resolve().parents[3]
CONSERVATIVE_PATH = ROOT / "config" / "conservative.yaml"

_SNAPSHOT: dict[str, Any] = {}


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ImportError:
        return _parse_minimal_yaml(text)


def _parse_minimal_yaml(text: str) -> dict[str, Any]:
    """Fallback when PyYAML is not installed (conservative.yaml is simple)."""
    data: dict[str, Any] = {}
    current_list: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not line.startswith("-"):
            current_list = line[:-1]
            data[current_list] = []
            continue
        if line.startswith("- ") and current_list:
            data.setdefault(current_list, []).append(line[2:].strip().strip('"'))
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key, val = key.strip(), val.strip()
            current_list = None
            if val.lower() in ("true", "false"):
                data[key] = val.lower() == "true"
            elif val.startswith('"'):
                data[key] = val.strip('"')
            else:
                try:
                    data[key] = float(val) if "." in val else int(val)
                except ValueError:
                    data[key] = val.split("#", 1)[0].strip()
    return data


def _snapshot() -> None:
    _SNAPSHOT.clear()
    for name in dir(t):
        if name.isupper() and not name.startswith("_"):
            val = getattr(t, name)
            if isinstance(val, (int, float, bool, list, dict)):
                _SNAPSHOT[name] = (
                    dict(val) if isinstance(val, dict) else list(val) if isinstance(val, list) else val
                )


def _restore() -> None:
    for name, val in _SNAPSHOT.items():
        setattr(t, name, val)


def apply_config_dict(cfg: dict[str, Any]) -> None:
    if "GATE_THRESHOLD" in cfg:
        t.GATE_THRESHOLD = float(cfg["GATE_THRESHOLD"])
    if "MAX_POSITION_SIZE" in cfg:
        t.MAX_POSITION_SIZE = float(cfg["MAX_POSITION_SIZE"])
    if "FNG_HARD_STOP" in cfg:
        t.FNG_HARD_STOP = int(cfg["FNG_HARD_STOP"])
    if "FUNDING_HARD_STOP" in cfg:
        t.FUNDING_HARD_STOP = float(cfg["FUNDING_HARD_STOP"])
    if "HARD_STOPS" in cfg:
        t.HARD_STOP_FALSIFIERS = list(cfg["HARD_STOPS"])
    if "SOFT_WARNINGS" in cfg:
        t.SOFT_WARNING_FALSIFIERS = list(cfg["SOFT_WARNINGS"])
    if "OI_CHANGE_SOFT" in cfg:
        t.OI_CHANGE_SOFT = float(cfg["OI_CHANGE_SOFT"])
    if "HOLDER_CONCENTRATION_SOFT" in cfg:
        t.HOLDER_CONCENTRATION_SOFT = float(cfg["HOLDER_CONCENTRATION_SOFT"])
    if "DERIVATIVES_POSITIVE_MILD" in cfg:
        t.DERIVATIVES_POSITIVE_MILD = bool(cfg["DERIVATIVES_POSITIVE_MILD"])
    if "MIN_LAYER_SCORE" in cfg:
        t.MIN_LAYER_SCORE = float(cfg["MIN_LAYER_SCORE"])


@contextmanager
def apply_strategy_config(path: Path | None = None) -> Iterator[dict[str, Any]]:
    cfg = _load_yaml(path or CONSERVATIVE_PATH)
    _snapshot()
    try:
        apply_config_dict(cfg)
        yield cfg
    finally:
        _restore()


def load_conservative_config() -> dict[str, Any]:
    return _load_yaml(CONSERVATIVE_PATH)
