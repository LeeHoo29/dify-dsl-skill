# App DSL Shape

## Graph-Based App

Use this shape for Workflow and Chatflow apps. Set the exact `version` supported by the target instance.

```yaml
version: 0.7.0
kind: app
app:
  name: my-app
  mode: workflow
  icon: "🤖"
  icon_background: "#E0F2FE"
  icon_type: emoji
  description: ""
  use_icon_as_answer_icon: false
dependencies: []
workflow:
  conversation_variables: []
  environment_variables: []
  features: {}
  graph:
    nodes: []
    edges: []
```

Common app modes include `workflow`, `advanced-chat`, `chat`, `completion`, and `agent-chat`. Workflow and Advanced Chat use a graph. Chatbot, Text Generator, and Agent exports can use `model_config` instead.

## RAG Pipeline

RAG Pipeline exports use a separate kind and version series:

```yaml
version: 0.1.0
kind: rag_pipeline
rag_pipeline:
  name: my-pipeline
  icon: "📙"
  icon_type: emoji
  icon_background: "#FFEAD5"
  icon_url: null
  description: ""
dependencies: []
workflow:
  graph:
    nodes: []
    edges: []
```

Do not infer the RAG Pipeline version from the App DSL version. Check the target Dify release.

## Dependencies

`dependencies` can be empty for model-free workflows. Add model or plugin dependencies when the target import requires them, using a compatible target-version export as the reference.

## Portable Configuration

- Keep environment variable defaults empty when they will contain credentials or installation-specific values.
- Omit credential IDs, dataset IDs, webhook debug URLs, plugin subscriptions, signed URLs, and workspace identifiers.
- Do not claim a file is portable when it intentionally binds to a specific Dify workspace.
