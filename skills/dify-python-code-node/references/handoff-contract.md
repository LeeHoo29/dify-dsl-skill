# Code Node Handoff Contract

Return a compact contract that the workflow author can translate directly into Dify YAML:

```yaml
source: docs/dify-code-nodes/order_flow/normalize_order.py
inputs:
  - name: raw_order
    type: string
    required: true
    source: [start, raw_order]
outputs:
  can_continue:
    type: boolean
    purpose: branch condition
  error_message:
    type: string
    purpose: failure response
  order:
    type: object
    purpose: normalized downstream payload
branch_field: can_continue
iteration_field: null
tests:
  - valid order
  - malformed JSON
```

The `source` file is authoritative. Input selectors belong to the workflow and can differ when one script is reused by several nodes. Output names and types must remain consistent with the script's returned keys.

Use Dify type names: `string`, `number`, `boolean`, `object`, `file`, `array`, `array[string]`, `array[number]`, `array[boolean]`, and `array[object]`.
