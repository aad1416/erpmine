"""Route-level test for POST /admin/features/{id}/chats/{id}/admin-message: proves
AdminMessageResponse.attachments serialises whatever the admin chat service returns.
Mirrors tests/routes/test_chats_attachments.py's stub pattern - a minimal standalone
app with stubbed dependencies, no real DB or LLM."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.models.Users import User
from app.dependencies.auth import get_admin_user
from app.dependencies.chat import get_admin_chat_agent_service, get_memory_service
from app.dependencies.features import get_feature_service
from app.routes.admin_chat import router as admin_chat_router


ATTACHMENT = {
    "kind": "table",
    "title": "Top vendors",
    "columns": [{"key": "vendor", "label": "Vendor", "type": "string"}],
    "rows": [["Acme"]],
    "row_count": 1,
    "truncated": False,
    "provenance": {
        "sql": "SELECT vendor_name FROM vendors WHERE store_id = 'store-9'",
        "transforms": [],
        "row_count": 1,
        "generated_at": "2026-09-15T00:00:00Z",
    },
}


class _StubAdminChatAgentService:
    def __init__(self, result):
        self.result = result

    async def process_admin_message(self, **kwargs):
        return self.result


class _StubMemoryService:
    def get_chat_by_id(self, chat_id):
        return SimpleNamespace(id=chat_id, user_id="admin-1", feature_id=1)


class _StubFeatureService:
    def get_feature_by_id(self, feature_id):
        return SimpleNamespace(id=feature_id)


def _admin_user():
    return User(
        id="admin-1",
        name="Jane Admin",
        username="jadmin",
        password="",
        user_type="admin",
        store_id="store-9",
        accesses=[],
    )


@pytest.fixture
def client_and_service():
    result = {
        "response": "Here are the top vendors.",
        "intent": {"behavior_change": False, "rag_data": True},
        "persona_update": None,
        "sources": [],
        "user_message_id": 10,
        "assistant_message_id": 11,
        "attachments": [ATTACHMENT],
    }
    service = _StubAdminChatAgentService(result)

    app = FastAPI()
    app.include_router(admin_chat_router)
    app.dependency_overrides[get_admin_user] = _admin_user
    app.dependency_overrides[get_admin_chat_agent_service] = lambda: service
    app.dependency_overrides[get_memory_service] = lambda: _StubMemoryService()
    app.dependency_overrides[get_feature_service] = lambda: _StubFeatureService()
    yield TestClient(app), service
    app.dependency_overrides.clear()


def test_admin_message_response_serialises_attachments_from_service(client_and_service):
    client, _ = client_and_service

    response = client.post(
        "/admin/features/1/chats/1/admin-message", json={"message": "top vendors?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["db_query_result"] is None
    assert body["attachments"] == [ATTACHMENT]


def test_admin_message_response_defaults_attachments_to_empty_list(client_and_service):
    client, service = client_and_service
    service.result = {
        "response": "hi",
        "intent": {"behavior_change": False, "rag_data": False},
        "persona_update": None,
        "sources": [],
        "user_message_id": 10,
        "assistant_message_id": 11,
    }

    response = client.post(
        "/admin/features/1/chats/1/admin-message", json={"message": "hello"}
    )

    assert response.status_code == 200
    assert response.json()["attachments"] == []
