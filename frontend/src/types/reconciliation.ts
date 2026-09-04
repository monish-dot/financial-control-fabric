export type ReconciliationSide = 'INTERNAL' | 'EXTERNAL';

export type ReconciliationItemType =
  | 'SETTLEMENT_OBLIGATION'
  | 'BANK_SETTLEMENT'
  | 'PARTNER_CONFIRMATION';

export type ReconciliationStatus =
  | 'FULLY_RECONCILED'
  | 'PARTIALLY_RECONCILED'
  | 'UNRECONCILED'
  | 'INFEASIBLE';

export interface ReconciliationItem {
  item_id: string;
  side: ReconciliationSide;
  item_type: ReconciliationItemType;
  entity_id?: string | null;
  account_id?: string | null;
  merchant_id?: string | null;
  partner_id?: string | null;
  amount: string;
  currency: string;
  timestamp: string;
  reference_id?: string | null;
  status?: string;
  metadata?: Record<string, any>;
}

export interface MatchAllocation {
  allocation_id: string;
  internal_item_id: string;
  external_item_id: string;
  allocated_amount: string;
  currency: string;
  confidence: string;
  reason: string;
  constraints_satisfied: boolean;
  metadata?: Record<string, any>;
}

export interface ReconciliationResult {
  reconciliation_id: string;
  matched_amount: string;
  unmatched_internal_amount: string;
  unmatched_external_amount: string;
  allocation_count: number;
  match_rate: string;
  currency: string;
  status: ReconciliationStatus;
  allocations: MatchAllocation[];
  explanation: string;
  metadata?: Record<string, any>;
}

export interface ReconciliationConstraints {
  timestamp_tolerance_minutes?: number | null;
  normalize_references?: boolean;
  require_reference_match?: boolean;
  require_entity_match?: boolean;
  require_account_match?: boolean;
  require_merchant_match?: boolean;
  require_partner_match?: boolean;
  minimum_compatibility_score?: string;
}

export interface ReconciliationRequest {
  internal_items: ReconciliationItem[];
  external_items: ReconciliationItem[];
  constraints?: ReconciliationConstraints;
  reconciliation_id?: string | null;
}
