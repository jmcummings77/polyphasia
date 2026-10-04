#!/usr/bin/env bash
# Script for running all tests and reporting coverage.
# May be called from any working directory.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
python -m pytest --cov=polyphasia --cov-config=pyproject.toml --cov-report=term-missing "$@"
