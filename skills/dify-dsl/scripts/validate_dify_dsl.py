#!/usr/bin/env python3
"""Static checks for Dify DSL YAML.

This validator catches common authoring mistakes before a real Dify API import.
It does not replace Dify's import validation.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR: PyYAML is required. Install it or run inside the Dify project environment.")
    sys.exit(2)


VALID_KINDS = {"app", "rag_pipeline"}
DEFAULT_APP_DSL_VERSION = "0.7.0"
GRAPH_APP_MODES = {"workflow", "advanced-chat"}
MODEL_CONFIG_APP_MODES = {"agent-chat", "chat", "completion"}
CUSTOM_TOOL_PROVIDER_TYPES = {"api", "workflow"}
VALID_OUTPUT_TYPES = {
    "string",
    "number",
    "boolean",
    "object",
    "file",
    "array",
    "array[string]",
    "array[boolean]",
    "array[object]",
    "array[number]",
}
UNSUPPORTED_CUSTOM_OUTPUT_TYPES = {"array[file]"}
TRUSTED_SELECTOR_ROOTS = {"env", "sys", "conversation", "app", "rag"}
CANVAS_ONLY_NODE_TYPES = {"custom-note"}
ENV_REF_RE = re.compile(r"\{\{#env\.([A-Za-z_][A-Za-z0-9_]*)#\}\}")
TEMPLATE_REF_RE = re.compile(r"\{\{#([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)(?:\.[^#{}]+)?#\}\}")
DSL_VERSION_RE = re.compile(r"CURRENT_APP_DSL_VERSION\s*=\s*[\"']([^\"']+)[\"']")
SECRET_VALUE_RE = re.compile(
    r"(?:"
    r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"ASIA[0-9A-Z]{16}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AIza[0-9A-Za-z_-]{30,}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r")"
)
WORKSPACE_BOUND_KEYS = {
    "app_id",
    "credential_id",
    "dataset_id",
    "dataset_ids",
    "subscription_id",
    "tenant_id",
    "webhook_url",
    "workflow_id",
    "workspace_id",
}

KNOWN_NODE_OUTPUTS: dict[str, set[str]] = {
    "http-request": {"body", "status_code", "headers", "files"},
    "llm": {"text", "usage", "finish_reason"},
    "question-classifier": {"class_name"},
    "template-transform": {"output"},
    "variable-aggregator": {"output"},
}
LOOP_BUILTIN_OUTPUTS = {"loop_round"}


class Issue:
    def __init__(self, level: str, message: str) -> None:
        self.level = level
        self.message = message

    def __str__(self) -> str:
        return f"{self.level}: {self.message}"


def add_error(issues: list[Issue], message: str) -> None:
    issues.append(Issue("ERROR", message))


def add_warning(issues: list[Issue], message: str) -> None:
    issues.append(Issue("WARN", message))


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def collect_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(collect_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(collect_strings(child))
    return found


def iter_values(value: Any, path: str = "root") -> list[tuple[str, str | None, Any]]:
    found: list[tuple[str, str | None, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            found.append((child_path, str(key), child))
            found.extend(iter_values(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            found.append((child_path, None, child))
            found.extend(iter_values(child, child_path))
    return found


def has_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def validate_portability(data: dict[str, Any], issues: list[Issue]) -> None:
    for path, key, value in iter_values(data):
        if key in WORKSPACE_BOUND_KEYS and has_value(value):
            add_error(issues, f"portable mode: workspace-bound field at {path} must be empty or removed")
        if isinstance(value, str) and SECRET_VALUE_RE.search(value):
            add_error(issues, f"portable mode: possible secret value detected at {path}")

        if key != "environment_variables" or not isinstance(value, list):
            continue
        for index, variable in enumerate(value):
            if not isinstance(variable, dict):
                continue
            if variable.get("value_type") == "secret" and has_value(variable.get("value")):
                add_error(
                    issues,
                    f"portable mode: secret environment variable value at {path}[{index}].value must be empty",
                )


def parse_version(value: Any) -> tuple[int, ...] | None:
    parts = re.findall(r"\d+", str(value))
    if not parts:
        return None
    return tuple(int(part) for part in parts)


def compare_versions(left: Any, right: Any) -> int | None:
    left_version = parse_version(left)
    right_version = parse_version(right)
    if left_version is None or right_version is None:
        return None
    length = max(len(left_version), len(right_version))
    padded_left = left_version + (0,) * (length - len(left_version))
    padded_right = right_version + (0,) * (length - len(right_version))
    if padded_left > padded_right:
        return 1
    if padded_left < padded_right:
        return -1
    return 0


def find_current_app_dsl_version(source_path: Path | None) -> str | None:
    search_roots: list[Path] = []
    if source_path is not None:
        resolved = source_path.resolve()
        search_roots.extend([resolved.parent, *resolved.parents])
    cwd = Path.cwd().resolve()
    search_roots.extend([cwd, *cwd.parents])

    seen: set[Path] = set()
    for root in search_roots:
        if root in seen:
            continue
        seen.add(root)
        candidate = root / "api" / "constants" / "dsl_version.py"
        if not candidate.exists():
            continue
        match = DSL_VERSION_RE.search(candidate.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return None


def iter_selector_lists(value: Any) -> list[list[Any]]:
    selectors: list[list[Any]] = []
    if isinstance(value, dict):
        for key in (
            "value_selector",
            "variable_selector",
            "index_chunk_variable_selector",
            "iterator_selector",
            "output_selector",
        ):
            selector = value.get(key)
            if key == "variable_selector" and value.get("enabled") is False:
                continue
            if isinstance(selector, list) and selector:
                selectors.append(selector)

        value_is_selector = (
            value.get("value_type") == "variable"
            or value.get("input_type") == "variable"
            or value.get("type") == "variable"
        )
        selector_value = value.get("value")
        if value_is_selector and isinstance(selector_value, list):
            selectors.append(selector_value)

        for child in value.values():
            selectors.extend(iter_selector_lists(child))
    elif isinstance(value, list):
        for child in value:
            selectors.extend(iter_selector_lists(child))
    return selectors


def get_main_info(code: str) -> tuple[set[str], set[str], str | None]:
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return set(), set(), f"Python syntax error: {error}"

    main_func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            main_func = node
            break

    if main_func is None:
        return set(), set(), "missing top-level main(...) function"

    params = {arg.arg for arg in main_func.args.args}
    return_keys: set[str] = set()
    for node in ast.walk(main_func):
        if not isinstance(node, ast.Return):
            continue
        if isinstance(node.value, ast.Dict):
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    return_keys.add(key.value)

    return params, return_keys, None


def validate_code_node(node_id: str, data: dict[str, Any], issues: list[Issue]) -> None:
    language = data.get("code_language")
    if not language:
        add_error(issues, f"code node {node_id}: missing data.code_language")
        return

    outputs = as_dict(data.get("outputs"))
    for output_name, output_def in outputs.items():
        output_type = as_dict(output_def).get("type")
        if output_type in UNSUPPORTED_CUSTOM_OUTPUT_TYPES:
            add_error(
                issues,
                f"code node {node_id}: custom output {output_name} uses unsupported type {output_type!r}; use native file outputs directly for LLM vision",
            )
            continue
        if output_type not in VALID_OUTPUT_TYPES:
            add_error(issues, f"code node {node_id}: output {output_name} has invalid type {output_type!r}")
    variables = as_list(data.get("variables"))
    variable_names = {
        variable.get("variable")
        for variable in variables
        if isinstance(variable, dict) and isinstance(variable.get("variable"), str)
    }

    if language != "python3":
        add_warning(issues, f"code node {node_id}: static code analysis only supports python3, got {language!r}")
        return

    code = data.get("code")
    if not isinstance(code, str) or not code.strip():
        add_error(issues, f"code node {node_id}: missing data.code")
        return

    params, return_keys, error = get_main_info(code)
    if error:
        add_error(issues, f"code node {node_id}: {error}")
        return

    extra_inputs = variable_names - params
    if extra_inputs:
        add_error(issues, f"code node {node_id}: variables not in main parameters: {sorted(extra_inputs)}")

    missing_inputs = params - variable_names
    if missing_inputs:
        add_warning(issues, f"code node {node_id}: main parameters not wired in data.variables: {sorted(missing_inputs)}")

    declared_outputs = set(outputs.keys())
    missing_outputs = return_keys - declared_outputs
    if missing_outputs:
        add_error(issues, f"code node {node_id}: returned keys not declared in outputs: {sorted(missing_outputs)}")

    unused_outputs = declared_outputs - return_keys
    if return_keys and unused_outputs:
        add_error(issues, f"code node {node_id}: declared outputs not seen in literal returns: {sorted(unused_outputs)}")


def validate_llm_node(node_id: str, data: dict[str, Any], issues: list[Issue]) -> None:
    context = data.get("context")
    if not isinstance(context, dict):
        add_error(
            issues,
            f"llm node {node_id}: missing data.context; use {{enabled: false, variable_selector: []}} when context is unused",
        )
    else:
        context_enabled = context.get("enabled")
        variable_selector = context.get("variable_selector")
        if not isinstance(context_enabled, bool):
            add_error(issues, f"llm node {node_id}: data.context.enabled must be a boolean")
        if "variable_selector" not in context:
            add_warning(
                issues,
                f"llm node {node_id}: data.context.variable_selector should be [] when context is disabled",
            )
        elif not isinstance(variable_selector, list):
            add_error(issues, f"llm node {node_id}: data.context.variable_selector must be a list")
        elif context_enabled and not variable_selector:
            add_error(issues, f"llm node {node_id}: enabled context requires a non-empty variable_selector")

    completion_params = as_dict(as_dict(data.get("model")).get("completion_params"))
    if "enable_max_tokens" in completion_params:
        add_warning(
            issues,
            f"llm node {node_id}: model.completion_params.enable_max_tokens is not present in standard exports; verify it against the target Dify version",
        )
    if "enable_stream" in completion_params and not isinstance(completion_params["enable_stream"], bool):
        add_error(issues, f"llm node {node_id}: model.completion_params.enable_stream must be a boolean")

    max_tokens = completion_params.get("max_tokens")
    if max_tokens is not None and (
        not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens <= 0
    ):
        add_error(issues, f"llm node {node_id}: model.completion_params.max_tokens must be a positive integer")


def validate_tool_node(node_id: str, data: dict[str, Any], issues: list[Issue]) -> None:
    provider_type = data.get("provider_type")
    if provider_type != "builtin":
        return

    schema_types = {
        schema.get("name"): schema.get("type")
        for schema in as_list(data.get("paramSchemas"))
        if isinstance(schema, dict) and isinstance(schema.get("name"), str)
    }
    tool_parameters = as_dict(data.get("tool_parameters"))
    for parameter_name, schema_type in schema_types.items():
        parameter = as_dict(tool_parameters.get(parameter_name))
        if not parameter:
            continue
        if schema_type == "string" and parameter.get("type") == "variable" and isinstance(parameter.get("value"), list):
            add_warning(
                issues,
                f"tool node {node_id}: builtin string parameter {parameter_name!r} uses a selector-array binding; compare it with an export from the target Dify version because some versions rewrite this shape",
            )


def validate_http_request_node(node_id: str, data: dict[str, Any], issues: list[Issue]) -> None:
    body = data.get("body")
    if not isinstance(body, dict):
        add_error(
            issues,
            f"http-request node {node_id}: missing data.body mapping; use body: {{type: none, data: []}} for requests without a body",
        )
        return

    body_type = body.get("type")
    if not isinstance(body_type, str) or not body_type:
        add_error(issues, f"http-request node {node_id}: data.body.type must be a non-empty string")

    if "data" not in body:
        add_error(
            issues,
            f"http-request node {node_id}: missing data.body.data; the workflow editor dereferences body.data while rendering",
        )
    elif not isinstance(body.get("data"), (str, list)):
        add_error(issues, f"http-request node {node_id}: data.body.data must be a string or list")


def validate_document_extractor_node(node_id: str, data: dict[str, Any], issues: list[Issue]) -> None:
    if not isinstance(data.get("is_array_file"), bool):
        add_error(
            issues,
            f"document-extractor node {node_id}: data.is_array_file must be an explicit boolean",
        )


def validate_variable_name(context: str, value: Any, issues: list[Issue]) -> None:
    if not isinstance(value, str) or not value:
        add_error(issues, f"{context}: variable name is required")


def validate_model_config(model_config: dict[str, Any], app_mode: str, issues: list[Issue]) -> None:
    model = model_config.get("model")
    if not isinstance(model, dict):
        add_warning(issues, f"app mode {app_mode}: model_config.model is missing or not a mapping")
    else:
        for field in ("mode", "name", "provider"):
            if not model.get(field):
                add_warning(issues, f"app mode {app_mode}: model_config.model.{field} is empty")

    if app_mode == "agent-chat":
        validate_agent_mode(as_dict(model_config.get("agent_mode")), issues)

    user_input_form = model_config.get("user_input_form")
    if user_input_form is not None:
        validate_user_input_form(user_input_form, issues)


def validate_agent_mode(agent_mode: dict[str, Any], issues: list[Issue]) -> None:
    if not agent_mode:
        add_error(issues, "agent-chat app requires model_config.agent_mode")
        return
    if agent_mode.get("enabled") is not True:
        add_error(issues, "agent-chat app requires model_config.agent_mode.enabled: true")
    strategy = agent_mode.get("strategy")
    if not isinstance(strategy, str) or not strategy:
        add_error(issues, "agent-chat app requires model_config.agent_mode.strategy")
    max_iteration = agent_mode.get("max_iteration")
    if not isinstance(max_iteration, int) or isinstance(max_iteration, bool) or max_iteration <= 0:
        add_error(issues, "agent-chat app requires positive integer model_config.agent_mode.max_iteration")

    tools = agent_mode.get("tools")
    if tools is None:
        add_warning(issues, "agent-chat app has no model_config.agent_mode.tools")
        return
    if not isinstance(tools, list):
        add_error(issues, "model_config.agent_mode.tools must be a list")
        return
    for index, tool in enumerate(tools):
        validate_agent_tool_binding(index, tool, issues)


def validate_agent_tool_binding(index: int, tool: Any, issues: list[Issue]) -> None:
    context = f"agent tool {index}"
    if not isinstance(tool, dict):
        add_error(issues, f"{context}: expected mapping")
        return
    provider_type = tool.get("provider_type")
    if not isinstance(provider_type, str) or not provider_type:
        add_error(issues, f"{context}: provider_type is required")
        return
    for field in ("provider_id", "provider_name", "tool_name", "tool_label"):
        if not isinstance(tool.get(field), str) or not tool.get(field):
            add_error(issues, f"{context}: {field} is required")
    if provider_type in CUSTOM_TOOL_PROVIDER_TYPES:
        tool_parameters = tool.get("tool_parameters")
        if not isinstance(tool_parameters, dict):
            add_error(issues, f"{context}: custom {provider_type} tool requires tool_parameters mapping")
        for workflow_node_only_field in ("paramSchemas", "params", "outputs", "tool_node_version"):
            if workflow_node_only_field in tool:
                add_warning(
                    issues,
                    f"{context}: {workflow_node_only_field} is usually workflow-node-only; omit it unless copied from a target-version export",
                )


def validate_user_input_form(user_input_form: Any, issues: list[Issue]) -> None:
    if not isinstance(user_input_form, list):
        add_error(issues, "model_config.user_input_form must be a list")
        return
    for index, item in enumerate(user_input_form):
        if not isinstance(item, dict) or len(item) != 1:
            add_error(issues, f"user_input_form item {index}: expected single-key mapping")
            continue
        input_type, config = next(iter(item.items()))
        if not isinstance(config, dict):
            add_error(issues, f"user_input_form item {index}: {input_type} config must be a mapping")
            continue
        validate_variable_name(f"user_input_form item {index}", config.get("variable"), issues)


def collect_available_outputs(nodes: list[Any]) -> dict[str, set[str] | None]:
    available: dict[str, set[str] | None] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if not isinstance(node_id, str):
            continue
        data = as_dict(node.get("data"))
        node_type = data.get("type")

        if node_type in {"start", "user-input"}:
            available[node_id] = {
                variable.get("variable")
                for variable in as_list(data.get("variables"))
                if isinstance(variable, dict) and isinstance(variable.get("variable"), str)
            }
        elif node_type == "code":
            available[node_id] = {
                output_name
                for output_name in as_dict(data.get("outputs")).keys()
                if isinstance(output_name, str)
            }
        elif node_type == "tool":
            tool_outputs = {
                output_name
                for output_name in as_dict(data.get("outputs")).keys()
                if isinstance(output_name, str)
            }
            if tool_outputs:
                tool_outputs.update({"text", "files", "json"})
                available[node_id] = tool_outputs
            else:
                available[node_id] = None
        elif node_type == "loop":
            loop_outputs = set(LOOP_BUILTIN_OUTPUTS)
            for loop_variable in as_list(data.get("loop_variables")):
                if isinstance(loop_variable, dict) and isinstance(loop_variable.get("label"), str):
                    loop_outputs.add(loop_variable["label"])
            available[node_id] = loop_outputs
        elif node_type == "variable-aggregator":
            groups = as_list(as_dict(data.get("advanced_settings")).get("groups"))
            group_outputs = {
                str(group.get("group_name"))
                for group in groups
                if isinstance(group, dict) and group.get("group_name")
            }
            available[node_id] = group_outputs | {"output"} if group_outputs else {"output"}
        elif isinstance(node_type, str) and node_type in KNOWN_NODE_OUTPUTS:
            available[node_id] = set(KNOWN_NODE_OUTPUTS[node_type])
        else:
            available[node_id] = None
    return available


def is_native_file_output_node(data: dict[str, Any], node_type: str) -> bool:
    if node_type in {"http-request", "tool"}:
        return True
    if node_type != "iteration":
        return False
    output_selector = data.get("output_selector")
    return (
        isinstance(output_selector, list)
        and len(output_selector) >= 2
        and isinstance(output_selector[0], str)
        and output_selector[1] == "files"
    )


def validate_selector(
    selector: list[Any],
    node_types: dict[str, str],
    available_outputs: dict[str, set[str] | None],
    env_names: set[str],
    used_code_outputs: dict[str, set[str]],
    issues: list[Issue],
    context: str,
) -> None:
    if len(selector) < 2 or not isinstance(selector[0], str) or not isinstance(selector[1], str):
        add_warning(issues, f"{context}: selector should contain at least [node_id, variable], got {selector!r}")
        return

    root = selector[0]
    variable = selector[1]
    if root == "env":
        if variable not in env_names:
            add_warning(issues, f"{context}: environment variable {variable!r} is referenced but not declared")
        return
    if root in TRUSTED_SELECTOR_ROOTS:
        return
    if root not in node_types:
        add_error(issues, f"{context}: selector root {root!r} is not a known node or trusted scope")
        return

    known_outputs = available_outputs.get(root)
    if known_outputs is not None and variable not in known_outputs:
        add_error(issues, f"{context}: node {root!r} has no output variable {variable!r}")

    if root in used_code_outputs:
        used_code_outputs[root].add(variable)


def node_loop_id(node: dict[str, Any], node_id: str) -> str | None:
    data = as_dict(node.get("data"))
    node_type = data.get("type")
    if node_type == "loop":
        return node_id
    if data.get("loop_id"):
        return str(data.get("loop_id"))
    parent_id = node.get("parentId")
    if isinstance(parent_id, str):
        return parent_id
    return None


def validate_loop_structure(
    nodes: list[Any],
    edges: list[Any],
    node_types: dict[str, str],
    issues: list[Issue],
) -> None:
    loop_ids = {node_id for node_id, node_type in node_types.items() if node_type == "loop"}
    node_by_id = {node.get("id"): node for node in nodes if isinstance(node, dict) and isinstance(node.get("id"), str)}

    for node_id, node in node_by_id.items():
        data = as_dict(node.get("data"))
        node_type = data.get("type")
        parent_id = node.get("parentId")
        loop_id = data.get("loop_id")
        in_loop = data.get("isInLoop") is True or isinstance(loop_id, str) or parent_id in loop_ids

        if node_type == "loop":
            continue
        if node_type == "loop-start":
            if parent_id not in loop_ids:
                add_error(issues, f"loop-start node {node_id}: parentId must point to a loop node")
            continue
        if node_type == "loop-end":
            if node.get("type") != "custom-simple":
                add_error(issues, f"loop-end node {node_id}: outer type must be custom-simple")
            if data.get("isInLoop") is not True:
                add_error(issues, f"loop-end node {node_id}: data.isInLoop must be true")
            if not isinstance(loop_id, str) or loop_id not in loop_ids:
                add_error(issues, f"loop-end node {node_id}: data.loop_id must point to a loop node")
            if parent_id != loop_id:
                add_error(issues, f"loop-end node {node_id}: parentId must match data.loop_id")
            continue

        if in_loop:
            effective_loop_id = loop_id or parent_id
            if effective_loop_id not in loop_ids:
                add_error(issues, f"node {node_id}: loop_id/parentId must point to a loop node")
            if data.get("isInLoop") is not True:
                add_error(issues, f"node {node_id}: nodes inside a loop must set data.isInLoop to true")
            if loop_id and parent_id and loop_id != parent_id:
                add_error(issues, f"node {node_id}: parentId and data.loop_id must match")

    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            continue
        data = as_dict(edge.get("data"))
        edge_loop_id = data.get("loop_id")
        if data.get("isInLoop") is True:
            if not isinstance(edge_loop_id, str) or edge_loop_id not in loop_ids:
                add_error(issues, f"edge {edge.get('id', index)}: loop edge must set data.loop_id to a loop node")
        if not isinstance(edge_loop_id, str):
            continue

        source_node = node_by_id.get(edge.get("source"))
        target_node = node_by_id.get(edge.get("target"))
        for endpoint_name, endpoint_node in (("source", source_node), ("target", target_node)):
            if not isinstance(endpoint_node, dict):
                continue
            endpoint_id = endpoint_node.get("id")
            endpoint_loop_id = node_loop_id(endpoint_node, str(endpoint_id))
            if endpoint_loop_id != edge_loop_id:
                add_error(
                    issues,
                    f"edge {edge.get('id', index)}: {endpoint_name} node {endpoint_id!r} is not inside loop {edge_loop_id!r}",
                )


def validate_container_connectivity(
    nodes: list[Any],
    edges: list[Any],
    node_types: dict[str, str],
    issues: list[Issue],
) -> None:
    node_by_id = {node.get("id"): node for node in nodes if isinstance(node, dict) and isinstance(node.get("id"), str)}
    incoming = {node_id: 0 for node_id in node_by_id}
    outgoing = {node_id: 0 for node_id in node_by_id}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source")
        target = edge.get("target")
        if isinstance(source, str) and source in outgoing:
            outgoing[source] += 1
        if isinstance(target, str) and target in incoming:
            incoming[target] += 1

    container_output_source: dict[str, str] = {}
    for node_id, node in node_by_id.items():
        data = as_dict(node.get("data"))
        if data.get("type") in {"iteration", "loop"}:
            output_selector = data.get("output_selector")
            if isinstance(output_selector, list) and output_selector and isinstance(output_selector[0], str):
                container_output_source[node_id] = output_selector[0]

    start_types = {"iteration-start", "loop-start"}
    terminal_types = {"loop-end", "end", "answer", "assigner", "variable-assigner"}
    container_types = {"iteration", "loop"}
    for node_id, node in node_by_id.items():
        data = as_dict(node.get("data"))
        node_type = node_types.get(node_id, "")
        parent_id = node.get("parentId")
        if not isinstance(parent_id, str) or node_types.get(parent_id) not in container_types:
            continue
        if node_type in CANVAS_ONLY_NODE_TYPES or node_type in container_types:
            continue

        is_output_source = container_output_source.get(parent_id) == node_id
        if node_type in start_types:
            if outgoing.get(node_id, 0) == 0:
                add_error(issues, f"container child {node_id}: {node_type} has no outgoing edge")
            continue

        if incoming.get(node_id, 0) == 0:
            add_error(issues, f"container child {node_id}: node inside {parent_id!r} has no incoming edge")
        if (
            node_type not in terminal_types
            and not is_output_source
            and outgoing.get(node_id, 0) == 0
        ):
            add_error(issues, f"container child {node_id}: node inside {parent_id!r} has no outgoing edge")


def validate_workflow(workflow: dict[str, Any], issues: list[Issue]) -> None:
    graph = as_dict(workflow.get("graph"))
    if not graph:
        add_error(issues, "workflow.graph is missing or not a mapping")
        return

    nodes = as_list(graph.get("nodes"))
    edges = as_list(graph.get("edges"))
    if not nodes:
        add_error(issues, "workflow.graph.nodes is empty or missing")
    if graph.get("edges") is None:
        add_error(issues, "workflow.graph.edges is missing")

    node_types: dict[str, str] = {}
    code_output_names: dict[str, set[str]] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            add_error(issues, f"node at index {index}: expected mapping")
            continue
        node_id = node.get("id")
        data = as_dict(node.get("data"))
        node_type = data.get("type")
        outer_type = node.get("type")
        if not isinstance(node_id, str) or not node_id:
            add_error(issues, f"node at index {index}: missing id")
            continue
        if node_id in node_types:
            add_error(issues, f"duplicate node id {node_id}")
        if not isinstance(node_type, str) or not node_type:
            if outer_type in CANVAS_ONLY_NODE_TYPES:
                node_type = str(outer_type)
            else:
                add_error(issues, f"node {node_id}: missing data.type")
                node_type = ""
        node_types[node_id] = node_type
        output_type = data.get("output_type")
        if output_type in UNSUPPORTED_CUSTOM_OUTPUT_TYPES and not is_native_file_output_node(data, node_type):
            add_error(
                issues,
                f"node {node_id}: custom output_type {output_type!r} is not supported for {node_type!r}; use native file outputs directly for vision inputs",
            )
        if node_type == "code":
            validate_code_node(node_id, data, issues)
            code_output_names[node_id] = {
                output_name for output_name in as_dict(data.get("outputs")).keys() if isinstance(output_name, str)
            }
        elif node_type == "llm":
            validate_llm_node(node_id, data, issues)
        elif node_type == "tool":
            validate_tool_node(node_id, data, issues)
        elif node_type == "http-request":
            validate_http_request_node(node_id, data, issues)
        elif node_type == "document-extractor":
            validate_document_extractor_node(node_id, data, issues)

    available_outputs = collect_available_outputs(nodes)
    env_vars = as_list(workflow.get("environment_variables"))
    env_names = {
        item.get("name")
        for item in env_vars
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    used_code_outputs = {node_id: set() for node_id in code_output_names}

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        data = as_dict(node.get("data"))
        if data.get("type") == "document-extractor":
            selector = data.get("variable_selector")
            if (
                isinstance(selector, list)
                and len(selector) >= 2
                and selector[1] == "files"
                and node_types.get(selector[0]) == "http-request"
                and data.get("is_array_file") is not True
            ):
                add_error(
                    issues,
                    f"document-extractor node {node_id}: selector {selector!r} is an HTTP files array, so data.is_array_file must be true",
                )
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            add_error(issues, f"edge at index {index}: expected mapping")
            continue
        source = edge.get("source")
        target = edge.get("target")
        data = as_dict(edge.get("data"))
        if source not in node_types:
            add_error(issues, f"edge {edge.get('id', index)}: unknown source {source!r}")
        if target not in node_types:
            add_error(issues, f"edge {edge.get('id', index)}: unknown target {target!r}")
        source_type = data.get("sourceType")
        target_type = data.get("targetType")
        if source in node_types and source_type and source_type != node_types[source]:
            add_error(
                issues,
                f"edge {edge.get('id', index)}: sourceType {source_type!r} does not match node {source!r} type {node_types[source]!r}",
            )
        if target in node_types and target_type and target_type != node_types[target]:
            add_error(
                issues,
                f"edge {edge.get('id', index)}: targetType {target_type!r} does not match node {target!r} type {node_types[target]!r}",
            )

    validate_loop_structure(nodes, edges, node_types, issues)
    validate_container_connectivity(nodes, edges, node_types, issues)

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        data = as_dict(node.get("data"))
        if data.get("type") in {"start", "user-input"}:
            continue
        variables = data.get("variables")
        if variables is None:
            continue
        if data.get("type") == "variable-aggregator":
            for selector in as_list(variables):
                if not isinstance(selector, list) or not selector:
                    add_error(issues, f"node {node_id}: variable-aggregator selector is not a list")
                    continue
                validate_selector(
                    selector,
                    node_types,
                    available_outputs,
                    env_names,
                    used_code_outputs,
                    issues,
                    f"node {node_id}: variable-aggregator selector",
                )
            continue
        for variable in as_list(variables):
            if not isinstance(variable, dict):
                add_error(issues, f"node {node_id}: data.variables item is not a mapping")
                continue
            selector = variable.get("value_selector")
            if not isinstance(selector, list) or not selector:
                add_error(issues, f"node {node_id}: variable {variable.get('variable')!r} missing value_selector")
                continue
            validate_selector(
                selector,
                node_types,
                available_outputs,
                env_names,
                used_code_outputs,
                issues,
                f"node {node_id}: variable {variable.get('variable')!r}",
            )

    for selector in iter_selector_lists(workflow):
        validate_selector(
            selector,
            node_types,
            available_outputs,
            env_names,
            used_code_outputs,
            issues,
            "workflow selector",
        )

    refs: set[str] = set()
    for text in collect_strings(workflow):
        refs.update(ENV_REF_RE.findall(text))
        for root, variable in TEMPLATE_REF_RE.findall(text):
            validate_selector(
                [root, variable],
                node_types,
                available_outputs,
                env_names,
                used_code_outputs,
                issues,
                "template reference",
            )
    missing_env = refs - env_names
    if missing_env:
        add_warning(issues, f"environment variables referenced but not declared: {sorted(missing_env)}")

    for node_id, declared_outputs in code_output_names.items():
        unused_outputs = declared_outputs - used_code_outputs[node_id]
        if unused_outputs:
            add_warning(issues, f"code node {node_id}: declared outputs not referenced downstream: {sorted(unused_outputs)}")


def validate(
    data: Any,
    source_path: Path | None = None,
    target_version: str | None = None,
    portable: bool = False,
) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(data, dict):
        add_error(issues, "YAML root must be a mapping")
        return issues

    kind = data.get("kind")
    if kind not in VALID_KINDS:
        add_error(issues, f"kind must be one of {sorted(VALID_KINDS)}, got {kind!r}")

    version = data.get("version")
    if version is None:
        add_error(issues, "version is required")
    elif not isinstance(version, (str, int, float)):
        add_error(issues, f"version must be a string-like scalar, got {type(version).__name__}")
    elif kind == "app":
        current_version = target_version or find_current_app_dsl_version(source_path) or DEFAULT_APP_DSL_VERSION
        comparison = compare_versions(version, current_version) if current_version else None
        if comparison == 1:
            add_error(issues, f"app DSL version {version!r} is newer than target version {current_version!r}")
        elif current_version and comparison not in {None, 0}:
            add_warning(issues, f"app DSL version {version!r} differs from target version {current_version!r}")

    dependencies = data.get("dependencies")
    if dependencies is not None and not isinstance(dependencies, list):
        add_error(issues, "dependencies must be a list when present")

    if kind == "app":
        app = data.get("app")
        if not isinstance(app, dict):
            add_error(issues, "kind app requires app mapping")
            app_mode = ""
        else:
            app_mode = str(app.get("mode") or "")
            if not app.get("name"):
                add_warning(issues, "app.name is empty")
            if not app_mode:
                add_error(issues, "app.mode is required")
    elif kind == "rag_pipeline":
        app_mode = ""
        pipeline = data.get("rag_pipeline")
        if not isinstance(pipeline, dict):
            add_error(issues, "kind rag_pipeline requires rag_pipeline mapping")
        elif not pipeline.get("name"):
            add_warning(issues, "rag_pipeline.name is empty")
    else:
        app_mode = ""

    model_config = data.get("model_config")
    if kind == "app" and app_mode in MODEL_CONFIG_APP_MODES:
        if not isinstance(model_config, dict):
            add_error(issues, f"app mode {app_mode!r} requires model_config mapping")
        else:
            validate_model_config(model_config, app_mode, issues)

    workflow = data.get("workflow")
    if workflow is not None:
        if not isinstance(workflow, dict):
            add_error(issues, "workflow must be a mapping")
        else:
            validate_workflow(workflow, issues)
    elif kind in {"rag_pipeline"}:
        add_error(issues, "rag_pipeline DSL requires workflow")
    elif kind == "app" and app_mode in GRAPH_APP_MODES:
        add_error(issues, f"app mode {app_mode!r} requires workflow graph")

    if portable:
        validate_portability(data, issues)

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Statically validate a Dify DSL YAML file.")
    parser.add_argument("path", type=Path, help="Path to a Dify DSL YAML file")
    parser.add_argument(
        "--target-version",
        help=(
            "Target App DSL version. Defaults to a nearby Dify source checkout version "
            f"or {DEFAULT_APP_DSL_VERSION}."
        ),
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Reject non-empty secrets and workspace-bound identifiers.",
    )
    parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="Return a non-zero status when warnings are present.",
    )
    args = parser.parse_args()

    path = args.path
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        return 2

    try:
        data = load_yaml(path)
    except Exception as error:
        print(f"ERROR: failed to parse YAML: {error}")
        return 1

    issues = validate(data, path, target_version=args.target_version, portable=args.portable)
    for issue in issues:
        print(issue)

    errors = [issue for issue in issues if issue.level == "ERROR"]
    print(f"Checked {path}: {len(errors)} error(s), {len(issues) - len(errors)} warning(s)")
    warnings = [issue for issue in issues if issue.level == "WARN"]
    return 1 if errors or (args.warnings_as_errors and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
