#!/usr/bin/env bash
set -euo pipefail

rm -rf .mypy_cache || true

mypy --no-incremental "$@"
