from .files import files_router
from .documents import documents_router
from .personas import router as personas_router
from .chats import router as chats_router
from .admin_chat import router as admin_chat_router
from .voice import router as voice_router
from .features import router as features_router
from .classrooms import classrooms_router
from .tools import tools_router
from .support_monitoring import router as support_monitoring_router

__all__ = [
    "files_router",
    "documents_router",
    "personas_router",
    "chats_router",
    "admin_chat_router",
    "voice_router",
    "features_router",
    "classrooms_router",
    "tools_router",
    "support_monitoring_router",
]
