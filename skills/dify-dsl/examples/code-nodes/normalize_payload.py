# Dify input variables:
# - raw_json (String, required): JSON object text supplied by the Start node.
#
# Dify output variables:
# - can_continue (Boolean): Whether parsing succeeded.
# - error_message (String): Safe parsing error for the failure branch.
# - result (Object): Shallow normalized payload for downstream nodes.
import json


def main(raw_json: str) -> dict:
    try:
        parsed = json.loads(raw_json or "{}")
        if not isinstance(parsed, dict):
            raise ValueError("input must be a JSON object")
    except Exception as error:
        return {
            "can_continue": False,
            "error_message": str(error),
            "result": {},
        }

    return {
        "can_continue": True,
        "error_message": "",
        "result": {str(key): value for key, value in list(parsed.items())[:20]},
    }
