#!/usr/bin/env python3
"""Check that a local Dify DSL file is synced to the local Dify app."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sync import resolve_inner_api_key


DEFAULT_BASE_URL = "http://127.0.0.1:8127"
DEFAULT_MAP_PATH = Path("dev-dsl/.dify-sync-map.json")
DEFAULT_COMPOSE_FILE = Path("docker/docker-compose.yaml")
DEFAULT_COMPOSE_ENV_FILE = Path("docker/.env")
DEFAULT_COMPOSE_OVERRIDE_FILE = Path("docker/docker-compose.override.yaml")
DEFAULT_ENV_PROFILE = Path("config/dify-env.local.yml")


class CheckError(RuntimeError):
    """Raised for expected sync-check failures."""


@dataclass(frozen=True)
class LocalDslSummary:
    name: str
    mode: str
    version: str
    kind: str
    node_count: int
    edge_count: int
    graph_sha256: str


@dataclass(frozen=True)
class AppDbSummary:
    id: str
    workspace_id: str
    name: str
    mode: str
    workflow_id: str
    workflow_version: str
    created_at: str
    updated_at: str


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    dify_root = Path(args.dify_root).resolve()
    dsl_path = resolve_path(project_root, args.dsl)
    map_path = resolve_path(project_root, args.map)

    try:
        source_text = dsl_path.read_text(encoding="utf-8")
        local_text = apply_env_profile_for_check(
            repo_root=project_root,
            yaml_content=source_text,
            env_profile_arg=args.env_profile,
            no_env_profile=args.no_env_profile,
        )
        local_sha = hashlib.sha256(local_text.encode("utf-8")).hexdigest()
        local_summary = summarize_dsl(local_text)

        mapping_entry = get_mapping_entry(project_root, map_path, dsl_path)
        app_id = args.app_id or mapping_entry.get("app_id")
        workspace_id = args.workspace_id or mapping_entry.get("workspace_id") or os.environ.get("DIFY_WORKSPACE_ID")
        if not app_id:
            raise CheckError(f"No app_id found for {relative_key(project_root, dsl_path)}. Sync it first or pass --app-id.")
        if not workspace_id:
            raise CheckError("No workspace_id found. Sync once, pass --workspace-id, or set DIFY_WORKSPACE_ID.")

        check_mapping(mapping_entry, local_sha, args.strict_sha, args.require_published)

        if not args.via_container:
            raise CheckError("Public local verification only supports --via-container.")
        inner_api_key = resolve_inner_api_key(
            repo_root=dify_root,
            explicit=args.inner_api_key,
            compose_env_file=Path(args.compose_env_file),
        )
        db_summary = fetch_db_summary_via_container(
            repo_root=dify_root,
            app_id=app_id,
            compose_file=Path(args.compose_file),
            compose_env_file=Path(args.compose_env_file),
            compose_override_file=Path(args.compose_override_file),
            service=args.compose_service,
        )
        if db_summary.workspace_id != workspace_id:
            raise CheckError(
                f"App workspace does not match the sync target: app={db_summary.workspace_id}, expected={workspace_id}"
            )
        exported_text = export_dsl_via_container(
            repo_root=dify_root,
            app_id=app_id,
            inner_api_key=inner_api_key,
            compose_file=Path(args.compose_file),
            compose_env_file=Path(args.compose_env_file),
            compose_override_file=Path(args.compose_override_file),
            service=args.compose_service,
        )

        exported_summary = summarize_dsl(exported_text)
        compare_summaries(local_summary, exported_summary)
        if args.require_published:
            check_published_runtime(mapping_entry, db_summary)

        print("sync-check: ok")
        print(f"dsl: {relative_key(project_root, dsl_path)}")
        print(f"app_id: {app_id}")
        print(f"workspace_id: {workspace_id}")
        print(f"local_sha256: {local_sha}")
        print(f"map_sha256: {mapping_entry.get('sha256') or ''}")
        if args.require_published:
            print(f"published_sha256: {mapping_entry.get('published_sha256') or ''}")
            print(f"published_workflow_id: {db_summary.workflow_id}")
            print(f"published_workflow_version: {db_summary.workflow_version}")
        print(f"app: {db_summary.name} ({db_summary.mode})")
        print(f"nodes: {local_summary.node_count}")
        print(f"edges: {local_summary.edge_count}")
        print(f"base_url: {args.base_url.rstrip('/')}")
        print(f"open: {args.base_url.rstrip('/')}/app/{app_id}/workflow")
        return 0
    except (CheckError, json.JSONDecodeError, OSError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a local Dify DSL sync result.")
    parser.add_argument("dsl", help="Path to the local app DSL YAML file.")
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
    parser.add_argument("--app-id", help="Explicit app_id to verify.")
    parser.add_argument("--workspace-id", help="Expected workspace/tenant id.")
    parser.add_argument("--inner-api-key", help="Inner API key. Defaults to DIFY_INNER_API_KEY or compose env file.")
    parser.add_argument("--via-container", action="store_true", help="Call Inner API from inside the local api container.")
    parser.add_argument("--compose-file", default=str(DEFAULT_COMPOSE_FILE))
    parser.add_argument("--compose-env-file", default=str(DEFAULT_COMPOSE_ENV_FILE))
    parser.add_argument("--compose-override-file", default=str(DEFAULT_COMPOSE_OVERRIDE_FILE))
    parser.add_argument("--compose-service", default="api")
    parser.add_argument(
        "--env-profile",
        default=os.environ.get("DIFY_ENV_PROFILE", str(DEFAULT_ENV_PROFILE)),
        help="Environment variable profile used to compute the effective local DSL. Defaults to config/dify-env.local.yml when present.",
    )
    parser.add_argument(
        "--no-env-profile",
        action="store_true",
        help="Check the DSL exactly as written without applying an environment variable profile.",
    )
    parser.add_argument(
        "--strict-sha",
        action="store_true",
        help="Fail if mapping sha256 does not equal the current local DSL sha256.",
    )
    parser.add_argument(
        "--require-published",
        action="store_true",
        help="Fail unless the current effective DSL was published after sync.",
    )
    return parser


def apply_env_profile_for_check(
    *,
    repo_root: Path,
    yaml_content: str,
    env_profile_arg: str,
    no_env_profile: bool,
) -> str:
    if no_env_profile or not env_profile_arg:
        return yaml_content

    profile_path = Path(env_profile_arg)
    if not profile_path.is_absolute():
        profile_path = repo_root / profile_path
    if not profile_path.exists():
        return yaml_content

    dsl = yaml.safe_load(yaml_content)
    if not isinstance(dsl, dict):
        raise CheckError("DSL YAML must contain a mapping before applying env profile.")
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or not isinstance(profile.get("environment_variables"), dict):
        raise CheckError(f"Environment profile must contain environment_variables mapping: {profile_path}")

    env_vars = dsl.get("workflow", {}).get("environment_variables")
    if not isinstance(env_vars, list):
        app = dsl.get("app")
        app_mode = str(app.get("mode") or "") if isinstance(app, dict) else ""
        if app_mode in {"agent-chat", "chat", "completion"} and "workflow" not in dsl:
            return yaml_content
        raise CheckError("DSL workflow.environment_variables is not a list; cannot apply env profile.")

    by_name: dict[str, dict[str, Any]] = {}
    for item in env_vars:
        if isinstance(item, dict) and item.get("name"):
            by_name[str(item["name"])] = item

    env_profile = profile["environment_variables"]
    missing = sorted(name for name in env_profile if name not in by_name)
    allow_undeclared = profile.get("allow_undeclared_variables") is True
    if missing and not allow_undeclared:
        raise CheckError(
            "Environment profile contains variables not declared in DSL: "
            + ", ".join(missing)
        )

    for name, override in env_profile.items():
        if name not in by_name:
            continue
        if not isinstance(override, dict):
            raise CheckError(f"Environment profile item must be a mapping: {name}")
        target = by_name[name]
        if "value" in override and override["value"] is not None:
            target["value"] = override["value"]
        if "value_type" in override:
            target["value_type"] = override["value_type"]

    return yaml.safe_dump(dsl, allow_unicode=True, sort_keys=False, width=1000)


def summarize_dsl(text: str) -> LocalDslSummary:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise CheckError("DSL YAML must contain a mapping.")
    app = data.get("app")
    if not isinstance(app, dict):
        raise CheckError("DSL missing app mapping.")
    mode = str(app.get("mode") or "")
    workflow = data.get("workflow")
    graph = workflow.get("graph") if isinstance(workflow, dict) else {}
    nodes = graph.get("nodes") if isinstance(graph, dict) else []
    edges = graph.get("edges") if isinstance(graph, dict) else []
    if mode in {"workflow", "advanced-chat"} and (not isinstance(nodes, list) or not isinstance(edges, list)):
        raise CheckError("DSL missing workflow graph nodes/edges.")
    if not isinstance(nodes, list):
        nodes = []
    if not isinstance(edges, list):
        edges = []
    normalized_graph = normalize_exported_graph(graph if isinstance(graph, dict) else {})
    return LocalDslSummary(
        name=str(app.get("name") or ""),
        mode=mode,
        version=str(data.get("version") or ""),
        kind=str(data.get("kind") or ""),
        node_count=len(nodes),
        edge_count=len(edges),
        graph_sha256=hashlib.sha256(
            json.dumps(normalized_graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    )


def normalize_exported_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Remove fields that Dify intentionally drops or rewrites during import/export."""
    normalized = copy.deepcopy(graph)
    normalized.pop("viewport", None)
    nodes = normalized.get("nodes")
    if not isinstance(nodes, list):
        return normalized
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        remove_key_recursively(data, "credential_id")
        node_type = data.get("type")
        if node_type == "knowledge-retrieval":
            data.pop("dataset_ids", None)
        elif node_type == "trigger-schedule":
            data.pop("config", None)
        elif node_type == "trigger-webhook":
            data.pop("webhook_url", None)
            data.pop("webhook_debug_url", None)
        elif node_type == "trigger-plugin":
            data.pop("subscription_id", None)
    return normalized


def remove_key_recursively(value: Any, key: str) -> None:
    if isinstance(value, dict):
        value.pop(key, None)
        for child in value.values():
            remove_key_recursively(child, key)
    elif isinstance(value, list):
        for child in value:
            remove_key_recursively(child, key)


def get_mapping_entry(repo_root: Path, map_path: Path, dsl_path: Path) -> dict[str, Any]:
    if not map_path.exists():
        raise CheckError(f"Sync map does not exist: {map_path}")
    payload = json.loads(map_path.read_text(encoding="utf-8"))
    files = payload.get("files")
    if not isinstance(files, dict):
        raise CheckError(f"Sync map has no files object: {map_path}")
    key = relative_key(repo_root, dsl_path)
    entry = files.get(key)
    if not isinstance(entry, dict):
        raise CheckError(f"Sync map has no entry for {key}.")
    return entry


def check_mapping(
    entry: dict[str, Any],
    local_sha: str,
    strict_sha: bool,
    require_published: bool = False,
) -> None:
    status = entry.get("last_import_status")
    if status not in {"completed", "completed-with-warnings"}:
        raise CheckError(f"Last import status is not successful: {status}")
    map_sha = entry.get("sha256")
    if strict_sha and map_sha != local_sha:
        raise CheckError(f"Mapping sha256 does not match current local DSL: map={map_sha}, local={local_sha}")
    if require_published:
        published_sha = entry.get("published_sha256")
        workflow_id = entry.get("published_workflow_id")
        if published_sha != local_sha or not workflow_id:
            raise CheckError(
                "Current local DSL is not recorded as published: "
                f"published={published_sha}, local={local_sha}. Run sync with --publish."
            )


def check_published_runtime(entry: dict[str, Any], db_summary: AppDbSummary) -> None:
    if not db_summary.workflow_id or not db_summary.workflow_version:
        raise CheckError("Dify app does not have a published workflow.")
    if entry.get("published_workflow_id") != db_summary.workflow_id:
        raise CheckError(
            "Published workflow id does not match the sync map: "
            f"map={entry.get('published_workflow_id')}, database={db_summary.workflow_id}"
        )
    if entry.get("published_workflow_version") != db_summary.workflow_version:
        raise CheckError(
            "Published workflow version does not match the sync map: "
            f"map={entry.get('published_workflow_version')}, database={db_summary.workflow_version}"
        )


def compare_summaries(local: LocalDslSummary, exported: LocalDslSummary) -> None:
    problems = []
    for field in ("name", "mode", "version", "kind", "node_count", "edge_count"):
        if getattr(local, field) != getattr(exported, field):
            problems.append(f"{field}: local={getattr(local, field)!r}, exported={getattr(exported, field)!r}")
    if local.graph_sha256 != exported.graph_sha256:
        problems.append(
            f"graph_sha256: local={local.graph_sha256!r}, exported={exported.graph_sha256!r}"
        )
    if problems:
        raise CheckError("Exported app DSL summary does not match local DSL:\n" + "\n".join(problems))


def export_dsl_via_container(
    *,
    repo_root: Path,
    app_id: str,
    inner_api_key: str,
    compose_file: Path,
    compose_env_file: Path,
    compose_override_file: Path,
    service: str,
) -> str:
    if not inner_api_key:
        raise CheckError("Provide --inner-api-key or set DIFY_INNER_API_KEY.")
    code = f'''
import json
import urllib.error
import urllib.request

url = "http://127.0.0.1:5001/inner/api/enterprise/apps/{app_id}/dsl"
request = urllib.request.Request(url, headers={{"X-Inner-Api-Key": {inner_api_key!r}}}, method="GET")
try:
    with urllib.request.urlopen(request, timeout=60) as response:
        print(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    print(exc.read().decode("utf-8"))
    raise SystemExit(1)
'''
    completed = run_compose_python(
        repo_root,
        compose_file,
        compose_env_file,
        compose_override_file,
        service,
        code,
    )
    last_line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise CheckError(f"Container export did not return JSON:\n{completed.stdout.strip()}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), str):
        raise CheckError("Container export returned an unexpected payload.")
    return payload["data"]


def fetch_db_summary_via_container(
    *,
    repo_root: Path,
    app_id: str,
    compose_file: Path,
    compose_env_file: Path,
    compose_override_file: Path,
    service: str,
) -> AppDbSummary:
    code = f'''
import json
from sqlalchemy import text
from app import app as flask_app
from extensions.ext_database import db

with flask_app.app_context():
    row = db.session.execute(
        text("""
            select app.id, app.tenant_id, app.name, app.mode, app.workflow_id,
                   workflow.version as workflow_version,
                   app.created_at, app.updated_at
            from apps as app
            left join workflows as workflow on workflow.id = app.workflow_id
            where app.id = :app_id
        """),
        {{"app_id": {app_id!r}}},
    ).mappings().first()
    if row is None:
        raise SystemExit("app not found")
    print(json.dumps({{
        "id": str(row["id"]),
        "workspace_id": str(row["tenant_id"]),
        "name": row["name"],
        "mode": row["mode"],
        "workflow_id": str(row["workflow_id"] or ""),
        "workflow_version": str(row["workflow_version"] or ""),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }}, ensure_ascii=False))
'''
    completed = run_compose_python(
        repo_root,
        compose_file,
        compose_env_file,
        compose_override_file,
        service,
        code,
    )
    last_line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise CheckError(f"Container DB check did not return JSON:\n{completed.stdout.strip()}") from exc
    return AppDbSummary(
        id=str(payload.get("id") or ""),
        workspace_id=str(payload.get("workspace_id") or ""),
        name=str(payload.get("name") or ""),
        mode=str(payload.get("mode") or ""),
        workflow_id=str(payload.get("workflow_id") or ""),
        workflow_version=str(payload.get("workflow_version") or ""),
        created_at=str(payload.get("created_at") or ""),
        updated_at=str(payload.get("updated_at") or ""),
    )


def run_compose_python(
    repo_root: Path,
    compose_file: Path,
    compose_env_file: Path,
    compose_override_file: Path,
    service: str,
    code: str,
) -> subprocess.CompletedProcess[str]:
    command = compose_base(repo_root, compose_file, compose_env_file, compose_override_file) + [
        "exec",
        "-T",
        service,
        "/app/api/.venv/bin/python",
        "-",
    ]
    completed = subprocess.run(
        command,
        cwd=repo_root,
        input=code,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise CheckError(f"Command failed: {shlex.join(command)}\n{completed.stdout.strip()}")
    return completed


def compose_base(
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


def resolve_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def relative_key(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
