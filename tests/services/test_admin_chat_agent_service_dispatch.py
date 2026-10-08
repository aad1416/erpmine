"""Dispatch test: sending an admin message to a `reports` Feature
(Feature.entity_id == "reports") runs ReportsAgentRunner; any other Feature keeps
running the existing AdminChatAgentRunner unchanged. Mirrors
tests/services/test_chat_agent_service_dispatch.py's stub pattern."""

from types import SimpleNamespace

import pytest

from app.services.admin_chat_agent_service import AdminChatAgentService


class _StubMemoryService:
    def get_chat_history(self, chat_id):
        return []

    def save_message(self, chat_id, message):
        message.id = 99
        return message


class _StubPersonaService:
    def __init__(self, persona):
        self._persona = persona

    def get_persona_for_feature(self, feature_id):
        return self._persona


class _StubQuery:
    def __init__(self, feature):
        self._feature = feature

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._feature


class _StubSession:
    def __init__(self, feature):
        self._feature = feature

    def query(self, model):
        return _StubQuery(self._feature)

    def close(self):
        pass


class _StubReportsRunner:
    def __init__(self):
        self.calls = []

    async def run(self, *, persona_prompt_text, model_name, run_input, ctx):
        self.calls.append(
            {
                "persona_prompt_text": persona_prompt_text,
                "model_name": model_name,
                "run_input": run_input,
                "ctx": ctx,
            }
        )
        return "reports answer", [], []


class _StubAdminChatRunner:
    def __init__(self):
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return "admin answer", [], [], None, False


class _StubLegacyAdminChatService:
    def __init__(self):
        self.calls = []

    async def process_admin_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"response": "legacy answer"}


def _service(feature_entity_id, reports_runner, admin_chat_runner, persona_model="gpt-4o"):
    persona = SimpleNamespace(prompt_text="Be helpful.", model_name=persona_model)
    feature = SimpleNamespace(id=1, store_id="store-9", entity_id=feature_entity_id)
    legacy = _StubLegacyAdminChatService()
    return (
        AdminChatAgentService(
            memory_service=_StubMemoryService(),
            persona_service=_StubPersonaService(persona),
            legacy_admin_chat_service=legacy,
            admin_chat_agent_runner=admin_chat_runner,
            document_retrieval_tool_service=None,
            database_query_tool_service=None,
            db_session_factory=lambda: _StubSession(feature),
            reports_agent_runner=reports_runner,
            files_service=None,
        ),
        legacy,
    )


@pytest.mark.asyncio
async def test_reports_entity_id_dispatches_to_reports_agent_runner():
    reports_runner = _StubReportsRunner()
    admin_chat_runner = _StubAdminChatRunner()
    service, _legacy = _service("reports", reports_runner, admin_chat_runner)

    result = await service.process_admin_message(
        chat_id=1,
        user_message="which customers bought in 2026?",
        feature_id=1,
        admin_user_id="admin-1",
        user_accesses=["VENDOR_READ_STORE_PANEL"],
        user_store_id="store-9",
    )

    assert result["response"] == "reports answer"
    assert result["attachments"] == []
    assert result["persona_update"] is None
    assert result["intent"] == {"behavior_change": False, "rag_data": True}
    assert len(reports_runner.calls) == 1
    assert reports_runner.calls[0]["ctx"].user_id == "admin-1"
    assert reports_runner.calls[0]["ctx"].store_id == "store-9"
    assert reports_runner.calls[0]["ctx"].user_accesses == ["VENDOR_READ_STORE_PANEL"]
    assert admin_chat_runner.calls == []


@pytest.mark.asyncio
async def test_non_reports_feature_still_uses_admin_chat_agent_runner():
    reports_runner = _StubReportsRunner()
    admin_chat_runner = _StubAdminChatRunner()
    service, _legacy = _service(None, reports_runner, admin_chat_runner)

    result = await service.process_admin_message(
        chat_id=1,
        user_message="update the persona",
        feature_id=1,
        admin_user_id="admin-1",
        user_accesses=[],
        user_store_id="store-9",
    )

    assert result["response"] == "admin answer"
    assert "attachments" not in result
    assert result["persona_update"] is None
    assert result["intent"] == {"behavior_change": False, "rag_data": False}
    assert result["sources"] == []
    assert len(admin_chat_runner.calls) == 1
    assert reports_runner.calls == []


@pytest.mark.asyncio
async def test_legacy_model_reports_feature_uses_legacy_fallback():
    reports_runner = _StubReportsRunner()
    admin_chat_runner = _StubAdminChatRunner()
    service, legacy = _service(
        "reports", reports_runner, admin_chat_runner, persona_model="claude-3"
    )

    result = await service.process_admin_message(
        chat_id=1,
        user_message="hello",
        feature_id=1,
        admin_user_id="admin-1",
        user_accesses=[],
        user_store_id="store-9",
    )

    assert result["response"] == "legacy answer"
    assert len(legacy.calls) == 1
    assert reports_runner.calls == []
    assert admin_chat_runner.calls == []
