# Model Config Apps

Use this reference for `chat`, `completion`, and `agent-chat` exports whose behavior lives under `model_config` rather than `workflow.graph`.

## Agent Shape

```yaml
version: 0.7.0
kind: app
app:
  name: My Agent
  mode: agent-chat
dependencies: []
model_config:
  agent_mode:
    enabled: true
    max_iteration: 5
    strategy: function_call
    tools: []
  model:
    mode: chat
    name: <configured model name>
    provider: <configured provider>
  pre_prompt: "..."
  prompt_type: simple
```

Model names, provider identifiers, Agent strategies, and tool shapes vary by Dify version and installed plugins. Prefer a current export from the target instance.

## Rules

- Keep top-level `kind`, `version`, `app`, and `dependencies` consistent with the App DSL.
- Do not add `workflow.graph` merely to make the file resemble a Workflow app.
- Do not invent provider, plugin, credential, dataset, or tool identifiers.
- Keep file upload settings under `model_config.file_upload` for pure model-config apps.
- Agent tools under `model_config.agent_mode.tools[]` use a different shape from graph Tool nodes. Copy them from a compatible export or registry response.
- Validate the final file, then separately verify import and tool availability on the target workspace when requested.

## Choose Workflow Instead

Use a graph-based Workflow when execution must follow deterministic branches, typed Code-node transforms, explicit loops, or stable typed outputs. Use `agent-chat` when the configured model should decide which tools to call during a conversation.
