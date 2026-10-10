/** Sales Knowledge (`/api/v1/knowledge/*`), mirroring knowledge/schemas.py. */

export type KnowledgeCollectionType =
  | "icp"
  | "services"
  | "capabilities"
  | "case_studies"
  | "portfolio"
  | "industry_playbooks"
  | "sales_playbooks"
  | "past_proposals"
  | "proposal_templates"
  | "winning_outreach"
  | "objections"
  | "pricing_guidance"
  | "industry_notes"
  | "product_docs";

export const KNOWLEDGE_COLLECTION_TYPES: readonly KnowledgeCollectionType[] = [
  "services",
  "capabilities",
  "case_studies",
  "portfolio",
  "industry_playbooks",
  "sales_playbooks",
  "icp",
  "past_proposals",
  "proposal_templates",
  "winning_outreach",
  "objections",
  "pricing_guidance",
  "industry_notes",
  "product_docs",
];

export type KnowledgeVisibility = "workspace" | "private" | "restricted";

/** draft | ingesting | ready | failed | archived */
export type KnowledgeDocumentStatus =
  | "draft"
  | "ingesting"
  | "ready"
  | "failed"
  | "archived";

export interface KnowledgeCollection {
  collection_id: string;
  slug: string;
  name: string;
  collection_type: KnowledgeCollectionType;
  description: string | null;
  document_count: number;
  created_at: string;
}

export interface KnowledgeCollectionListResponse {
  collections: KnowledgeCollection[];
}

export interface KnowledgeCollectionCreateRequest {
  slug: string;
  name: string;
  collection_type: KnowledgeCollectionType;
  description?: string | null;
}

export interface KnowledgeDocument {
  document_id: string;
  collection_id: string;
  document_type: string;
  title: string;
  source_name: string | null;
  visibility: KnowledgeVisibility;
  status: KnowledgeDocumentStatus;
  current_version: number;
  chunk_count: number;
  language: string;
  industry: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocumentListResponse {
  documents: KnowledgeDocument[];
}

export interface KnowledgeDocumentCreateRequest {
  collection_id: string;
  title: string;
  content: string;
  source_name?: string | null;
  source_uri?: string | null;
  visibility?: KnowledgeVisibility;
  language?: string;
  industry?: string | null;
}

export type KnowledgeIngestionStatus =
  | "queued"
  | "running"
  | "completed"
  | "skipped_unchanged"
  | "failed";

export interface KnowledgeIngestion {
  ingestion_id: string;
  document_id: string;
  status: KnowledgeIngestionStatus;
  version: number;
  chunk_count: number;
  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_tokens: number;
  fallback_used: boolean;
  latency_ms: number | null;
  error_code: string | null;
  error_message: string | null;
  trace_id: string;
}

export interface KnowledgeSearchRequest {
  query: string;
  collection_types?: KnowledgeCollectionType[] | null;
  industry?: string | null;
  limit?: number | null;
}

export interface KnowledgeCitation {
  chunk_id: string;
  document_id: string;
  document_title: string;
  document_type: string;
  section: string | null;
  version: number;
  excerpt: string;
  score: number;
  vector_score: number;
  keyword_score: number;
}

export interface KnowledgeSearchResponse {
  query: string;
  results: KnowledgeCitation[];
  candidate_count: number;
  embedding_model: string | null;
  degraded: boolean;
}
