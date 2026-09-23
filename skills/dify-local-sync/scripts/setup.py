#!/usr/bin/env python3
"""Safely enable Dify Inner API for a local Docker Compose deployment."""

from __future__ import annotations

import argparse
import json
import secrets
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_COMPOSE_FILE = Path("docker/docker-compose.yaml")
DEFAULT_COMPOSE_ENV_FILE = Path("docker/.env")
DEFAULT_COMPOSE_OVERRIDE_FILE = Path("docker/docker-compose.override.yaml")
MANAGED_OVERRIDE_MARKER = "# Managed by dify-local-sync."


class SetupError(RuntimeError):
    """Raised for expected setup failures."""


def read_env_value(path: Path, name: str) -> str | None:
    if not path.is_file():
        return None
    prefix = f"{name}="
    found = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            found = value or None
    return found


def update_env_text(text: str, updates: dict[str, str]) -> str:
    written: set[str] = set()
    lines: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            lines.append(raw_line)
            continue
        name = stripped.split("=", 1)[0]
        if name not in updates:
            lines.append(raw_line)
            continue
        if name not in written:
            lines.append(f"{name}={updates[name]}")
            written.add(name)
    remaining = [name for name in updates if name not in written]
    if remaining and lines and lines[-1] != "":
        lines.append("")
    for name in remaining:
        lines.append(f"{name}={updates[name]}")
    return "\n".join(lines).rstrip() + "\n"


def render_compose_override(api_service: str) -> str:
    return (
        f"{MANAGED_OVERRIDE_MARKER}\n"
        "# The secret remains in docker/.env and is expanded by Docker Compose.\n"
        "services:\n"
        f"  {api_service}:\n"
        "    environment:\n"
        "      INNER_API: ${INNER_API:-false}\n"
        "      INNER_API_KEY: ${INNER_API_KEY:-}\n"
    )


def compose_base(
    dify_root: Path,
    compose_file: Path,
    env_file: Path,
    override_file: Path | None,
) -> list[str]:
    command = ["docker", "compose", "-f", str(compose_file)]
    if override_file is not None and override_file.is_file():
        command.extend(["-f", str(override_file)])
    command.extend(["--env-file", str(env_file)])
    return command


def run(command: list[str], *, cwd: Path, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise SetupError(f"Command failed: {shlex.join(command)}\n{completed.stdout.strip()}")
    return completed


def is_git_tracked(dify_root: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(dify_root.resolve())
    except ValueError:
        return False
    completed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative.as_posix()],
        cwd=dify_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def verify_container_config(
    *,
    dify_root: Path,
    compose_file: Path,
    env_file: Path,
    override_file: Path,
    api_service: str,
    container_python: str,
) -> None:
    code = '''
import json
from configs import dify_config
print(json.dumps({
    "inner_api_enabled": bool(dify_config.INNER_API),
    "inner_api_key_configured": bool(dify_config.INNER_API_KEY),
}))
'''
    completed = run(
        compose_base(dify_root, compose_file, env_file, override_file)
        + ["exec", "-T", api_service, container_python, "-"],
        cwd=dify_root,
        input_text=code,
    )
    last_line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise SetupError(f"API container configuration check returned invalid JSON:\n{completed.stdout.strip()}") from exc
    if payload != {"inner_api_enabled": True, "inner_api_key_configured": True}:
        raise SetupError("API container did not load INNER_API=true with a configured key")


def resolve_under(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def make_backup(path: Path, backup_dir: Path, label: str, stamp: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.chmod(0o700)
    ignore_file = backup_dir / ".gitignore"
    if not ignore_file.exists():
        ignore_file.write_text("*\n", encoding="utf-8")
    backup = backup_dir / f"{stamp}-{label}.env"
    shutil.copy2(path, backup)
    backup.chmod(0o600)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Inner API for a local self-hosted Dify Docker stack.")
    parser.add_argument(
        "--dify-root",
        "--repo-root",
        dest="dify_root",
        type=Path,
        default=Path.cwd(),
        help="Root of the local Dify source/deployment checkout (--repo-root is a compatibility alias).",
    )
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE_FILE)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_COMPOSE_ENV_FILE)
    parser.add_argument("--override-file", type=Path, default=DEFAULT_COMPOSE_OVERRIDE_FILE)
    parser.add_argument("--api-service", default="api")
    parser.add_argument("--container-python", default="/app/api/.venv/bin/python")
    parser.add_argument("--rotate-key", action="store_true", help="Generate a new key even when one exists")
    parser.add_argument("--apply", action="store_true", help="Write configuration and recreate the API service")
    args = parser.parse_args()

    dify_root = args.dify_root.resolve()
    compose_file = resolve_under(dify_root, args.compose_file)
    env_file = resolve_under(dify_root, args.env_file)
    override_file = resolve_under(dify_root, args.override_file)

    try:
        if not compose_file.is_file():
            raise SetupError(f"Compose file not found: {compose_file}")
        if not env_file.is_file():
            raise SetupError(f"Compose env file not found: {env_file}")
        if is_git_tracked(dify_root, env_file):
            raise SetupError(f"Refusing to store INNER_API_KEY in a Git-tracked file: {env_file}")

        expected_override = render_compose_override(args.api_service)
        override_exists = override_file.is_file()
        override_text = override_file.read_text(encoding="utf-8") if override_exists else ""
        override_managed = override_exists and MANAGED_OVERRIDE_MARKER in override_text
        if override_exists and not override_managed:
            raise SetupError(
                f"Compose override already exists and is not managed by dify-local-sync: {override_file}. "
                "Pass --override-file with an unused local path."
            )
        if override_exists and is_git_tracked(dify_root, override_file):
            raise SetupError(f"Refusing to modify a Git-tracked Compose override: {override_file}")

        run(compose_base(dify_root, compose_file, env_file, override_file) + ["config", "--services"], cwd=dify_root)
        enabled = (read_env_value(env_file, "INNER_API") or "").lower() == "true"
        key_exists = bool(read_env_value(env_file, "INNER_API_KEY"))
        override_needs_write = override_text != expected_override
        changed = not enabled or not key_exists or args.rotate_key or override_needs_write

        print(f"dify_root: {dify_root}")
        print(f"compose_file: {compose_file}")
        print(f"env_file: {env_file}")
        print(f"override_file: {override_file}")
        print(f"inner_api_enabled: {enabled}")
        print(f"inner_api_key_configured: {key_exists}")
        print(f"planned_change: {changed}")
        print("inner_api_key: <redacted>")

        if not args.apply:
            print("dry-run: pass --apply to update configuration and recreate the API service")
            return 0

        if not changed:
            verify_container_config(
                dify_root=dify_root,
                compose_file=compose_file,
                env_file=env_file,
                override_file=override_file,
                api_service=args.api_service,
                container_python=args.container_python,
            )
            print("setup: already configured and verified")
            return 0

        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = env_file.parent / ".dify-local-sync-backups"
        env_backup = make_backup(env_file, backup_dir, "compose-env", stamp)
        previous_text = env_file.read_text(encoding="utf-8")
        key = read_env_value(env_file, "INNER_API_KEY")
        if not key or args.rotate_key:
            key = secrets.token_urlsafe(48)

        override_created = not override_exists
        override_backup = None
        if override_exists and override_needs_write:
            override_backup = make_backup(override_file, backup_dir, "compose-override", stamp)
        if override_needs_write:
            override_file.parent.mkdir(parents=True, exist_ok=True)
            override_file.write_text(expected_override, encoding="utf-8")
            override_file.chmod(0o600)

        env_file.write_text(
            update_env_text(previous_text, {"INNER_API": "true", "INNER_API_KEY": key}),
            encoding="utf-8",
        )
        env_file.chmod(0o600)

        try:
            compose = compose_base(dify_root, compose_file, env_file, override_file)
            run(compose + ["up", "-d", "--force-recreate", args.api_service], cwd=dify_root)
            verify_container_config(
                dify_root=dify_root,
                compose_file=compose_file,
                env_file=env_file,
                override_file=override_file,
                api_service=args.api_service,
                container_python=args.container_python,
            )
        except Exception:
            shutil.copy2(env_backup, env_file)
            env_file.chmod(0o600)
            if override_created:
                override_file.unlink(missing_ok=True)
            elif override_backup is not None:
                shutil.copy2(override_backup, override_file)
            compose = compose_base(dify_root, compose_file, env_file, override_file)
            run(compose + ["up", "-d", "--force-recreate", args.api_service], cwd=dify_root)
            raise

        print("setup: configured and verified")
        print(f"backup: {env_backup}")
        return 0
    except (SetupError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
