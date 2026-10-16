"""MCP ASGI mount + host lifespan entrypoint"""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from starlette.applications import Starlette

from app.config.setting import settings

logger = logging.getLogger(__name__)

_mcp_asgi_app: Starlette | None = None


def build_mcp_asgi_app() -> Starlette:
    """
    Return the Streamable HTTP Starlette app (endpoint path /mcp inside the mount).
    """
    global _mcp_asgi_app
    if _mcp_asgi_app is not None:
        return _mcp_asgi_app

    from app.mcp.server import mcp

    _mcp_asgi_app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=getattr(settings, "MCP_STATELESS_HTTP", True),
    )
    logger.info(
        "MCP Streamable HTTP app built (stateless_http=%s)",
        getattr(settings, "MCP_STATELESS_HTTP", True),
    )
    return _mcp_asgi_app


@asynccontextmanager
async def mcp_session_lifespan() -> AsyncIterator[None]:
    """
    Enter mcp.session_manager.run() for the host process lifetime.

    call only when settings.MCP_ENABLED is True.
    must run after build_mcp_asgi_app() so session_manager exists.
    """
    from app.mcp.server import mcp

    build_mcp_asgi_app()

    logger.info("MCP session manager starting")
    async with mcp.session_manager.run():
        logger.info("MCP session manager running")
        try:
            yield
        finally:
            logger.info("MCP session manager stopping")