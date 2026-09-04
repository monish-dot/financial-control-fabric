import { request } from './client';
import {
  InvestigationReport,
  InvestigationRequest,
  EvidenceItem,
  InvestigationHypothesis,
  AgentAuditEvent,
  ControllerAction,
  RevalidationResult,
} from '../types/agent';

export async function launchInvestigation(payload: InvestigationRequest): Promise<InvestigationReport> {
  return request<InvestigationReport>('/agent/investigate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getInvestigation(investigationId: string): Promise<InvestigationReport> {
  return request<InvestigationReport>(`/agent/investigations/${encodeURIComponent(investigationId)}`);
}

export async function getInvestigationEvidence(investigationId: string): Promise<EvidenceItem[]> {
  return request<EvidenceItem[]>(`/agent/investigations/${encodeURIComponent(investigationId)}/evidence`);
}

export async function getInvestigationHypotheses(investigationId: string): Promise<InvestigationHypothesis[]> {
  return request<InvestigationHypothesis[]>(`/agent/investigations/${encodeURIComponent(investigationId)}/hypotheses`);
}

export async function getInvestigationAudit(investigationId: string): Promise<AgentAuditEvent[]> {
  return request<AgentAuditEvent[]>(`/agent/investigations/${encodeURIComponent(investigationId)}/audit`);
}

export async function requestRecommendation(investigationId: string): Promise<ControllerAction> {
  return request<ControllerAction>(`/agent/investigations/${encodeURIComponent(investigationId)}/recommendation`, {
    method: 'POST',
  });
}

export async function approveInvestigation(
  investigationId: string,
  payload: { approved: boolean; approved_by: string }
): Promise<ControllerAction> {
  return request<ControllerAction>(`/agent/investigations/${encodeURIComponent(investigationId)}/approve`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function revalidateInvestigation(
  investigationId: string,
  payload: {
    new_control_result?: any;
    events?: any[];
    context?: any;
  }
): Promise<RevalidationResult> {
  return request<RevalidationResult>(`/agent/investigations/${encodeURIComponent(investigationId)}/revalidate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function attachProofToInvestigation(
  investigationId: string,
  proofId: string
): Promise<InvestigationReport> {
  return request<InvestigationReport>(`/agent/investigations/${encodeURIComponent(investigationId)}/attach-proof`, {
    method: 'POST',
    body: JSON.stringify({ proof_id: proofId }),
  });
}
