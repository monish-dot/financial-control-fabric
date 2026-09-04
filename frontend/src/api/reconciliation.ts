import { request } from './client';
import { ReconciliationRequest, ReconciliationResult } from '../types/reconciliation';

export async function reconcileSettlement(payload: ReconciliationRequest): Promise<ReconciliationResult> {
  return request<ReconciliationResult>('/reconciliation/settlement', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getReconciliation(reconciliationId: string): Promise<ReconciliationResult> {
  return request<ReconciliationResult>(`/reconciliation/${encodeURIComponent(reconciliationId)}`);
}
