from __future__ import annotations

import json
from typing import Any

from services.llm import OpenRouterClient, OpenRouterError


QUESTION_HINTS = {
    "what",
    "how",
    "why",
    "when",
    "where",
    "does",
    "do",
    "can",
    "could",
    "coverage",
    "claim",
    "policy",
    "premium",
}
QUOTE_HINTS = {"quote", "price", "pricing", "premium", "buy", "purchase", "insurance"}
AFFIRM_HINTS = {"yes", "accept", "confirm", "looks good", "good", "approve", "ok", "okay"}
ADJUST_HINTS = {"adjust", "change", "modify", "update", "edit"}
RESTART_HINTS = {"restart", "start over", "reset"}
PROGRESSION_HINTS = {
    "next",
    "what next",
    "whats next",
    "what's next",
    "continue",
    "go on",
    "proceed",
}


def classify_intent(state: dict[str, Any], message: str, client: OpenRouterClient | None = None) -> str:
    # Apply deterministic overrides before the LLM for states where the answer is unambiguous.
    forced = _classify_deterministic(state, message)
    if forced is not None:
        return forced

    # In the transactional quote flow, protect field answers and confirm-step replies from
    # live LLM misclassification. This is the path hit by inputs like "2019" or "Toyota, Camry..."
    # that must stay inside collect_details instead of drifting into RAG.
    rules_result = _classify_with_rules(state, message)
    if state.get("mode") == "transactional" and rules_result in {"response", "quote"}:
        return rules_result

    llm_result = _classify_with_llm(state, message, client)
    if llm_result in {"question", "quote", "response"}:
        return llm_result
    return rules_result


def _classify_deterministic(state: dict[str, Any], message: str) -> str | None:
    """Return a forced intent for states where the classification is unambiguous, else None."""
    lowered = message.strip().lower()
    tokens = set(lowered.split())
    mode = state.get("mode", "conversational")
    quote_step = state.get("quote_step", "identify")
    current_field = state.get("current_field")

    # Restart is always a response when transactional, or a fresh quote trigger otherwise.
    if any(token in lowered for token in RESTART_HINTS):
        return "response" if mode == "transactional" else "quote"

    # Fresh explicit quote requests should never be downgraded into generic RAG.
    # This covers starts like "I want a quote for auto insurance" and
    # "Can I get a home insurance quote?" even when the LLM misclassifies them.
    if "quote" in lowered:
        return "quote"

    # Waiting for the user to pick an insurance type: if they name a product, it is a response.
    # We bypass the LLM here because "home" / "auto" / "life" alone is reliably misclassified
    # as a question by small LLMs that see the word without context.
    if mode == "transactional" and quote_step == "identify":
        if _PRODUCT_KEYWORDS & tokens:
            return "response"
        if any(phrase in lowered for phrase in PROGRESSION_HINTS) or any(token in tokens for token in AFFIRM_HINTS):
            return "response"
        # Not a product keyword — fall through to LLM/rules (may be a real question)
        return None

    # Waiting for a field value: if the message has no question mark and no question words,
    # treat it as a field response so the LLM cannot misroute it.
    if mode == "transactional" and current_field:
        if "quote" in lowered:
            return "quote"
        if "?" not in lowered and not any(w in tokens for w in QUESTION_HINTS):
            return "response"
        if any(phrase in lowered for phrase in PROGRESSION_HINTS):
            return "response"

    # Once already in a quote flow, conversational-looking "continue" turns should remain
    # in the transactional branch instead of resetting or drifting into generic chat.
    if mode == "transactional" and quote_step in {"collect", "confirm"}:
        if any(phrase in lowered for phrase in PROGRESSION_HINTS):
            return "response"

    return None


def route_after_router(state: dict[str, Any]) -> str:
    intent = state.get("intent", "question")
    if intent == "question":
        return "rag_answer"
    if intent == "quote":
        if not state.get("insurance_type"):
            return "identify_product"
        return "collect_details"

    step = state.get("quote_step", "identify")
    step_to_node = {
        "identify": "identify_product",
        "collect": "collect_details",
        "validate": "validate_quote",
        "confirm": "confirm",
    }
    return step_to_node.get(step, "rag_answer")


def interpret_confirmation(message: str) -> str | None:
    lowered = message.strip().lower()
    if any(token in lowered for token in RESTART_HINTS):
        return "restart"
    if any(token in lowered for token in ADJUST_HINTS):
        return "adjust"
    if any(token in lowered for token in AFFIRM_HINTS):
        return "accept"
    return None


def _classify_with_llm(state: dict[str, Any], message: str, client: OpenRouterClient | None) -> str | None:
    if client is None:
        try:
            client = OpenRouterClient.from_env()
        except Exception:
            return None

    try:
        payload = client.chat_json(
            system_prompt=(
                "Classify the user message into exactly one intent: "
                "question, quote, or response. "
                "Return JSON with a single key named intent."
            ),
            user_prompt=json.dumps(
                {
                    "message": message,
                    "mode": state.get("mode"),
                    "quote_step": state.get("quote_step"),
                    "insurance_type": state.get("insurance_type"),
                    "current_field": state.get("current_field"),
                }
            ),
            max_tokens=60,
        )
    except (OpenRouterError, Exception):
        return None

    intent = payload.get("intent")
    if isinstance(intent, str):
        return intent.strip().lower()
    return None


_PRODUCT_KEYWORDS = {
    "auto",
    "car",
    "vehicle",
    "motor",
    "home",
    "house",
    "property",
    "condo",
    "apartment",
    "life",
}


def _classify_with_rules(state: dict[str, Any], message: str) -> str:
    lowered = message.strip().lower()
    tokens = set(lowered.split())
    mode = state.get("mode", "conversational")
    current_field = state.get("current_field")
    quote_step = state.get("quote_step", "identify")

    if any(token in lowered for token in RESTART_HINTS):
        return "response" if mode == "transactional" else "quote"

    if "quote" in lowered or "insurance quote" in lowered:
        return "quote"

    # Waiting for the user to pick an insurance type — treat product keywords as a response,
    # everything else as a question so RAG can still handle real questions.
    if mode == "transactional" and quote_step == "identify":
        if _PRODUCT_KEYWORDS & tokens:
            return "response"
        if any(phrase in lowered for phrase in PROGRESSION_HINTS) or any(token in tokens for token in AFFIRM_HINTS):
            return "response"
        # A non-product message while waiting for type selection → question (RAG answers it)
        return "question"

    if mode == "transactional" and quote_step == "confirm":
        return "response"

    if mode == "transactional" and current_field:
        if any(phrase in lowered for phrase in PROGRESSION_HINTS):
            return "response"
        if "?" in lowered and "quote" not in lowered:
            return "question"
        return "response"

    if "?" in lowered or any(token in lowered.split() for token in QUESTION_HINTS):
        if "quote" not in lowered:
            return "question"

    if any(token in lowered.split() for token in QUOTE_HINTS) and "quote" in lowered:
        return "quote"

    return "question"
