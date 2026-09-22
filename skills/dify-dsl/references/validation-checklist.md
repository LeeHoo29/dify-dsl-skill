# Validation Checklist

Use this before describing a DSL as import-ready.

## Top Level

- YAML root is a mapping.
- `kind` is `app` or `rag_pipeline`.
- `version` is present and compatible with the target Dify instance.
- `dependencies` is a list when present.
- `app.mode` selects the correct configuration style: graph-based Workflow/Chatflow or `model_config` apps.
- RAG Pipeline DSL includes `rag_pipeline` and a workflow graph.

## Graph

- Node IDs are unique.
- Every executable node has `data.type`.
- Every edge source and target exists.
- Edge `sourceType` and `targetType` match connected nodes.
- Selectors point to existing scopes and statically known outputs.
- Environment references are declared.
- End and Answer outputs reference valid upstream values.
- File inputs carry complete upload metadata.
- HTTP Request nodes include `body.type` and `body.data`, including bodyless GET requests.
- Document Extractor nodes declare boolean `is_array_file`.
- LLM nodes declare `context.enabled` and `context.variable_selector`.

## Containers

- Iteration and Loop children use parent-relative `position` values.
- Child containment metadata matches the parent container.
- Internal edge containment metadata and `zIndex` match a working target-version export.
- Every executable child is connected by edges.
- Container `output_selector` names a real child output and matches `output_type`.
- Downstream Code inputs declare the value type exported by the container.

## Code Nodes

- `code_language` and code are present.
- Python code defines a top-level `main(...)`.
- Input variable names match `main(...)` parameters.
- Statically visible returned keys match declared outputs.
- Output types are valid Dify types.
- Deep or unknown objects are summarized or serialized as JSON strings only when a downstream consumer needs the full payload.
- Custom file-array outputs are not used.

## Portability

- In portable mode, Secret values are empty or supplied outside the DSL.
- In portable mode, dataset, workspace, credential, app, and workflow IDs are absent. Workspace-targeted exports may retain them in ordinary validation mode.
- Webhook and signed URLs are not embedded in examples.
- Tool identity and parameter schemas come from the target workspace or a compatible export.

## Limits

Static validation cannot prove successful import, plugin availability, model configuration, runtime behavior, or editor rendering. Verify those separately when the user asks for a deployed or runtime-ready result.
