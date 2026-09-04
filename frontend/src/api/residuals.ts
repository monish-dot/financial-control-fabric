import { request } from './client';
import {
  ResidualObservation,
  ResidualDistributionResponse,
  ResidualBaseline,
  ResidualAnalysis,
} from '../types/residuals';
import { ControlDomain } from '../types/controls';

export async function listResiduals(params?: {
  domain?: ControlDomain;
  entity_id?: string;
  account_id?: string;
  merchant_id?: string;
  partner_id?: string;
  currency?: string;
  limit?: number;
  offset?: number;
}): Promise<ResidualObservation[]> {
  const query = new URLSearchParams();
  if (params?.domain) query.set('domain', params.domain);
  if (params?.entity_id) query.set('entity_id', params.entity_id);
  if (params?.account_id) query.set('account_id', params.account_id);
  if (params?.merchant_id) query.set('merchant_id', params.merchant_id);
  if (params?.partner_id) query.set('partner_id', params.partner_id);
  if (params?.currency) query.set('currency', params.currency);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));

  const qs = query.toString();
  return request<ResidualObservation[]>(`/residuals${qs ? `?${qs}` : ''}`);
}

export async function getResidual(residualId: string): Promise<ResidualObservation> {
  return request<ResidualObservation>(`/residuals/${encodeURIComponent(residualId)}`);
}

export async function getResidualDistribution(
  domain: ControlDomain,
  currency?: string
): Promise<ResidualDistributionResponse> {
  const qs = currency ? `?currency=${encodeURIComponent(currency)}` : '';
  return request<ResidualDistributionResponse>(`/residuals/distribution/${domain}${qs}`);
}

export async function getResidualBaseline(
  domain: ControlDomain,
  params?: {
    entity_id?: string;
    account_id?: string;
    currency?: string;
  }
): Promise<ResidualBaseline> {
  const query = new URLSearchParams();
  if (params?.entity_id) query.set('entity_id', params.entity_id);
  if (params?.account_id) query.set('account_id', params.account_id);
  if (params?.currency) query.set('currency', params.currency);

  const qs = query.toString();
  return request<ResidualBaseline>(`/residuals/baseline/${domain}${qs ? `?${qs}` : ''}`);
}

export async function analyzeResiduals(
  domain: ControlDomain,
  payload: {
    residuals?: any[];
    baseline_id?: string;
    baseline_residuals?: any[];
    rolling_window?: number;
    currency?: string;
  }
): Promise<ResidualAnalysis> {
  return request<ResidualAnalysis>(`/residuals/analyze/${domain}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
