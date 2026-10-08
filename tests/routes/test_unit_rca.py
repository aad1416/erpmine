"""Route-level tests for POST /tools/unit-rca — auth wiring, body plumbing, and that
store_id is taken from the token rather than the request body. Analysis behavior is
covered by tests/services/test_unit_rca_service.py; these prove the HTTP layer only,
using a minimal standalone app rather than app.main (which pulls in scheduler startup
wiring irrelevant to this route)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.models.Users import User
from app.dependencies.auth import get_current_user
from app.dependencies.unit_rca import get_unit_rca_service
from app.routes.tools import tools_router
from app.schemas.unit_rca import UnitRCAResponse

REPORT = UnitRCAResponse(
    problem_definition="Compressor short-cycles.",
    cause_identification="Low refrigerant charge.",
    preventive_action="Leak-check the braze joint.",
)


class _StubService:
    def __init__(self, result=REPORT):
        self.result = result
        self.calls = []

    async def analyze(self, unit_id, ticket_id, store_id):
        self.calls.append(
            {"unit_id": unit_id, "ticket_id": ticket_id, "store_id": store_id}
        )
        return self.result


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
    app = FastAPI()
    app.include_router(tools_router)
    service = _StubService()
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_unit_rca_service] = lambda: service
    yield TestClient(app), service
    app.dependency_overrides.clear()


def test_returns_the_rca_report(client_and_service):
    client, _ = client_and_service
    response = client.post(
        "/tools/unit-rca", json={"unit_id": "unit-1", "ticket_id": "tk-1"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "problem_definition": "Compressor short-cycles.",
        "cause_identification": "Low refrigerant charge.",
        "preventive_action": "Leak-check the braze joint.",
        "saved": True,
        "save_error": None,
    }


def test_store_id_comes_from_the_token_not_the_body(client_and_service):
    client, service = client_and_service
    client.post(
        "/tools/unit-rca",
        json={"unit_id": "unit-1", "ticket_id": "tk-1", "store_id": "attacker-store"},
    )

    # store_id is never read from the body — a caller cannot reach another store's
    # documents by supplying one.
    assert service.calls == [
        {"unit_id": "unit-1", "ticket_id": "tk-1", "store_id": "store-9"}
    ]


def test_unsaved_rca_still_returns_200_with_the_failure_flagged(client_and_service):
    client, service = client_and_service
    service.result = UnitRCAResponse(
        **REPORT.model_dump(exclude={"saved", "save_error"}),
        saved=False,
        save_error="unexpected status 503",
    )

    response = client.post(
        "/tools/unit-rca", json={"unit_id": "unit-1", "ticket_id": "tk-1"}
    )

    assert response.status_code == 200
    assert response.json()["saved"] is False
    assert response.json()["save_error"] == "unexpected status 503"


def test_missing_ticket_id_is_422():
    app = FastAPI()
    app.include_router(tools_router)
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_unit_rca_service] = lambda: _StubService()

    response = TestClient(app).post("/tools/unit-rca", json={"unit_id": "unit-1"})
    assert response.status_code == 422
    app.dependency_overrides.clear()
