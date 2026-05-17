from __future__ import annotations

from sqlalchemy import select
from test_workspace_e2e import (
    _build_session_factory,
    _login,
    _override_client,
    _seed_workspace,
)

from app.modules.assistant.models import ChatMessage
from app.modules.assistant.service import AssistantService


def _fake_tokens(self, db, *, workspace_id, messages, lead):
    yield "Assistant reply."


def _chat(client, token, *, lead_id=None, session_id=None, text="Hello"):
    body = {
        "messages": [{"id": "m1", "role": "user", "parts": [{"type": "text", "text": text}]}]
    }
    if lead_id:
        body["lead_id"] = lead_id
    if session_id:
        body["session_id"] = session_id
    return client.post(
        "/api/v1/assistant/chat",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )


def test_chat_creates_new_session_when_no_session_id_given(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = _chat(client, token, lead_id=seed.lead_public_id, text="Tell me about this lead")
        assert response.status_code == 200

        list_response = client.get(
            "/api/v1/assistant/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Tell me about this lead"


def test_chat_reuses_session_when_session_id_provided(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text="First question")

        list_resp = client.get(
            "/api/v1/assistant/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        session_id = list_resp.json()["items"][0]["public_id"]

        _chat(client, token, session_id=session_id, text="Follow-up question")

        list_resp2 = client.get(
            "/api/v1/assistant/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert len(list_resp2.json()["items"]) == 1


def test_chat_returns_404_for_unknown_session_id(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = _chat(client, token, session_id="cs_nonexistent", text="Hello")

    assert response.status_code == 404


def test_chat_persists_user_and_assistant_messages(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = _chat(client, token, lead_id=seed.lead_public_id, text="What are the opportunities?")
        assert response.status_code == 200

    with session_factory() as db:
        msgs = list(db.scalars(select(ChatMessage).order_by(ChatMessage.created_at)))

    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[0].content == "What are the opportunities?"
    assert msgs[1].role == "assistant"
    assert msgs[1].content == "Assistant reply."


def test_chat_messages_ordered_by_creation_time(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text="First")

        list_resp = client.get(
            "/api/v1/assistant/sessions", headers={"Authorization": f"Bearer {token}"}
        )
        session_id = list_resp.json()["items"][0]["public_id"]
        _chat(client, token, session_id=session_id, text="Second")

        detail_resp = client.get(
            f"/api/v1/assistant/sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    messages = detail_resp.json()["messages"]
    user_msgs = [m for m in messages if m["role"] == "user"]
    assert user_msgs[0]["content"] == "First"
    assert user_msgs[1]["content"] == "Second"


def test_list_sessions_returns_sessions_newest_first(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text="Alpha question")
        _chat(client, token, lead_id=seed.lead_public_id, text="Beta question")

        list_resp = client.get(
            "/api/v1/assistant/sessions", headers={"Authorization": f"Bearer {token}"}
        )

    items = list_resp.json()["items"]
    assert len(items) == 2
    assert items[0]["title"] == "Beta question"
    assert items[1]["title"] == "Alpha question"


def test_get_session_detail_includes_all_messages(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text="Detail test")

        list_resp = client.get(
            "/api/v1/assistant/sessions", headers={"Authorization": f"Bearer {token}"}
        )
        session_id = list_resp.json()["items"][0]["public_id"]

        detail_resp = client.get(
            f"/api/v1/assistant/sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["public_id"] == session_id
    assert len(data["messages"]) == 2
    roles = [m["role"] for m in data["messages"]]
    assert "user" in roles
    assert "assistant" in roles


def test_delete_session_returns_204_and_removes_it(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text="Delete me")

        list_resp = client.get(
            "/api/v1/assistant/sessions", headers={"Authorization": f"Bearer {token}"}
        )
        session_id = list_resp.json()["items"][0]["public_id"]

        delete_resp = client.delete(
            f"/api/v1/assistant/sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert delete_resp.status_code == 204

        list_after = client.get(
            "/api/v1/assistant/sessions", headers={"Authorization": f"Bearer {token}"}
        )

    assert list_after.json()["items"] == []


def test_delete_nonexistent_session_returns_404() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.delete(
            "/api/v1/assistant/sessions/cs_doesnotexist",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404


def test_session_title_truncated_to_80_chars(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    long_text = "A" * 120

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text=long_text)

        list_resp = client.get(
            "/api/v1/assistant/sessions", headers={"Authorization": f"Bearer {token}"}
        )

    title = list_resp.json()["items"][0]["title"]
    assert len(title) <= 80
    assert title == "A" * 80
