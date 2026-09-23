# Stop Dragging Dify Nodes: Generate, Layout, Validate, and Publish Workflows from Natural Language

Building a Dify Workflow involves more than writing node logic. You also need to maintain selectors, Code-node contracts, graph edges, canvas positions, version fields, workspace bindings, and Draft versus Published state.

`dify-dsl-skill` turns that work into a reproducible authoring pipeline:

https://github.com/LeeHoo29/dify-dsl-skill

> Describe the workflow in natural language, then generate maintainable DSL with canonical Python sources, deterministic layout, static validation, and optional local publication.

![30-second demo](https://raw.githubusercontent.com/LeeHoo29/dify-dsl-skill/main/assets/demo.gif)

## What The Agent Actually Does

```text
natural-language requirement
-> graph and node contracts
-> canonical Python Code sources
-> embedded Code synchronization
-> deterministic ELK layout
-> portability and DSL validation
-> optional local Draft synchronization
-> explicit Workflow publication
-> Draft and Published verification
```

The repository includes a directly importable, model-free [Customer Feedback Triage showcase](https://github.com/LeeHoo29/dify-dsl-skill/tree/main/showcase/customer-feedback-triage). It demonstrates validation, decision branches, Variable Aggregator convergence, canonical Python files, and one stable End-node contract without requiring a model provider, plugin, dataset, or external API.

## Canonical Code Instead Of YAML Drift

Dify DSL must embed Code-node source in `data.code`, but embedded YAML text should not become the maintained source of truth.

This project keeps each reusable Python script in a standalone `.py` file and generates the embedded DSL copy. The synchronizer verifies that:

- `main(...)` parameters match Code-node inputs;
- returned keys match declared outputs;
- source paths remain inside the approved registry;
- embedded source cannot silently drift.

## Layout Is A Delivery Requirement

Importable YAML can still leave a broken or unreadable canvas. The pinned ELK layout tool handles root DAGs, branches, notes, and Loop/Iteration children, then checks overlap and idempotence. A generated workflow should not require routine mouse-based cleanup before review.

## Local Draft Sync And Publication

The optional `dify-local-sync` Skill supports user-controlled local Docker Compose deployments. It defaults to dry-run, keeps Inner API container-local, records file-to-App mappings, and verifies the exported Draft plus the current Published Workflow pointer.

Dify Inner API is an internal trusted surface, not a stable third-party API. Cloud or remote Draft transport should use official `difyctl`; local publication remains explicitly authorized and version-sensitive.

## Install

```bash
npx skills add LeeHoo29/dify-dsl-skill \
  --skill dify-dsl \
  --skill dify-python-code-node \
  --skill dify-local-sync \
  -g -a codex -a claude-code -y
```

The automated compatibility baseline is Dify 1.17.1 with App DSL 0.7.0. Workflow and Chatflow are the primary supported modes; model-config apps and RAG Pipeline authoring remain experimental.

The project is MIT licensed. Version evidence, reproducible import failures, and portable workflow contributions are welcome.
