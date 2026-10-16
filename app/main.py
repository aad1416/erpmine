import logging
from contextlib import AsyncExitStack, asynccontextmanager

import agents
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.setting import settings
from app.services.seed_scheduler import start_seed_scheduler, stop_seed_scheduler
from app.services.log_sync_retry_job import (
    start_log_sync_retry_scheduler,
    stop_log_sync_retry_scheduler,
)
from app.support.init import start_support, stop_support

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)-8s [%(process)d] %(name)s: %(message)s",
    force=True,  # uvicorn installs its own handlers first; take the root logger back
)

logger = logging.getLogger(__name__)


def _validate_ticket_api_settings() -> None:
    """The ticket API backs both the support pipeline and the /tools field service
    ticket summary endpoint, and the latter is not gated on SUPPORT_ENABLED — so these
    are checked at every boot, not only when support is on."""
    missing = [
        field
        for field in ("TICKET_API_BASE_URL", "TICKET_API_BEARER_TOKEN")
        if not getattr(settings, field)
    ]
    if missing:
        raise RuntimeError(
            "Ticket API settings are required (used by the support pipeline and "
            f"/tools/field-service-ticket-summary) but are not configured: {', '.join(missing)}"
        )


from app.routes import (
    files_router,
    documents_router,
    personas_router,
    chats_router,
    admin_chat_router,
    voice_router,
    features_router,
    classrooms_router,
    tools_router,
    support_monitoring_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.OPENAI_API_KEY:
        agents.set_default_openai_key(
            settings.OPENAI_API_KEY,
            use_for_tracing=settings.CHAT_AGENT_SDK_TRACING,
        )
    if not settings.CHAT_AGENT_SDK_TRACING:
        agents.set_tracing_disabled(True)

    if settings.SEED_SCHEDULER_ENABLED and settings.lyndom_db_url:
        start_seed_scheduler()
    elif settings.SEED_SCHEDULER_ENABLED:
        logger.warning("Seed scheduler disabled: lyndom_db_url is not configured")

    _validate_ticket_api_settings()

    if settings.SUPPORT_ENABLED:
        await start_support(app)
        start_log_sync_retry_scheduler()

    async with AsyncExitStack() as stack:
        if getattr(settings, "MCP_ENABLED", False):
            from app.mcp.mount import mcp_session_lifespan

            await stack.enter_async_context(mcp_session_lifespan())
            logger.info("MCP enabled and session manager entered")
        else:
            logger.info("MCP disabled (MCP_ENABLED=false)")

        yield

        stop_seed_scheduler()

        if settings.SUPPORT_ENABLED:
            await stop_support()
            stop_log_sync_retry_scheduler()


app = FastAPI(
    title="UT AI Agent API",
    description="AI Agent with RAG, multi-LLM support, and feature-based isolation",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS to allow all domains
# TODO: we have to restrict the origins to the allowed domains later on real production environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files_router)
app.include_router(documents_router)
app.include_router(personas_router)
app.include_router(chats_router)
app.include_router(admin_chat_router)
app.include_router(voice_router)
app.include_router(features_router)
app.include_router(classrooms_router)
app.include_router(tools_router)
app.include_router(support_monitoring_router)


if getattr(settings, "MCP_ENABLED", False):
    from app.mcp.mount import build_mcp_asgi_app

    app.mount("/mcp", build_mcp_asgi_app())
    logger.info("MCP mounted at /mcp (Streamable HTTP endpoint under that prefix)")