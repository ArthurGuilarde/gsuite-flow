import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# These tests exercise the uninitialized template; after bootstrap the copied files no longer match it.
pytestmark = pytest.mark.skipif(
    json.loads((ROOT / "suite-app.json").read_text(encoding="utf-8"))["app_id"] != "suite-example",
    reason="repositório já inicializado pelo bootstrap",
)
TEMPLATE_FILES = [
    "scripts/bootstrap.py",
    ".env.example",
    "suite-app.json",
    "pyproject.toml",
    "README.md",
    "src/frontend/index.html",
    "docs/project-context.md",
    "docs/adrs/MASTER-ADR.md",
]
# Windows pipes default to the ANSI code page; the assertions decode Portuguese output as UTF-8.
UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def copy_template(tmp_path):
    for path in TEMPLATE_FILES:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / path, tmp_path / path)


def run_check(tmp_path):
    return subprocess.run(
        [sys.executable, str(tmp_path / "scripts/bootstrap.py"), "--check"],
        capture_output=True,
        encoding="utf-8",
        env=UTF8_ENV,
    )


def test_bootstrap_exclusive(tmp_path):
    copy_template(tmp_path)
    command = [
        sys.executable,
        str(tmp_path / "scripts/bootstrap.py"),
        "--app-id",
        "minha-app",
        "--name",
        "Minha aplicação",
    ]
    assert subprocess.run(command, capture_output=True).returncode == 0
    before = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "CHANGE_ME" not in before
    assert "**APP_ID:** minha-app" in (tmp_path / "docs/project-context.md").read_text(encoding="utf-8")
    assert "**Projeto:** Minha aplicação" in (tmp_path / "docs/adrs/MASTER-ADR.md").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "suite-app.json").read_text(encoding="utf-8"))["app_id"] == "minha-app"
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert (tmp_path / ".env").read_text(encoding="utf-8") == before


def test_bootstrap_personalizes_project_metadata(tmp_path):
    copy_template(tmp_path)
    name = 'Gestão "Alfa"'
    command = [sys.executable, str(tmp_path / "scripts/bootstrap.py"), "--app-id", "gestao-alfa", "--name", name]
    result = subprocess.run(command, capture_output=True, encoding="utf-8", env=UTF8_ENV)
    assert result.returncode == 0, result.stderr
    assert "--check" in result.stdout
    assert (tmp_path / "README.md").read_text(encoding="utf-8").startswith(f"# {name}\n")
    project = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "gestao-alfa"' in project
    assert 'version = "0.1.0"' in project
    assert 'description = "Gestão \\"Alfa\\": Guilarde Suite application"' in project
    master = (tmp_path / "docs/adrs/MASTER-ADR.md").read_text(encoding="utf-8")
    assert f"**Projeto:** {name}  \n" in master
    assert f"**Última atualização:** {date.today().isoformat()}  \n" in master
    assert "Gestão &quot;Alfa&quot;" in (tmp_path / "src/frontend/index.html").read_text(encoding="utf-8")


def test_bootstrap_check_lists_template_leftovers(tmp_path):
    copy_template(tmp_path)
    before = run_check(tmp_path)
    assert before.returncode == 1
    for item in ("suite-app.json", "pyproject.toml", "README.md", "project-context.md", ".env não existe"):
        assert item in before.stdout
    assert not (tmp_path / ".env").exists()

    command = [sys.executable, str(tmp_path / "scripts/bootstrap.py"), "--app-id", "minha-app", "--name", "Minha"]
    assert subprocess.run(command, capture_output=True).returncode == 0
    after = run_check(tmp_path)
    assert after.returncode == 1
    pending = after.stdout.splitlines()
    assert len(pending) == 3
    assert "project-context.md" in pending[0]
    assert {"OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"} == {line.rsplit(" ", 1)[1] for line in pending[1:]}
    # Secrets are never echoed by the check.
    secret = next(line for line in (tmp_path / ".env").read_text(encoding="utf-8").splitlines() if "PASSWORD=" in line)
    assert secret.split("=", 1)[1] not in after.stdout
