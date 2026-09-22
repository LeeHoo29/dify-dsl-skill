#!/usr/bin/env python3
"""Run the public validator against a checked-out Dify fixture corpus."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
VALIDATOR_PATH = ROOT / "skills" / "dify-dsl" / "scripts" / "validate_dify_dsl.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("dify_dsl_validator", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load validator: {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixture_paths(dify_root: Path) -> list[Path]:
    roots = [
        dify_root / "api" / "tests" / "fixtures" / "workflow",
        dify_root / "api" / "services" / "rag_pipeline" / "transform",
    ]
    paths: list[Path] = []
    for root in roots:
        if root.is_dir():
            paths.extend(sorted(root.glob("*.yml")))
            paths.extend(sorted(root.glob("*.yaml")))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Dify's official DSL fixtures.")
    parser.add_argument("dify_root", type=Path, help="Path to a Dify source checkout")
    parser.add_argument("--target-version", default="0.7.0")
    args = parser.parse_args()

    paths = fixture_paths(args.dify_root)
    if not paths:
        print("ERROR: no official workflow or RAG fixtures found", file=sys.stderr)
        return 2

    validator = load_validator()
    failed = 0
    warnings = 0
    for path in paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        issues = validator.validate(data, source_path=path, target_version=args.target_version)
        errors = [str(issue) for issue in issues if issue.level == "ERROR"]
        warnings += sum(issue.level == "WARN" for issue in issues)
        if not errors:
            continue
        failed += 1
        print(f"ERROR: {path}: {len(errors)} validator error(s)", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)

    print(f"Audited {len(paths)} official fixture(s): failed={failed}, warnings={warnings}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
