from __future__ import annotations

from nodes.router import interpret_confirmation


def confirm(state: dict, message: str) -> dict:
    action = interpret_confirmation(message)
    quote_result = state.get("quote_result")

    if action == "accept" and not quote_result:
        _append_assistant_message(
            state,
            "There is no quote ready to confirm yet. Please complete the quote details first.",
        )
        state["mode"] = "transactional"
        state["quote_step"] = "collect" if state.get("insurance_type") else "identify"
        return state

    if action == "accept":
        quote_result = quote_result or {}
        summary = quote_result.get("summary", "your insurance quote")
        _append_assistant_message(
            state,
            f"Confirmed. I have finalized {summary}. Reply restart if you want to begin another quote.",
        )
        state["mode"] = "conversational"
        state["quote_step"] = "identify"
        state["current_field"] = None
        return state

    if action == "adjust":
        insurance_type = state.get("insurance_type")
        state["quote_step"] = "collect"
        state["current_field"] = None
        state["collected_data"] = {}
        state["quote_result"] = None
        state["mode"] = "transactional"
        state["insurance_type"] = insurance_type
        return state

    if action == "restart":
        _reset_quote_state(state)
        _append_assistant_message(
            state,
            "The quote flow has been restarted. Which insurance type would you like: auto, home, or life?",
        )
        return state

    _append_assistant_message(
        state,
        "Please reply accept, adjust, or restart so I know how to handle the quote.",
    )
    return state


def _reset_quote_state(state: dict) -> None:
    state["mode"] = "transactional"
    state["quote_step"] = "identify"
    state["insurance_type"] = None
    state["collected_data"] = {}
    state["quote_result"] = None
    state["pending_question"] = None
    state["current_field"] = None
    state["last_error"] = None


def _append_assistant_message(state: dict, content: str) -> None:
    messages = list(state.get("messages", []))
    messages.append({"role": "assistant", "content": content})
    state["messages"] = messages
