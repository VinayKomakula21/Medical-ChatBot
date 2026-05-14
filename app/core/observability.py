"""Langfuse observability — free-tier wrapper.

Why this exists:
  The project's LLM calls are raw HTTP (Groq's OpenAI-compatible endpoint),
  not a LangChain ChatModel. So we instrument manually with the Langfuse SDK's
  low-level `trace()` / `generation()` / `span()` calls.

Why it's a wrapper, not direct imports everywhere:
  - The project must run with NO Langfuse key (LANGFUSE_ENABLED=False is default).
    Every helper here is a no-op in that case. Service code doesn't need to
    branch on the flag — it just calls `obs.trace(...)` and gets a stub if disabled.
  - If we ever swap to Phoenix / Helicone / OpenLLMetry, we change one file.

Free-tier defaults:
  - Cloud Hobby tier: 50k observations/month
  - Self-host fallback: set LANGFUSE_HOST to your self-hosted URL — no event cap.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazily-imported Langfuse client. None when disabled or import fails.
_client: Any = None
_init_attempted = False


def _get_client() -> Any:
    global _client, _init_attempted
    if _init_attempted:
        return _client
    _init_attempted = True

    if not settings.LANGFUSE_ENABLED:
        return None
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        logger.warning(
            "LANGFUSE_ENABLED=true but keys not configured — observability disabled."
        )
        return None

    try:
        from langfuse import Langfuse  # type: ignore
    except ImportError:
        logger.warning("langfuse not installed — observability disabled.")
        return None

    try:
        _client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info("Langfuse initialized (host=%s)", settings.LANGFUSE_HOST)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse init failed: %s — observability disabled.", exc)
        _client = None
    return _client


# ---------------------------------------------------------------------------
# Stub spans — returned when observability is disabled. They expose the same
# minimal surface as Langfuse's span/generation objects so callers don't need
# to branch.
# ---------------------------------------------------------------------------
class _StubSpan:
    id: Optional[str] = None

    def update(self, **_: Any) -> None:
        pass

    def end(self, **_: Any) -> None:
        pass

    def __enter__(self) -> "_StubSpan":
        return self

    def __exit__(self, *_: Any) -> None:
        pass


_STUB = _StubSpan()


@contextmanager
def trace(name: str, user_id: Optional[str] = None, metadata: Optional[dict] = None) -> Iterator[Any]:
    """Top-level trace for an end-user request.

    Usage:
        with obs.trace("chat.message", user_id=str(user.id)) as t:
            ...
            print("trace_id:", t.id)   # surface this to clients
    """
    client = _get_client()
    if client is None:
        yield _STUB
        return

    t = client.trace(name=name, user_id=user_id, metadata=metadata or {})
    try:
        yield t
    finally:
        # Trace auto-finalizes on flush; explicit end() not needed.
        pass


@contextmanager
def span(
    parent: Any,
    name: str,
    input: Any = None,
    metadata: Optional[dict] = None,
) -> Iterator[Any]:
    """Nested span (e.g. retrieval). `parent` is the trace or another span."""
    if parent is _STUB or parent is None or _get_client() is None:
        yield _STUB
        return
    s = parent.span(name=name, input=input, metadata=metadata or {})
    try:
        yield s
    finally:
        try:
            s.end()
        except Exception as exc:  # noqa: BLE001
            logger.debug("span.end failed: %s", exc)


@contextmanager
def generation(
    parent: Any,
    name: str,
    model: str,
    input: Any = None,
    model_parameters: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> Iterator[Any]:
    """LLM generation span — surfaces input/output/usage in the Langfuse UI."""
    if parent is _STUB or parent is None or _get_client() is None:
        yield _STUB
        return
    g = parent.generation(
        name=name,
        model=model,
        input=input,
        model_parameters=model_parameters or {},
        metadata=metadata or {},
    )
    try:
        yield g
    finally:
        try:
            g.end()
        except Exception as exc:  # noqa: BLE001
            logger.debug("generation.end failed: %s", exc)


def flush() -> None:
    """Force-flush pending events. Call on app shutdown or before exiting tests."""
    client = _get_client()
    if client is not None:
        try:
            client.flush()
        except Exception as exc:  # noqa: BLE001
            logger.debug("langfuse flush failed: %s", exc)
