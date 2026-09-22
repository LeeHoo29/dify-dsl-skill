# Tool Bindings

Dify tool nodes can refer to builtin plugins, custom API providers, or published workflows. Their identity and parameter metadata are workspace- and version-dependent.

## Source Of Truth

Use one of these sources, in order:

1. A working export from the target workspace and Dify version.
2. The target workspace's tool or plugin registry response.
3. The installed plugin package schema.

Never invent `provider_id`, `plugin_id`, `plugin_unique_identifier`, `credential_id`, tool names, or opaque subscription identifiers.

## Portable Files

- Omit credentials and workspace-bound authorization IDs.
- Keep plugin dependencies explicit when the target import needs them.
- Preserve `paramSchemas`, `params`, and `tool_parameters` shapes from a compatible export.
- Match each bound value to the declared parameter type.
- Use Dify template strings for mixed string bindings and selector arrays only where the exported parameter shape expects them.

## Agent Tools

`model_config.agent_mode.tools[]` is flatter than a Workflow graph tool node. Do not copy graph-only fields such as node positions, graph outputs, or edge metadata into an Agent tool binding unless the target export contains them.

Static validation can check obvious shape problems but cannot prove that a provider, credential, or plugin exists in the target workspace.
