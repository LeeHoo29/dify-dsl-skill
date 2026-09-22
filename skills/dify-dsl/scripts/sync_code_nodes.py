#!/usr/bin/env python3
"""Synchronize canonical Python sources into Dify Code nodes."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR: PyYAML is required. Install the repository requirements first.")
    raise SystemExit(2)


SOURCE_RE = re.compile(r"(?:^|\n)Code source:\s*`?([^`\n]+\.py)`?(?:\n|$)", re.IGNORECASE)


@dataclass(frozen=True)
class SyncIssue:
    path: Path
    node_id: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: Code node {self.node_id}: {self.message}"


def normalize_code(code: str) -> str:
    return code.replace("\r\n", "\n").strip() + "\n"


def extract_source(desc: object) -> str | None:
    match = SOURCE_RE.search(str(desc or ""))
    return match.group(1).strip() if match else None


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def main_contract(code: str) -> tuple[set[str], set[str], str | None]:
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return set(), set(), f"source has invalid Python syntax: {error}"

    function = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"),
        None,
    )
    if function is None:
        return set(), set(), "source is missing top-level main(...)"

    inputs = {argument.arg for argument in function.args.args}
    outputs: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Dict):
            continue
        for key in node.value.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                outputs.add(key.value)
    return inputs, outputs, None


def synchronize_file(
    dsl_path: Path,
    *,
    repo_root: Path,
    source_root: Path,
    write: bool,
) -> tuple[bool, list[SyncIssue]]:
    repo_root = repo_root.resolve()
    source_root = source_root.resolve()
    data = yaml.safe_load(dsl_path.read_text(encoding="utf-8")) or {}
    nodes = data.get("workflow", {}).get("graph", {}).get("nodes", [])
    if not isinstance(nodes, list):
        return False, [SyncIssue(dsl_path, "<graph>", "workflow.graph.nodes must be a list")]

    changed = False
    issues: list[SyncIssue] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data")
        if not isinstance(node_data, dict) or node_data.get("type") != "code":
            continue

        node_id = str(node.get("id") or "<missing-id>")
        declared_source = extract_source(node_data.get("desc"))
        if not declared_source:
            issues.append(SyncIssue(dsl_path, node_id, "missing `Code source: <path>.py` in data.desc"))
            continue

        source_path = (repo_root / declared_source).resolve()
        if not is_within(source_path, source_root):
            issues.append(SyncIssue(dsl_path, node_id, f"source is outside {source_root}"))
            continue
        if not source_path.is_file():
            issues.append(SyncIssue(dsl_path, node_id, f"source does not exist: {declared_source}"))
            continue

        source_code = normalize_code(source_path.read_text(encoding="utf-8"))
        source_inputs, source_outputs, contract_error = main_contract(source_code)
        if contract_error:
            issues.append(SyncIssue(dsl_path, node_id, contract_error))
            continue

        yaml_inputs = {
            str(item.get("variable"))
            for item in node_data.get("variables", [])
            if isinstance(item, dict) and item.get("variable")
        }
        yaml_outputs = {
            str(name)
            for name in (node_data.get("outputs") or {})
        }
        contract_matches = True
        if yaml_inputs != source_inputs:
            contract_matches = False
            issues.append(
                SyncIssue(
                    dsl_path,
                    node_id,
                    f"input contract differs: source={sorted(source_inputs)}, dsl={sorted(yaml_inputs)}",
                )
            )
        if source_outputs and yaml_outputs != source_outputs:
            contract_matches = False
            issues.append(
                SyncIssue(
                    dsl_path,
                    node_id,
                    f"output contract differs: source={sorted(source_outputs)}, dsl={sorted(yaml_outputs)}",
                )
            )
        if not contract_matches:
            continue

        embedded_code = normalize_code(str(node_data.get("code") or ""))
        if embedded_code == source_code:
            continue
        if write:
            node_data["code"] = source_code
            changed = True
        else:
            issues.append(SyncIssue(dsl_path, node_id, f"embedded code differs from {declared_source}"))

    if changed and write and not issues:
        rendered = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)
        dsl_path.write_text(rendered, encoding="utf-8")
    return changed and not issues, issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronize Python sources into Dify Code nodes.")
    parser.add_argument("dsl", nargs="+", type=Path, help="Dify DSL YAML file(s)")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-root", type=Path, default=Path("docs/dify-code-nodes"))
    parser.add_argument("--write", action="store_true", help="Update embedded data.code values")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    source_root = (repo_root / args.source_root).resolve()
    all_issues: list[SyncIssue] = []
    changed_count = 0
    for raw_path in args.dsl:
        path = raw_path if raw_path.is_absolute() else repo_root / raw_path
        if not path.is_file():
            print(f"ERROR: DSL file not found: {path}", file=sys.stderr)
            return 2
        changed, issues = synchronize_file(
            path,
            repo_root=repo_root,
            source_root=source_root,
            write=args.write,
        )
        changed_count += int(changed)
        all_issues.extend(issues)

    for issue in all_issues:
        print(f"ERROR: {issue}", file=sys.stderr)
    if all_issues:
        return 1
    action = "updated" if args.write else "verified"
    print(f"{action} {len(args.dsl)} DSL file(s); changed={changed_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
