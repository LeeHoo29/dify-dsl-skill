# Dify input variables:
# - category (String, required): Feedback category.
# - customer_id (String, required): Customer or ticket identifier.
# - feedback (String, required): Normalized feedback text.
# - priority (String, required): Triage priority.
#
# Dify output variables:
# - action (String): Recommended handling action.
# - result (String): Human-readable triage summary.
def main(category: str, customer_id: str, feedback: str, priority: str) -> dict:
    action = "Contact the customer within four business hours and open a service-recovery ticket."
    result = (
        f"PRIORITY FOLLOW-UP | customer={customer_id} | priority={priority} | "
        f"category={category} | feedback={feedback}"
    )
    return {"action": action, "result": result}
