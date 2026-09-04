import { request } from './client';
import { FinancialEvent, EventCreateResponse } from '../types/events';

export async function createEvent(event: Partial<FinancialEvent>): Promise<EventCreateResponse> {
  return request<EventCreateResponse>('/events', {
    method: 'POST',
    body: JSON.stringify(event),
  });
}

export async function listEvents(params?: {
  event_type?: string;
  entity_id?: string;
  account_id?: string;
  merchant_id?: string;
  limit?: number;
  offset?: number;
}): Promise<FinancialEvent[]> {
  const query = new URLSearchParams();
  if (params?.event_type) query.set('event_type', params.event_type);
  if (params?.entity_id) query.set('entity_id', params.entity_id);
  if (params?.account_id) query.set('account_id', params.account_id);
  if (params?.merchant_id) query.set('merchant_id', params.merchant_id);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));

  const qs = query.toString();
  return request<FinancialEvent[]>(`/events${qs ? `?${qs}` : ''}`);
}

export async function getEvent(eventId: string): Promise<FinancialEvent> {
  return request<FinancialEvent>(`/events/${encodeURIComponent(eventId)}`);
}
