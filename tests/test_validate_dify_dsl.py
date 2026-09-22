from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
VALIDATOR_PATH = ROOT / "skills" / "dify-dsl" / "scripts" / "validate_dify_dsl.py"
SPEC = importlib.util.spec_from_file_location("validate_dify_dsl", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def workflow(*nodes: dict[str, object], version: str = "0.7.0") -> dict[str, object]:
    return {
        "kind": "app",
        "version": version,
        "dependencies": [],
        "app": {"name": "Fixture", "mode": "workflow"},
        "workflow": {
            "environment_variables": [],
            "graph": {"nodes": list(nodes), "edges": []},
        },
    }


def messages(data: dict[str, object], target_version: str = "0.7.0") -> list[str]:
    return [str(issue) for issue in VALIDATOR.validate(data, target_version=target_version)]


class ValidatorTests(unittest.TestCase):
    def test_public_examples_have_no_errors(self) -> None:
        examples = ROOT / "skills" / "dify-dsl" / "examples"
        for path in examples.glob("*.yml"):
            with self.subTest(path=path.name):
                issues = VALIDATOR.validate(
                    VALIDATOR.load_yaml(path),
                    source_path=path,
                    target_version="0.7.0",
                    portable=True,
                )
                self.assertEqual([], [str(issue) for issue in issues if issue.level == "ERROR"])

    def test_version_is_checked_against_explicit_target(self) -> None:
        result = messages(workflow(version="0.7.0"), target_version="0.6.0")
        self.assertTrue(any("newer than" in message for message in result))

    def test_bodyless_http_request_requires_explicit_body_data(self) -> None:
        node = {
            "id": "request",
            "type": "custom",
            "data": {"type": "http-request", "method": "get", "body": {"type": "none"}},
        }
        result = messages(workflow(node))
        self.assertTrue(any("missing data.body.data" in message for message in result))

    def test_document_extractor_requires_file_cardinality(self) -> None:
        node = {
            "id": "extract",
            "type": "custom",
            "data": {"type": "document-extractor", "variable_selector": ["sys", "files"]},
        }
        result = messages(workflow(node))
        self.assertTrue(any("is_array_file must be an explicit boolean" in message for message in result))

    def test_llm_requires_context_mapping(self) -> None:
        node = {
            "id": "llm",
            "type": "custom",
            "data": {"type": "llm", "model": {"completion_params": {}}},
        }
        result = messages(workflow(node))
        self.assertTrue(any("missing data.context" in message for message in result))

    def test_code_return_keys_must_be_declared(self) -> None:
        node = {
            "id": "code",
            "type": "custom",
            "data": {
                "type": "code",
                "code_language": "python3",
                "code": "def main():\n    return {'result': 'ok'}\n",
                "variables": [],
                "outputs": {},
            },
        }
        result = messages(workflow(node))
        self.assertTrue(any("returned keys not declared" in message for message in result))

    def test_array_boolean_is_a_valid_code_output_type(self) -> None:
        node = {
            "id": "code",
            "type": "custom",
            "data": {
                "type": "code",
                "code_language": "python3",
                "code": "def main():\n    return {'flags': [True, False]}\n",
                "variables": [],
                "outputs": {"flags": {"type": "array[boolean]", "children": None}},
            },
        }
        result = messages(workflow(node))
        self.assertFalse(any("invalid type" in message for message in result))

    def test_long_variable_names_are_not_rejected_without_version_evidence(self) -> None:
        data = {
            "kind": "app",
            "version": "0.7.0",
            "dependencies": [],
            "app": {"name": "Fixture", "mode": "chat"},
            "model_config": {
                "model": {"mode": "chat", "name": "model", "provider": "provider"},
                "user_input_form": [
                    {"text-input": {"variable": "a_variable_name_longer_than_thirty_characters"}}
                ],
            },
        }
        result = messages(data)
        self.assertFalse(any("longer than" in message for message in result))

    def test_workspace_credential_is_only_rejected_in_portable_mode(self) -> None:
        data = {
            "kind": "app",
            "version": "0.7.0",
            "dependencies": [],
            "app": {"name": "Fixture", "mode": "agent-chat"},
            "model_config": {
                "model": {"mode": "chat", "name": "model", "provider": "provider"},
                "agent_mode": {
                    "enabled": True,
                    "max_iteration": 3,
                    "strategy": "function_call",
                    "tools": [
                        {
                            "provider_type": "builtin",
                            "provider_id": "provider",
                            "provider_name": "provider",
                            "tool_name": "tool",
                            "tool_label": "Tool",
                            "credential_id": "workspace-credential",
                        }
                    ],
                },
            },
        }
        ordinary = [str(issue) for issue in VALIDATOR.validate(data, target_version="0.7.0")]
        portable = [
            str(issue)
            for issue in VALIDATOR.validate(data, target_version="0.7.0", portable=True)
        ]
        self.assertFalse(any("credential_id" in message for message in ordinary))
        self.assertTrue(any("workspace-bound field" in message for message in portable))

    def test_empty_optional_selector_does_not_warn(self) -> None:
        node = {
            "id": "start",
            "type": "custom",
            "data": {"type": "start", "variables": [], "optional_selector": []},
        }
        result = messages(workflow(node))
        self.assertFalse(any("selector should contain" in message for message in result))

    def test_validator_does_not_enforce_project_specific_prompt_names(self) -> None:
        start = {
            "id": "start",
            "type": "custom",
            "data": {
                "type": "start",
                "variables": [{"variable": "selection_rule", "type": "text-input"}],
            },
        }
        result = messages(workflow(start))
        self.assertFalse(any("lacks 'prompt'" in message for message in result))

    def test_portable_mode_rejects_secret_values_without_echoing_them(self) -> None:
        secret = "sk-" + "proj-" + "examplevalue123456789"
        data = workflow()
        data["workflow"]["environment_variables"] = [
            {"name": "API_KEY", "value_type": "secret", "value": secret}
        ]

        result = [
            str(issue)
            for issue in VALIDATOR.validate(data, target_version="0.7.0", portable=True)
        ]

        self.assertTrue(any("secret environment variable" in message for message in result))
        self.assertFalse(any(secret in message for message in result))

    def test_portable_mode_rejects_dataset_ids(self) -> None:
        node = {
            "id": "knowledge",
            "type": "custom",
            "data": {"type": "knowledge-retrieval", "dataset_ids": ["workspace-dataset"]},
        }
        result = [
            str(issue)
            for issue in VALIDATOR.validate(
                workflow(node),
                target_version="0.7.0",
                portable=True,
            )
        ]
        self.assertTrue(any("workspace-bound field" in message for message in result))

    def test_yaml_loader_rejects_invalid_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.yml"
            path.write_text("kind: [", encoding="utf-8")
            with self.assertRaises(Exception):
                VALIDATOR.load_yaml(path)


if __name__ == "__main__":
    unittest.main()
