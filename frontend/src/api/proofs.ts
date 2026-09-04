import { request } from './client';
import {
  ControlProof,
  ProofVerificationResult,
  MerkleMembershipProof,
} from '../types/proof';

export async function generateProof(payload: {
  control_result: any;
  context: Record<string, any>;
  events?: any[] | null;
  proof_id?: string | null;
}): Promise<ControlProof> {
  return request<ControlProof>('/proofs/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getProof(proofId: string): Promise<ControlProof> {
  return request<ControlProof>(`/proofs/${encodeURIComponent(proofId)}`);
}

export async function verifyProof(
  proofId: string,
  payload: { events?: any[] | null } = {}
): Promise<ProofVerificationResult> {
  return request<ProofVerificationResult>(`/proofs/${encodeURIComponent(proofId)}/verify`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getMembershipProof(
  proofId: string,
  eventId: string
): Promise<MerkleMembershipProof> {
  return request<MerkleMembershipProof>(
    `/proofs/${encodeURIComponent(proofId)}/events/${encodeURIComponent(eventId)}/membership`
  );
}
