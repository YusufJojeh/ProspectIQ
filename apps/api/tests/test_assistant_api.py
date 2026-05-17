import json

from app.modules.assistant.service import AssistantService
from tests.test_workspace_e2e import (
    _build_session_factory,
    _login,
    _override_client,
    _seed_workspace,
)


def test_assistant_chat_streams_grounded_response(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    def _fake_stream(self, db, *, workspace_id, messages, lead, session=None):
        lead_id = lead.public_id if lead is not None else "no-lead"
        yield f"## Assistant\n\nLead: {lead_id}\n\nQuestion: {messages[-1].parts[0].text}"

    monkeypatch.setattr(AssistantService, "stream_response", _fake_stream)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/assistant/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lead_id": seed.lead_public_id,
                "messages": [
                    {
                        "id": "msg-user-1",
                        "role": "user",
                        "parts": [{"type": "text", "text": "What stands out about this lead?"}],
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    assert 'data: {"type": "start"' in response.text
    assert '"type": "text-delta"' in response.text

    streamed_text = ""
    for line in response.text.splitlines():
        if not line.startswith("data: {"):
            continue
        payload = json.loads(line.removeprefix("data: "))
        if payload.get("type") == "text-delta":
            streamed_text += str(payload.get("delta", ""))

    assert seed.lead_public_id in streamed_text
    assert "What stands out about this lead?" in streamed_text
    assert "data: [DONE]" in response.text


def test_assistant_chat_rejects_unknown_lead() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/assistant/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lead_id": "lead_missing",
                "messages": [
                    {
                        "id": "msg-user-1",
                        "role": "user",
                        "parts": [{"type": "text", "text": "Summarize it"}],
                    }
                ],
            },
        )

    assert response.status_code == 404


def test_assistant_workspace_mode_chat_no_lead(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    def _fake_stream(self, db, *, workspace_id, messages, lead, session=None):
        yield "Workspace-level response without a specific lead."

    monkeypatch.setattr(AssistantService, "stream_response", _fake_stream)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/assistant/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "messages": [
                    {
                        "id": "msg-1",
                        "role": "user",
                        "parts": [{"type": "text", "text": "What leads need follow-up?"}],
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    assert "Workspace-level response" in response.text


def test_assistant_streaming_sse_format_completeness(monkeypatch) -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    def _fake_stream(self, db, *, workspace_id, messages, lead, session=None):
        yield "Token one. "
        yield "Token two."

    monkeypatch.setattr(AssistantService, "stream_response", _fake_stream)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = client.post(
            "/api/v1/assistant/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lead_id": seed.lead_public_id,
                "messages": [
                    {
                        "id": "m1",
                        "role": "user",
                        "parts": [{"type": "text", "text": "Summarize this lead"}],
                    }
                ],
            },
        )

    assert response.status_code == 200
    event_types = []
    for line in response.text.splitlines():
        if not line.startswith("data: {"):
            continue
        payload = json.loads(line.removeprefix("data: "))
        event_types.append(payload.get("type"))

    assert event_types == ["start", "text-start", "text-delta", "text-delta", "text-end", "finish"]
    assert "data: [DONE]" in response.text
