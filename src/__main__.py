"""Operational entry point. Load the selected profile before importing the application."""

import argparse
import os
import sys
from pathlib import Path


def configure_profile(args, parser):
    from dotenv import dotenv_values

    root = Path(__file__).resolve().parents[1]
    env_file = Path(args.env_file)
    if args.env_file != ".env" and not env_file.is_file():
        parser.error("The selected --env-file does not exist")
    if env_file.is_file():
        for key, value in dotenv_values(env_file, encoding="utf-8").items():
            if value is not None:
                os.environ.setdefault(key, value)
    profile = args.profile
    if args.host:
        os.environ["HOST"] = args.host
    if args.port is not None:
        os.environ["PORT"] = str(args.port)
    if profile == "dev":
        from cryptography.fernet import Fernet

        os.environ.update(
            ENVIRONMENT="development",
            AUTH_MODE="local",
            COOKIE_SECURE="false",
            SESSION_COOKIE="guilarde_dev_session",
            LOG_FORMAT="console",
        )
        os.environ["HOST"] = args.host or "127.0.0.1"
        display_host = f"[{os.environ['HOST']}]" if ":" in os.environ["HOST"] else os.environ["HOST"]
        os.environ["PUBLIC_URL"] = f"http://{display_host}:{os.environ.get('PORT', '8000')}"
        os.environ["DATABASE_URL"] = os.environ.get("DEV_DATABASE_URL", "sqlite:///" + str(root / ".local/dev.sqlite3"))
        if not os.environ["DATABASE_URL"].startswith(("sqlite:///", "sqlite+pysqlite:///")):
            parser.error("dev profile requires DEV_DATABASE_URL with a SQLite file")
        os.environ["MIGRATION_DATABASE_URL"] = os.environ["DATABASE_URL"]
        key_file = root / ".local/session.key"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with key_file.open("xb") as file:
                file.write(Fernet.generate_key())
            key_file.chmod(0o600)
        except FileExistsError:
            pass
        os.environ["SESSION_ENCRYPTION_KEY"] = key_file.read_text().strip()
    else:
        os.environ["ENVIRONMENT"] = "production" if profile == "production" else "development"
        if os.environ.get("AUTH_MODE", "oidc") != "oidc":
            parser.error("integrated and production profiles require AUTH_MODE=oidc")
        os.environ["AUTH_MODE"] = "oidc"
        if not os.environ.get("DATABASE_URL", "").startswith("postgresql+psycopg://"):
            parser.error("integrated and production profiles require a PostgreSQL DATABASE_URL")
    if args.reload and profile == "production":
        parser.error("--reload is forbidden in production")
    if profile == "production":
        os.environ["DEBUG"] = "false"
    else:
        os.environ["DEBUG"] = "true" if args.reload else "false"
    # Avoid fallback to a different .env after an explicit --env-file was selected.
    os.environ["APP_ENV_FILE"] = str(env_file.resolve())
    os.environ["APP_PROFILE"] = profile
    return profile


def migrate():
    from alembic import command
    from alembic.config import Config

    from src.backend.core.config import BASE_DIR

    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "src/backend/migrations"))
    command.upgrade(config, "head")


def check_external():
    import httpx

    from src.backend.core.config import settings

    if settings.AUTH_MODE == "local":
        print("Infra externa: dispensada no perfil dev.")
        return
    if not settings.OIDC_CLIENT_ID or not settings.OIDC_CLIENT_SECRET:
        raise RuntimeError("Configure OIDC_CLIENT_ID and OIDC_CLIENT_SECRET")
    url = settings.OIDC_ISSUER.rstrip("/") + "/.well-known/openid-configuration"
    with httpx.Client(timeout=5, follow_redirects=False) as client:
        response = client.get(url)
        response.raise_for_status()
        metadata = response.json()
        if metadata.get("issuer") != settings.OIDC_ISSUER:
            raise RuntimeError("OIDC discovery issuer does not match OIDC_ISSUER")
        if not all(metadata.get(key) for key in ("authorization_endpoint", "token_endpoint", "jwks_uri")):
            raise RuntimeError("OIDC discovery is missing required endpoints")
        # Token validation uses this fixed, issuer-scoped URL; verify it too.
        keys = client.get(settings.OIDC_ISSUER.rstrip("/") + "/jwks/")
        keys.raise_for_status()
        if not keys.json().get("keys"):
            raise RuntimeError("OIDC JWKS contains no keys")
    print("OIDC: discovery e JWKS acessíveis. Core: valide memberships no login e seleção de tenant.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or operate a Guilarde application")
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "migrate", "check"])
    parser.add_argument("--profile", choices=["dev", "integrated", "production"], required=True)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--reload", action="store_true")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        profile = configure_profile(args, parser)
        from src.backend.core.config import safe_public_address, settings
        from src.backend.core.database import safe_database_identifier, verify_database

        target_database_url = settings.DATABASE_URL
        if profile == "production" and args.command == "migrate":
            migration_url = settings.MIGRATION_DATABASE_URL
            if not migration_url:
                parser.error("Production migrations require MIGRATION_DATABASE_URL in the migration env file")
            from sqlalchemy.engine import make_url

            migration_target = make_url(migration_url)
            runtime_target = make_url(settings.DATABASE_URL)
            if migration_target.username == runtime_target.username:
                parser.error("Production migrations require a separate owner credential from the runtime role")
            migration_location = (
                (migration_target.host or "").lower(),
                migration_target.port or 5432,
                migration_target.database,
            )
            runtime_location = (
                (runtime_target.host or "").lower(),
                runtime_target.port or 5432,
                runtime_target.database,
            )
            if migration_location != runtime_location:
                parser.error("Production migration and runtime URLs must target the same PostgreSQL database")
            target_database_url = migration_url

        if profile == "production" and args.command != "migrate" and settings.MIGRATION_DATABASE_URL:
            parser.error(
                "Remove MIGRATION_DATABASE_URL from the production runtime environment; use owner only for migrate"
            )
        print(
            "Configuração: "
            f"perfil={profile} auth={settings.AUTH_MODE} endereço={safe_public_address(settings.PUBLIC_URL)} "
            f"banco={safe_database_identifier(target_database_url)}"
        )
        if args.command == "migrate":
            migrate()
            print(f"Migrações concluídas ({profile}).")
        elif args.command == "check":
            verify_database()
            print(f"Banco e migrações: OK ({profile}).")
            check_external()
        else:
            import uvicorn

            if profile == "dev":
                migrate()
                print("DEV LOCAL: identidades fictícias; SQLite não valida RLS do PostgreSQL.")
        if args.command == "serve":
            uvicorn.run(
                "src.backend.main:app",
                host=settings.HOST,
                port=settings.PORT,
                reload=args.reload,
                access_log=False,
                proxy_headers=False,
            )
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            message = "; ".join(item["msg"] for item in exc.errors(include_input=False, include_context=False))
        else:
            # Connection exceptions may contain credentials or URLs; never echo them.
            message = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print(f"Falha: {message}. Consulte docs/operations.md.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
