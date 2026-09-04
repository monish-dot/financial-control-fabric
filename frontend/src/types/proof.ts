import { ControlDomain, ControlResult, ControlStatus } from './controls';

export type VerificationFailureReason =
  | 'VALID'
  | 'EVENT_TAMPERED'
  | 'EVENT_MISSING'
  | 'EVENT_ADDED'
  | 'CONTROL_RESULT_MISMATCH'
  | 'INVALID_PROOF'
  | 'UNKNOWN_ERROR';

export interface MerkleProofStep {
  sibling_hash: string;
  position: 'LEFT' | 'RIGHT';
}

export interface MerkleMembershipProof {
  proof_id: string;
  event_id: string;
  leaf_hash: string;
  merkle_root: string;
  proof_steps: MerkleProofStep[];
  verified: boolean;
}

export interface ControlProof {
  proof_id: string;
  control_id: string;
  domain: ControlDomain;
  entity_id?: string | null;
  period_start: string;
  period_end: string;
  event_count: number;
  event_ids: string[];
  merkle_root: string;
  control_status: ControlStatus;
  expected_amount: string;
  actual_amount: string;
  residual_amount: string;
  currency: string;
  context: Record<string, any>;
  generated_at: string;
  metadata: Record<string, any>;
}

export interface ProofVerificationResult {
  proof_id: string;
  valid: boolean;
  merkle_root_expected: string;
  merkle_root_computed: string;
  event_count_expected: number;
  event_count_computed: number;
  control_result_consistent: boolean;
  tampering_detected: boolean;
  failure_reason: VerificationFailureReason;
  recomputed_result?: ControlResult | null;
  metadata: Record<string, any>;
}
