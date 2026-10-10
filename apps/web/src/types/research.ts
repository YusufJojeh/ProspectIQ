/**
 * Evidence Graph and research history, mirroring
 * research/evidence_graph.py and research/schemas.py.
 */

export type CanonicalFactStatus = "supported" | "conflicting" | "unknown";

export interface EvidenceSource {
  /** Citable id (`ev_…`); the only form of lead evidence a final answer may cite. */
  evidence_ref: string | null;
  provider: string;
  source_type: string;
  url: string | null;
  observed_at: string;
  actor_run_id: string | null;
  confidence: number;
  source_quality: number;
}

export interface ContradictingValue {
  value: string;
  providers: string[];
  sources: EvidenceSource[];
}

export interface CanonicalFact {
  claim_type: string;
  value: string;
  status: CanonicalFactStatus;
  confidence: number;
  freshness_score: number;
  source_quality: number;
  sources: EvidenceSource[];
  contradicting_values: ContradictingValue[];
}

export interface EvidenceGroup {
  group: string;
  facts: CanonicalFact[];
}

export interface EvidenceGraph {
  lead_id: string;
  groups: EvidenceGroup[];
  evidence_confidence: number;
  research_coverage: number;
  generated_at: string;
}

export interface ResearchHistoryChange {
  change_id: string | null;
  claim_type: string;
  change_type: string;
  before: string | null;
  after: string | null;
  significance: number;
  explanation: string | null;
}

export interface ResearchHistoryItem {
  run_id: string;
  mode: string;
  depth: string;
  started_at: string;
  completed_at: string;
  status: string;
  evidence_confidence: number;
  research_coverage: number;
  score_before: number | null;
  score_after: number | null;
  changes: ResearchHistoryChange[];
}

export interface ResearchHistoryResponse {
  lead_id: string;
  items: ResearchHistoryItem[];
  pagination: { page: number; per_page: number; total: number };
}
