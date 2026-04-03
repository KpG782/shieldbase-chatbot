from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from env import load_project_env
from graph import run_graph
from state import ChatState, build_initial_state

load_project_env()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("shieldbase.main")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


class ResetRequest(BaseModel):
    session_id: str = Field(min_length=1)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Auto-ingest the knowledge base on startup so the first query never hits an empty collection."""
    from services.vectorstore import ensure_knowledge_base_index

    try:
        index = ensure_knowledge_base_index()
        logger.info(
            "Knowledge base ready — backend=%s chunks=%d",
            index.backend,
            len(index.chunks),
        )
    except Exception as exc:
        logger.error("Knowledge base ingestion failed at startup: %s", exc)

    yield


app = FastAPI(title="ShieldBase Insurance Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_STORE: dict[str, ChatState] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/debug")
async def debug() -> JSONResponse:
    """Diagnostic endpoint: shows KB status, a retrieval probe, and LLM reachability."""
    from services.vectorstore import ensure_knowledge_base_index, search_knowledge_base
    from services.llm import OpenRouterClient, OpenRouterConfigError, OpenRouterError

    # --- KB status ---
    kb_status: dict[str, Any] = {}
    try:
        index = ensure_knowledge_base_index()
        probe = search_knowledge_base("what insurance products do you offer", top_k=3)
        kb_status = {
            "ok": True,
            "backend": index.backend,
            "chunk_count": len(index.chunks),
            "retrieval_probe": [
                {"title": r.title, "source": r.source, "score": round(r.score, 4), "snippet": r.content[:120]}
                for r in probe
            ],
        }
    except Exception as exc:
        kb_status = {"ok": False, "error": str(exc)}

    # --- LLM status ---
    llm_status: dict[str, Any] = {}
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    llm_status["api_key_present"] = bool(api_key)
    llm_status["api_key_prefix"] = api_key[:12] + "..." if api_key else "(missing)"
    llm_status["model"] = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
    try:
        client = OpenRouterClient.from_env()
        result = client.chat_text(
            system_prompt="You are a test bot.",
            user_prompt="Reply with exactly: OK",
            max_tokens=10,
            temperature=0.0,
        )
        llm_status["ok"] = True
        llm_status["ping_response"] = result
    except OpenRouterConfigError as exc:
        llm_status["ok"] = False
        llm_status["error"] = f"Config error: {exc}"
    except OpenRouterError as exc:
        llm_status["ok"] = False
        llm_status["error"] = f"Request error: {exc}"
    except Exception as exc:
        llm_status["ok"] = False
        llm_status["error"] = f"Unexpected: {exc}"

    return JSONResponse({
        "knowledge_base": kb_status,
        "llm": llm_status,
        "session_count": len(SESSION_STORE),
    })


@app.post("/reset")
async def reset_session(payload: ResetRequest) -> JSONResponse:
    SESSION_STORE[payload.session_id] = build_initial_state(payload.session_id)
    return JSONResponse({"status": "reset", "session_id": payload.session_id})


@app.post("/chat")
async def chat(payload: ChatRequest) -> StreamingResponse:
    session_state = SESSION_STORE.get(payload.session_id) or build_initial_state(payload.session_id)
    session_state["trace_id"] = str(uuid4())

    try:
        next_state = run_graph(session_state, payload.message)
    except Exception as exc:
        async def error_stream() -> AsyncGenerator[str, None]:
            yield _format_sse("error", {"message": f"The assistant could not process the request: {exc}"})

        return StreamingResponse(error_stream(), media_type="text/event-stream")

    SESSION_STORE[payload.session_id] = next_state
    assistant_message = _last_assistant_message(next_state)

    async def event_stream() -> AsyncGenerator[str, None]:
        if not assistant_message:
            yield _format_sse("error", {"message": "No assistant response was generated."})
            return

        for token in _tokenize_message(assistant_message):
            yield _format_sse("token", token)
            await asyncio.sleep(0.005)

        yield _format_sse(
            "message_complete",
            {
                "message": assistant_message,
                "quote_result": next_state.get("quote_result"),
                "session": _public_session_state(next_state),
                "session_id": payload.session_id,
                "trace_id": next_state.get("trace_id"),
            },
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _last_assistant_message(state: ChatState) -> str:
    for message in reversed(state.get("messages", [])):
        if message.get("role") == "assistant":
            return str(message.get("content", ""))
    return ""


def _tokenize_message(content: str) -> list[str]:
    if not content:
        return []
    words = content.split()
    return [word + (" " if index < len(words) - 1 else "") for index, word in enumerate(words)]


def _public_session_state(state: ChatState) -> dict[str, Any]:
    return {
        "session_id": state.get("session_id"),
        "mode": state.get("mode"),
        "intent": state.get("intent"),
        "quote_step": state.get("quote_step"),
        "insurance_type": state.get("insurance_type"),
        "current_field": state.get("current_field"),
        "trace_id": state.get("trace_id"),
        "has_quote_result": bool(state.get("quote_result")),
    }


def _format_sse(event: str, data: Any) -> str:
    serialized = json.dumps(data)
    return f"event: {event}\ndata: {serialized}\n\n"
