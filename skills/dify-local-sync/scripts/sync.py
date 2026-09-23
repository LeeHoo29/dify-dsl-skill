#!/usr/bin/env python3
"""Sync a local Dify app DSL file to a local Dify console instance.

The script imports a DSL as a new app on first run, records the returned
``app_id`` in a local map, and reuses that ``app_id`` for later overwrites.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_BASE_URL = "http://127.0.0.1:8127"
DEFAULT_MAP_PATH = Path("dev-dsl/.dify-sync-map.json")
DEFAULT_COMPOSE_FILE = Path("docker/docker-compose.yaml")
DEFAULT_COMPOSE_ENV_FILE = Path("docker/.env")
DEFAULT_COMPOSE_OVERRIDE_FILE = Path("docker/docker-compose.override.yaml")
DEFAULT_ENV_PROFILE = Path("config/dify-env.local.yml")


class SyncError(RuntimeError):
    """Raised for expected sync failures."""


@dataclass(frozen=True)
class ImportResult:
    id: str
    status: str
    app_id: str | None
    app_mode: str | None
    current_dsl_version: str
    imported_dsl_version: str
    error: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ImportResult":
        return cls(
            id=str(payload.get("id") or ""),
            status=str(payload.get("status") or ""),
            app_id=payload.get("app_id"),
            app_mode=payload.get("app_mode"),
            current_dsl_version=str(payload.get("current_dsl_version") or ""),
            imported_dsl_version=str(payload.get("imported_dsl_version") or ""),
            error=str(payload.get("error") or ""),
        )


@dataclass(frozen=True)
class PublishResult:
    workflow_id: str
    workflow_version: str


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    dify_root = Path(args.dify_root).resolve()
    dsl_path = (project_root / args.dsl).resolve() if not Path(args.dsl).is_absolute() else Path(args.dsl).resolve()
    map_path = (project_root / args.map).resolve() if not Path(args.map).is_absolute() else Path(args.map).resolve()

    try:
        yaml_content = read_dsl(dsl_path)
        import_yaml_content, env_summary = apply_env_profile_for_sync(
            repo_root=project_root,
            yaml_content=yaml_content,
            env_profile_arg=args.env_profile,
            no_env_profile=args.no_env_profile,
        )
        sha256 = hashlib.sha256(import_yaml_content.encode("utf-8")).hexdigest()
        if not args.skip_validation:
            run_validator(project_root, dsl_path)

        if not args.via_container:
            raise SyncError("Public local sync only supports --via-container; remote Inner API access is intentionally disabled.")

        mapping = load_mapping(map_path)
        rel_dsl_path = _relative_key(project_root, dsl_path)
        existing = mapping.get("files", {}).get(rel_dsl_path, {})
        mapped_app_id = existing.get("app_id") if isinstance(existing, dict) else None
        mapped_workspace_id = existing.get("workspace_id") if isinstance(existing, dict) else None
        app_id = args.app_id or (None if args.force_create else mapped_app_id)
        requested_workspace_id = args.workspace_id or mapped_workspace_id or os.environ.get("DIFY_WORKSPACE_ID")
        dsl_app_mode = get_app_mode(import_yaml_content)
        account_email, workspace_id = resolve_local_context_via_container(
            repo_root=dify_root,
            account_email=args.account_email,
            workspace_id=requested_workspace_id,
            compose_file=Path(args.compose_file),
            compose_env_file=Path(args.compose_env_file),
            compose_override_file=Path(args.compose_override_file),
            service=args.compose_service,
        )

        if args.publish and dsl_app_mode not in {"workflow", "advanced-chat"}:
            raise SyncError(f"--publish does not support app mode {dsl_app_mode!r}.")

        if not args.apply:
            if app_id and dsl_app_mode not in {"workflow", "advanced-chat"}:
                print(
                    f"dry-run: app mode {dsl_app_mode!r} cannot be overwritten by the current Dify DSL import path; "
                    "use --force-create to create a replacement app and update the sync map."
                )
                return 1
            action = "overwrite" if app_id else "create"
            print(f"dry-run: would {action} app from {rel_dsl_path}")
            if app_id:
                print(f"dry-run: target app_id={app_id}")
            if workspace_id:
                print(f"dry-run: workspace_id={workspace_id}")
            if args.publish:
                print("dry-run: would publish the imported workflow")
            print(f"dry-run: sha256={sha256}")
            if env_summary:
                print(f"dry-run: env_profile={env_summary['profile']}")
                for item in env_summary["variables"]:
                    print(f"dry-run: env={item['name']} ({item['value_type']})")
            return 0

        if app_id and dsl_app_mode not in {"workflow", "advanced-chat"}:
            raise SyncError(
                f"app mode {dsl_app_mode!r} cannot be overwritten by the current Dify DSL import path. "
                "Use --force-create to create a replacement app and update the sync map."
            )

        inner_api_key = resolve_inner_api_key(
            repo_root=dify_root,
            explicit=args.inner_api_key,
            compose_env_file=Path(args.compose_env_file),
        )
        if app_id:
            result = overwrite_via_container_service(
                repo_root=dify_root,
                yaml_content=import_yaml_content,
                app_id=app_id,
                workspace_id=workspace_id,
                account_email=account_email,
                name=args.name,
                description=args.description,
                compose_file=Path(args.compose_file),
                compose_env_file=Path(args.compose_env_file),
                compose_override_file=Path(args.compose_override_file),
                service=args.compose_service,
            )
        else:
            result = create_via_inner_api_container(
                repo_root=dify_root,
                yaml_content=import_yaml_content,
                workspace_id=workspace_id,
                inner_api_key=inner_api_key,
                account_email=account_email,
                name=args.name,
                description=args.description,
                compose_file=Path(args.compose_file),
                compose_env_file=Path(args.compose_env_file),
                compose_override_file=Path(args.compose_override_file),
                service=args.compose_service,
            )
        if result.status == "pending":
            result = confirm_import_via_container(
                repo_root=dify_root,
                import_id=result.id,
                account_email=account_email,
                workspace_id=workspace_id,
                compose_file=Path(args.compose_file),
                compose_env_file=Path(args.compose_env_file),
                compose_override_file=Path(args.compose_override_file),
                service=args.compose_service,
            )
        if result.status not in {"completed", "completed-with-warnings"} or not result.app_id:
            raise SyncError(f"Import failed: {result.error or result.status}")
        if app_id and result.app_id != app_id:
            raise SyncError(f"Mapped app_id {app_id} must be overwritten, but import returned app_id {result.app_id}.")

        publish_result = None
        if args.publish:
            publish_result = publish_via_container(
                repo_root=dify_root,
                app_id=result.app_id,
                account_email=account_email,
                compose_file=Path(args.compose_file),
                compose_env_file=Path(args.compose_env_file),
                compose_override_file=Path(args.compose_override_file),
                service=args.compose_service,
            )

        update_mapping(
            mapping=mapping,
            map_path=map_path,
            dsl_key=rel_dsl_path,
            result=result,
            sha256=sha256,
            base_url=args.base_url,
            action="overwrite" if app_id else "create",
            workspace_id=workspace_id,
            publish_result=publish_result,
        )
        print(f"synced: {rel_dsl_path}")
        print(f"status: {result.status}")
        print(f"app_id: {result.app_id}")
        if publish_result is not None:
            print(f"published: {publish_result.workflow_version}")
        print(f"map: {_relative_key(project_root, map_path)}")
        if env_summary:
            print(f"env_profile: {env_summary['profile']}")
            for item in env_summary["variables"]:
                print(f"env: {item['name']} ({item['value_type']})")
        return 0
    except (OSError, SyncError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import or overwrite a local Dify app DSL and remember the local file -> app_id mapping.",
    )
    parser.add_argument("dsl", help="Path to the app DSL YAML file.")
    parser.add_argument("--project-root", default=str(Path.cwd()), help="Root used to resolve the DSL, sync map, and environment profile.")
    parser.add_argument(
        "--dify-root",
        "--repo-root",
        dest="dify_root",
        default=os.environ.get("DIFY_ROOT", str(Path.cwd())),
        help="Root of the local Dify deployment (--repo-root is a compatibility alias).",
    )
    parser.add_argument("--base-url", default=os.environ.get("DIFY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--map", default=str(DEFAULT_MAP_PATH), help="Path to the sync mapping JSON file.")
    parser.add_argument("--app-id", help="Explicit target app_id. Also updates the mapping.")
    parser.add_argument("--force-create", action="store_true", help="Ignore any mapped app_id and create a new app.")
    parser.add_argument("--workspace-id", help="Dify workspace/tenant id. Defaults to mapped value or DIFY_WORKSPACE_ID.")
    parser.add_argument("--inner-api-key", help="Inner API key. Defaults to DIFY_INNER_API_KEY or compose env file.")
    parser.add_argument("--name", help="Override imported app name.")
    parser.add_argument("--description", help="Override imported app description.")
    parser.add_argument(
        "--via-container",
        action="store_true",
        help="Call Inner API from inside the running local api container.",
    )
    parser.add_argument(
        "--account-email",
        default=os.environ.get("DIFY_ACCOUNT_EMAIL"),
        help="Active local account email used as DSL creator. Auto-detected only when exactly one active account exists.",
    )
    parser.add_argument("--compose-file", default=str(DEFAULT_COMPOSE_FILE), help="Docker compose file for --via-container.")
    parser.add_argument(
        "--compose-env-file",
        default=str(DEFAULT_COMPOSE_ENV_FILE),
        help="Docker compose env file for --via-container.",
    )
    parser.add_argument(
        "--compose-override-file",
        default=str(DEFAULT_COMPOSE_OVERRIDE_FILE),
        help="Compose override created by setup; loaded when present.",
    )
    parser.add_argument("--compose-service", default="api", help="Docker compose service name for --via-container.")
    parser.add_argument(
        "--env-profile",
        default=os.environ.get("DIFY_ENV_PROFILE", str(DEFAULT_ENV_PROFILE)),
        help="Environment variable profile applied before local import. Defaults to config/dify-env.local.yml when present.",
    )
    parser.add_argument(
        "--no-env-profile",
        action="store_true",
        help="Import the DSL exactly as written without applying an environment variable profile.",
    )
    parser.add_argument("--skip-validation", action="store_true", help="Skip local DSL static validation.")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish the imported local workflow through the API container Service Layer.",
    )
    parser.add_argument("--apply", action="store_true", help="Execute import/overwrite. Without this flag the command is dry-run only.")
    return parser


def read_dsl(path: Path) -> str:
    if not path.exists():
        raise SyncError(f"DSL file does not exist: {path}")
    if not path.is_file():
        raise SyncError(f"DSL path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def get_app_mode(yaml_content: str) -> str:
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError:
        return ""
    app = data.get("app") if isinstance(data, dict) else None
    return str(app.get("mode") or "") if isinstance(app, dict) else ""


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


def resolve_inner_api_key(*, repo_root: Path, explicit: str | None, compose_env_file: Path) -> str:
    key = explicit or os.environ.get("DIFY_INNER_API_KEY")
    env_path = compose_env_file if compose_env_file.is_absolute() else repo_root / compose_env_file
    key = key or read_env_value(env_path, "INNER_API_KEY")
    if not key:
        raise SyncError(
            "Inner API key is not configured. Run the dify-local-sync setup command with --apply, "
            "or provide DIFY_INNER_API_KEY."
        )
    return key


def resolve_local_context_via_container(
    *,
    repo_root: Path,
    account_email: str | None,
    workspace_id: str | None,
    compose_file: Path,
    compose_env_file: Path,
    compose_override_file: Path,
    service: str,
) -> tuple[str, str]:
    payload = {"account_email": account_email, "workspace_id": workspace_id}
    code = f'''
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import app as flask_app
from extensions.ext_database import db
from models import Account
from models.account import AccountStatus, TenantAccountJoin

payload = {payload!r}
with flask_app.app_context():
    with Session(db.engine, expire_on_commit=False) as session:
        if payload["account_email"]:
            accounts = session.scalars(
                select(Account).where(
                    Account.email == payload["account_email"],
                    Account.status == AccountStatus.ACTIVE,
                ).limit(2)
            ).all()
        else:
            accounts = session.scalars(
                select(Account).where(Account.status == AccountStatus.ACTIVE).limit(2)
            ).all()
        if len(accounts) != 1:
            raise SystemExit("provide --account-email; local Dify does not have exactly one matching active account")
        account = accounts[0]
        joins = session.scalars(
            select(TenantAccountJoin).where(TenantAccountJoin.account_id == account.id)
        ).all()
        if payload["workspace_id"]:
            matching = [join for join in joins if str(join.tenant_id) == payload["workspace_id"]]
            if not matching:
                raise SystemExit("account is not a member of the requested workspace")
            selected = matching[0]
        else:
            current = [join for join in joins if join.current]
            if len(current) == 1:
                selected = current[0]
            elif len(joins) == 1:
                selected = joins[0]
            else:
                raise SystemExit("provide --workspace-id; account belongs to multiple workspaces")
        print(json.dumps({{
            "account_email": account.email,
            "workspace_id": str(selected.tenant_id),
        }}))
'''
    completed = _run(
        _compose_base(repo_root, compose_file, compose_env_file, compose_override_file)
        + ["exec", "-T", service, "/app/api/.venv/bin/python", "-"],
        repo_root,
        input_text=code,
    )
    last_line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    try:
        result = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise SyncError(f"Could not resolve local Dify account/workspace:\n{completed.stdout.strip()}") from exc
    resolved_email = str(result.get("account_email") or "")
    resolved_workspace = str(result.get("workspace_id") or "")
    if not resolved_email or not resolved_workspace:
        raise SyncError("Local Dify account/workspace resolution returned incomplete data.")
    return resolved_email, resolved_workspace


def apply_env_profile_for_sync(
    *,
    repo_root: Path,
    yaml_content: str,
    env_profile_arg: str,
    no_env_profile: bool,
) -> tuple[str, dict[str, Any] | None]:
    if no_env_profile or not env_profile_arg:
        return yaml_content, None

    profile_path = Path(env_profile_arg)
    if not profile_path.is_absolute():
        profile_path = repo_root / profile_path
    if not profile_path.exists():
        return yaml_content, None

    dsl = yaml.safe_load(yaml_content)
    if not isinstance(dsl, dict):
        raise SyncError("DSL YAML must contain a mapping before applying env profile.")
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or not isinstance(profile.get("environment_variables"), dict):
        raise SyncError(f"Environment profile must contain environment_variables mapping: {profile_path}")

    env_vars = dsl.get("workflow", {}).get("environment_variables")
    if not isinstance(env_vars, list):
        app = dsl.get("app")
        app_mode = str(app.get("mode") or "") if isinstance(app, dict) else ""
        if app_mode in {"agent-chat", "chat", "completion"} and "workflow" not in dsl:
            return yaml_content, None
        raise SyncError("DSL workflow.environment_variables is not a list; cannot apply env profile.")

    by_name: dict[str, dict[str, Any]] = {}
    for item in env_vars:
        if isinstance(item, dict) and item.get("name"):
            by_name[str(item["name"])] = item

    env_profile = profile["environment_variables"]
    missing = sorted(name for name in env_profile if name not in by_name)
    allow_undeclared = profile.get("allow_undeclared_variables") is True
    if missing and not allow_undeclared:
        raise SyncError(
            "Environment profile contains variables not declared in DSL: "
            + ", ".join(missing)
        )

    summary: list[dict[str, str]] = []
    for name, override in env_profile.items():
        if name not in by_name:
            continue
        if not isinstance(override, dict):
            raise SyncError(f"Environment profile item must be a mapping: {name}")
        target = by_name[name]
        if "value" in override and override["value"] is not None:
            target["value"] = override["value"]
        if "value_type" in override:
            target["value_type"] = override["value_type"]
        summary.append({"name": name, "value_type": str(target.get("value_type") or "")})

    return (
        yaml.safe_dump(dsl, allow_unicode=True, sort_keys=False, width=1000),
        {"profile": _relative_key(repo_root, profile_path), "variables": summary},
    )


def run_validator(repo_root: Path, dsl_path: Path) -> None:
    validator = Path(__file__).resolve().parents[2] / "dify-dsl" / "scripts" / "validate_dify_dsl.py"
    if not validator.exists():
        raise SyncError(f"DSL validator not found: {validator}")
    completed = subprocess.run(
        [sys.executable, str(validator), str(dsl_path)],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise SyncError(f"DSL validation failed:\n{completed.stdout.strip()}")


def create_via_inner_api_container(
    *,
    repo_root: Path,
    yaml_content: str,
    workspace_id: str,
    inner_api_key: str,
    account_email: str,
    name: str | None,
    description: str | None,
    compose_file: Path,
    compose_env_file: Path,
    compose_override_file: Path,
    service: str,
) -> ImportResult:
    compose = _compose_base(repo_root, compose_file, compose_env_file, compose_override_file)
    payload: dict[str, Any] = {
        "yaml_content": yaml_content,
        "creator_email": account_email,
    }
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description

    curl_code = _container_curl_code(
        path=f"/inner/api/enterprise/workspaces/{workspace_id}/dsl/import",
        payload=payload,
        inner_api_key=inner_api_key,
    )
    completed = _run(
        compose
        + [
            "exec",
            "-T",
            service,
            "/app/api/.venv/bin/python",
            "-",
        ],
        repo_root,
        input_text=curl_code,
    )

    last_line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    try:
        payload_json = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise SyncError(f"Container Inner API import did not return JSON:\n{completed.stdout.strip()}") from exc
    if not isinstance(payload_json, dict):
        raise SyncError("Container Inner API import returned non-object JSON.")
    result = ImportResult.from_payload(payload_json)
    return result


def overwrite_via_container_service(
    *,
    repo_root: Path,
    yaml_content: str,
    app_id: str,
    workspace_id: str,
    account_email: str,
    name: str | None,
    description: str | None,
    compose_file: Path,
    compose_env_file: Path,
    compose_override_file: Path,
    service: str,
) -> ImportResult:
    payload = {
        "yaml_content": yaml_content,
        "app_id": app_id,
        "workspace_id": workspace_id,
        "account_email": account_email,
        "name": name,
        "description": description,
    }
    code = _container_overwrite_code(payload)
    completed = _run(
        _compose_base(repo_root, compose_file, compose_env_file, compose_override_file)
        + ["exec", "-T", service, "/app/api/.venv/bin/python", "-"],
        repo_root,
        input_text=code,
    )
    last_line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    try:
        payload_json = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise SyncError(f"Container overwrite did not return JSON:\n{completed.stdout.strip()}") from exc
    if not isinstance(payload_json, dict):
        raise SyncError("Container overwrite returned non-object JSON.")
    return ImportResult.from_payload(payload_json)


def _container_overwrite_code(payload: dict[str, Any]) -> str:
    return f'''
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import app as flask_app
from extensions.ext_database import db
from models import Account
from models.account import AccountStatus
from services.app_dsl_service import AppDslService
from services.entities.dsl_entities import ImportMode, ImportStatus

payload = {payload!r}
with flask_app.app_context():
    with Session(db.engine, expire_on_commit=False) as session:
        account = session.scalar(
            select(Account).where(
                Account.email == payload["account_email"],
                Account.status == AccountStatus.ACTIVE,
            ).limit(1)
        )
        if account is None:
            raise SystemExit("active account not found")
        if hasattr(account, "set_tenant_id_with_session"):
            account.set_tenant_id_with_session(payload["workspace_id"], session=session)
        else:
            account.set_tenant_id(payload["workspace_id"])
        result = AppDslService(session).import_app(
            account=account,
            import_mode=ImportMode.YAML_CONTENT,
            yaml_content=payload["yaml_content"],
            name=payload["name"],
            description=payload["description"],
            app_id=payload["app_id"],
        )
        if result.status == ImportStatus.FAILED:
            session.rollback()
        else:
            session.commit()
        print(result.model_dump_json())
'''


def _container_curl_code(*, path: str, payload: dict[str, Any], inner_api_key: str) -> str:
    data = {
        "path": path,
        "payload": payload,
        "inner_api_key": inner_api_key,
    }
    return f"""
import json
import urllib.error
import urllib.request

data = {data!r}
url = "http://127.0.0.1:5001" + data["path"]
body = json.dumps(data["payload"]).encode("utf-8")
request = urllib.request.Request(
    url,
    data=body,
    headers={{"Content-Type": "application/json", "X-Inner-Api-Key": data["inner_api_key"]}},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=60) as response:
        print(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    print(exc.read().decode("utf-8"))
    raise SystemExit(1)
"""


def confirm_import_via_container(
    *,
    repo_root: Path,
    import_id: str,
    account_email: str,
    workspace_id: str,
    compose_file: Path,
    compose_env_file: Path,
    compose_override_file: Path,
    service: str,
) -> ImportResult:
    payload = {"import_id": import_id, "account_email": account_email, "workspace_id": workspace_id}
    code = f'''
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import app as flask_app
from extensions.ext_database import db
from models import Account
from models.account import AccountStatus
from services.app_dsl_service import AppDslService
from services.entities.dsl_entities import ImportStatus

payload = {payload!r}
with flask_app.app_context():
    with Session(db.engine, expire_on_commit=False) as session:
        account = session.scalar(
            select(Account).where(
                Account.email == payload["account_email"],
                Account.status == AccountStatus.ACTIVE,
            ).limit(1)
        )
        if account is None:
            raise SystemExit("active account not found")
        if hasattr(account, "set_tenant_id_with_session"):
            account.set_tenant_id_with_session(payload["workspace_id"], session=session)
        else:
            account.set_tenant_id(payload["workspace_id"])
        result = AppDslService(session).confirm_import(import_id=payload["import_id"], account=account)
        if result.status == ImportStatus.FAILED:
            session.rollback()
        else:
            session.commit()
        print(result.model_dump_json())
'''
    completed = _run(
        _compose_base(repo_root, compose_file, compose_env_file, compose_override_file)
        + ["exec", "-T", service, "/app/api/.venv/bin/python", "-"],
        repo_root,
        input_text=code,
    )
    last_line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    try:
        payload_json = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise SyncError(f"Container import confirmation did not return JSON:\n{completed.stdout.strip()}") from exc
    if not isinstance(payload_json, dict):
        raise SyncError("Container import confirmation returned non-object JSON.")
    return ImportResult.from_payload(payload_json)


def publish_via_container(
    *,
    repo_root: Path,
    app_id: str,
    account_email: str,
    compose_file: Path,
    compose_env_file: Path,
    compose_override_file: Path,
    service: str,
) -> PublishResult:
    completed = _run(
        _compose_base(repo_root, compose_file, compose_env_file, compose_override_file)
        + ["exec", "-T", service, "/app/api/.venv/bin/python", "-"],
        repo_root,
        input_text=_container_publish_code(app_id=app_id, account_email=account_email),
    )
    last_line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise SyncError(f"Container publish did not return JSON:\n{completed.stdout.strip()}") from exc
    workflow_id = str(payload.get("workflow_id") or "") if isinstance(payload, dict) else ""
    workflow_version = str(payload.get("workflow_version") or "") if isinstance(payload, dict) else ""
    if not workflow_id or not workflow_version:
        raise SyncError("Container publish returned an incomplete result.")
    return PublishResult(workflow_id=workflow_id, workflow_version=workflow_version)


def _container_publish_code(*, app_id: str, account_email: str) -> str:
    payload = {"app_id": app_id, "account_email": account_email}
    return f"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import app as flask_app
from extensions.ext_database import db
from libs.datetime_utils import naive_utc_now
from models import Account, App
from models.account import AccountStatus
from services.workflow_service import WorkflowService

payload = {payload!r}

with flask_app.app_context():
    with Session(db.engine, expire_on_commit=False) as session:
        app_model = session.get(App, payload["app_id"])
        if app_model is None:
            raise SystemExit("app not found")
        account = session.scalar(
            select(Account)
            .where(Account.email == payload["account_email"], Account.status == AccountStatus.ACTIVE)
            .limit(1)
        )
        if account is None:
            raise SystemExit("active account not found")
        if hasattr(account, "set_tenant_id_with_session"):
            account.set_tenant_id_with_session(app_model.tenant_id, session=session)
        else:
            account.set_tenant_id(app_model.tenant_id)
        workflow = WorkflowService().publish_workflow(
            session=session,
            app_model=app_model,
            account=account,
            marked_name="Local DSL sync",
            marked_comment="Published by dify-local-sync --publish.",
        )
        app_model.workflow_id = workflow.id
        app_model.updated_by = account.id
        app_model.updated_at = naive_utc_now()
        session.commit()
        print(json.dumps({{
            "workflow_id": str(workflow.id),
            "workflow_version": str(workflow.version),
        }}))
"""


def _compose_base(
    repo_root: Path,
    compose_file: Path,
    compose_env_file: Path,
    compose_override_file: Path | None = None,
) -> list[str]:
    resolved_compose = compose_file if compose_file.is_absolute() else repo_root / compose_file
    resolved_env = compose_env_file if compose_env_file.is_absolute() else repo_root / compose_env_file
    command = ["docker", "compose", "-f", str(resolved_compose)]
    if compose_override_file is not None:
        resolved_override = (
            compose_override_file if compose_override_file.is_absolute() else repo_root / compose_override_file
        )
        if resolved_override.is_file():
            command.extend(["-f", str(resolved_override)])
    command.extend(["--env-file", str(resolved_env)])
    return command


def _run(
    command: list[str],
    cwd: Path,
    *,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and completed.returncode != 0:
        raise SyncError(f"Command failed: {shlex.join(command)}\n{completed.stdout.strip()}")
    return completed


def load_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "files": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SyncError(f"Mapping file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SyncError(f"Mapping file must contain a JSON object: {path}")
    files = data.setdefault("files", {})
    if not isinstance(files, dict):
        raise SyncError(f"Mapping file field 'files' must be an object: {path}")
    data.setdefault("version", 1)
    return data


def update_mapping(
    *,
    mapping: dict[str, Any],
    map_path: Path,
    dsl_key: str,
    result: ImportResult,
    sha256: str,
    base_url: str,
    action: str,
    workspace_id: str | None,
    publish_result: PublishResult | None = None,
) -> None:
    files = mapping.setdefault("files", {})
    previous = files.get(dsl_key) if isinstance(files.get(dsl_key), dict) else {}
    entry = {
        "app_id": result.app_id,
        "app_mode": result.app_mode,
        "base_url": base_url.rstrip("/"),
        "workspace_id": workspace_id,
        "tenant_id": workspace_id,
        "last_action": action,
        "last_import_status": result.status,
        "current_dsl_version": result.current_dsl_version,
        "imported_dsl_version": result.imported_dsl_version,
        "sha256": sha256,
        "synced_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    publish_keys = (
        "published_sha256",
        "published_workflow_id",
        "published_workflow_version",
        "published_at",
    )
    if publish_result is None:
        entry.update({key: previous[key] for key in publish_keys if key in previous})
    else:
        entry.update(
            {
                "published_sha256": sha256,
                "published_workflow_id": publish_result.workflow_id,
                "published_workflow_version": publish_result.workflow_version,
                "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
    files[dsl_key] = entry
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    map_path.chmod(0o600)


def _relative_key(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
