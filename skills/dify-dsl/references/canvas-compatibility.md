# Canvas Compatibility

Use this when DSL imports but the workflow editor crashes, hides internal edges, or renders an oversized Iteration or Loop container.

## Editor Crashes

Check the browser console and compare the affected node with an export from the same Dify version. Common incomplete shapes include:

- HTTP Request without `body.type` and `body.data`.
- Document Extractor without boolean `is_array_file`.
- LLM node without `context.enabled` and `context.variable_selector`.
- Start file variables without upload-method, file-type, or extension arrays.
- Iteration child bindings without an explicit `value_type` where the editor cannot infer one.

Do not change business logic until the first missing field named by the console stack has been checked.

## Hidden Container Edges

A valid edge can render behind its container. Compare these fields with a working export:

- `data.isInIteration` / `data.isInLoop`;
- `data.iteration_id` / `data.loop_id`;
- `sourceType` and `targetType`;
- visible `zIndex` values used by sibling internal edges.

Do not assume a universal `zIndex`; preserve the target version's export style.

## Oversized Containers

Container child `position` values are parent-relative. `positionAbsolute` is the parent position plus the child position. Copying canvas-absolute coordinates into `position` can make Dify expand the container to thousands of pixels.

Check the container's outer `width` and `height`, the corresponding values under `data`, and every child's two position mappings.

## Nested Iteration Items

Some node editors cannot bind nested properties directly from an `array[object]` iteration item. Add a first child Code node that accepts `[iteration_id, item]` as an object and returns the required first-level fields. Bind later LLM, HTTP, and Tool nodes to those outputs.

Static validation cannot fully reproduce the React editor. For UI-sensitive changes, import into a disposable app on the target Dify version and inspect the affected node and container.
