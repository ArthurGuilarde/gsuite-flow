"""Run required validation; integration is explicit and must not silently skip in CI."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration", action="store_true")
    args = parser.parse_args()
    if args.integration and not all(
        os.environ.get(key) for key in ("TEST_MIGRATION_DATABASE_URL", "TEST_DATABASE_URL")
    ):
        parser.error("--integration requires both disposable PostgreSQL test URLs")
    commands = [
        [sys.executable, "scripts/check_cli_docs.py"],
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "mypy"],
        [sys.executable, "-m", "pytest", "--cov", "--cov-report=term-missing:skip-covered"],
    ]
    if not args.integration:
        commands[-1] += ["-m", "not integration"]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
