from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from nodes.collect_details import collect_details, get_field_prompt
from nodes.confirm import confirm
from nodes.identify_product import detect_product, identify_product
from nodes.rag import rag_answer
from nodes.router import classify_intent, route_after_router
from nodes.validate_quote import validate_quote
from state import ChatState, clone_state


def _router_node(state: ChatState) -> ChatState:
    working_state = clone_state(state)
    messages = working_state.get("messages", [])
    if not messages:
        return working_state

    latest_message = messages[-1].get("content", "")
    intent = classify_intent(working_state, latest_message)
    working_state["intent"] = intent

    if intent == "quote":
        requested_product = detect_product(latest_message)
        if (
            requested_product
            and requested_product != working_state.get("insurance_type")
            and working_state.get("mode") == "transactional"
        ):
            _reset_quote_progress(working_state)

    if intent == "question" and working_state.get("mode") == "transactional":
        working_state["pending_question"] = latest_message

    return working_state


def _rag_node(state: ChatState) -> ChatState:
    working_state = ChatState(**rag_answer(clone_state(state)))
    if working_state.get("mode") != "transactional":
        return working_state

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


def _identify_product_node(state: ChatState) -> ChatState:
    latest_message = state.get("messages", [])[-1].get("content", "")
    return ChatState(**identify_product(clone_state(state), latest_message))


def _collect_details_node(state: ChatState) -> ChatState:
    current_field = state.get("current_field")
    latest_message = state.get("messages", [])[-1].get("content", "")
    message = latest_message if current_field else None
    return ChatState(**collect_details(clone_state(state), message))


def _validate_quote_node(state: ChatState) -> ChatState:
    return ChatState(**validate_quote(clone_state(state)))


def _confirm_node(state: ChatState) -> ChatState:
    latest_message = state.get("messages", [])[-1].get("content", "")
    return ChatState(**confirm(clone_state(state), latest_message))


def _route_from_router(state: ChatState) -> Literal[
    "rag_answer",
    "identify_product",
    "collect_details",
    "validate_quote",
    "confirm",
]:
    return route_after_router(state)  # type: ignore[return-value]


def _route_after_identify(state: ChatState) -> Literal["collect_details", "__end__"]:
    return "collect_details" if state.get("quote_step") == "collect" else END


def _route_after_collect(state: ChatState) -> Literal["validate_quote", "__end__"]:
    return "validate_quote" if state.get("quote_step") == "validate" else END


def _route_after_confirm(state: ChatState) -> Literal["collect_details", "__end__"]:
    return "collect_details" if state.get("quote_step") == "collect" else END


def _build_graph():
    graph = StateGraph(ChatState)
    graph.add_node("router", _router_node)
    graph.add_node("rag_answer", _rag_node)
    graph.add_node("identify_product", _identify_product_node)
    graph.add_node("collect_details", _collect_details_node)
    graph.add_node("validate_quote", _validate_quote_node)
    graph.add_node("confirm", _confirm_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _route_from_router,
        {
            "rag_answer": "rag_answer",
            "identify_product": "identify_product",
            "collect_details": "collect_details",
            "validate_quote": "validate_quote",
            "confirm": "confirm",
        },
    )
    graph.add_edge("rag_answer", END)
    graph.add_conditional_edges(
        "identify_product",
        _route_after_identify,
        {
            "collect_details": "collect_details",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "collect_details",
        _route_after_collect,
        {
            "validate_quote": "validate_quote",
            END: END,
        },
    )
    graph.add_edge("validate_quote", END)
    graph.add_conditional_edges(
        "confirm",
        _route_after_confirm,
        {
            "collect_details": "collect_details",
            END: END,
        },
    )

    return graph.compile()


COMPILED_GRAPH = _build_graph()


def run_graph(state: ChatState, message: str) -> ChatState:
    working_state = clone_state(state)
    working_state["last_error"] = None

    messages = list(working_state.get("messages", []))
    messages.append({"role": "user", "content": message})
    working_state["messages"] = messages

    next_state = COMPILED_GRAPH.invoke(working_state)
    return ChatState(**dict(next_state))


def _reset_quote_progress(state: ChatState) -> None:
    state["insurance_type"] = None
    state["collected_data"] = {}
    state["quote_result"] = None
    state["pending_question"] = None
    state["current_field"] = None
    state["quote_step"] = "identify"
    state["mode"] = "transactional"


def _append_to_last_assistant_message(state: ChatState, suffix: str) -> None:
    messages = list(state.get("messages", []))
    if not messages:
        return
    if messages[-1].get("role") != "assistant":
        return
    messages[-1]["content"] = f"{messages[-1].get('content', '')}{suffix}"
    state["messages"] = messages
