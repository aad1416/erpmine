"""Dispatch test (ticket 07): sending a message to a `reports` Feature
(Feature.entity_id == "reports") runs ReportsAgentRunner; any other Feature keeps
running the existing ChatAgentRunner unchanged."""

from types import SimpleNamespace

import pytest

from app.services.chat_agent_service import ChatAgentService


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


class _StubChatRunner:
    def __init__(self):
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return "chat answer", [], []


def _service(feature_entity_id, reports_runner, chat_runner):
    persona = SimpleNamespace(prompt_text="Be helpful.", model_name="gpt-4o")
    feature = SimpleNamespace(id=1, store_id="store-9", entity_id=feature_entity_id)
    return ChatAgentService(
        memory_service=_StubMemoryService(),
        persona_service=_StubPersonaService(persona),
        legacy_chat_service=None,
        chat_agent_runner=chat_runner,
        document_retrieval_tool_service=None,
        database_query_tool_service=None,
        db_session_factory=lambda: _StubSession(feature),
        reports_agent_runner=reports_runner,
        files_service=None,
    )


@pytest.mark.asyncio
async def test_reports_entity_id_dispatches_to_reports_agent_runner():
    reports_runner = _StubReportsRunner()
    chat_runner = _StubChatRunner()
    service = _service("reports", reports_runner, chat_runner)

    result = await service.process_message(
        chat_id=1,
        user_message="which customers bought in 2026?",
        feature_id=1,
        user_id="u-1",
        user_accesses=["VENDOR_READ_STORE_PANEL"],
        user_store_id="store-9",
    )

    assert result["response"] == "reports answer"
    assert result["attachments"] == []
    assert result["db_query_result"] == []
    assert len(reports_runner.calls) == 1
    assert reports_runner.calls[0]["ctx"].store_id == "store-9"
    assert reports_runner.calls[0]["ctx"].user_accesses == ["VENDOR_READ_STORE_PANEL"]
    assert chat_runner.calls == []


@pytest.mark.asyncio
async def test_non_reports_feature_still_uses_chat_agent_runner():
    reports_runner = _StubReportsRunner()
    chat_runner = _StubChatRunner()
    service = _service(None, reports_runner, chat_runner)

    result = await service.process_message(
        chat_id=1,
        user_message="hello",
        feature_id=1,
        user_id="u-1",
        use_rag=False,
        use_db=False,
        user_accesses=[],
        user_store_id="store-9",
    )

    assert result["response"] == "chat answer"
    assert "attachments" not in result
    assert len(chat_runner.calls) == 1
    assert reports_runner.calls == []
