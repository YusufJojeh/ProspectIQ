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

    monkeypatch.setattr(
        AssistantService,
        "generate_response",
        lambda self, db, workspace_id, messages, lead_public_id: (
            f"## Assistant\n\nLead: {lead_public_id}\n\nQuestion: {messages[-1].parts[0].text}"
        ),
    )

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
