# Dify DSL Skill

[![CI](https://github.com/LeeHoo29/dify-dsl-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/LeeHoo29/dify-dsl-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-16A085.svg)](LICENSE)
[![Dify 1.17.1](https://img.shields.io/badge/Dify-1.17.1-0B3D3A.svg)](https://github.com/langgenius/dify/releases/tag/1.17.1)
[![App DSL 0.7.0](https://img.shields.io/badge/App%20DSL-0.7.0-0B3D3A.svg)](https://github.com/langgenius/dify/blob/main/api/constants/dsl_version.py)

[中文说明](README.zh-CN.md)

![Dify DSL Skill overview](assets/hero.svg)

![30-second workflow demo](assets/demo.gif)

The final scene includes a redacted canvas crop from a real local Dify run; account and workspace sidebars are excluded.

Turn natural-language requirements into usable, maintainable, and automatically laid-out [Dify](https://github.com/langgenius/dify) Workflow or Chatflow DSL.

The project combines Agent guidance with deterministic tooling so a generated workflow can be reviewed, validated, and imported without routine mouse-based canvas cleanup.

> Unofficial community project. Not affiliated with or endorsed by LangGenius.

## What Ships

- `dify-dsl`: designs the graph, writes YAML, integrates Code-node contracts, applies ELK layout, and performs pre-import validation.
- `dify-python-code-node`: writes and tests every new or materially changed Python Code-node source.
- `dify-local-sync`: safely configures a user-controlled local Dify, imports or overwrites Draft, optionally publishes, and strictly verifies the result.
- Static validator: checks graph integrity, selectors, Code contracts, Loop/Iteration structure, editor-sensitive fields, versions, and portable secrets.
- Code source synchronizer: keeps canonical `.py` files and embedded `data.code` byte-equivalent after newline normalization.
- ELK auto-layout: lays out the full graph, branches, notes, and Loop/Iteration children; verifies idempotence and overlap.

## Why This Project

| Approach | Natural-language authoring | Deterministic layout | Canonical Code sources | Draft sync | Workflow publication |
|---|---:|---:|---:|---:|---:|
| Manual Dify UI | No | Manual | Limited | Yes | Yes |
| Workflow template collection | No | Prebuilt only | Varies | Manual | Manual |
| Official `difyctl` | No | No | No | Cloud/remote | No |
| `dify-dsl-skill` | Yes | Yes | Yes | Local self-hosted | Local self-hosted |

Template collections help you reuse an existing workflow. This project helps an Agent design a new workflow from requirements, keep Python maintainable, lay out the canvas, validate the result, and optionally synchronize it to a local Dify.

## Supported Scope

| Artifact | v0.3 status |
|---|---|
| Workflow (`workflow`) | Primary |
| Chatflow (`advanced-chat`) | Primary |
| App DSL `0.7.0` | Primary, audited against Dify 1.17.1 fixtures |
| App DSL `0.6.0` | Compatibility mode; pass `--target-version 0.6.0` |
| Agent / Chatbot / Text Generator model-config apps | Experimental guidance and structural validation |
| RAG Pipeline | Experimental authoring; official upstream fixtures are validator-audited |
| Local self-hosted Docker import/publish | Supported through explicit `dify-local-sync` authorization |
| Dify Cloud or remote-host publication | Out of scope; use official [`difyctl`](https://docs.dify.ai/en/cli/install) for Draft import/export |

## Install

Install all three skills for Codex and Claude Code:

```bash
npx skills add LeeHoo29/dify-dsl-skill \
  --skill dify-dsl \
  --skill dify-python-code-node \
  --skill dify-local-sync \
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

### Prerequisites By Mode

| Mode | Required | Not required from this repository |
|---|---|---|
| Install Skills only | Node.js 20+ and npm/npx | Python, Docker, or a Dify instance |
| Generate, validate, and auto-layout DSL | Python 3.10+, `pip`, Node.js 20+, npm, and Git for cloning | Docker or a running Dify instance |
| Local Draft sync and publication | The authoring prerequisites, Docker Engine/Desktop with Compose v2, a running user-controlled Dify Compose stack, and an active Dify account/workspace | A second host-side Python installation for the Dify container; the API container provides its own runtime |

The Skill does not install Dify itself. Follow Dify's official self-hosted installation guide first, then point `dify-local-sync` at that deployment directory. For a quick preflight:

```bash
node --version
npm --version
python3 --version
docker --version
docker compose version
```

Only the first two commands are needed to install the Skills. Python and the pinned Node dependencies are needed for the validator/layout toolchain. Docker and a running Dify stack are needed only for local synchronization.

### Install With Natural Language

You can ask an Agent to install the repository instead of typing the shell command:

```text
Install the three Skills from https://github.com/LeeHoo29/dify-dsl-skill
for this Agent: dify-dsl, dify-python-code-node, and dify-local-sync.
Use the repository's documented `npx skills add` command.
Only install the Skills. Do not change my Dify configuration, import any DSL,
or publish a Workflow.
```

For authoring only, omit `dify-local-sync`:

```text
Install `dify-dsl` and `dify-python-code-node` from
https://github.com/LeeHoo29/dify-dsl-skill for this Agent.
Only install the Skills and verify that both are discoverable.
```

Installation changes the Agent's local Skill directory. It does not configure `INNER_API_KEY`, modify Docker, import a DSL, or publish a Dify app.

Before asking the Agent to install or synchronize anything, you can use this read-only preflight request:

```text
Check whether this machine has Node.js/npm, Python 3.10+, Git, and Docker Compose v2.
Then check whether my local Dify Docker stack is reachable and identify its Dify version.
Report missing prerequisites and compatibility risks only.
Do not install software, change Docker, configure Inner API, import DSL, or publish a Workflow.
```

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
  -> optional local Draft import and explicit publication
```

## Showcase

[Customer Feedback Triage](showcase/customer-feedback-triage/README.md) is a model-free, directly importable Workflow generated from a natural-language requirement. It demonstrates validation, two decision stages, three branch results, Variable Aggregator convergence, canonical Python sources, automatic layout, and a stable final output.

```text
Customer input -> Validate -> Priority decision
                         |-> Invalid submission
                         |-> Priority follow-up
                         `-> Standard review
                                   -> Merge -> End
```

The Showcase passes Code-source synchronization, ELK overlap/idempotence checks, portable validation with 0 errors/0 warnings, and focused Python behavior tests. A Chinese [launch article](docs/launch-article.zh-CN.md), English [launch article](docs/launch-article.en.md), and channel-specific [community launch kit](docs/community-launch-kit.md) are included for reuse.

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

## Quick Local Self-Hosted Sync

`dify-local-sync` is restricted to a user-controlled local Dify Docker Compose deployment. Dify 1.17.1 is the tested baseline. It never exposes Inner API through a remote URL and never prints the generated key.

An Agent can drive the complete flow from natural language:

```text
Use $dify-dsl to build, source-sync, auto-layout, and validate this workflow.
Then use $dify-local-sync with my local Dify at /path/to/dify.
Ask separately before changing local Inner API configuration, synchronizing Draft,
and publishing the Workflow.
```

Inspect without changing anything:

```bash
python3 skills/dify-local-sync/scripts/setup.py --dify-root /path/to/dify
```

After explicitly authorizing local configuration:

```bash
python3 skills/dify-local-sync/scripts/setup.py --dify-root /path/to/dify --apply
```

Preview an import/overwrite:

```bash
python3 skills/dify-local-sync/scripts/sync.py dev-dsl/app.yml \
  --project-root /path/to/dsl-project \
  --dify-root /path/to/dify --via-container \
  --account-email user@example.com
```

After explicitly authorizing Draft synchronization and publication:

```bash
python3 skills/dify-local-sync/scripts/sync.py dev-dsl/app.yml \
  --project-root /path/to/dsl-project \
  --dify-root /path/to/dify --via-container \
  --account-email user@example.com \
  --apply --publish

python3 skills/dify-local-sync/scripts/verify.py dev-dsl/app.yml \
  --project-root /path/to/dsl-project \
  --dify-root /path/to/dify --via-container \
  --strict-sha --require-published
```

Setup writes the key only to Dify's ignored Compose env file and creates an ignored Compose override that injects it into API. Creation and Draft export use container-local Inner API. Overwrite, version confirmation, and publication use Dify's Service Layer inside the API container because Dify 1.17.1 does not expose those operations through Inner API. Setup, Draft create/overwrite, and publication remain distinct authorization boundaries.

The local sync scripts are tested against Dify `1.17.1`. Other Dify versions may change the internal Service Layer or Inner API payloads. Start with setup inspection and sync dry-run; do not use `--apply` until the target version and Compose layout have been checked.

## Code Source Policy

Dify must embed Code-node source in YAML, but embedded text should not become the canonical source in a maintained repository.

For `dev-dsl/*.yml` repository mode:

- canonical source lives under `docs/dify-code-nodes/**/*.py`;
- each Code node description contains `Code source: docs/dify-code-nodes/<path>.py`;
- `sync_code_nodes.py --write` embeds the source;
- a normal check fails on a missing marker, missing source, path escape, contract mismatch, or code drift.

## Evidence

Public examples include a minimal Workflow, a minimal Chatflow, and a managed-Code Workflow whose canonical Python source is synchronized into the DSL.

- Local unit and package tests cover validation, portable-secret handling, Code-source synchronization, branch/container layout, local env setup, Profile application, and publication mapping.
- CI audits Dify `1.17.1`'s official Workflow fixtures and RAG transform templates without copying those fixtures into this repository.
- Public examples pass strict portable validation and idempotent layout checks.

Pre-import checks alone do not prove runtime behavior. A local sync is complete only after Draft verification and, when requested, Published pointer/version verification. Models, datasets, plugins, and target-workspace credentials still belong to the target Dify installation.

## Security

The public repository contains no real credentials, dataset IDs, workspace IDs, signed URLs, or private endpoints. Local sync refuses Git-tracked Compose env files and keeps keys container-local. See [SECURITY.md](SECURITY.md) before reporting a suspected leak or attaching an exported DSL.

## FAQ

### Does this install Dify?

No. Skill installation and DSL authoring do not require Dify. Local synchronization requires an existing user-controlled Docker Compose deployment.

### Does installation modify my Dify instance?

No. Installing the Skills only changes the Agent's Skill directory. Setup, Draft synchronization, and publication are separately authorized operations.

### Why use this instead of `difyctl`?

Use official `difyctl` for Dify Cloud or remote Draft transport. Use this project when you need natural-language workflow authoring, canonical Code sources, deterministic canvas layout, static validation, or explicitly authorized local publication.

### Which Dify version is supported?

Dify 1.17.1 with App DSL 0.7.0 is the automated compatibility baseline. A live Dify 1.15.0 import and publication was also demonstrated, but that instance exports DSL 0.6.0 and therefore does not pass the current strict version-equality check. Treat other versions as dry-run-first targets.

### Why did verification fail after a successful import?

Check the local/exported DSL versions first. The verifier intentionally rejects version, graph, Workspace, SHA, or Published-pointer drift instead of reporting a partial match as success.

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
