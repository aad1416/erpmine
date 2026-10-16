"""MCP API-key auth: maps X-API-Key / Bearer tokens to AccessToken + feature ACL."""
import json
import logging
from dataclasses import dataclass
from typing import Any

from mcp.server.auth.provider import AccessToken, TokenVerifier

from app.config.setting import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class McpClientConfig:
    name: str
    feature_ids: frozenset[int]


def load_mcp_clients(raw: str | None = None) -> dict[str, McpClientConfig]:
    raw = raw if raw is not None else settings.MCP_API_KEYS
    try:
        data: dict[str, Any] = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("MCP_API_KEYS must be valid JSON") from exc

    clients: dict[str, McpClientConfig] = {}
    for key, cfg in data.items():
        if not key or not isinstance(cfg, dict):
            continue
        name = str(cfg.get("name") or key)
        ids = cfg.get("feature_ids") or []
        clients[str(key)] = McpClientConfig(
            name=name,
            feature_ids=frozenset(int(i) for i in ids),
        )
    return clients


class ApiKeyTokenVerifier(TokenVerifier):

    def __init__(self, clients: dict[str, McpClientConfig] | None = None) -> None:
        self._clients = clients if clients is not None else load_mcp_clients()

    async def verify_token(self, token: str) -> AccessToken | None:
        client = self._clients.get(token)
        if client is None:
            return None
        resource = settings.MCP_RESOURCE_URL or "http://127.0.0.1:8000/mcp"
        return AccessToken(
            token=token,
            client_id=client.name,
            scopes=["rag:read"],
            resource=resource,
        )


_CLIENTS: dict[str, McpClientConfig] = {}


def init_auth() -> tuple[ApiKeyTokenVerifier, dict[str, McpClientConfig]]:
    global _CLIENTS
    _CLIENTS = load_mcp_clients()
    return ApiKeyTokenVerifier(_CLIENTS), _CLIENTS


def allowed_feature_ids(token: str | None) -> frozenset[int]:
    if not token:
        return frozenset()
    client = _CLIENTS.get(token)
    return client.feature_ids if client else frozenset()


def client_name(token: str | None) -> str | None:
    if not token:
        return None
    client = _CLIENTS.get(token)
    return client.name if client else None