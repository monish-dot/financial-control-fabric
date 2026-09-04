import { request } from './client';
import { ControlDefinition, ControlDomain, ControlResult, ControlEvaluationRequest } from '../types/controls';

export async function listControls(): Promise<ControlDefinition[]> {
  return request<ControlDefinition[]>('/controls');
}

export async function getControl(domain: ControlDomain): Promise<ControlDefinition> {
  return request<ControlDefinition>(`/controls/${domain}`);
}

export async function evaluateControl(
  domain: ControlDomain,
  payload: ControlEvaluationRequest
): Promise<ControlResult> {
  return request<ControlResult>(`/controls/evaluate/${domain}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
