"""Check that the explicit CLI profiles and their commands stay documented."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from src.__main__ import build_parser

    parser = build_parser()
    actions = {action.dest: action for action in parser._actions}
    profile_action = actions["profile"]
    profiles = set(profile_action.choices or ())
    if not profile_action.required:
        raise SystemExit("CLI documentation parity failed: --profile must remain required")
    command_action = actions["command"]
    commands = set(command_action.choices or ())

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    operations = (ROOT / "docs/operations.md").read_text(encoding="utf-8")
    missing = []
    for profile in sorted(profiles):
        if f"`{profile}`" not in readme or f"--profile {profile}" not in operations:
            missing.append(profile)
    if missing:
        raise SystemExit(f"CLI documentation parity failed: profiles missing from README/operations: {missing}")

    readme_examples = {
        "dev": ("python -m src --profile dev --reload",),
        "integrated": ("python -m src migrate --profile integrated", "python -m src --profile integrated"),
        "production": ("python -m src migrate --profile production --env-file .env.production.migration",),
    }
    for _profile, examples in readme_examples.items():
        for example in examples:
            if example not in readme:
                missing.append(example)
    for profile in profiles:
        for command in commands:
            example = (
                f"python -m src --profile {profile}"
                if command == "serve"
                else f"python -m src {command} --profile {profile}"
            )
            if profile == "production":
                env_file = ".env.production.migration" if command == "migrate" else ".env.production"
                example += f" --env-file {env_file}"
            if example not in operations:
                missing.append(example)
    if missing:
        raise SystemExit(f"CLI documentation parity failed: missing scenario examples: {missing}")

    # Catch unsafe profile-less examples in the operational documentation.
    for path in [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip().lstrip("`> ")
            if stripped.startswith("python -m src") and "--profile" not in stripped:
                raise SystemExit(
                    f"CLI documentation parity failed: {path.relative_to(ROOT)}:{line_number} omits --profile"
                )

    print(f"CLI documentation parity: {len(profiles)} profiles and {len(commands)} commands documented.")


if __name__ == "__main__":
    main()
