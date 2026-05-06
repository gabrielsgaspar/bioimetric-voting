from __future__ import annotations

from pathlib import Path

import yaml

from utils import repo_path


def load_config(config_path: str | Path) -> dict:
    resolved = repo_path(config_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {resolved}")
    with resolved.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Config file did not parse to a dictionary: {resolved}")
    config["config_path"] = str(resolved)
    return config


def dump_config(config: dict, output_path: str | Path) -> None:
    resolved = repo_path(output_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False, allow_unicode=False)
