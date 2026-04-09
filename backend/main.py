from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from env import load_project_env
from graph import run_graph
from state import ChatState, build_initial_state
from streaming_context import clear_on_token, set_on_token

load_project_env()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("shieldbase.main")

# ── CORS ──────────────────────────────────────────────────────────────────────
# Restrict to known origins. Set ALLOWED_ORIGINS env var for production.
# Default is safe for local dev only.
_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
    if origin.strip()
]

# ── Rate limiting ─────────────────────────────────────────────────────────────
_CHAT_RATE_LIMIT = os.getenv("RATE_LIMIT_CHAT", "60/minute")
_RESET_RATE_LIMIT = os.getenv("RATE_LIMIT_RESET", "20/minute")

limiter = Limiter(key_func=get_remote_address)


def _is_rate_limit_disabled() -> bool:
    """Check at request time so tests can override via monkeypatch.setenv."""
    return os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "false"


# ── Session store ─────────────────────────────────────────────────────────────
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 hour default


def _init_redis_client() -> Any:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None
    try:
        import redis as redis_lib  # type: ignore[import]

        client = redis_lib.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        logger.info("Redis session store connected: %s", redis_url.split("@")[-1])
        return client
    except Exception as exc:
        logger.warning(
            "Redis unavailable (%s) — falling back to in-memory session store. "
            "Sessions will be lost on restart.",
            exc,
        )
        return None


class _SessionStore:
    """Session store with optional Redis persistence and in-memory fallback.

    Provides a dict-like interface so existing code and tests that access
    SESSION_STORE[key] continue to work unchanged.

    When REDIS_URL is set and Redis is reachable:
    - Sessions survive server restarts.
    - Multiple backend instances share the same session data (horizontal scaling).
    - Each session has a TTL; idle sessions are evicted automatically.

    When Redis is unavailable, the store falls back to an in-process dict
    with the original behaviour (sessions lost on restart, no scaling).
    """

    def __init__(self) -> None:
        self._memory: dict[str, ChatState] = {}
        self._redis: Any = _init_redis_client()

    # -- dict-like interface --------------------------------------------------

    def get(self, key: str, default: ChatState | None = None) -> ChatState | None:
        if self._redis is not None:
            try:
                raw = self._redis.get(f"session:{key}")
                if raw:
                    return ChatState(**json.loads(raw))
            except Exception as exc:
                logger.warning("Redis GET failed for session %s: %s — using in-memory", key, exc)
        return self._memory.get(key, default)

    def __setitem__(self, key: str, value: ChatState) -> None:
        self._memory[key] = value
        if self._redis is not None:
            try:
                serializable = {k: v for k, v in dict(value).items()}
                self._redis.setex(
                    f"session:{key}",
                    SESSION_TTL_SECONDS,
                    json.dumps(serializable),
                )
            except Exception as exc:
                logger.warning("Redis SET failed for session %s: %s — state stored in memory only", key, exc)

    def __getitem__(self, key: str) -> ChatState:
        result = self.get(key)
        if result is None:
            raise KeyError(key)
        return result

    def __contains__(self, key: object) -> bool:
        return self.get(str(key)) is not None  # type: ignore[arg-type]

    def clear(self) -> None:
        """Clear in-memory store. Used by tests; does not flush Redis."""
        self._memory.clear()

    def __len__(self) -> int:
        return len(self._memory)


SESSION_STORE = _SessionStore()


# ── Pydantic models ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


class ResetRequest(BaseModel):
    session_id: str = Field(min_length=1)


# ── Application ───────────────────────────────────────────────────────────────

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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

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
    llm_status["model"] = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
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
        "session_backend": "redis" if SESSION_STORE._redis is not None else "memory",
        "cors_origins": _CORS_ORIGINS,
        "rate_limit_enabled": not _is_rate_limit_disabled(),
    })


@app.post("/reset")
@limiter.limit(_RESET_RATE_LIMIT, exempt_when=_is_rate_limit_disabled)
async def reset_session(request: Request, payload: ResetRequest) -> JSONResponse:
    SESSION_STORE[payload.session_id] = build_initial_state(payload.session_id)
    return JSONResponse({"status": "reset", "session_id": payload.session_id})


@app.post("/chat")
@limiter.limit(_CHAT_RATE_LIMIT, exempt_when=_is_rate_limit_disabled)
async def chat(request: Request, payload: ChatRequest) -> StreamingResponse:
    session_state = SESSION_STORE.get(payload.session_id) or build_initial_state(payload.session_id)
    session_state["trace_id"] = str(uuid4())

    loop = asyncio.get_running_loop()
    token_queue: asyncio.Queue[str | None] = asyncio.Queue()
    tokens_emitted: dict[str, bool] = {"any": False}

    def _on_token(token: str) -> None:
        tokens_emitted["any"] = True
        loop.call_soon_threadsafe(token_queue.put_nowait, token)

    def _run_in_thread() -> ChatState:
        """Run the synchronous LangGraph in a thread-pool worker.

        The on_token callback is registered in thread-local storage so rag.py
        can find it without any changes to ChatState or the graph signatures.
        A None sentinel is always placed on the queue when the thread exits
        (even on exception) so the async generator unblocks correctly.
        """
        set_on_token(_on_token)
        try:
            return run_graph(session_state, payload.message)
        finally:
            clear_on_token()
            loop.call_soon_threadsafe(token_queue.put_nowait, None)  # sentinel

    async def event_stream() -> AsyncGenerator[str, None]:
        future = loop.run_in_executor(None, _run_in_thread)

        # Yield real LLM tokens as they arrive from the streaming callback.
        while True:
            token = await token_queue.get()
            if token is None:  # sentinel — graph thread has finished
                break
            yield _format_sse("token", token)

        try:
            next_state = await future
        except Exception as exc:
            yield _format_sse("error", {"message": f"The assistant could not process the request: {exc}"})
            return

        SESSION_STORE[payload.session_id] = next_state
        assistant_message = _last_assistant_message(next_state)

        if not assistant_message:
            yield _format_sse("error", {"message": "No assistant response was generated."})
            return

        # For deterministic responses (field prompts, validation errors, quote results)
        # no LLM was called, so no tokens were streamed. Simulate word-by-word streaming
        # to keep a consistent UX for all response types.
        if not tokens_emitted["any"]:
            for word_token in _tokenize_message(assistant_message):
                yield _format_sse("token", word_token)
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


# ── Helpers ───────────────────────────────────────────────────────────────────

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
