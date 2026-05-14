"""Unit tests for app.core.observability.

Verifies the no-op contract: with Langfuse disabled (default), the trace /
span / generation context managers yield silent stubs that accept update()
and end() without erroring. This is the contract that keeps the rest of the
app safe to call obs.* unconditionally.
"""

from __future__ import annotations

import pytest

from app.core import observability as obs


@pytest.fixture(autouse=True)
def _disable_langfuse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the no-op path regardless of the user's local .env."""
    monkeypatch.setattr(obs.settings, "LANGFUSE_ENABLED", False)
    # Reset module-level cache so each test re-evaluates `_get_client`.
    monkeypatch.setattr(obs, "_client", None)
    monkeypatch.setattr(obs, "_init_attempted", False)


class TestNoopContract:
    def test_get_client_returns_none_when_disabled(self) -> None:
        assert obs._get_client() is None

    def test_trace_yields_stub_and_does_not_raise(self) -> None:
        with obs.trace(name="x") as t:
            # The stub object has .update(), .end(), and an .id attribute.
            t.update(input={"q": "anything"})
            t.update(metadata={"foo": "bar"})
            t.update(output="anything")
            t.end()
            assert hasattr(t, "id")

    def test_span_under_stub_trace_is_also_stub(self) -> None:
        with obs.trace(name="t") as t, obs.span(t, name="retrieval") as s:
            s.update(output={"n": 1})

    def test_generation_under_stub_trace_is_also_stub(self) -> None:
        with obs.trace(name="t") as t:
            with obs.generation(t, name="gen", model="m") as g:
                g.update(output="hello")

    def test_flush_does_not_raise_when_client_absent(self) -> None:
        obs.flush()

    def test_span_with_none_parent_is_stub(self) -> None:
        with obs.span(None, name="orphan") as s:
            s.update(metadata={"k": "v"})

    def test_generation_with_none_parent_is_stub(self) -> None:
        with obs.generation(None, name="g", model="m") as g:
            g.update(output="ok")


class TestEnabledWithoutKeys:
    """If observability is 'enabled' but the keys are missing, behave like noop
    (and log a warning — but don't raise)."""

    def test_enabled_without_keys_falls_back_to_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(obs.settings, "LANGFUSE_ENABLED", True)
        monkeypatch.setattr(obs.settings, "LANGFUSE_PUBLIC_KEY", None)
        monkeypatch.setattr(obs.settings, "LANGFUSE_SECRET_KEY", None)
        monkeypatch.setattr(obs, "_client", None)
        monkeypatch.setattr(obs, "_init_attempted", False)
        assert obs._get_client() is None

        # And the public API still works.
        with obs.trace(name="x") as t:
            t.update(input="x")
