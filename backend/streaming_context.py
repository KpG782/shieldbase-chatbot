"""Thread-local storage for the streaming on_token callback.

This module provides a zero-dependency way to pass the streaming callback
from the FastAPI request handler (asyncio thread) into the LangGraph
execution thread without modifying the ChatState schema or graph signatures.

Usage
-----
In the request handler (asyncio context):

    from streaming_context import clear_on_token, set_on_token

    def _on_token(token: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, token)

    def _run_in_thread():
        set_on_token(_on_token)
        try:
            return run_graph(state, message)
        finally:
            clear_on_token()
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

In a node that needs to stream (e.g. rag.py):

    from streaming_context import get_on_token

    on_token = get_on_token()  # Returns None when not in a streaming context
    content = client.chat_text(..., on_token=on_token)
"""

from __future__ import annotations

import threading
from collections.abc import Callable

_local: threading.local = threading.local()


def set_on_token(callback: Callable[[str], None]) -> None:
    """Register a streaming callback for the current thread."""
    _local.callback = callback


def get_on_token() -> Callable[[str], None] | None:
    """Return the streaming callback for the current thread, or None."""
    return getattr(_local, "callback", None)


def clear_on_token() -> None:
    """Remove the streaming callback for the current thread."""
    _local.callback = None
