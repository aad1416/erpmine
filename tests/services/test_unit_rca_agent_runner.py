"""The RCA agent's document tool must scope retrieval to the resolved feature id and
accumulate sources across repeated searches — the agent is expected to search more than
once while narrowing in on a component."""

import json

import pytest
from agents.tool_context import ToolContext

from app.services.unit_rca_agent_runner import (
    UnitRCAToolContext,
    _merge_sources,
    search_equipment_documentation,
)


class _StubRetrievalService:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    async def retrieve(self, *, query, feature_id, top_k):
        self.calls.append({"query": query, "feature_id": feature_id, "top_k": top_k})
        return self._results.pop(0)


class _Result:
    def __init__(self, content, sources):
        self.content = content
        self.sources = sources


def _ctx(service):
    return UnitRCAToolContext(
        feature_id=42,
        rag_top_k=5,
        document_retrieval_tool_service=service,
    )


async def _invoke(ctx, query):
    """Invoke the tool the way the SDK does, so the real argument parsing runs."""
    arguments = json.dumps({"query": query})
    return await search_equipment_documentation.on_invoke_tool(
        ToolContext(
            ctx,
            tool_name="search_equipment_documentation",
            tool_call_id="call-1",
            tool_arguments=arguments,
        ),
        arguments,
    )


@pytest.mark.asyncio
async def test_tool_scopes_retrieval_to_resolved_feature_id():
    service = _StubRetrievalService([_Result("Compressor spec sheet", [])])
    ctx = _ctx(service)

    content = await _invoke(ctx, "compressor short cycling")

    assert content == "Compressor spec sheet"
    assert service.calls == [
        {"query": "compressor short cycling", "feature_id": 42, "top_k": 5}
    ]


@pytest.mark.asyncio
async def test_repeated_searches_accumulate_deduplicated_sources():
    service = _StubRetrievalService(
        [
            _Result("first", [{"document_id": "d1", "chunk_index": 0}]),
            _Result(
                "second",
                [
                    {"document_id": "d1", "chunk_index": 0},  # duplicate
                    {"document_id": "d2", "chunk_index": 3},
                ],
            ),
        ]
    )
    ctx = _ctx(service)

    await _invoke(ctx, "first query")
    await _invoke(ctx, "second query")

    assert len(service.calls) == 2
    assert ctx.sources == [
        {"document_id": "d1", "chunk_index": 0},
        {"document_id": "d2", "chunk_index": 3},
    ]


def test_merge_sources_is_keyed_on_document_and_chunk():
    existing = [{"document_id": "d1", "chunk_index": 0}]
    _merge_sources(
        existing,
        [
            {"document_id": "d1", "chunk_index": 0},
            {"document_id": "d1", "chunk_index": 1},
        ],
    )
    assert existing == [
        {"document_id": "d1", "chunk_index": 0},
        {"document_id": "d1", "chunk_index": 1},
    ]
