from __future__ import annotations

import ast
import importlib.util
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
SCRIPT_DIR = ROOT / "skills" / "dify-local-sync" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SETUP = load_module("dify_local_setup", "setup.py")
SYNC = load_module("sync", "sync.py")
VERIFY = load_module("dify_local_verify", "verify.py")


class LocalSyncTests(unittest.TestCase):
    def test_setup_updates_env_without_exposing_or_duplicating_key(self) -> None:
        original = (
            "# local config\n"
            "INNER_API=false\n"
            "INNER_API_KEY=stale-secret\n"
            "OTHER=value\n"
            "INNER_API_KEY=duplicate-secret\n"
        )
        updated = SETUP.update_env_text(
            original,
            {"INNER_API": "true", "INNER_API_KEY": "generated-secret"},
        )
        self.assertIn("# local config", updated)
        self.assertIn("INNER_API=true", updated)
        self.assertIn("INNER_API_KEY=generated-secret", updated)
        self.assertEqual(1, updated.count("INNER_API_KEY="))

    def test_key_reader_uses_last_value_and_removes_matching_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "INNER_API_KEY=stale\nINNER_API_KEY=\"current-secret\"\n",
                encoding="utf-8",
            )
            self.assertEqual("current-secret", SETUP.read_env_value(env_file, "INNER_API_KEY"))

    def test_setup_override_injects_inner_api_without_embedding_secret(self) -> None:
        override = SETUP.render_compose_override("api")
        self.assertIn("INNER_API: ${INNER_API:-false}", override)
        self.assertIn("INNER_API_KEY: ${INNER_API_KEY:-}", override)
        self.assertNotIn("generated-secret", override)

    def test_compose_command_loads_existing_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compose = root / "docker" / "docker-compose.yaml"
            env_file = root / "docker" / ".env"
            override = root / "docker" / "docker-compose.override.yaml"
            compose.parent.mkdir()
            compose.touch()
            env_file.touch()
            override.touch()
            command = SYNC._compose_base(
                root,
                Path("docker/docker-compose.yaml"),
                Path("docker/.env"),
                Path("docker/docker-compose.override.yaml"),
            )
            self.assertEqual(2, command.count("-f"))
            self.assertIn(str(override), command)

    def test_key_resolves_from_compose_env_without_logging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_file = root / "docker" / ".env"
            env_file.parent.mkdir()
            env_file.write_text("INNER_API=true\nINNER_API_KEY=local-secret\n", encoding="utf-8")
            key = SYNC.resolve_inner_api_key(
                repo_root=root,
                explicit=None,
                compose_env_file=Path("docker/.env"),
            )
            self.assertEqual("local-secret", key)

    def test_environment_profile_only_updates_declared_variables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile.yml"
            profile.write_text(
                yaml.safe_dump(
                    {
                        "allow_undeclared_variables": True,
                        "environment_variables": {
                            "API_KEY": {"value": "secret-value", "value_type": "secret"},
                            "UNUSED": {"value": "ignored", "value_type": "string"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            source = yaml.safe_dump(
                {
                    "kind": "app",
                    "app": {"name": "Fixture", "mode": "workflow"},
                    "workflow": {
                        "environment_variables": [
                            {"name": "API_KEY", "value": "", "value_type": "secret"}
                        ]
                    },
                },
                sort_keys=False,
            )
            rendered, summary = SYNC.apply_env_profile_for_sync(
                repo_root=root,
                yaml_content=source,
                env_profile_arg="profile.yml",
                no_env_profile=False,
            )
            data = yaml.safe_load(rendered)
            self.assertEqual("secret-value", data["workflow"]["environment_variables"][0]["value"])
            self.assertEqual([{"name": "API_KEY", "value_type": "secret"}], summary["variables"])
            self.assertNotIn("secret-value", json.dumps(summary))

    def test_mapping_records_publish_state_without_account_email(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".dify-sync-map.json"
            result = SYNC.ImportResult(
                id="import-1",
                status="completed",
                app_id="app-1",
                app_mode="workflow",
                current_dsl_version="0.7.0",
                imported_dsl_version="0.7.0",
                error="",
            )
            publish = SYNC.PublishResult(workflow_id="workflow-1", workflow_version="version-1")
            SYNC.update_mapping(
                mapping={"version": 1, "files": {}},
                map_path=path,
                dsl_key="dev-dsl/app.yml",
                result=result,
                sha256="abc",
                base_url="http://127.0.0.1:8127",
                action="create",
                workspace_id="workspace-1",
                publish_result=publish,
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            entry = payload["files"]["dev-dsl/app.yml"]
            self.assertNotIn("account_email", entry)
            self.assertEqual("workflow-1", entry["published_workflow_id"])
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_container_service_helpers_are_valid_python(self) -> None:
        overwrite_code = SYNC._container_overwrite_code(
            {
                "yaml_content": "kind: app\n",
                "app_id": "app-1",
                "workspace_id": "workspace-1",
                "account_email": "user@example.com",
                "name": None,
                "description": None,
            }
        )
        ast.parse(overwrite_code)
        ast.parse(SYNC._container_publish_code(app_id="app-1", account_email="user@example.com"))
        self.assertIn('app_id=payload["app_id"]', overwrite_code)

    def test_inner_api_create_payload_does_not_support_overwrite_id(self) -> None:
        code = SYNC._container_curl_code(
            path="/inner/api/enterprise/workspaces/workspace-1/dsl/import",
            payload={"yaml_content": "kind: app\n", "creator_email": "user@example.com"},
            inner_api_key="secret",
        )
        ast.parse(code)
        self.assertNotIn("app_id", code)

    def test_verify_rejects_unpublished_current_sha(self) -> None:
        with self.assertRaises(VERIFY.CheckError):
            VERIFY.check_mapping(
                {"last_import_status": "completed", "sha256": "abc"},
                "abc",
                strict_sha=True,
                require_published=True,
            )

    def test_verify_detects_remote_graph_content_drift(self) -> None:
        local = VERIFY.summarize_dsl(
            yaml.safe_dump(
                {
                    "version": "0.7.0",
                    "kind": "app",
                    "app": {"name": "Fixture", "mode": "workflow"},
                    "workflow": {
                        "graph": {
                            "nodes": [{"id": "code", "data": {"type": "code", "code": "return 1"}}],
                            "edges": [],
                            "viewport": {"x": 10, "y": 20, "zoom": 1},
                        }
                    },
                },
                sort_keys=False,
            )
        )
        exported = VERIFY.summarize_dsl(
            yaml.safe_dump(
                {
                    "version": "0.7.0",
                    "kind": "app",
                    "app": {"name": "Fixture", "mode": "workflow"},
                    "workflow": {
                        "graph": {
                            "nodes": [{"id": "code", "data": {"type": "code", "code": "return 2"}}],
                            "edges": [],
                        }
                    },
                },
                sort_keys=False,
            )
        )
        with self.assertRaises(VERIFY.CheckError):
            VERIFY.compare_summaries(local, exported)


if __name__ == "__main__":
    unittest.main()
