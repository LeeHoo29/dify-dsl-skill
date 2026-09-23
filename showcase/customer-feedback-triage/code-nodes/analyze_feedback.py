# Dify input variables:
# - customer_id (String, required): Customer or ticket identifier.
# - feedback (String, required): Customer feedback text.
# - rating (Number, required): Rating from 1 to 5.
#
# Dify output variables:
# - can_continue (Boolean): Whether all required inputs are valid.
# - category (String): Deterministic feedback category.
# - error_message (String): Validation failure reason.
# - needs_follow_up (Boolean): Whether the feedback needs priority handling.
# - normalized_feedback (String): Cleaned feedback text.
# - priority (String): high, medium, or normal.
from typing import Any


NEGATIVE_TERMS = (
    "broken",
    "cancel",
    "damaged",
    "late",
    "missing",
    "refund",
    "unusable",
)


def main(customer_id: str, feedback: str, rating: Any) -> dict:
    customer = str(customer_id or "").strip()
    text = " ".join(str(feedback or "").split())
    try:
        score = int(float(rating))
    except (TypeError, ValueError):
        score = 0

    if not customer:
        return {
            "can_continue": False,
            "category": "invalid",
            "error_message": "customer_id is required",
            "needs_follow_up": False,
            "normalized_feedback": text,
            "priority": "normal",
        }
    if not text:
        return {
            "can_continue": False,
            "category": "invalid",
            "error_message": "feedback is required",
            "needs_follow_up": False,
            "normalized_feedback": "",
            "priority": "normal",
        }
    if score < 1 or score > 5:
        return {
            "can_continue": False,
            "category": "invalid",
            "error_message": "rating must be between 1 and 5",
            "needs_follow_up": False,
            "normalized_feedback": text,
            "priority": "normal",
        }

    lowered = text.lower()
    negative_match = any(term in lowered for term in NEGATIVE_TERMS)
    needs_follow_up = score <= 2 or negative_match
    priority = "high" if score == 1 or negative_match else "medium" if score <= 3 else "normal"
    category = "service_recovery" if needs_follow_up else "positive" if score >= 4 else "general"

    return {
        "can_continue": True,
        "category": category,
        "error_message": "",
        "needs_follow_up": needs_follow_up,
        "normalized_feedback": text,
        "priority": priority,
    }
