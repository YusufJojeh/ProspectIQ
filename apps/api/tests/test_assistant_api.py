import json

from test_workspace_e2e import (
    _build_session_factory,
    _login,
    _override_client,
    _seed_workspace,
)

from app.modules.assistant.schemas import AssistantMessageInput, AssistantMessagePartInput
from app.modules.assistant.service import (
    AssistantSearchContext,
    AssistantService,
    StreamingRuntimeCandidate,
)
from app.modules.users.models import Workspace


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


def test_workspace_response_recommends_best_stored_lead() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    service = AssistantService()

    with session_factory() as db:
        workspace = db.query(Workspace).filter(Workspace.public_id == seed.workspace_public_id).one()
        response = service._build_workspace_response(
            db,
            workspace_id=workspace.id,
            messages=[
                AssistantMessageInput(
                    id="msg-workspace-best",
                    role="user",
                    parts=[
                        AssistantMessagePartInput(
                            type="text",
                            text="Who is the best lead today?",
                        )
                    ],
                )
            ],
            search_context=AssistantSearchContext(
                used_search=False,
                search_status="not_needed",
                sources=[],
            ),
        )

    assert "Acme Dental" in response
    assert "82/100" in response
    assert "Top candidates" in response
    assert "pass a `lead_id`" not in response


def test_workspace_response_uses_arabic_for_arabic_request() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    service = AssistantService()

    with session_factory() as db:
        workspace = db.query(Workspace).filter(Workspace.public_id == seed.workspace_public_id).one()
        response = service._build_workspace_response(
            db,
            workspace_id=workspace.id,
            messages=[
                AssistantMessageInput(
                    id="msg-workspace-best-ar",
                    role="user",
                    parts=[
                        AssistantMessagePartInput(
                            type="text",
                            text="من أفضل عميل اليوم؟",
                        )
                    ],
                )
            ],
            search_context=AssistantSearchContext(
                used_search=False,
                search_status="not_needed",
                sources=[],
            ),
        )

    assert "مساعد مساحة العمل" in response
    assert "Acme Dental" in response
    assert "أفضل المرشحين" in response


def test_workspace_question_routes_through_llm_not_canned(monkeypatch) -> None:
    """A workspace question must be answered by the LLM grounded on real leads,
    not by the deterministic canned builders, whenever a provider is configured."""
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    service = AssistantService()

    monkeypatch.setattr(
        AssistantService,
        "_resolve_runtime_candidates",
        lambda self, settings: [
            StreamingRuntimeCandidate(provider_name="openai", stream_fn="openai")
        ],
    )

    captured: dict[str, object] = {}

    def _fake_openai(self, *, settings, llm_messages):
        captured["messages"] = llm_messages
        yield "LLM_SENTINEL: grounded comparison and recommendation"

    monkeypatch.setattr(AssistantService, "_stream_with_openai", _fake_openai)

    with session_factory() as db:
        workspace = (
            db.query(Workspace).filter(Workspace.public_id == seed.workspace_public_id).one()
        )
        tokens = list(
            service._generate_tokens(
                db,
                workspace_id=workspace.id,
                messages=[
                    AssistantMessageInput(
                        id="msg-cmp",
                        role="user",
                        parts=[
                            AssistantMessagePartInput(
                                type="text",
                                text="Compare the top 3 leads and explain the tradeoffs.",
                            )
                        ],
                    )
                ],
                lead=None,
            )
        )

    output = "".join(tokens)
    # LLM produced the answer …
    assert "LLM_SENTINEL" in output
    # … and the deterministic canned headers are NOT used as the primary response.
    assert "# 📊 Comparison" not in output
    assert "🎯 Qualified Leads" not in output
    # The LLM was grounded on the real stored lead.
    serialized = json.dumps(captured["messages"])
    assert "Acme Dental" in serialized


def test_workspace_question_falls_back_to_deterministic_without_provider(monkeypatch) -> None:
    """With no AI provider configured, the workspace path degrades gracefully to the
    deterministic builder rather than erroring."""
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)
    service = AssistantService()

    monkeypatch.setattr(
        AssistantService, "_resolve_runtime_candidates", lambda self, settings: []
    )

    with session_factory() as db:
        workspace = (
            db.query(Workspace).filter(Workspace.public_id == seed.workspace_public_id).one()
        )
        tokens = list(
            service._generate_tokens(
                db,
                workspace_id=workspace.id,
                messages=[
                    AssistantMessageInput(
                        id="msg-fallback",
                        role="user",
                        parts=[
                            AssistantMessagePartInput(
                                type="text",
                                text="Who is the best lead today?",
                            )
                        ],
                    )
                ],
                lead=None,
            )
        )

    output = "".join(tokens)
    assert "Acme Dental" in output


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
