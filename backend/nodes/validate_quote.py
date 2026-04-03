from __future__ import annotations

from services.quote_calculator import calculate_quote, validate_quote_inputs


def validate_quote(state: dict, message: str | None = None) -> dict:
    insurance_type = state.get("insurance_type")
    collected_data = dict(state.get("collected_data", {}))

    validation = validate_quote_inputs(insurance_type, collected_data)
    if not validation.ok:
        state["quote_step"] = "collect"
        state["current_field"] = validation.field
        _append_assistant_message(
            state,
            validation.message or "One of the quote fields is invalid. Please try again.",
        )
        if validation.field:
            collected_data.pop(validation.field, None)
        state["collected_data"] = collected_data
        return state

    quote_result = calculate_quote(insurance_type, collected_data)
    state["quote_result"] = quote_result
    state["quote_step"] = "confirm"
    _append_assistant_message(
        state,
        (
            f"Your estimated {insurance_type} premium is ${quote_result['premium']:.2f} per year. "
            "Reply accept to confirm, adjust to change details, or restart to start over."
        ),
    )
    return state


def _append_assistant_message(state: dict, content: str) -> None:
    messages = list(state.get("messages", []))
    messages.append({"role": "assistant", "content": content})
    state["messages"] = messages
