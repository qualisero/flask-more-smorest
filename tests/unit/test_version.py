"""Tests for version consistency across package files."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_version_matches_pyproject() -> None:
    """Test that __version__ in __init__.py matches pyproject.toml."""
    import flask_more_smorest

    # Read version from pyproject.toml
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    pyproject_version = pyproject["tool"]["poetry"]["version"]
    package_version = flask_more_smorest.__version__

    assert package_version == pyproject_version, (
        f"Version mismatch: __init__.py has '{package_version}' but pyproject.toml has '{pyproject_version}'"
    )
