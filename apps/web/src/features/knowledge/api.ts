import { request } from "@/lib/api-client";
import type {
  KnowledgeCollection,
  KnowledgeCollectionCreateRequest,
  KnowledgeCollectionListResponse,
  KnowledgeDocumentCreateRequest,
  KnowledgeDocumentListResponse,
  KnowledgeIngestion,
  KnowledgeSearchRequest,
  KnowledgeSearchResponse,
} from "@/types/knowledge";

const BASE = "/api/v1/knowledge";

export function listKnowledgeCollections() {
  return request<KnowledgeCollectionListResponse>(`${BASE}/collections`);
}

export function createKnowledgeCollection(
  payload: KnowledgeCollectionCreateRequest,
) {
  return request<KnowledgeCollection>(
    `${BASE}/collections`,
    { method: "POST" },
    payload,
  );
}

export function listKnowledgeDocuments(params: { collectionId?: string } = {}) {
  const query = new URLSearchParams();
  if (params.collectionId) query.set("collection_id", params.collectionId);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<KnowledgeDocumentListResponse>(`${BASE}/documents${suffix}`);
}

export function createKnowledgeDocument(payload: KnowledgeDocumentCreateRequest) {
  return request<KnowledgeIngestion>(
    `${BASE}/documents`,
    { method: "POST" },
    payload,
  );
}

/**
 * The server re-ingests from supplied content (it keeps no re-readable copy)
 * and validates the same body as document creation.
 */
export function reingestKnowledgeDocument(
  documentId: string,
  payload: KnowledgeDocumentCreateRequest,
) {
  return request<KnowledgeIngestion>(
    `${BASE}/documents/${documentId}/reingest`,
    { method: "POST" },
    payload,
  );
}

export function deleteKnowledgeDocument(documentId: string) {
  return request<null>(`${BASE}/documents/${documentId}`, { method: "DELETE" });
}

export function searchKnowledge(payload: KnowledgeSearchRequest) {
  return request<KnowledgeSearchResponse>(
    `${BASE}/search`,
    { method: "POST" },
    payload,
  );
}
