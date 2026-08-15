"""Integration tests over the HTTP API."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.main import app
from app.models import Base
from app.seed.seed import seed_all


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    with Session() as s:
        seed_all(s)
        s.commit()

    def override():
        db = Session()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    # Skip the app's own create_all/seed lifespan: this fixture owns the schema.
    os.environ["SEED_ON_START"] = "0"
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
    os.unlink(path)


def _answer_value(client, question, correct=True):
    if question["type"] == "spelling":
        return question["concept"] if correct else "zzzz"
    # The API deliberately does not reveal which option is right, so resolve it
    # the way a test may: via the debug-free route of trying the concept name.
    for opt in question["options"]:
        if correct and opt["value"] == question.get("concept"):
            return opt["value"]
    return question["options"][0]["value"]


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_child_lifecycle(client):
    created = client.post("/api/children", json={"name": "Jammu", "birth_year": 2020})
    assert created.status_code == 201
    child = created.json()

    assert client.get(f"/api/children/{child['id']}").json()["name"] == "Jammu"
    renamed = client.patch(f"/api/children/{child['id']}", json={"name": "Jammu B"})
    assert renamed.json()["name"] == "Jammu B"
    assert any(c["id"] == child["id"] for c in client.get("/api/children").json())


def test_full_session_flow(client):
    child = client.post("/api/children", json={"name": "Flow", "birth_year": 2019}).json()
    session = client.post(f"/api/children/{child['id']}/sessions", json={"subject": "english"}).json()
    assert session["session_type"] == "diagnostic"

    asked = []
    for _ in range(session["planned_questions"]):
        q = client.post(f"/api/sessions/{session['id']}/next-question").json()
        if q is None:
            break
        asked.append(q["question_id"])
        # The payload must never leak the answer to the client.
        assert "answer" not in q
        assert "difficulty" not in q
        res = client.post(f"/api/sessions/{session['id']}/answer", json={
            "attempt_id": q["attempt_id"],
            "answer": _answer_value(client, q),
            "response_time_ms": 2500,
        }).json()
        assert res["verdict"] in ("yes", "not_yet")

    assert len(asked) == len(set(asked)), "API repeated a question in one session"

    summary = client.post(f"/api/sessions/{session['id']}/complete").json()
    assert summary["questions_presented"] == len(asked)
    assert "vocabulary_band" in summary


def test_answering_twice_is_rejected(client):
    child = client.post("/api/children", json={"name": "Dup"}).json()
    session = client.post(f"/api/children/{child['id']}/sessions", json={"subject": "english"}).json()
    q = client.post(f"/api/sessions/{session['id']}/next-question").json()
    body = {"attempt_id": q["attempt_id"], "answer": "anything"}
    assert client.post(f"/api/sessions/{session['id']}/answer", json=body).status_code == 200
    assert client.post(f"/api/sessions/{session['id']}/answer", json=body).status_code == 409


def test_hints_are_progressive(client):
    child = client.post("/api/children", json={"name": "Hinty"}).json()
    session = client.post(f"/api/children/{child['id']}/sessions", json={"subject": "english"}).json()
    q = client.post(f"/api/sessions/{session['id']}/next-question").json()
    if not q["hint_available"]:
        pytest.skip("question has no hints")
    hint = client.post(
        f"/api/sessions/{session['id']}/hint",
        params={"attempt_id": q["attempt_id"], "level": 1},
    ).json()
    assert hint["level"] == 1 and hint["text"]


def test_child_progress_uses_bands_not_numbers(client):
    child = client.post("/api/children", json={"name": "Bands"}).json()
    progress = client.get(f"/api/children/{child['id']}/progress").json()
    assert progress["skills"], "no skills reported"
    for skill in progress["skills"]:
        assert skill["band"] in ("just started", "getting there", "good", "really good")


def test_parent_summary_exposes_numbers(client):
    child = client.post("/api/children", json={"name": "Parent view"}).json()
    session = client.post(f"/api/children/{child['id']}/sessions", json={"subject": "english"}).json()
    for _ in range(3):
        q = client.post(f"/api/sessions/{session['id']}/next-question").json()
        if q is None:
            break
        client.post(f"/api/sessions/{session['id']}/answer", json={
            "attempt_id": q["attempt_id"], "answer": _answer_value(client, q), "response_time_ms": 2000,
        })
    summary = client.get(f"/api/children/{child['id']}/parent-summary").json()
    assert "narrative" in summary and summary["skills"]
    assert summary["sessions_this_week"] >= 1


def test_debug_learner_state_explains_the_model(client):
    child = client.post("/api/children", json={"name": "Debug"}).json()
    session = client.post(f"/api/children/{child['id']}/sessions", json={"subject": "english"}).json()
    q = client.post(f"/api/sessions/{session['id']}/next-question").json()
    client.post(f"/api/sessions/{session['id']}/answer", json={
        "attempt_id": q["attempt_id"], "answer": _answer_value(client, q), "response_time_ms": 2000,
    })
    state = client.get(f"/api/children/{child['id']}/debug/learner-state").json()
    assert state["subject"] == "English"
    assert "strong" in state and "weak" in state and "due_for_review" in state


def test_notebook_returns_specimens(client):
    child = client.post("/api/children", json={"name": "Notebook"}).json()
    session = client.post(f"/api/children/{child['id']}/sessions", json={"subject": "english"}).json()
    for _ in range(4):
        q = client.post(f"/api/sessions/{session['id']}/next-question").json()
        if q is None:
            break
        client.post(f"/api/sessions/{session['id']}/answer", json={
            "attempt_id": q["attempt_id"], "answer": _answer_value(client, q), "response_time_ms": 2000,
        })
    notebook = client.get(f"/api/children/{child['id']}/notebook").json()
    assert notebook, "notebook is empty after a session"
    assert {s["status"] for s in notebook} <= {"mastered", "learning", "needs_review", "not_found"}
