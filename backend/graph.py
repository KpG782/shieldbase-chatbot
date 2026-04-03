from __future__ import annotations

from typing import Any

from nodes.collect_details import collect_details, get_field_prompt
from nodes.confirm import confirm
from nodes.identify_product import detect_product, identify_product
from nodes.rag import rag_answer
from nodes.router import classify_intent, route_after_router
from nodes.validate_quote import validate_quote
from state import ChatState, clone_state


def run_graph(state: ChatState, message: str) -> ChatState:
    working_state = clone_state(state)
    working_state["last_error"] = None

    messages = list(working_state.get("messages", []))
    messages.append({"role": "user", "content": message})
    working_state["messages"] = messages

    intent = classify_intent(working_state, message)
    working_state["intent"] = intent

    if intent == "quote":
        requested_product = detect_product(message)
        if (
            requested_product
            and requested_product != working_state.get("insurance_type")
            and working_state.get("mode") == "transactional"
        ):
            _reset_quote_progress(working_state)

    if intent == "question" and working_state.get("mode") == "transactional":
        working_state["pending_question"] = message

    current_node = route_after_router(working_state)

    if current_node == "rag_answer":
        working_state = ChatState(**rag_answer(working_state))
        if working_state.get("mode") == "transactional":
            step = working_state.get("quote_step")
            if (
                step == "collect"
                and working_state.get("insurance_type")
                and working_state.get("current_field")
            ):
                _append_to_last_assistant_message(
                    working_state,
                    f"\n\nNow, back to your {working_state['insurance_type']} quote — "
                    f"{get_field_prompt(working_state['insurance_type'], working_state['current_field'])}",
                )
            elif step == "identify":
                _append_to_last_assistant_message(
                    working_state,
                    "\n\nNow, which insurance type would you like a quote for: auto, home, or life?",
                )
        return working_state

    if current_node == "identify_product":
        working_state = ChatState(**identify_product(working_state, message))
        if working_state.get("quote_step") == "collect":
            working_state = ChatState(**collect_details(working_state))
        return working_state

    if current_node == "collect_details":
        working_state = ChatState(**collect_details(working_state, message))
        if working_state.get("quote_step") == "validate":
            working_state = ChatState(**validate_quote(working_state))
        return working_state

    if current_node == "validate_quote":
        return ChatState(**validate_quote(working_state))

    if current_node == "confirm":
        working_state = ChatState(**confirm(working_state, message))
        if working_state.get("quote_step") == "collect":
            working_state = ChatState(**collect_details(working_state))
        return working_state

    return working_state


def _reset_quote_progress(state: dict[str, Any]) -> None:
    state["insurance_type"] = None
    state["collected_data"] = {}
    state["quote_result"] = None
    state["pending_question"] = None
    state["current_field"] = None
    state["quote_step"] = "identify"
    state["mode"] = "transactional"


def _append_to_last_assistant_message(state: dict[str, Any], suffix: str) -> None:
    messages = list(state.get("messages", []))
    if not messages:
        return
    if messages[-1].get("role") != "assistant":
        return
    messages[-1]["content"] = f"{messages[-1].get('content', '')}{suffix}"
    state["messages"] = messages
