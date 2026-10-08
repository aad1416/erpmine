"""Route-level test for POST /features/{id}/chats/{id}/messages: proves
SendMessageResponse.attachments serialises whatever the chat service returns
(map decision D5 / ticket 04). In the style of tests/routes/test_unit_rca.py —
a minimal standalone app with stubbed dependencies, no real DB or LLM."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.models.Users import User
from app.dependencies.auth import get_current_user
from app.dependencies.chat import get_chat_agent_service, get_memory_service
from app.dependencies.features import get_feature_service
from app.routes.chats import router as chats_router


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


class _StubChatAgentService:
    def __init__(self, result):
        self.result = result

    async def process_message(self, **kwargs):
        return self.result


class _StubMemoryService:
    def get_chat_by_id(self, chat_id):
        return SimpleNamespace(id=chat_id, user_id="u-1", feature_id=1)


class _StubFeatureService:
    def get_feature_by_id(self, feature_id):
        return SimpleNamespace(id=feature_id)


def _user():
    return User(
        id="u-1",
        name="Jane Doe",
        username="jdoe",
        password="",
        user_type="user",
        store_id="store-9",
        accesses=[],
    )


@pytest.fixture
def client_and_service():
    result = {
        "response": "Here are the top vendors.",
        "user_message_id": 10,
        "assistant_message_id": 11,
        "sources": [],
        "persona_model": "gpt-4o",
        "attachments": [ATTACHMENT],
    }
    service = _StubChatAgentService(result)

    app = FastAPI()
    app.include_router(chats_router)
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_chat_agent_service] = lambda: service
    app.dependency_overrides[get_memory_service] = lambda: _StubMemoryService()
    app.dependency_overrides[get_feature_service] = lambda: _StubFeatureService()
    yield TestClient(app), service
    app.dependency_overrides.clear()


def test_send_message_response_serialises_attachments_from_service(client_and_service):
    client, _ = client_and_service

    response = client.post(
        "/features/1/chats/1/messages", json={"message": "top vendors?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["db_query_result"] is None
    assert body["attachments"] == [ATTACHMENT]


def test_send_message_response_defaults_attachments_to_empty_list(client_and_service):
    client, service = client_and_service
    service.result = {
        "response": "hi",
        "user_message_id": 10,
        "assistant_message_id": 11,
        "sources": [],
        "persona_model": "gpt-4o",
    }

    response = client.post(
        "/features/1/chats/1/messages", json={"message": "hello"}
    )

    assert response.status_code == 200
    assert response.json()["attachments"] == []
