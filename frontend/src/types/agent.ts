import { ControlDomain, ControlResult } from './controls';
import { AnomalyScoreDetails } from './residuals';

export type AgentState =
  | 'DETECTED'
  | 'INVESTIGATING'
  | 'EVIDENCE_COLLECTED'
  | 'HYPOTHESES_TESTED'
  | 'RECOMMENDATION_READY'
  | 'AWAITING_APPROVAL'
  | 'APPROVED'
  | 'REJECTED'
  | 'REVALIDATING'
  | 'RESOLVED'
  | 'INCONCLUSIVE';

export type InvestigationStatus = 'INVESTIGATING' | 'COMPLETED' | 'INCONCLUSIVE';

export type RootCauseCategory =
  | 'MISSING_EVENT'
  | 'DUPLICATE_EVENT'
  | 'TIMING_DIFFERENCE'
  | 'AMOUNT_DIFFERENCE'
  | 'FEE_DIFFERENCE'
  | 'TAX_DIFFERENCE'
  | 'ADJUSTMENT_DIFFERENCE'
  | 'BANK_POSTING_DELAY'
  | 'RECONCILIATION_ALLOCATION'
  | 'REVENUE_TIMING'
  | 'INTERCOMPANY_MISMATCH'
  | 'DATA_INGESTION'
  | 'UNKNOWN';

export type RetrievalStatus =
  | 'SUCCESS'
  | 'NO_EVIDENCE'
  | 'INSUFFICIENT_EVIDENCE';

export type ReasoningStatus =
  | 'CONSISTENT'
  | 'INCONCLUSIVE'
  | 'CONTRADICTED'
  | 'SUPPORTED';

export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED';

export type AuditActor = 'SYSTEM' | 'AGENT' | 'CONTROLLER';

export interface RootCauseFinding {
  finding_id: string;
  category: RootCauseCategory;
  description: string;
  confidence: string;
  retrieval_status: RetrievalStatus;
  reasoning_status: ReasoningStatus;
  impact_amount: string;
  currency: string;
  supporting_evidence: string[];
  calculation_ids?: string[];
}

export interface EvidenceItem {
  evidence_id: string;
  source_type: string;
  source_id: string;
  field: string;
  value: string;
  timestamp: string;
  relevance: string;
  metadata: Record<string, any>;
  // Backwards-compat optional fields
  event_type?: string;
  record_id?: string;
  amount?: string;
  currency?: string;
  description?: string;
}

export interface InvestigationHypothesis {
  hypothesis_id: string;
  description: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  calculation_ids: string[];
  confidence: string;
  status: string;
  retrieval_status: RetrievalStatus;
  reasoning_status: ReasoningStatus;
  explanation: string;
  // Optional compat
  notes?: string;
}

export interface CalculationResult {
  calculation_id: string;
  formula: string;
  inputs: Record<string, any>;
  result: string;
  currency: string;
  calculation_trace?: string[];
  name?: string;
}

export interface InvestigationReport {
  investigation_id: string;
  control_id: string;
  domain: ControlDomain;
  entity_id?: string | null;
  account_id?: string | null;
  merchant_id?: string | null;
  partner_id?: string | null;
  status: InvestigationStatus;
  summary: string;
  root_causes: RootCauseFinding[];
  hypotheses: InvestigationHypothesis[];
  evidence: EvidenceItem[];
  calculations: CalculationResult[];
  anomaly_score: AnomalyScoreDetails | string;
  recommended_action: string;
  requires_human_approval: boolean;
  created_at: string;
  audit_ids: string[];
  proof_id?: string | null;
  merkle_root?: string | null;
  proof_status?: string | null;
  metadata: Record<string, any>;
}

export interface ControllerAction {
  action_id: string;
  investigation_id: string;
  action_type: string;
  description: string;
  proposed_by: AuditActor;
  requires_approval: boolean;
  approval_status: ApprovalStatus;
  approved_by?: string | null;
  approved_at?: string | null;
  notes?: string | null;
  supporting_evidence?: string[];
}

export interface RevalidationResult {
  control_id: string;
  previous_residual: string;
  new_residual: string;
  previous_status: string;
  new_status: string;
  resolved: boolean;
  explanation: string;
  // Optional compat
  investigation_id?: string;
  evaluated_at?: string;
  details?: Record<string, any>;
}

export interface AgentAuditEvent {
  audit_id: string;
  investigation_id: string;
  timestamp: string;
  actor: AuditActor;
  action: string;
  tool_name?: string | null;
  input_summary: string;
  output_summary: string;
  evidence_ids: string[];
  calculation_ids: string[];
}

export interface InvestigationRequest {
  investigation_id: string;
  control_id: string;
  domain: ControlDomain;
  entity_id?: string | null;
  account_id?: string | null;
  merchant_id?: string | null;
  partner_id?: string | null;
  period_start: string;
  period_end: string;
  control_result: ControlResult;
  anomaly_score: any;
  residual_summary: any;
  reconciliation_summary?: any;
  metadata?: Record<string, any>;
}
