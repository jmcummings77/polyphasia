#!/usr/bin/env bash
# Script for running all tests and reporting coverage.
# Run from project root.

set -e

python -m pytest -c testing_framework/pytest.ini --quiet polyphasia
