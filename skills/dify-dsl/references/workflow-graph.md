# Workflow Graph

Workflow and Chatflow apps serialize their execution logic under `workflow.graph.nodes` and `workflow.graph.edges`. Match a target-version export whenever a node has fields not covered here.

## Node Shape

```yaml
- id: normalize
  type: custom
  data:
    type: code
    title: Normalize
    desc: Normalize the submitted text.
  position: {x: 380, y: 240}
  positionAbsolute: {x: 380, y: 240}
  sourcePosition: right
  targetPosition: left
  width: 244
  height: 90
  selected: false
```

`data.type` is the semantic node type. Most graph nodes use outer `type: custom`; container start/end nodes can use specialized outer types.

## Edge Shape

```yaml
- id: start-source-normalize-target
  source: start
  sourceHandle: source
  target: normalize
  targetHandle: target
  type: custom
  data:
    sourceType: start
    targetType: code
    isInIteration: false
    isInLoop: false
  zIndex: 0
```

Every source and target must exist. Keep `sourceType` and `targetType` aligned with the connected nodes. Branch handles come from the branch node's exported case or class identifiers.

## Selectors

Selector arrays identify a scope and variable:

```yaml
value_selector: [normalize, result]
```

- The root is normally a node ID, `env`, `sys`, `conversation`, or another Dify-recognized scope.
- A selector rooted at a node must name an output that node actually exposes.
- String templates use `{{#node_id.output_name#}}` or `{{#env.NAME#}}`.
- Declare every referenced environment variable under `workflow.environment_variables`.
- Specialized nodes may serialize selectors differently. `variable-aggregator`, for example, can use a list of selector lists.

## Iteration And Loop

Container children require both visual containment and executable edges.

- Child `position` is relative to the parent container.
- Child `positionAbsolute` is the parent position plus child position.
- Child nodes carry the parent ID and the containment fields exported by the target Dify version.
- Internal edges carry matching `isInIteration` / `isInLoop` and container IDs.
- Preserve the `zIndex` used by a working target-version export. Low values can hide otherwise valid internal edges behind the container.
- Every executable child has an incoming edge. Non-terminal children also have outgoing edges, except a child used directly as the container `output_selector` source.
- For `array[object]` iteration items, parse the item into first-level outputs before binding fields into nodes whose UI cannot resolve nested item paths.

## Files And Vision

- Treat files as native Dify values, not ordinary Code node objects.
- Point LLM vision selectors at native file-producing outputs such as an HTTP Request `files` output or a Start file variable.
- Do not declare custom Code, LLM, or Variable Aggregator outputs as `array[file]`.
- An iteration may expose `array[file]` only when its `output_selector` points directly at a native file-producing child output verified on the target version.
- Start `file` and `file-list` variables include their exported upload-method, file-type, and extension metadata.

## LLM Nodes

Keep model parameters under `data.model.completion_params`. Parameter availability and limits depend on the model provider, so do not apply a universal `max_tokens` value.

Every LLM node includes the exported context shape:

```yaml
context:
  enabled: false
  variable_selector: []
```

When context is enabled, point `variable_selector` at the intended retrieval or upstream output.

## Common Node Roles

- `start` / `user-input`: inputs.
- `end`: Workflow outputs.
- `answer`: Chatflow response.
- `llm`: model call.
- `code`: deterministic transformation.
- `http-request`: external HTTP call.
- `if-else` and `question-classifier`: branching.
- `iteration` and `loop`: repeated subgraphs.
- `knowledge-retrieval`: knowledge-base retrieval.
- `template-transform`: text templating.
- `variable-aggregator`: branch output merging.
- `tool`: builtin, API, workflow, or plugin tool invocation.
