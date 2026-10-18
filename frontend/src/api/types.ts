// Shared API response types mirroring the backend Pydantic schemas.

export type EpistemicStatus = "fact" | "unverified_claim" | "inference" | "hypothesis";

export interface Me {
  id: string;
  username: string;
  email?: string | null;
  name?: string | null;
  role: string;
  permissions: Record<string, boolean>;
}

export interface CaseItem {
  id: string;
  case_identifier: string;
  title: string;
  description: string | null;
  status: string;
  created_by: string;
  created_at: string;
  archived_at: string | null;
  my_case_role: string | null;
}

export interface Member {
  user_id: string;
  username: string;
  case_role: string;
}

export interface Evidence {
  id: string;
  case_id: string;
  type: string;
  indicator_type: string | null;
  indicator_value: string | null;
  original_filename: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  verification_status: string;
  retention_status: string;
  source: string | null;
  acquired_at: string;
  processing_history: unknown[];
  chain_of_custody: unknown[];
}

export interface AgentExecution {
  agent_name: string;
  status: string;
  duration_ms: number | null;
  error: Record<string, unknown> | null;
  created_at: string;
}

export interface InvestigationStatus {
  id: string;
  case_id: string;
  status: string;
  hypothesis: string | null;
  findings_count: number;
  contradictions_count: number;
  confidence_band: string | null;
  timeline_count: number;
  errors: Record<string, unknown>[];
  agent_executions: AgentExecution[];
  started_at: string;
  completed_at: string | null;
}

export interface Finding {
  agent_name: string;
  epistemic_status: EpistemicStatus;
  claim_type: string | null;
  payload: Record<string, unknown>;
}

export interface Contradiction {
  kind: "verified_contradiction" | "plausible_alternative" | "open_question";
  description: string;
  basis: string | null;
  refs: Record<string, unknown>;
}

export interface Confidence {
  score: number | null;
  band: string;
  factors: Record<string, { value: number; weight: number; rationale: string }>;
  limitations: string[];
  ibmz: {
    score: number | null;
    simulated: boolean;
    available: boolean;
    detail: string;
    source: string;
  } | null;
}

export interface TimelineEvent {
  at: string;
  label?: string;
  source?: string;
  investigation_id?: string;
}

export interface GraphNode {
  id: string;
  label: string;
  value: string;
  props: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  rel: string;
  provenance: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  note: string | null;
}

export interface Report {
  id: string;
  run_id: string;
  status: string;
  content: Record<string, unknown>;
  content_hash: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  case_id: string | null;
  actor_id: string | null;
  action: string;
  detail: Record<string, unknown>;
  entry_hash: string;
  created_at: string;
}

export interface UserItem {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
}
