#!/usr/bin/env bash
set -euo pipefail

# Type-check the project with pyright. Paths come from [tool.pyright] in
# pyproject.toml, so no arguments are needed for a full run.
poetry run pyright "$@"
