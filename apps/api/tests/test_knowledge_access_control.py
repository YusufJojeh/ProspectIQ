"""Knowledge document visibility must hold for listing and mutation, not only retrieval.

Regression: `GET /knowledge/documents` once returned every document in the
workspace, and any member could re-ingest or archive a document they were not
allowed to see. `restricted` documents could also be created by roles that
could never read them back.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from test_workspace_e2e import _build_session_factory, _login, _override_client, _seed_workspace

from app.core.config import clear_settings_cache

_CONTENT = "# Pricing\n\nRetainers begin at 4500 SAR per month for the standard tier."


def _headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_document(
    client: TestClient, headers: dict[str, str], collection_id: str, title: str, visibility: str
) -> Any:
    return client.post(
        "/api/v1/knowledge/documents",
        json={
            "collection_id": collection_id,
            "title": title,
            "content": _CONTENT,
            "visibility": visibility,
        },
        headers=headers,
    )


def _titles(client: TestClient, headers: dict[str, str]) -> set[str]:
    response = client.get("/api/v1/knowledge/documents", headers=headers)
    assert response.status_code == 200
    return {doc["title"] for doc in response.json()["documents"]}


def test_listing_and_mutation_respect_document_visibility(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_ENV", "test")
    clear_settings_cache()
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        admin = {"Authorization": f"Bearer {_login(client, seed)}"}
        manager = _headers(client, "manager@example.com", "ManagerPass123!")
        member = _headers(client, "sales@example.com", "SalesPass123!")

        collection = client.post(
            "/api/v1/knowledge/collections",
            json={"slug": "pricing", "name": "Pricing", "collection_type": "pricing_guidance"},
            headers=admin,
        )
        assert collection.status_code == 201
        collection_id = collection.json()["collection_id"]

        shared = _create_document(client, admin, collection_id, "Shared pricing", "workspace")
        restricted = _create_document(client, admin, collection_id, "Board-only pricing", "restricted")
        private = _create_document(client, member, collection_id, "Member scratchpad", "private")
        assert {shared.status_code, restricted.status_code, private.status_code} == {201}
        restricted_id = restricted.json()["document_id"]
        private_id = private.json()["document_id"]

        # Listing is scoped to what the caller may retrieve.
        assert _titles(client, member) == {"Shared pricing", "Member scratchpad"}
        assert _titles(client, manager) == {"Shared pricing", "Board-only pricing"}
        assert _titles(client, admin) == {"Shared pricing", "Board-only pricing"}

        # A document the caller cannot see is reported missing, for every mutation.
        for headers, document_id in ((member, restricted_id), (admin, private_id), (manager, private_id)):
            assert (
                client.delete(f"/api/v1/knowledge/documents/{document_id}", headers=headers).status_code
                == 404
            )
            assert (
                client.post(
                    f"/api/v1/knowledge/documents/{document_id}/reingest",
                    json={
                        "collection_id": collection_id,
                        "title": "x",
                        "content": "Replacement text that must never be applied.",
                    },
                    headers=headers,
                ).status_code
                == 404
            )
        # ...and nothing was changed by the refused attempts.
        assert _titles(client, member) == {"Shared pricing", "Member scratchpad"}

        # The owner and an elevated role may manage what they can see.
        assert (
            client.delete(f"/api/v1/knowledge/documents/{private_id}", headers=member).status_code
            == 204
        )
        assert (
            client.delete(f"/api/v1/knowledge/documents/{restricted_id}", headers=manager).status_code
            == 204
        )


def test_restricted_documents_can_only_be_created_by_elevated_roles(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("APP_ENV", "test")
    clear_settings_cache()
    session_factory = _build_session_factory()
    seed = _seed_workspace(session_factory)

    with _override_client(session_factory) as client:
        admin = {"Authorization": f"Bearer {_login(client, seed)}"}
        member = _headers(client, "sales@example.com", "SalesPass123!")
        collection_id = client.post(
            "/api/v1/knowledge/collections",
            json={"slug": "notes", "name": "Notes", "collection_type": "industry_notes"},
            headers=admin,
        ).json()["collection_id"]

        forbidden = _create_document(client, member, collection_id, "Sneaky", "restricted")
        assert forbidden.status_code == 403
        assert "Sneaky" not in _titles(client, admin)
        assert _create_document(client, member, collection_id, "Fine", "workspace").status_code == 201
