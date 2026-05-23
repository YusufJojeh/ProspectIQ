from __future__ import annotations

import json
from types import SimpleNamespace

from sqlalchemy import select
from test_workspace_e2e import (
    _build_session_factory,
    _login,
    _override_client,
    _seed_workspace,
)

from app.core.security import hash_password
from app.modules.assistant.models import ChatMessage
from app.modules.assistant.service import AssistantService
from app.modules.leads.models import Lead
from app.modules.users.models import User, Workspace
from app.shared.enums.jobs import ProviderFetchStatus


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


def _stream_events(response):
    events = []
    for line in response.text.splitlines():
        if not line.startswith("data: {"):
            continue
        events.append(json.loads(line.removeprefix("data: ")))
    return events


def _event_data(response, event_type):
    return [event for event in _stream_events(response) if event.get("type") == event_type]


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
    assert items[0]["lead_id"] == seed.lead_public_id


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

        _chat(
            client,
            token,
            lead_id=seed.lead_public_id,
            session_id=session_id,
            text="Follow-up question",
        )

        list_resp2 = client.get(
            "/api/v1/assistant/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert len(list_resp2.json()["items"]) == 1


def test_chat_follow_up_uses_persisted_session_context(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    seen_transcripts: list[list[str]] = []

    def _capture_tokens(self, db, *, workspace_id, messages, lead):
        seen_transcripts.append(
            [
                "\n".join(part.text or "" for part in message.parts if part.type == "text")
                for message in messages
            ]
        )
        yield "Assistant reply."

    monkeypatch.setattr(AssistantService, "_generate_tokens", _capture_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text="First question")

        list_resp = client.get(
            "/api/v1/assistant/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        session_id = list_resp.json()["items"][0]["public_id"]

        _chat(
            client,
            token,
            lead_id=seed.lead_public_id,
            session_id=session_id,
            text="Follow-up question",
        )

    assert seen_transcripts[-1] == [
        "First question",
        "Assistant reply.",
        "Follow-up question",
    ]


def test_chat_session_rejects_mismatched_lead_context(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with session_factory() as db:
        original = db.query(Lead).filter(Lead.public_id == seed.lead_public_id).one()
        other = Lead(
            workspace_id=original.workspace_id,
            company_name="Other Dental",
            city="Istanbul",
            data_completeness=0.4,
            data_confidence=0.4,
            has_website=False,
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        other_public_id = other.public_id

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text="First question")
        list_resp = client.get(
            "/api/v1/assistant/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        session_id = list_resp.json()["items"][0]["public_id"]
        response = _chat(
            client,
            token,
            lead_id=other_public_id,
            session_id=session_id,
            text="Use a different lead",
        )

    assert response.status_code == 404


def test_chat_session_blocks_cross_workspace_access(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    service = AssistantService()
    with session_factory() as db:
        other_workspace = Workspace(public_id="ws_other", name="Other Workspace")
        db.add(other_workspace)
        db.commit()
        db.refresh(other_workspace)
        other_user = User(
            workspace_id=other_workspace.id,
            email="other-admin@example.com",
            full_name="Other Admin",
            hashed_password=hash_password("OtherPass123!"),
            role="admin",
        )
        db.add(other_user)
        db.commit()
        session = service.get_or_create_session(
            db,
            workspace_id=other_workspace.id,
            session_public_id=None,
            lead=None,
            first_user_message="Private other workspace thread",
        )
        other_session_public_id = session.public_id

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.get(
            f"/api/v1/assistant/sessions/{other_session_public_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404


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


def test_chat_context_uses_recent_window_for_long_sessions() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    service = AssistantService()

    with session_factory() as db:
        lead = db.query(Lead).filter(Lead.public_id == seed.lead_public_id).one()
        session = service.get_or_create_session(
            db,
            workspace_id=lead.workspace_id,
            session_public_id=None,
            lead=lead,
            first_user_message="Long thread",
        )
        for index in range(30):
            service.session_repository.add_message(
                db,
                session_id=session.id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"Message {index}",
            )

        messages = service._messages_from_session_history(db, session=session)

    rendered = [
        "\n".join(part.text or "" for part in message.parts if part.type == "text")
        for message in messages
    ]
    assert len(rendered) == 24
    assert rendered[0] == "Message 6"
    assert rendered[-1] == "Message 29"


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
        _chat(client, token, lead_id=seed.lead_public_id, session_id=session_id, text="Second")

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


def test_chat_search_required_prompt_triggers_serpapi_and_attaches_sources(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    calls: list[str] = []

    class FakeSerpApiService:
        def web_search(self, db, *, workspace_id, search_job_id, query):
            calls.append(query)
            return SimpleNamespace(status=ProviderFetchStatus.OK.value), {
                "organic_results": [
                    {
                        "title": "Acme Dental Official",
                        "link": "https://acmedental.example",
                        "snippet": "Official website for Acme Dental.",
                    },
                    {
                        "title": "Acme Dental Official duplicate",
                        "link": "https://acmedental.example",
                        "snippet": "Duplicate should be ignored.",
                    },
                    {
                        "title": "Local competitor",
                        "link": "https://competitor.example",
                        "snippet": "Competitor SEO result.",
                    },
                ]
            }

    def _search_aware_tokens(self, db, *, workspace_id, messages, lead):
        search_context = self._get_active_search_context()
        assert search_context.used_search is True
        yield "Used external evidence and stored CRM data."

    monkeypatch.setattr("app.modules.assistant.service.SerpApiService", FakeSerpApiService)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _search_aware_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = _chat(
            client,
            token,
            lead_id=seed.lead_public_id,
            text="Search the latest competitors and SEO presence for this website",
        )

    assert response.status_code == 200
    assert calls
    search_events = _event_data(response, "data-search")
    assert search_events[0]["data"]["used_search"] is True
    assert search_events[0]["data"]["search_status"] == "used"
    assert len(search_events[0]["data"]["sources"]) == 2
    assert len(_event_data(response, "source-url")) == 2


def test_chat_crm_only_prompt_does_not_trigger_search(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    class FailingSerpApiService:
        def web_search(self, db, *, workspace_id, search_job_id, query):
            raise AssertionError("CRM-only assistant prompt should not run external search")

    monkeypatch.setattr("app.modules.assistant.service.SerpApiService", FailingSerpApiService)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = _chat(
            client,
            token,
            lead_id=seed.lead_public_id,
            text="Explain the main reasons behind this lead's current stored score.",
        )

    assert response.status_code == 200
    search_events = _event_data(response, "data-search")
    assert search_events[0]["data"] == {
        "used_search": False,
        "search_status": "not_needed",
        "sources": [],
    }
    assert _event_data(response, "source-url") == []


def test_chat_arabic_search_intent_uses_search_and_keeps_arabic_answer(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    class FakeSerpApiService:
        def web_search(self, db, *, workspace_id, search_job_id, query):
            return SimpleNamespace(status=ProviderFetchStatus.OK.value), {
                "organic_results": [
                    {
                        "title": "Acme Dental SEO",
                        "link": "https://seo.example/acme",
                        "snippet": "English search evidence is allowed.",
                    }
                ]
            }

    def _arabic_tokens(self, db, *, workspace_id, messages, lead):
        yield "تم استخدام أدلة خارجية مع بيانات النظام المخزنة."

    monkeypatch.setattr("app.modules.assistant.service.SerpApiService", FakeSerpApiService)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _arabic_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = _chat(
            client,
            token,
            lead_id=seed.lead_public_id,
            text="ابحث عن أحدث المنافسين و SEO لهذا العميل",
        )

    assert response.status_code == 200
    assert _event_data(response, "data-search")[0]["data"]["search_status"] == "used"
    assert "تم استخدام أدلة خارجية" in response.text


def test_chat_search_failure_returns_graceful_response_without_sources(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    class FailingSerpApiService:
        def web_search(self, db, *, workspace_id, search_job_id, query):
            raise RuntimeError("provider timeout")

    def _fallback_tokens(self, db, *, workspace_id, messages, lead):
        search_context = self._get_active_search_context()
        assert search_context.search_status == "failed"
        yield "External search was unavailable, so I used stored CRM context only."

    monkeypatch.setattr("app.modules.assistant.service.SerpApiService", FailingSerpApiService)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fallback_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = _chat(
            client,
            token,
            lead_id=seed.lead_public_id,
            text="search latest market position",
        )

    assert response.status_code == 200
    assert _event_data(response, "data-search")[0]["data"] == {
        "used_search": False,
        "search_status": "failed",
        "sources": [],
    }
    assert _event_data(response, "source-url") == []


def test_chat_empty_search_results_do_not_hallucinate_sources(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    class EmptySerpApiService:
        def web_search(self, db, *, workspace_id, search_job_id, query):
            return SimpleNamespace(status=ProviderFetchStatus.OK.value), {"organic_results": []}

    monkeypatch.setattr("app.modules.assistant.service.SerpApiService", EmptySerpApiService)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = _chat(
            client,
            token,
            lead_id=seed.lead_public_id,
            text="search current website visibility",
        )

    assert response.status_code == 200
    assert _event_data(response, "data-search")[0]["data"] == {
        "used_search": True,
        "search_status": "used",
        "sources": [],
    }
    assert _event_data(response, "source-url") == []


def test_list_sessions_filters_by_lead_public_id(monkeypatch) -> None:
    """Part 9: GET /api/v1/assistant/sessions?lead_id=<lead> returns only that lead's sessions."""
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    # Create a second lead in the same workspace
    with session_factory() as db:
        first_lead = db.query(Lead).filter(Lead.public_id == seed.lead_public_id).one()
        other_lead = Lead(
            workspace_id=first_lead.workspace_id,
            company_name="Other Co",
            city="Istanbul",
            data_completeness=0.5,
            data_confidence=0.5,
            has_website=False,
        )
        db.add(other_lead)
        db.commit()
        db.refresh(other_lead)
        other_lead_public_id = other_lead.public_id

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text="First-lead question")
        _chat(client, token, lead_id=other_lead_public_id, text="Other-lead question")

        # No filter → both sessions visible
        all_resp = client.get(
            "/api/v1/assistant/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert len(all_resp.json()["items"]) == 2

        # Filter by first lead → only that session
        filtered_resp = client.get(
            f"/api/v1/assistant/sessions?lead_id={seed.lead_public_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = filtered_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["lead_id"] == seed.lead_public_id


def test_list_sessions_includes_message_count_and_preview(monkeypatch) -> None:
    """Part 9: session list items expose message_count + last_message_preview."""
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text="What is the score driver?")

        list_resp = client.get(
            "/api/v1/assistant/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )

    items = list_resp.json()["items"]
    assert len(items) == 1
    item = items[0]
    # Each chat round persists 2 messages (user + assistant)
    assert item["message_count"] == 2
    assert item["last_message_preview"] is not None
    # Last message is the assistant reply
    assert "Assistant reply" in item["last_message_preview"]


def test_list_sessions_with_unknown_lead_id_returns_empty(monkeypatch) -> None:
    """Filtering by an unknown lead public_id returns an empty list, not 404."""
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _chat(client, token, lead_id=seed.lead_public_id, text="Indexed under real lead")
        resp = client.get(
            "/api/v1/assistant/sessions?lead_id=ld_doesnotexist",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_chat_search_metadata_does_not_expose_api_keys_or_raw_payload(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    secret = "serpapi-secret-value"
    monkeypatch.setenv("SERPAPI_API_KEY", secret)

    class FakeSerpApiService:
        def web_search(self, db, *, workspace_id, search_job_id, query):
            return SimpleNamespace(status=ProviderFetchStatus.OK.value), {
                "search_metadata": {"id": "raw-provider-id", "secret": secret},
                "organic_results": [
                    {
                        "title": "Public source",
                        "link": "https://public.example/source",
                        "snippet": "Public snippet.",
                    }
                ],
            }

    monkeypatch.setattr("app.modules.assistant.service.SerpApiService", FakeSerpApiService)
    monkeypatch.setattr(AssistantService, "_generate_tokens", _fake_tokens)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = _chat(
            client,
            token,
            lead_id=seed.lead_public_id,
            text="search latest SEO sources",
        )

    assert response.status_code == 200
    assert secret not in response.text
    assert "raw-provider-id" not in response.text
    assert "search_metadata" not in response.text
