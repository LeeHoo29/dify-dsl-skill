# Code Node Rules

For any Dify Code node, use these rules. If the host environment has a dedicated Dify Code node skill, use it as an additional reference when writing or materially revising code.

## DSL Shape

```yaml
data:
  title: Parse Response
  type: code
  desc: Extract job_id and validation fields.
  code_language: python3
  code: |
    import json

    # Dify input variables:
    # - response_body (String, required): HTTP response body.
    #
    # Dify output variables:
    # - ok (Boolean): Branch on this field.
    # - result (Object): Parsed payload.
    def main(response_body: str) -> dict:
        try:
            result = json.loads(response_body or "{}")
        except Exception as error:
            return {"ok": False, "error_message": str(error), "result": {}}
        return {"ok": True, "error_message": "", "result": result}
  variables:
    - variable: response_body
      value_selector:
        - http_node
        - body
  outputs:
    ok:
      type: boolean
      children: null
    error_message:
      type: string
      children: null
    result:
      type: object
      children: null
```

## Hard Requirements

- Use a top-level `main(...)` function.
- `main` must return a dict/object.
- Every Code node input variable in `data.variables[].variable` must match a `main` parameter.
- Every expected returned key must be declared in `data.outputs`.
- Prefer `python3` unless the user explicitly asks for JavaScript.
- Keep Python code standard-library only unless Dify sandbox package availability is confirmed.
- Do not use file IO, network calls, env vars, shell commands, `argparse`, `sys.argv`, stdin, or stdout unless explicitly required and supported.
- Return structured validation fields instead of raising for expected input problems.

## Recommended Output Fields

Use branchable and downstream-friendly fields:

- `ok` or `can_continue`: Boolean branch field.
- `error_message`: String reason when validation fails.
- `missing_required_fields`: Array[String] when validating payloads.
- `result`: Object or Array for downstream Code/Iteration nodes.
- `result_json`: String JSON for LLM prompt context.

## Object Depth Safety

Dify Code execution validates returned `object` outputs with a limited nesting depth. Deep API payloads can fail at runtime with errors like `Depth limit 5 reached, object too deep.` This often happens when returning full third-party responses such as product data, review summaries, debug traces, raw HTTP responses, tool `structured_result`, or nested error details.

Use this contract for deep or unknown payloads:

- Keep every declared `type: object` output shallow, preferably a summary with scalar fields and short lists.
- Put a complete deep payload in a paired `type: string` JSON field only when a downstream consumer genuinely needs it.
- Do not remove or rename existing output variables when fixing depth failures if downstream nodes may depend on them; keep the same Object output name and change its value to a shallow summary.
- Avoid nesting one full workflow/tool result inside another Object output. Prefer a shallow canonical result and an optional JSON string for the full payload.

Paired JSON string outputs are a tool, not a default. Before adding or keeping fields like `image_urls_json`, `product_json`, or `raw_response_json`, confirm a downstream node actually requires a string version, a full raw payload, or a user-facing debug export. If every downstream consumer can use the shallow Object or typed Array directly, keep only the canonical variable and remove the duplicate JSON input/output/binding/End output together.

Example:

```python
def main(raw_response):
    response = parse_response(raw_response)
    product = response.get("data", {}).get("product", {})
    image_urls = product.get("image_urls") or []
    product_summary = {
        "asin": product.get("asin") or "",
        "title": product.get("title") or "",
        "image_count": len(image_urls),
        "image_urls": [str(url) for url in image_urls],
    }
    return {
        "product": product_summary,
        "product_json": json.dumps(product, ensure_ascii=False),
    }
```

## Static Checks Before Import

- Parse the embedded code with Python `ast` when `code_language: python3`.
- Confirm `main(...)` exists.
- Confirm `data.variables` names are a subset of `main(...)` parameters.
- Confirm literal returned dict keys, when detectable, are declared in `outputs`.
- Confirm `outputs` types are Dify type names such as `string`, `number`, `boolean`, `object`, `array`, or typed arrays like `array[string]`.
