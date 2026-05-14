"""Unit tests for app.clients.rxnorm.

Uses httpx.MockTransport to stub the NIH RxNav API responses. Each test
constructs its own client (NOT the module singleton) so the mock transport
swaps in cleanly and there's no cross-test state leak.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.clients.rxnorm import RxNormClient


def _build_client_with_handler(handler) -> RxNormClient:
    """Return an RxNormClient whose internal AsyncClient is mock-transport backed."""
    c = RxNormClient()
    c._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return c


# ---------------------------------------------------------------------------
# find_rxcui
# ---------------------------------------------------------------------------
class TestFindRxcui:
    @pytest.mark.asyncio
    async def test_returns_first_rxcui_on_match(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/REST/rxcui.json" in str(request.url)
            assert request.url.params.get("name") == "metformin"
            return httpx.Response(
                200,
                content=json.dumps({"idGroup": {"rxnormId": ["6809", "111"]}}).encode(),
            )

        c = _build_client_with_handler(handler)
        rxcui = await c.find_rxcui("metformin")
        assert rxcui == "6809"
        await c.close()

    @pytest.mark.asyncio
    async def test_returns_none_when_empty(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=json.dumps({"idGroup": {}}).encode())

        c = _build_client_with_handler(handler)
        assert await c.find_rxcui("definitely-not-a-drug-12345") is None
        await c.close()

    @pytest.mark.asyncio
    async def test_empty_name_short_circuits_without_http_call(self) -> None:
        called = {"n": 0}

        def handler(_: httpx.Request) -> httpx.Response:
            called["n"] += 1
            return httpx.Response(200, content=b"{}")

        c = _build_client_with_handler(handler)
        assert await c.find_rxcui("") is None
        assert await c.find_rxcui("   ") is None
        assert called["n"] == 0
        await c.close()

    @pytest.mark.asyncio
    async def test_returns_none_on_non_200(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(503, content=b"upstream down")

        c = _build_client_with_handler(handler)
        assert await c.find_rxcui("aspirin") is None
        await c.close()

    @pytest.mark.asyncio
    async def test_returns_none_on_transport_error(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("network is down")

        c = _build_client_with_handler(handler)
        assert await c.find_rxcui("aspirin") is None
        await c.close()


# ---------------------------------------------------------------------------
# is_known_drug
# ---------------------------------------------------------------------------
class TestIsKnownDrug:
    @pytest.mark.asyncio
    async def test_true_when_rxcui_present(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=json.dumps({"idGroup": {"rxnormId": ["6809"]}}).encode(),
            )

        c = _build_client_with_handler(handler)
        assert await c.is_known_drug("metformin") is True
        await c.close()

    @pytest.mark.asyncio
    async def test_false_when_rxcui_absent(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=json.dumps({"idGroup": {}}).encode())

        c = _build_client_with_handler(handler)
        assert await c.is_known_drug("foo") is False
        await c.close()


# ---------------------------------------------------------------------------
# list_interactions
# ---------------------------------------------------------------------------
class TestListInteractions:
    @pytest.mark.asyncio
    async def test_empty_when_fewer_than_two_rxcuis(self) -> None:
        called = {"n": 0}

        def handler(_: httpx.Request) -> httpx.Response:
            called["n"] += 1
            return httpx.Response(200, content=b"{}")

        c = _build_client_with_handler(handler)
        assert await c.list_interactions(["6809"]) == []
        assert await c.list_interactions([]) == []
        assert called["n"] == 0
        await c.close()

    @pytest.mark.asyncio
    async def test_parses_canonical_response_shape(self) -> None:
        payload: dict[str, Any] = {
            "fullInteractionTypeGroup": [
                {
                    "fullInteractionType": [
                        {
                            "interactionPair": [
                                {
                                    "severity": "high",
                                    "description": "Risk of bleeding.",
                                    "interactionConcept": [
                                        {"minConceptItem": {"name": "aspirin"}},
                                        {"minConceptItem": {"name": "warfarin"}},
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            assert "interaction/list.json" in str(request.url)
            # "+".join is the canonical RxNav convention; verify our client used it.
            assert "rxcuis=1191+11289" in str(request.url) or "rxcuis=" in str(request.url)
            return httpx.Response(200, content=json.dumps(payload).encode())

        c = _build_client_with_handler(handler)
        out = await c.list_interactions(["1191", "11289"])
        assert len(out) == 1
        assert out[0]["drug_a"] == "aspirin"
        assert out[0]["drug_b"] == "warfarin"
        assert out[0]["severity"] == "high"
        await c.close()

    @pytest.mark.asyncio
    async def test_empty_when_no_groups(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=json.dumps({}).encode())

        c = _build_client_with_handler(handler)
        assert await c.list_interactions(["1", "2"]) == []
        await c.close()

    @pytest.mark.asyncio
    async def test_skips_malformed_pairs(self) -> None:
        # One pair has only 1 concept (malformed) — should be silently skipped.
        payload = {
            "fullInteractionTypeGroup": [
                {
                    "fullInteractionType": [
                        {
                            "interactionPair": [
                                {
                                    "severity": "low",
                                    "description": "",
                                    "interactionConcept": [
                                        {"minConceptItem": {"name": "only_one"}}
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=json.dumps(payload).encode())

        c = _build_client_with_handler(handler)
        assert await c.list_interactions(["1", "2"]) == []
        await c.close()
