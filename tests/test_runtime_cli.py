"""Behavioral coverage for the development/runtime command line."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args, env, timeout=15):
    return subprocess.run(
        [sys.executable, "-m", "src", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_dev_migrate_and_check_use_sqlite_without_starting_server(tmp_path):
    db_path = tmp_path / "local.sqlite3"
    env = os.environ.copy()
    env.update(
        DEV_DATABASE_URL=f"sqlite:///{db_path}",
        DATABASE_URL="postgresql+psycopg://invalid:invalid@127.0.0.1:1/unused",
        MIGRATION_DATABASE_URL="postgresql+psycopg://invalid:invalid@127.0.0.1:1/unused",
        AUTH_MODE="oidc",
        ENVIRONMENT="production",
    )
    env.pop("OIDC_CLIENT_ID", None)
    env.pop("OIDC_CLIENT_SECRET", None)

    migrated = run_cli("migrate", "--profile", "dev", env=env)
    assert migrated.returncode == 0, migrated.stderr
    assert db_path.is_file()
    assert "uvicorn" not in migrated.stdout.lower()

    checked = run_cli("check", "--profile", "dev", env=env)
    assert checked.returncode == 0, checked.stderr
    assert "uvicorn" not in checked.stdout.lower()
    assert "perfil=dev auth=local" in checked.stdout
    assert f"sqlite:///{db_path.name}" in checked.stdout
    assert "invalid" not in checked.stdout.lower()


def test_cli_requires_an_explicit_profile():
    result = run_cli(env=os.environ.copy())
    assert result.returncode != 0
    assert "--profile" in result.stderr
    assert "required" in result.stderr.lower()


def _production_env_file(path, migration_url=None):
    values = [
        "DATABASE_URL=postgresql+psycopg://runtime:runtime-secret@db.internal:5432/appdb",
        "PUBLIC_URL=https://app.example.test",
        "SESSION_ENCRYPTION_KEY=4XmJ1t0SXOjkCOaY1-6xD_SmEa_2L6et-F38rNO5FRs=",
        "OIDC_ISSUER=https://identity.example.test/issuer",
        "OIDC_CLIENT_ID=test-client",
        "OIDC_CLIENT_SECRET=test-secret",
        "CORE_URL=https://core.example.test",
    ]
    if migration_url:
        values.append(f"MIGRATION_DATABASE_URL={migration_url}")
    path.write_text("\n".join(values) + "\n", encoding="utf-8")


@pytest.mark.parametrize(
    "migration_url, expected_error",
    [
        (None, "require MIGRATION_DATABASE_URL"),
        (
            "postgresql+psycopg://runtime:another-secret@db.internal:5432/appdb",
            "separate owner credential",
        ),
        (
            "postgresql+psycopg://owner:owner-secret@db.internal:5432/otherdb",
            "same PostgreSQL database",
        ),
    ],
)
def test_production_migration_requires_separate_owner_target(tmp_path, migration_url, expected_error):
    env_file = tmp_path / ".env.production.migration"
    _production_env_file(env_file, migration_url)
    env = os.environ.copy()
    env.pop("MIGRATION_DATABASE_URL", None)
    result = run_cli("migrate", "--profile", "production", "--env-file", str(env_file), env=env)
    assert result.returncode != 0
    assert expected_error in result.stderr
    assert "runtime-secret" not in result.stderr + result.stdout
    assert "owner-secret" not in result.stderr + result.stdout


def test_direct_uvicorn_startup_logs_redacted_profile_address_and_database(tmp_path):
    db_path = tmp_path / "direct.sqlite3"
    env = os.environ.copy()
    env.update(DEV_DATABASE_URL=f"sqlite:///{db_path}", ENVIRONMENT="production", AUTH_MODE="oidc")
    for name in ("OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_ISSUER", "CORE_URL"):
        env.pop(name, None)
    migrated = run_cli("migrate", "--profile", "dev", env=env)
    assert migrated.returncode == 0, migrated.stderr

    port = _free_port()
    env.update(
        APP_PROFILE="dev",
        APP_ENV_FILE=str(tmp_path / "absent.env"),
        ENVIRONMENT="development",
        AUTH_MODE="local",
        DATABASE_URL=f"sqlite:///{db_path}",
        PUBLIC_URL=f"http://user:address-secret@127.0.0.1:{port}/?token=query-secret",
        HOST="127.0.0.1",
        PORT=str(port),
        COOKIE_SECURE="false",
        SESSION_ENCRYPTION_KEY="4XmJ1t0SXOjkCOaY1-6xD_SmEa_2L6et-F38rNO5FRs=",
        LOG_FORMAT="console",
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                pytest.fail(f"direct Uvicorn exited before serving HTTP: {stdout}\n{stderr}")
            try:
                if _request(urllib.request.build_opener(), f"http://127.0.0.1:{port}/health/live").status == 200:
                    break
            except (OSError, TimeoutError):
                time.sleep(0.15)
        else:
            pytest.fail("direct Uvicorn did not become ready on loopback")
    finally:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
    logs = stdout + stderr
    assert "Application startup profile=dev auth=local" in logs
    assert f"address=http://127.0.0.1:{port}" in logs
    assert "database=sqlite:///direct.sqlite3" in logs
    assert "address-secret" not in logs
    assert "query-secret" not in logs


def test_direct_production_uvicorn_rejects_migration_credentials(tmp_path):
    env = os.environ.copy()
    env.update(
        APP_PROFILE="production",
        APP_ENV_FILE=str(tmp_path / "absent.env"),
        ENVIRONMENT="production",
        AUTH_MODE="oidc",
        DATABASE_URL="postgresql+psycopg://runtime:runtime-secret@db.internal:5432/appdb",
        MIGRATION_DATABASE_URL="postgresql+psycopg://owner:owner-secret@db.internal:5432/appdb",
        PUBLIC_URL="https://app.example.test",
        COOKIE_SECURE="true",
        SESSION_ENCRYPTION_KEY="4XmJ1t0SXOjkCOaY1-6xD_SmEa_2L6et-F38rNO5FRs=",
        OIDC_CLIENT_ID="test-client",
        OIDC_CLIENT_SECRET="oidc-secret",
        CORE_URL="https://core.example.test",
    )
    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", "src.backend.main:app", "--host", "127.0.0.1", "--port", "0"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    logs = result.stdout + result.stderr
    assert result.returncode != 0
    assert "must not receive migration credentials" in logs
    assert "owner-secret" not in logs
    assert "runtime-secret" not in logs
    assert "oidc-secret" not in logs


def _container_command(path, marker):
    # The last match is the effective one; HEALTHCHECK continuation lines also start with CMD.
    lines = [line for line in (ROOT / path).read_text(encoding="utf-8").splitlines() if line.startswith(marker)]
    line = lines[-1]
    return json.loads(line.removeprefix(marker).strip())


def test_container_commands_start_through_the_profiled_cli():
    assert _container_command("Dockerfile", "CMD")[:6] == ["python", "-m", "src", "serve", "--profile", "production"]
    compose_app = _container_command("docker-compose.yml", "    command:")
    assert compose_app[:6] == ["python", "-m", "src", "serve", "--profile", "integrated"]


def test_container_production_command_rejects_migration_credentials(tmp_path):
    env_file = tmp_path / ".env.production"
    _production_env_file(env_file, "postgresql+psycopg://owner:owner-secret@db.internal:5432/appdb")
    env = os.environ.copy()
    env.pop("MIGRATION_DATABASE_URL", None)
    command = _container_command("Dockerfile", "CMD")
    result = run_cli(*command[3:], "--env-file", str(env_file), env=env)
    logs = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Remove MIGRATION_DATABASE_URL" in logs
    assert "owner-secret" not in logs
    assert "runtime-secret" not in logs


def test_postgres_database_identifier_excludes_credentials_and_query():
    from src.backend.core.database import safe_database_identifier

    identifier = safe_database_identifier(
        "postgresql+psycopg://runtime:do-not-log@db.internal:5432/appdb?sslpassword=query-secret"
    )
    assert identifier == "postgresql://db.internal:5432/appdb"
    assert "runtime" not in identifier
    assert "do-not-log" not in identifier
    assert "query-secret" not in identifier


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _request(opener, url, *, method="GET", body=None, headers=None):
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        return opener.open(request, timeout=2)
    except urllib.error.HTTPError as response:
        return response


def test_python_module_dev_serves_local_auth_and_tenant_context(tmp_path):
    """Exercise the documented command through a real loopback HTTP connection."""
    db_path = tmp_path / "http.sqlite3"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        DEV_DATABASE_URL=f"sqlite:///{db_path}",
        DATABASE_URL="postgresql+psycopg://invalid:invalid@127.0.0.1:1/unused",
        MIGRATION_DATABASE_URL="postgresql+psycopg://invalid:invalid@127.0.0.1:1/unused",
        AUTH_MODE="local",
        ENVIRONMENT="development",
        PUBLIC_URL=base_url,
        COOKIE_SECURE="false",
        RATE_LIMIT_ENABLED="false",
    )
    for name in ("OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_ISSUER", "CORE_URL"):
        env.pop(name, None)

    process = subprocess.Popen(
        [sys.executable, "-m", "src", "--profile", "dev", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else ""
                pytest.fail(f"development CLI exited before serving HTTP: {stderr}")
            try:
                response = _request(opener, f"{base_url}/health/live")
                if response.status == 200:
                    break
            except (OSError, TimeoutError):
                time.sleep(0.15)
        else:
            pytest.fail("development CLI did not become ready on loopback")

        login = _request(opener, f"{base_url}/auth/login")
        # urllib follows the documented redirect to the local sign-in page.
        assert login.status == 200
        assert login.geturl().endswith("/auth/dev/login")

        config_response = _request(opener, f"{base_url}/auth/dev/config")
        assert config_response.status == 200
        config = json.loads(config_response.read())
        assert {user["id"] for user in config["users"]} >= {"editor-a", "reader-a", "editor-b"}
        csrf = config["csrf_token"]

        rejected_login = _request(
            opener,
            f"{base_url}/auth/dev/login",
            method="POST",
            body=b'{"user_id":"editor-a"}',
            headers={"Content-Type": "application/json", "Origin": "https://attacker.example", "X-CSRF-Token": csrf},
        )
        assert rejected_login.status == 403

        login_response = _request(
            opener,
            f"{base_url}/auth/dev/login",
            method="POST",
            body=b'{"user_id":"editor-a"}',
            headers={"Content-Type": "application/json", "Origin": base_url, "X-CSRF-Token": csrf},
        )
        assert login_response.status == 204
        assert "httponly" in login_response.headers.get("Set-Cookie", "").lower()
        session_response = _request(opener, f"{base_url}/auth/session")
        assert session_response.status == 200
        session = json.loads(session_response.read())
        assert session["sub"] == "editor-a"
        assert "access_token" not in session
        assert "csrf_token" in session

        tenants_response = _request(opener, f"{base_url}/auth/tenants")
        assert tenants_response.status == 200
        tenants_payload = json.loads(tenants_response.read())
        tenant_list = tenants_payload.get("tenants", tenants_payload)
        assert tenant_list
        tenant_a = tenant_list[0]
        tenant_id = tenant_a.get("id", tenant_a.get("tenant_id"))
        assert tenant_id
        context = _request(
            opener,
            f"{base_url}/api/v1/context",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
        assert context.status == 200
        context_json = json.loads(context.read())
        assert {"access", "read", "write"} <= set(context_json["permissions"])

        # The read-only fixture can read the same tenant but must not inherit
        # the editor's write grant from the prior session.
        config = json.loads(_request(opener, f"{base_url}/auth/dev/config").read())
        reader_login = _request(
            opener,
            f"{base_url}/auth/dev/login",
            method="POST",
            body=b'{"user_id":"reader-a"}',
            headers={
                "Content-Type": "application/json",
                "Origin": base_url,
                "X-CSRF-Token": config["csrf_token"],
            },
        )
        assert reader_login.status == 204
        reader_context = _request(
            opener,
            f"{base_url}/api/v1/context",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
        assert reader_context.status == 200
        assert set(json.loads(reader_context.read())["permissions"]) == {"access", "read"}

        config = json.loads(_request(opener, f"{base_url}/auth/dev/config").read())
        other_user_login = _request(
            opener,
            f"{base_url}/auth/dev/login",
            method="POST",
            body=b'{"user_id":"editor-b"}',
            headers={
                "Content-Type": "application/json",
                "Origin": base_url,
                "X-CSRF-Token": config["csrf_token"],
            },
        )
        assert other_user_login.status == 204
        cross_tenant = _request(
            opener,
            f"{base_url}/api/v1/context",
            headers={"X-Tenant-ID": str(tenant_id)},
        )
        assert cross_tenant.status == 403
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
