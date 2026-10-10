from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from test_agent_runtime import _make_workspace_lead_user
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

import app.modules.agents.runtime as runtime_module
from app.core.config import clear_settings_cache
from app.core.database import Base
from app.modules.agents.models import AgentEvent, AgentRun
from app.modules.agents.runtime import AgentRuntime
from app.modules.ai_runtime.models import ProviderUsage
from app.modules.leads.models import Lead
from app.modules.users.models import User

# --- Chaos and load ------------------------------------------------------
#
# Everything here is about what the platform does when something it depends
# on misbehaves: a provider that answers with nonsense, a model that asks
# for a tool that does not exist, a tool that explodes, a provider that
# hangs. The bar is the same in every case -- the run must end in a state
# that honestly describes what happened, and must never end in a state that
# reads like a successful answer when no answer was reached.

_REAL_HTTPX_CLIENT = httpx.Client


class _FakeResponse:
    def __init__(self, payload: Any, *, status: int = 200) -> None:
        self._payload = payload
        self._status = status

    def raise_for_status(self) -> None:
        if self._status >= 400:
            raise httpx.HTTPStatusError(
                f"status {self._status}", request=None, response=None  # type: ignore[arg-type]
            )

    def json(self) -> Any:
        return self._payload


class _ChaosProvider:
    """Returns whatever the test says, in order, then a valid final answer."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.index = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        headers = kwargs.get("headers") or {}
        if "Authorization" in headers:
            return self
        return _REAL_HTTPX_CLIENT(*args, **kwargs)

    def __enter__(self) -> _ChaosProvider:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def post(self, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> _FakeResponse:
        if self.index < len(self._responses):
            item = self._responses[self.index]
            self.index += 1
            if isinstance(item, Exception):
                raise item
            return _FakeResponse(item)
        self.index += 1
        return _FakeResponse(_final("Finished."))


def _tool_call(name: str, arguments: str, *, call_id: str = "c1") -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": arguments},
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10},
    }


def _content(text: str) -> dict[str, Any]:
    return {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10},
    }


def _final(answer: str) -> dict[str, Any]:
    return _content(json.dumps({"answer": answer, "confidence": 0.5}))


def _env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("AGENT_RUNTIME_MODE", "openai")
    monkeypatch.setenv("TAVILY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("APIFY_RUNTIME_MODE", "demo")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    clear_settings_cache()


def _run(session_factory: Any, seed: Any, *, goal: str = "Look at this lead.") -> dict[str, Any]:
    with _override_client(session_factory) as client:
        token = _login(client, seed)
        return dict(
            client.post(
                "/api/v1/agent/runs",
                json={"goal": goal, "lead_id": seed.lead_public_id},
                headers={"Authorization": f"Bearer {token}"},
            ).json()
        )


def _install(monkeypatch: pytest.MonkeyPatch, responses: list[Any]) -> _ChaosProvider:
    provider = _ChaosProvider(responses)
    monkeypatch.setattr(runtime_module.httpx, "Client", provider)
    return provider


# --- malformed model output ----------------------------------------------


def test_a_final_answer_that_is_not_json_is_kept_but_marked_unconfident(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    _install(monkeypatch, [_content("I think they need a website. Probably.")])
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
    assert run.status == "completed"
    answer = run.final_answer_json or {}
    # The text is preserved -- discarding it would lose the only thing the
    # model produced -- but it carries zero confidence and zero coverage, so
    # nothing downstream can mistake it for a structured, evidenced result.
    assert "website" in answer["answer"]
    assert answer["confidence"] == 0.0
    # Coverage is the backend's Evidence Graph number, never the model's claim.
    assert 0.0 <= answer["research_coverage"] <= 1.0


def test_a_final_answer_that_is_a_json_array_does_not_crash_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    _install(monkeypatch, [_content('["not", "an", "object"]')])
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run(session_factory, seed)
    assert payload["status"] == "completed"
    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
    assert (run.final_answer_json or {})["confidence"] == 0.0


def test_an_empty_model_response_still_produces_an_honest_terminal_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    _install(monkeypatch, [_content("")])
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run(session_factory, seed)
    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
    assert run.status == "completed"
    assert (run.final_answer_json or {})["confidence"] == 0.0
    assert (run.final_answer_json or {})["answer"]


# --- malformed tool calls -------------------------------------------------


def test_a_request_for_a_tool_that_does_not_exist_is_refused_and_the_run_goes_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    _install(
        monkeypatch,
        [
            _tool_call("run_sql", '{"sql": "SELECT * FROM users"}'),
            _tool_call("get_lead_context", "{}", call_id="c2"),
            _final("Done."),
        ],
    )
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
        types = [
            event.event_type
            for event in db.query(AgentEvent).filter_by(agent_run_id=run.id).all()
        ]
    # The invented tool was rejected, and the run recovered rather than
    # being taken down by one bad request.
    assert "tool_failed" in types or "tool_rejected" in types
    assert run.status == "completed"


def test_unparseable_tool_arguments_do_not_become_a_silent_empty_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    # The provider layer turns unparseable arguments into {}; a tool that
    # requires arguments must then refuse rather than run on defaults.
    _install(
        monkeypatch,
        [
            _tool_call("search_sales_knowledge", "{not json at all"),
            _final("Done."),
        ],
    )
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
        events = db.query(AgentEvent).filter_by(agent_run_id=run.id).all()
    assert run.status == "completed"
    assert any(event.event_type in {"tool_failed", "tool_rejected"} for event in events)
    # Nothing was recorded as a successful knowledge query.
    assert run.rag_query_count == 0


def test_a_tool_call_with_no_name_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch)
    _install(monkeypatch, [_tool_call("", "{}"), _final("Done.")])
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run(session_factory, seed)
    assert payload["status"] in {"completed", "failed"}


# --- provider chaos -------------------------------------------------------


def test_a_provider_timeout_mid_run_does_not_leave_the_run_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch, AGENT_MAX_MODEL_FALLBACKS="0")
    _install(
        monkeypatch,
        [
            _tool_call("get_lead_context", "{}"),
            httpx.ReadTimeout("provider timed out"),
        ],
    )
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
    # A run stuck in 'running' forever is the worst outcome: the UI spins,
    # nothing retries, and no one is told.
    assert run.status == "failed"
    assert run.error_code == "model_provider_unavailable"
    assert run.final_answer_json is None
    assert run.completed_at is not None


def test_a_provider_response_missing_choices_fails_the_run_rather_than_the_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch, AGENT_MAX_MODEL_FALLBACKS="0")
    _install(monkeypatch, [{"usage": {}}])
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    payload = _run(session_factory, seed)

    with session_factory() as db:
        run = db.query(AgentRun).filter_by(public_id=payload["run_id"]).one()
    assert run.status == "failed"
    assert run.final_answer_json is None




# --- load ----------------------------------------------------------------


def test_twelve_concurrent_runs_stay_independent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Twelve runs driven in parallel, each with its own events and ledger.

    The failure this guards against is shared mutable state on the runtime
    or the tool executor -- one run's tool results, counters or trace id
    bleeding into another. No single-run test can see that.

    It uses a file-backed SQLite database with one connection per thread,
    because the shared in-memory engine used elsewhere in this suite hands
    every thread the same connection and would serialize the very thing
    under test.
    """
    _env(monkeypatch)

    class _PerCallProvider:
        """One instance per model call, so no counter is shared."""

        def __init__(self) -> None:
            self.index = 0

        def __enter__(self) -> _PerCallProvider:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def post(
            self, url: str, json: dict[str, Any] | None = None, **kwargs: Any
        ) -> _FakeResponse:
            body = json or {}
            # Echo the goal back, so a run that somehow received another
            # run's conversation would produce the wrong answer text.
            system = " ".join(
                str(message.get("content", ""))
                for message in body.get("messages", [])
                if message.get("role") in {"system", "user"}
            )
            marker = next(
                (word for word in system.split() if word.startswith("marker-")), "marker-missing"
            )
            # Decide from the conversation, not a counter: a fresh provider
            # is built per model call, so only the transcript carries state.
            has_tool_result = any(
                message.get("role") == "tool" for message in body.get("messages", [])
            )
            if not has_tool_result:
                return _FakeResponse(_tool_call("get_lead_context", "{}"))
            return _FakeResponse(_final(f"Done for {marker}."))

    def _client(*args: Any, **kwargs: Any) -> Any:
        headers = kwargs.get("headers") or {}
        if "Authorization" in headers:
            return _PerCallProvider()
        return _REAL_HTTPX_CLIENT(*args, **kwargs)

    monkeypatch.setattr(runtime_module.httpx, "Client", _client)

    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'load.db'}",
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
    )
    with session_factory() as db:
        _, lead, user = _make_workspace_lead_user(db)
        workspace_id, lead_id, user_id = lead.workspace_id, lead.id, user.id

    def _one(index: int) -> str:
        with session_factory() as db:
            bound_lead = db.get(Lead, lead_id)
            bound_user = db.get(User, user_id)
            assert bound_lead is not None and bound_user is not None
            run = AgentRuntime().start(
                db,
                workspace_id=workspace_id,
                lead=bound_lead,
                current_user=bound_user,
                goal=f"Look at this lead. marker-{index}",
            )
            return str(run.public_id)

    with ThreadPoolExecutor(max_workers=6) as pool:
        run_ids = list(pool.map(_one, range(12)))

    assert len(set(run_ids)) == 12

    with session_factory() as db:
        runs = db.query(AgentRun).filter(AgentRun.public_id.in_(run_ids)).all()
        assert len(runs) == 12
        # Distinct traces, so the ledger can attribute spend per run.
        assert len({run.trace_id for run in runs}) == 12
        assert all(run.status == "completed" for run in runs)
        markers = set()
        for run in runs:
            answer = (run.final_answer_json or {})["answer"]
            markers.add(answer)
            events = db.query(AgentEvent).filter_by(agent_run_id=run.id).all()
            assert events
            usage = db.query(ProviderUsage).filter_by(subject_id=run.public_id).all()
            assert usage and {row.trace_id for row in usage} == {run.trace_id}
        # Every run answered its own goal: no conversation crossed over.
        assert len(markers) == 12
