from __future__ import annotations

from typing import Any


PRODUCT_LABELS = {
    "auto": ("auto", "car", "vehicle", "driver"),
    "home": ("home", "house", "property", "condo", "apartment"),
    "life": ("life", "family", "term life"),
}


def identify_product(state: dict[str, Any], message: str) -> dict[str, Any]:
    state["mode"] = "transactional"
    state["quote_step"] = "identify"

    insurance_type = detect_product(message) or state.get("insurance_type")
    if not insurance_type:
        assistant_message = (
            "Which type of insurance quote would you like: auto, home, or life?"
        )
        state["current_field"] = None
        _append_assistant_message(state, assistant_message)
        return state

    state["insurance_type"] = insurance_type
    state["quote_step"] = "collect"
    state["current_field"] = None
    # Do not append a message here — collect_details (called immediately after in graph.py)
    # will emit the first field question, which becomes the visible response.
    return state


def detect_product(message: str | None) -> str | None:
    if not message:
        return None
    lowered = message.lower()
    for insurance_type, labels in PRODUCT_LABELS.items():
        if any(label in lowered for label in labels):
            return insurance_type
    return None


def _append_assistant_message(state: dict[str, Any], content: str) -> None:
    messages = list(state.get("messages", []))
    messages.append({"role": "assistant", "content": content})
    state["messages"] = messages
