/**
 * Client-side index for tracked investigation IDs and proof IDs.
 * Solves the read-only API constraint without inventing backend list endpoints.
 */

const INVESTIGATIONS_KEY = 'fcf_investigation_ids';
const PROOFS_KEY = 'fcf_proof_ids';

export function getTrackedInvestigations(): string[] {
  try {
    const raw = localStorage.getItem(INVESTIGATIONS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function trackInvestigation(id: string): void {
  if (!id) return;
  try {
    const list = getTrackedInvestigations();
    if (!list.includes(id)) {
      list.unshift(id);
      localStorage.setItem(INVESTIGATIONS_KEY, JSON.stringify(list.slice(0, 50)));
    }
  } catch {
    // ignore
  }
}

export function getTrackedProofs(): string[] {
  try {
    const raw = localStorage.getItem(PROOFS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function trackProof(id: string): void {
  if (!id) return;
  try {
    const list = getTrackedProofs();
    if (!list.includes(id)) {
      list.unshift(id);
      localStorage.setItem(PROOFS_KEY, JSON.stringify(list.slice(0, 50)));
    }
  } catch {
    // ignore
  }
}
