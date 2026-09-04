import { InvestigationReport, AgentAuditEvent, ControllerAction } from '../types/agent';

export type UnifiedWorkflowState =
  | 'DETECTED'
  | 'INVESTIGATING'
  | 'EVIDENCE_COLLECTED'
  | 'HYPOTHESES_TESTED'
  | 'RECOMMENDATION_READY'
  | 'AWAITING_APPROVAL'
  | 'APPROVED'
  | 'REVALIDATING'
  | 'RESOLVED'
  | 'CONTROL_PROOF'
  | 'VERIFIED'
  | 'REJECTED'
  | 'INCONCLUSIVE';

export const WORKFLOW_PIPELINE: UnifiedWorkflowState[] = [
  'DETECTED',
  'INVESTIGATING',
  'EVIDENCE_COLLECTED',
  'HYPOTHESES_TESTED',
  'RECOMMENDATION_READY',
  'AWAITING_APPROVAL',
  'APPROVED',
  'REVALIDATING',
  'RESOLVED',
  'CONTROL_PROOF',
  'VERIFIED',
];

export function deriveAuthoritativeState(
  report?: InvestigationReport | null,
  auditEvents?: AgentAuditEvent[] | null,
  action?: ControllerAction | null
): UnifiedWorkflowState {
  if (!report) return 'DETECTED';

  // 1. Proof attached & verified
  if (report.proof_id) {
    if (report.proof_status === 'VERIFIED') return 'VERIFIED';
    return 'CONTROL_PROOF';
  }

  // 2. Metadata explicitly resolved
  if (report.metadata?.state === 'RESOLVED') {
    return 'RESOLVED';
  }

  // 3. Inspect audit events for revalidation or approval
  if (auditEvents && auditEvents.length > 0) {
    const revEvent = [...auditEvents].reverse().find((e) => e.action === 'REVALIDATED');
    if (revEvent) {
      if (revEvent.output_summary?.includes('resolved=True')) {
        return 'RESOLVED';
      }
      return 'INCONCLUSIVE';
    }

    const appEvent = [...auditEvents].reverse().find((e) => e.action === 'APPROVAL_RECORDED');
    if (appEvent) {
      if (appEvent.output_summary?.includes('APPROVED') || appEvent.input_summary?.includes('approved=True')) {
        return 'APPROVED';
      }
      if (appEvent.output_summary?.includes('REJECTED') || appEvent.input_summary?.includes('approved=False')) {
        return 'REJECTED';
      }
    }

    if (auditEvents.some((e) => e.action === 'RECOMMENDATION_READY')) {
      return 'AWAITING_APPROVAL';
    }
  }

  // 4. Action approval check
  if (action) {
    if (action.approval_status === 'APPROVED') return 'APPROVED';
    if (action.approval_status === 'REJECTED') return 'REJECTED';
    if (action.approval_status === 'PENDING') return 'AWAITING_APPROVAL';
  }

  // 5. Check metadata state
  const metaState = report.metadata?.state;
  if (metaState === 'RESOLVED') return 'RESOLVED';
  if (metaState === 'REVALIDATING') return 'REVALIDATING';
  if (metaState === 'AWAITING_APPROVAL') return 'AWAITING_APPROVAL';
  if (metaState === 'APPROVED') return 'APPROVED';
  if (metaState === 'RECOMMENDATION_READY') return 'RECOMMENDATION_READY';
  if (metaState === 'INCONCLUSIVE') return 'INCONCLUSIVE';

  // 6. Report-level completion
  if (report.status === 'COMPLETED') {
    return 'RECOMMENDATION_READY';
  }

  if (report.status === 'INCONCLUSIVE') {
    return 'INCONCLUSIVE';
  }

  return 'DETECTED';
}

export function getWorkflowStepIndex(state: UnifiedWorkflowState): number {
  if (state === 'REJECTED') return 5;
  if (state === 'INCONCLUSIVE') return 7;
  const idx = WORKFLOW_PIPELINE.indexOf(state);
  return idx >= 0 ? idx : 0;
}
