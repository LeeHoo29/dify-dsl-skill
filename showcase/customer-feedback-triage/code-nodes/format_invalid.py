# Dify input variables:
# - customer_id (String, required): Customer or ticket identifier.
# - error_message (String, required): Validation failure reason.
#
# Dify output variables:
# - action (String): Recommended correction action.
# - result (String): Human-readable validation result.
def main(customer_id: str, error_message: str) -> dict:
    customer = str(customer_id or "unknown").strip() or "unknown"
    reason = str(error_message or "invalid feedback input").strip()
    action = "Correct the input fields and submit the feedback again."
    result = f"INPUT REJECTED | customer={customer} | reason={reason}"
    return {"action": action, "result": result}
