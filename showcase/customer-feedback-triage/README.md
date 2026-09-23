# Customer Feedback Triage

An importable, model-free Dify Workflow that validates customer feedback, assigns a deterministic priority, branches urgent cases, and merges both paths into one stable output.

![Published Customer Feedback Triage canvas](canvas.png)

The screenshot is a redacted live import/publication result from a local Dify 1.15.0 instance. Automated compatibility remains pinned to Dify 1.17.1 / App DSL 0.7.0.

## Natural-Language Requirement

```text
Create a Dify Workflow that accepts a customer ID, a 1-5 rating, and free-text feedback.
Validate the inputs, normalize the feedback, and identify low ratings or operational terms
such as refund, damaged, missing, or late. Route those cases to priority follow-up and send
the remaining feedback to standard review. Return one stable result and recommended action.
Do not require a model provider, plugin, dataset, or external API.
```

## What It Demonstrates

- portable Workflow DSL with no workspace-bound dependencies;
- canonical Python sources outside YAML;
- deterministic validation and priority `if-else` routing;
- branch convergence through Variable Aggregator nodes;
- ELK automatic layout and static validation;
- one stable End-node contract.

## Try It

```bash
python3 skills/dify-dsl/scripts/sync_code_nodes.py \
  showcase/customer-feedback-triage/workflow.yml \
  --source-root showcase/customer-feedback-triage/code-nodes

node skills/dify-dsl/scripts/layout_dify_dsl.mjs \
  showcase/customer-feedback-triage/workflow.yml --check

python3 skills/dify-dsl/scripts/validate_dify_dsl.py \
  showcase/customer-feedback-triage/workflow.yml \
  --target-version 0.7.0 --portable
```

Suggested urgent input:

```text
customer_id: C-1042
rating: 1
feedback: My package arrived damaged and I need a refund.
```

Suggested standard input:

```text
customer_id: C-1043
rating: 5
feedback: Setup was clear and the product works well.
```
