"""Human gate configuration: controls which phase transitions require manual approval.

Reads .ai-loop/config/human_gates.json to determine whether each transition
should pause for human review ('manual') or proceed automatically ('auto').
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from orchestrator.constants import HUMAN_GATES_CONFIG_PATH

# Default policy when no config file exists or a transition is not listed.
_DEFAULT_POLICY = "auto"

# Transition keys use the format "phase_from -> phase_to".
_DEFAULTS = {
    "designing -> implementing": "manual",
    "implementing -> reviewing": "auto",
    "reviewing -> fixing": "auto",
    "reviewing -> designing": "manual",
    "reviewing -> done": "manual",
    "fixing -> reviewing": "auto",
}


def _load_config(path: Path = HUMAN_GATES_CONFIG_PATH) -> dict:
    """Load human_gates.json. Returns defaults on missing/invalid file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("transitions", {})
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return dict(_DEFAULTS)


def get_gate_policy(from_phase: str, to_phase: str, path: Path = HUMAN_GATES_CONFIG_PATH) -> str:
    """Return 'auto' or 'manual' for a given transition.

    Looks up 'from_phase -> to_phase' in config. Falls back to built-in
    defaults, then to the global default policy ('auto').
    """
    config = _load_config(path)
    key = f"{from_phase} -> {to_phase}"
    policy = config.get(key)
    if policy in ("auto", "manual"):
        return policy
    # Fall back to built-in defaults
    default = _DEFAULTS.get(key, _DEFAULT_POLICY)
    return default


def requires_human_approval(from_phase: str, to_phase: str, path: Path = HUMAN_GATES_CONFIG_PATH) -> bool:
    """Check if a transition requires manual human approval."""
    return get_gate_policy(from_phase, to_phase, path) == "manual"
