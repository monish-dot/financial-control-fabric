export type ControlDomain =
  | 'NODAL_ESCROW'
  | 'SETTLEMENT'
  | 'MERCHANT_PAYOUT'
  | 'REVENUE_RECOGNITION'
  | 'CROSS_ENTITY';

export type ControlStatus = 'PASS' | 'FAIL';

export interface ControlDefinition {
  domain: ControlDomain;
  control_id: string;
  description: string;
}

export interface ControlResult {
  control_id: string;
  domain: ControlDomain;
  entity_id?: string | null;
  period_start: string;
  period_end: string;
  expected_amount: string;
  actual_amount: string;
  residual_amount: string;
  currency: string;
  status: ControlStatus;
  tolerance: string;
  explanation: string;
  metadata: Record<string, any>;
}

export interface ControlEvaluationRequest {
  events?: any[] | null;
  context: Record<string, any>;
}
