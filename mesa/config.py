"""Centralized configuration loading.

All tunable thresholds (timeouts, confidence, schedule) live in ``config.yaml``
so they can be changed without touching code (ticket INFRA-003). Use
:func:`load_config` to read it and :func:`get` for dotted-key lookups.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Repo root is one level up from this file (mesa/config.py -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load and parse the YAML config file.

    Args:
        path: Optional path to a config file. Defaults to ``config.yaml`` at the repo root.

    Returns:
        The parsed configuration as a nested dict.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def get(config: dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    """Look up a value using a dotted key, e.g. ``get(cfg, "escalation.l1_wait_seconds")``.

    Returns ``default`` if any part of the path is missing.
    """
    node: Any = config
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
