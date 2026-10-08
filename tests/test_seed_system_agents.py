"""Seeding seam for the system-agent Features (SQLite fixture): a store with no
Features gets all six slugs including `reports` with its own persona, and a second
run creates nothing new and changes no existing persona, for every slug."""

import os

from app.db.models.Feature import Feature
from app.db.models.Persona import Persona
from scripts.seed_system_agents import SYSTEM_AGENTS, seed_system_agents

SEED_USER_ID = "00000000-0000-0000-0000-000000000001"
SHARED_PROMPT = "you are a helpful and direct assistant"
SHARED_MODEL = "gpt-4o"
REPORTS_PROMPT = "You are the Reports agent for this store."
REPORTS_MODEL = "gpt-4.1"

PERSONAS = {
    slug: (SHARED_PROMPT, SHARED_MODEL) for slug in SYSTEM_AGENTS
} | {"reports": (REPORTS_PROMPT, REPORTS_MODEL)}


class _StubLyndomDBRepository:
    def __init__(self, db_url):
        self.db_url = db_url

    def get_stores(self):
        return [{"id": "store-1", "name": "Store One"}]


def _seed(monkeypatch, db_session):
    monkeypatch.setenv("LYNDOM_DB_URL", "postgresql://unused")
    monkeypatch.setattr(
        "scripts.seed_system_agents.LyndomDBRepository", _StubLyndomDBRepository
    )
    seed_system_agents(db_session, SEED_USER_ID, PERSONAS)


def test_seed_creates_six_features_with_reports_persona_diverging_only(
    monkeypatch, db_session
):
    _seed(monkeypatch, db_session)

    features = db_session.query(Feature).filter(Feature.store_id == "store-1").all()
    assert {f.entity_id for f in features} == set(SYSTEM_AGENTS)

    personas_by_slug = {
        f.entity_id: db_session.get(Persona, f.persona_id) for f in features
    }

    reports_persona = personas_by_slug["reports"]
    assert reports_persona.prompt_text == REPORTS_PROMPT
    assert reports_persona.model_name == REPORTS_MODEL

    for slug, persona in personas_by_slug.items():
        if slug == "reports":
            continue
        assert persona.prompt_text == SHARED_PROMPT
        assert persona.model_name == SHARED_MODEL


def test_seed_is_idempotent_and_never_updates_existing_personas(
    monkeypatch, db_session
):
    _seed(monkeypatch, db_session)

    features_before = (
        db_session.query(Feature).filter(Feature.store_id == "store-1").all()
    )
    persona_ids_before = {f.entity_id: f.persona_id for f in features_before}
    persona_texts_before = {
        f.entity_id: db_session.get(Persona, f.persona_id).prompt_text
        for f in features_before
    }

    changed_personas = {
        slug: (f"changed prompt for {slug}", "gpt-4o-changed")
        for slug in SYSTEM_AGENTS
    }
    _seed_with_personas(monkeypatch, db_session, changed_personas)

    features_after = (
        db_session.query(Feature).filter(Feature.store_id == "store-1").all()
    )
    assert len(features_after) == len(features_before)

    persona_ids_after = {f.entity_id: f.persona_id for f in features_after}
    assert persona_ids_after == persona_ids_before

    for slug, persona_id in persona_ids_after.items():
        persona = db_session.get(Persona, persona_id)
        assert persona.prompt_text == persona_texts_before[slug]


def _seed_with_personas(monkeypatch, db_session, personas):
    monkeypatch.setenv("LYNDOM_DB_URL", "postgresql://unused")
    monkeypatch.setattr(
        "scripts.seed_system_agents.LyndomDBRepository", _StubLyndomDBRepository
    )
    seed_system_agents(db_session, SEED_USER_ID, personas)
