"""Initialize a new template instance without contacting the Core or modifying existing data."""

import argparse
import json
import re
import secrets
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_APP_ID = "suite-example"
TEMPLATE_PACKAGE = "template-suite-guilarde"
TEMPLATE_README_TITLE = "# template_suite_guilarde"
NEXT_STEPS = (
    "Preencha docs/project-context.md (objetivo, escopo, tenant, domínio e critérios de aceite).",
    "Revise os ADRs herdados em docs/adrs/ e aceite ou substitua os que estão Em discussão.",
    "Configure OIDC_CLIENT_ID e OIDC_CLIENT_SECRET no .env com o provider do Authentik.",
    "Registre suite-app.json no Core conforme docs/core-contract.md.",
    "Instale os hooks com pre-commit install e rode python scripts/validate.py.",
)


def replace_file(path: Path, old: str, new: str) -> None:
    if path.exists():
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def pending_items(root: Path) -> list[str]:
    """Return template leftovers without printing or reading secret values."""
    pending = []
    manifest = root / "suite-app.json"
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")).get("app_id") == TEMPLATE_APP_ID:
        pending.append(f"suite-app.json ainda usa app_id {TEMPLATE_APP_ID}; rode o bootstrap com --app-id")
    project = root / "pyproject.toml"
    if project.exists() and f'name = "{TEMPLATE_PACKAGE}"' in project.read_text(encoding="utf-8"):
        pending.append(f"pyproject.toml ainda se chama {TEMPLATE_PACKAGE}")
    readme = root / "README.md"
    if readme.exists() and readme.read_text(encoding="utf-8").startswith(TEMPLATE_README_TITLE + "\n"):
        pending.append("README.md ainda tem o título do template")
    context = root / "docs/project-context.md"
    if context.exists():
        undefined = context.read_text(encoding="utf-8").count("A definir")
        if undefined:
            pending.append(f"docs/project-context.md tem {undefined} seção(ões) A definir")
    env = root / ".env"
    if not env.exists():
        pending.append(".env não existe; rode o bootstrap")
    else:
        from dotenv import dotenv_values

        values = dotenv_values(env, encoding="utf-8")
        for key in ("OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"):
            if not (values.get(key) or "").strip():
                pending.append(f".env sem {key}")
    return pending


def check(root: Path) -> int:
    pending = pending_items(root)
    for item in pending:
        print("PENDENTE: " + item)
    if not pending:
        print("Nenhuma pendência de template encontrada.")
    return 1 if pending else 0


def initialize(args, parser) -> None:
    from cryptography.fernet import Fernet

    if not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", args.app_id):
        parser.error("app-id must have 3–63 lowercase letters, digits or hyphens")
    text_values = [value for value in vars(args).values() if isinstance(value, str)]
    if any("\n" in value or "\r" in value or "'" in value for value in text_values):
        parser.error("arguments must be single-line values without single quotes")
    destination = ROOT / ".env"
    if destination.exists():
        parser.error(".env already exists; refusing to overwrite secrets")
    owner_password, app_password = secrets.token_hex(24), secrets.token_hex(24)
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    changes = {
        "APP_ID": args.app_id,
        "PROJECT_NAME": "'" + args.name + "'",
        "PUBLIC_URL": args.public_url,
        "COOKIE_SECURE": "true" if args.public_url.startswith("https://") else "false",
        "POSTGRES_PASSWORD": owner_password,
        "APP_DB_PASSWORD": app_password,
        "SESSION_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "OIDC_ISSUER": args.issuer,
        "CORE_URL": args.core_url,
        "OIDC_AUDIENCE": args.app_id,
        "DATABASE_URL": f"postgresql+psycopg://guilarde_app:{app_password}@localhost:5432/guilarde",
        "MIGRATION_DATABASE_URL": f"postgresql+psycopg://guilarde_owner:{owner_password}@localhost:5432/guilarde",
    }
    env = (
        "\n".join(
            f"{line.split('=', 1)[0]}={changes[line.split('=', 1)[0]]}"
            if "=" in line and line.split("=", 1)[0] in changes
            else line
            for line in env.splitlines()
        )
        + "\n"
    )
    # Exclusive create keeps secrets safe on retries.
    with destination.open("x", encoding="utf-8") as file:
        file.write(env)
    destination.chmod(0o600)
    manifest_path = ROOT / "suite-app.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(app_id=args.app_id, name=args.name)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    project = ROOT / "pyproject.toml"
    text = project.read_text(encoding="utf-8")
    text = text.replace(f'name = "{TEMPLATE_PACKAGE}"', f'name = "{args.app_id}"')
    text = re.sub(r'^version = ".*"$', 'version = "0.1.0"', text, count=1, flags=re.MULTILINE)
    # A JSON string is a valid TOML basic string for any single-line name.
    description = json.dumps(args.name + ": Guilarde Suite application", ensure_ascii=False)
    text = re.sub(r"^description = .*$", lambda _: "description = " + description, text, count=1, flags=re.MULTILINE)
    project.write_text(text, encoding="utf-8")
    replace_file(ROOT / "README.md", TEMPLATE_README_TITLE + "\n", "# " + args.name + "\n")
    replace_file(ROOT / "src/frontend/index.html", "Guilarde Suite", escape(args.name))
    context = ROOT / "docs/project-context.md"
    replace_file(context, "**Projeto:** Guilarde Suite", "**Projeto:** " + args.name)
    replace_file(context, f"**APP_ID:** {TEMPLATE_APP_ID}", "**APP_ID:** " + args.app_id)
    master = ROOT / "docs/adrs/MASTER-ADR.md"
    if master.exists():
        text = master.read_text(encoding="utf-8")
        for label, value in (("Projeto", args.name), ("Última atualização", date.today().isoformat())):
            line = f"**{label}:** {value}  "
            text = re.sub(rf"^\*\*{label}:\*\* .*$", lambda _, line=line: line, text, count=1, flags=re.MULTILINE)
        master.write_text(text, encoding="utf-8")
    print("Inicializado. Próximos passos:")
    for number, step in enumerate(NEXT_STEPS, start=1):
        print(f"{number}. {step}")
    print("Confira o que falta com: python scripts/bootstrap.py --check")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="list template leftovers without changing files")
    parser.add_argument("--app-id")
    parser.add_argument("--name")
    parser.add_argument("--public-url", default="http://localhost:8000")
    parser.add_argument("--issuer", default="https://auth.guilarde.com/application/o/suite-example/")
    parser.add_argument("--core-url", default="https://core.guilarde.com")
    args = parser.parse_args()
    if args.check:
        raise SystemExit(check(ROOT))
    if not args.app_id or not args.name:
        parser.error("--app-id and --name are required unless --check is used")
    initialize(args, parser)


if __name__ == "__main__":
    main()
