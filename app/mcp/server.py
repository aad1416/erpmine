"""MCP server: thin tools only. Business logic lives in services."""

from __future__ import annotations

import logging
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl, Field

from app.config.setting import settings
from app.mcp.auth import allowed_feature_ids, client_name, init_auth
from app.mcp.models import (
    DocumentSource,
    FeatureInfo,
    ListFeaturesResult,
    SearchDocumentsResult,
)
from app.mcp.services import build_document_retrieval, list_features_for_ids, session_scope

logger = logging.getLogger(__name__)

_verifier, _ = init_auth()

_resource = settings.MCP_RESOURCE_URL or "http://127.0.0.1:8000/mcp"

mcp = MCPServer(
    "lyndom_mcp",
    instructions=(
        "Lyndom knowledge MCP server. "
        "Use list_features to see allowed feature IDs, then search_documents "
        "to retrieve ranked document chunks for a feature."
    ),
    token_verifier=_verifier,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl("https://lyndom.local/mcp-keys"),
        resource_server_url=AnyHttpUrl(_resource),
        required_scopes=["rag:read"],
        validate_token_resource=False,
    ),
)


def _require_feature(feature_id: int) -> str:
    """Return token string or raise a model-safe error."""
    access = get_access_token()
    if access is None:
        raise ValueError("Authentication required")
    allowed = allowed_feature_ids(access.token)
    if feature_id not in allowed:
        raise ValueError(f"feature_id={feature_id} is not accessible")
    return access.token


@mcp.tool(
    title="List accessible features",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
async def list_features() -> ListFeaturesResult:
    """List feature IDs this client is allowed to query with search_documents."""
    access = get_access_token()
    if access is None:
        return ListFeaturesResult(features=[])
    ids = allowed_feature_ids(access.token)
    rows = list_features_for_ids(ids)
    return ListFeaturesResult(
        features=[FeatureInfo(id=r["id"], name=r.get("name")) for r in rows]
    )


@mcp.tool(
    title="Search documents (RAG)",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
async def search_documents(
    query: Annotated[
        str,
        Field(min_length=1, description="Natural-language search query"),
    ],
    feature_id: Annotated[
        int,
        Field(ge=1, description="Feature ID whose document collections to search"),
    ],
    top_k: Annotated[
        int,
        Field(ge=1, le=20, description="Maximum number of chunks to return"),
    ] = 5,
) -> SearchDocumentsResult:
    """
    Search the Lyndom knowledge base for a feature.

    Searches the feature collection plus all classroom-item collections assigned
    to that feature. Returns only active documents, ranked by relevance, with
    source citations.
    """
    _require_feature(feature_id)
    trimmed = query.strip()
    if not trimmed:
        return SearchDocumentsResult(
            formatted="Error: empty search query.",
            sources=[],
            count=0,
        )

    with session_scope() as db:
        tool_svc = build_document_retrieval(db)
        result = await tool_svc.retrieve(
            query=trimmed,
            feature_id=feature_id,
            top_k=top_k,
        )

    sources = [
        DocumentSource(
            document_id=s.get("document_id"),
            file_id=s.get("file_id"),
            filename=s.get("filename"),
            file_type=s.get("file_type"),
            chunk_type=s.get("chunk_type"),
            chunk_index=s.get("chunk_index"),
            section_path=s.get("section_path"),
            page=s.get("page"),
            page_label=s.get("page_label"),
            table_id=s.get("table_id"),
            row_start=s.get("row_start"),
            row_end=s.get("row_end"),
        )
        for s in (result.sources or [])
    ]
    return SearchDocumentsResult(
        formatted=result.content,
        sources=sources,
        count=len(sources) if sources else (0 if "No matching" in result.content else 1),
    )