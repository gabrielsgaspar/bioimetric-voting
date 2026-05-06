from __future__ import annotations

from datetime import datetime, timezone
from math import erf, sqrt
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]


def repo_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def ensure_directory(path_like: str | Path) -> Path:
    path = repo_path(path_like)
    path.mkdir(parents=True, exist_ok=True)
    return path


def stars_from_pvalue(p_value: float | None) -> str:
    if p_value is None:
        return ""
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return ""


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def two_sided_p_from_z(z_value: float) -> float:
    return 2.0 * (1.0 - normal_cdf(abs(z_value)))


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric:
        return None
    return numeric


def latex_escape(text: str) -> str:
    escaped = text
    for old, new in {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
    }.items():
        escaped = escaped.replace(old, new)
    return escaped


def timestamp_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def title_from_variable(variable: str) -> str:
    return variable.replace("_", " ").strip().title()
