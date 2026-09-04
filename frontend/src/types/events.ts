export type EventType =
  | 'PAYMENT'
  | 'PAYOUT'
  | 'REFUND'
  | 'FEE'
  | 'TAX'
  | 'ADJUSTMENT'
  | 'BANK_CREDIT'
  | 'BANK_DEBIT'
  | 'JOURNAL_ENTRY'
  | 'REVENUE_RECOGNITION'
  | 'INTERCOMPANY_TRANSFER';

export interface FinancialEvent {
  event_id: string;
  event_type: EventType;
  source_system: string;
  source_id: string;
  entity_id?: string | null;
  account_id?: string | null;
  merchant_id?: string | null;
  partner_id?: string | null;
  amount: string; // Exact Decimal string representation
  currency: string;
  event_timestamp: string;
  effective_timestamp: string;
  parent_event_id?: string | null;
  status: string;
  metadata: Record<string, any>;
}

export interface EventCreateResponse {
  event: FinancialEvent;
  created: boolean;
  message: string;
}
