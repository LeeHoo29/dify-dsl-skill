# Dify DSL Skill

[![CI](https://github.com/LeeHoo29/dify-dsl-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/LeeHoo29/dify-dsl-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-16A085.svg)](LICENSE)
[![Dify 1.17.1](https://img.shields.io/badge/Dify-1.17.1-0B3D3A.svg)](https://github.com/langgenius/dify/releases/tag/1.17.1)
[![App DSL 0.7.0](https://img.shields.io/badge/App%20DSL-0.7.0-0B3D3A.svg)](https://github.com/langgenius/dify/blob/main/api/constants/dsl_version.py)

[中文说明](README.zh-CN.md)

![Dify DSL Skill overview](assets/hero.svg)

Turn natural-language requirements into usable, maintainable, and automatically laid-out [Dify](https://github.com/langgenius/dify) Workflow or Chatflow DSL.

The project combines Agent guidance with deterministic tooling so a generated workflow can be reviewed, validated, and imported without routine mouse-based canvas cleanup.

> Unofficial community project. Not affiliated with or endorsed by LangGenius.

## What Ships

- `dify-dsl`: designs the graph, writes YAML, integrates Code-node contracts, applies ELK layout, and performs pre-import validation.
- `dify-python-code-node`: writes and tests every new or materially changed Python Code-node source.
- Static validator: checks graph integrity, selectors, Code contracts, Loop/Iteration structure, editor-sensitive fields, versions, and portable secrets.
- Code source synchronizer: keeps canonical `.py` files and embedded `data.code` byte-equivalent after newline normalization.
- ELK auto-layout: lays out the full graph, branches, notes, and Loop/Iteration children; verifies idempotence and overlap.

## Supported Scope

| Artifact | v0.1 status |
|---|---|
| Workflow (`workflow`) | Primary |
| Chatflow (`advanced-chat`) | Primary |
| App DSL `0.7.0` | Primary, audited against Dify 1.17.1 fixtures |
| App DSL `0.6.0` | Compatibility mode; pass `--target-version 0.6.0` |
| Agent / Chatbot / Text Generator model-config apps | Experimental guidance and structural validation |
| RAG Pipeline | Experimental authoring; official upstream fixtures are validator-audited |
| Live import, publish, deployment, or plugin installation | Out of scope |

## Install

Install both skills for Codex and Claude Code:

```bash
npx skills add LeeHoo29/dify-dsl-skill \
  --skill dify-dsl \
  --skill dify-python-code-node \
  -g -a codex -a claude-code -y
```

For the complete validator and automatic layout toolchain, clone once and install the pinned runtimes:

```bash
git clone https://github.com/LeeHoo29/dify-dsl-skill.git
cd dify-dsl-skill
python3 -m pip install -r requirements.txt
npm ci --prefix skills/dify-dsl
```

Requirements: Python 3.10+, Node.js 20+, and npm.

## Generate With An Agent

```text
Use $dify-dsl to create a Dify 0.7.0 Workflow from this requirement.
Use $dify-python-code-node for every new Python Code node.
Keep reusable Python under docs/dify-code-nodes, apply automatic layout,
then run source, layout, portable, and DSL validation before delivery.
```

The intended pipeline is:

```text
natural language
  -> graph and node contracts
  -> canonical Python Code sources
  -> embedded Code synchronization
  -> ELK automatic layout
  -> static and portability validation
  -> pre-import DSL candidate
```

## Validate And Format

```bash
# Embed canonical Python sources and verify they cannot drift.
python3 skills/dify-dsl/scripts/sync_code_nodes.py dev-dsl/app.yml \
  --source-root docs/dify-code-nodes --write
python3 skills/dify-dsl/scripts/sync_code_nodes.py dev-dsl/app.yml \
  --source-root docs/dify-code-nodes

# Produce and verify deterministic, overlap-free layout.
node skills/dify-dsl/scripts/layout_dify_dsl.mjs dev-dsl/app.yml --write
node skills/dify-dsl/scripts/layout_dify_dsl.mjs dev-dsl/app.yml --check

# Validate the final portable artifact.
python3 skills/dify-dsl/scripts/validate_dify_dsl.py dev-dsl/app.yml \
  --target-version 0.7.0 --portable
```

Use `--portable` only for files intended to move between workspaces or be shared publicly. Ordinary validation allows target-workspace credential and dataset bindings.

## Code Source Policy

Dify must embed Code-node source in YAML, but embedded text should not become the canonical source in a maintained repository.

For `dev-dsl/*.yml` repository mode:

- canonical source lives under `docs/dify-code-nodes/**/*.py`;
- each Code node description contains `Code source: docs/dify-code-nodes/<path>.py`;
- `sync_code_nodes.py --write` embeds the source;
- a normal check fails on a missing marker, missing source, path escape, contract mismatch, or code drift.

## Evidence

Public examples include a minimal Workflow, a minimal Chatflow, and a managed-Code Workflow whose canonical Python source is synchronized into the DSL.

- Local unit and package tests cover validation, portable-secret handling, Code-source synchronization, and branch/container layout.
- CI audits Dify `1.17.1`'s official Workflow fixtures and RAG transform templates without copying those fixtures into this repository.
- Public examples pass strict portable validation and idempotent layout checks.

Passing these checks means "pre-import validated," not "runtime verified." Model providers, datasets, plugins, and target-workspace credentials still require the target Dify installation.

## Security

The public repository contains no real credentials, dataset IDs, workspace IDs, signed URLs, or private endpoints. See [SECURITY.md](SECURITY.md) before reporting a suspected leak or attaching an exported DSL.

## Development

```bash
python3 -m unittest discover -s tests -v
npm audit --prefix skills/dify-dsl
node skills/dify-dsl/scripts/layout_dify_dsl.mjs skills/dify-dsl/examples/*.yml --check
python3 skills/dify-dsl/scripts/validate_dify_dsl.py \
  skills/dify-dsl/examples/minimal-workflow.yml --target-version 0.7.0 --portable
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [ROADMAP.md](ROADMAP.md).

## License

MIT. Dify is a trademark of its respective owner and is distributed under its own license.
