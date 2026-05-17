from __future__ import annotations

from tests.test_workspace_e2e import (
    _build_session_factory,
    _login,
    _override_client,
    _seed_workspace,
)


def _generate_outreach(client, token, lead_id, *, language=None, regenerate=False):
    body = {"regenerate": regenerate}
    if language is not None:
        body["language"] = language
    return client.post(
        f"/api/v1/leads/{lead_id}/outreach/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )


def _get_latest_outreach(client, token, lead_id):
    return client.get(
        f"/api/v1/outreach/leads/{lead_id}/latest",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_outreach_default_language_is_english() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _generate_outreach(client, token, seed.lead_public_id)
        response = _get_latest_outreach(client, token, seed.lead_public_id)

    assert response.status_code == 200
    message = response.json()["message"]
    assert message is not None
    assert message["language"] == "en"


def test_outreach_arabic_language_is_accepted_and_persisted() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _generate_outreach(client, token, seed.lead_public_id, language="ar", regenerate=True)
        response = _get_latest_outreach(client, token, seed.lead_public_id)

    assert response.status_code == 200
    message = response.json()["message"]
    assert message is not None
    assert message["language"] == "ar"


def test_outreach_arabic_message_contains_translation_instruction() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        _generate_outreach(client, token, seed.lead_public_id, language="ar", regenerate=True)
        response = _get_latest_outreach(client, token, seed.lead_public_id)

    message_body = response.json()["message"]["message"]
    assert "Arabic" in message_body or "arabic" in message_body.lower()


def test_outreach_invalid_language_code_returns_422() -> None:
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        token = _login(client, seed)
        response = _generate_outreach(client, token, seed.lead_public_id, language="fr")

    assert response.status_code == 422
