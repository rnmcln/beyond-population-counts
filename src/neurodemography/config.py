"""Read the project TOML configuration without hidden global state."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def project_root() -> Path:
    """Return the repository root based on this installed source file."""

    return Path(__file__).resolve().parents[2]


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load analysis configuration."""

    config_path = Path(path) if path else project_root() / "config" / "analysis.toml"
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def resolve_project_path(value: str | Path) -> Path:
    """Resolve a configured project-relative path."""

    path = Path(value)
    return path if path.is_absolute() else project_root() / path
