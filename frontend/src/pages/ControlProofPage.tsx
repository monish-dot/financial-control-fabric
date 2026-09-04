import React, { useState } from 'react';
import { useQuery, useQueries, useMutation } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  KeyRound,
  ShieldCheck,
  ShieldAlert,
  Search,
  CheckCircle2,
  Copy,
  Check,
  GitCommit,
  Layers,
  ArrowDown,
} from 'lucide-react';
import { getProof, verifyProof, getMembershipProof } from '../api/proofs';
import { getTrackedProofs, trackProof } from '../lib/storage';
import { formatCurrency, formatTimestamp } from '../lib/formatters';
import { StatusBadge } from '../components/common/StatusBadge';
import { ProofVerificationResult, MerkleMembershipProof, ControlProof } from '../types/proof';


export const ControlProofPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const trackedProofs = getTrackedProofs();
  const selectedId = searchParams.get('id') || trackedProofs[0] || '';
  const [inputProofId, setInputProofId] = useState(selectedId);
  const [selectedEventId, setSelectedEventId] = useState<string>('');
  const [copied, setCopied] = useState(false);

  // 1. Fetch Proof Record
  const { data: proof, isLoading: proofLoading } = useQuery({
    queryKey: ['proof', selectedId],
    queryFn: () => (selectedId ? getProof(selectedId) : null),
    enabled: !!selectedId,
  });

  // Query all tracked proofs to build compact repository list
  const proofQueries = useQueries({
    queries: trackedProofs.map((id) => ({
      queryKey: ['proof-summary', id],
      queryFn: () => getProof(id),
      staleTime: 30000,
    })),
  });

  const availableProofs = proofQueries
    .map((q) => q.data)
    .filter((p): p is ControlProof => !!p);

  // 2. Mutation: Independent Verification
  const verifyMutation = useMutation({
    mutationFn: () => verifyProof(selectedId),
  });

  // 3. Mutation: Membership Proof Query
  const membershipMutation = useMutation({
    mutationFn: (eventId: string) => getMembershipProof(selectedId, eventId),
  });

  const handleSelect = (id: string) => {
    trackProof(id);
    setInputProofId(id);
    setSearchParams({ id });
    verifyMutation.reset();
    membershipMutation.reset();
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const verification = verifyMutation.data as ProofVerificationResult | undefined;
  const membership = membershipMutation.data as MerkleMembershipProof | undefined;

  return (
    <div className="space-y-6">
      {/* Header & Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-300 text-xs font-mono font-medium border border-emerald-800/50">
              TAMPER-EVIDENT CRYPTOGRAPHIC PROOF
            </span>
            <span className="text-xs text-slate-400">Deterministic Merkle Commitment</span>
          </div>
          <h2 className="text-xl font-bold text-slate-100 mt-1">Control Proof & Merkle Verification</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Cryptographic binding of committed financial events to the control result. Verified independently against the Financial Control Kernel.
          </p>
        </div>

        {/* Search input */}
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={inputProofId}
              onChange={(e) => setInputProofId(e.target.value)}
              placeholder="Proof ID..."
              className="bg-[#101522] border border-[#1e2638] rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 font-mono w-48 sm:w-64 focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            onClick={() => handleSelect(inputProofId)}
            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-medium"
          >
            Load
          </button>
        </div>
      </div>

      {/* Available Proofs History Table */}
      {availableProofs.length > 0 && (
        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-slate-200">
                Sealed Control Proofs Repository ({availableProofs.length})
              </h3>
            </div>
            <span className="text-xs font-mono text-slate-500">Select any proof to inspect Merkle tree</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-[#1e2638] text-slate-400 bg-slate-900/40">
                <tr>
                  <th className="py-2.5 px-3">Proof ID</th>
                  <th className="py-2.5 px-3">Control ID</th>
                  <th className="py-2.5 px-3">Domain</th>
                  <th className="py-2.5 px-3 text-center">Events</th>
                  <th className="py-2.5 px-3 text-center">Status</th>
                  <th className="py-2.5 px-3 text-right">Residual</th>
                  <th className="py-2.5 px-3">Generated Timestamp</th>
                  <th className="py-2.5 px-3 text-right">Selection</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2638]/50">
                {availableProofs.map((p) => {
                  const isSelected = selectedId === p.proof_id;
                  return (
                    <tr
                      key={p.proof_id}
                      onClick={() => handleSelect(p.proof_id)}
                      className={`cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-emerald-950/30 border-l-2 border-l-emerald-500'
                          : 'hover:bg-slate-800/30'
                      }`}
                    >
                      <td className="py-2.5 px-3 font-semibold text-emerald-300 font-mono">
                        {p.proof_id}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">{p.control_id}</td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 text-[10px] font-bold">
                          {p.domain}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center font-bold text-slate-200">
                        {p.event_count}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <StatusBadge status={p.control_status} size="sm" />
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-bold ${
                          p.residual_amount !== '0.00' && p.residual_amount !== '0'
                            ? 'text-rose-400'
                            : 'text-emerald-400'
                        }`}
                      >
                        {formatCurrency(p.residual_amount, p.currency)}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {formatTimestamp(p.generated_at)}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span
                          className={`text-xs font-semibold ${
                            isSelected ? 'text-emerald-400 font-bold' : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {isSelected ? 'Active Selection ✓' : 'Inspect ➔'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedId && proofLoading ? (
        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-12 text-center text-xs font-mono text-slate-400">
          Loading proof {selectedId}...
        </div>
      ) : selectedId && proof ? (
        <div className="space-y-6">
          {/* Proof Summary Card */}
          <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#1e2638]">
              <div>
                <div className="flex items-center gap-2.5">
                  <KeyRound className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-lg font-bold text-slate-100 font-mono">{proof.proof_id}</h3>
                  <StatusBadge status={proof.control_status} size="sm" />
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-400 font-mono mt-2">
                  <span>Domain: <strong className="text-slate-200">{proof.domain}</strong></span>
                  <span>Events: <strong className="text-slate-200">{proof.event_count}</strong></span>
                  <span>Generated: <strong className="text-slate-200">{formatTimestamp(proof.generated_at)}</strong></span>
                </div>
              </div>

              {/* Verify Action Button */}
              <button
                onClick={() => verifyMutation.mutate()}
                disabled={verifyMutation.isPending}
                className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-semibold shadow border border-emerald-400/40 transition-all disabled:opacity-50"
              >
                <ShieldCheck className="w-4 h-4" />
                {verifyMutation.isPending ? 'Verifying Against Kernel...' : 'Verify Proof Against Kernel'}
              </button>
            </div>

            {/* Committed Financial Invariant */}
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
              <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-500 block">EXPECTED AMOUNT</span>
                <span className="text-sm font-bold text-slate-100">
                  {formatCurrency(proof.expected_amount, proof.currency)}
                </span>
              </div>
              <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-500 block">ACTUAL AMOUNT</span>
                <span className="text-sm font-bold text-slate-100">
                  {formatCurrency(proof.actual_amount, proof.currency)}
                </span>
              </div>
              <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-500 block">RESIDUAL AMOUNT</span>
                <span className="text-sm font-bold text-slate-100">
                  {formatCurrency(proof.residual_amount, proof.currency)}
                </span>
              </div>
              <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-500 block">CONTROL STATUS</span>
                <span className="text-sm font-bold text-emerald-400">{proof.control_status}</span>
              </div>
            </div>

            {/* Committed Merkle Root Display */}
            <div className="mt-4 p-3.5 bg-black/60 rounded-lg border border-[#1e2638] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3 overflow-hidden">
                <span className="text-[11px] font-mono font-bold text-emerald-400 uppercase tracking-wider shrink-0">
                  MERKLE ROOT:
                </span>
                <span className="font-mono text-xs text-slate-300 truncate select-all">
                  {proof.merkle_root}
                </span>
              </div>
              <button
                onClick={() => copyToClipboard(proof.merkle_root)}
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 px-2.5 py-1 rounded bg-slate-800/80 border border-slate-700 shrink-0"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy Hash'}</span>
              </button>
            </div>
          </div>

          {/* Verification Result Banner (if run) */}
          {verification && (
            <div
              className={`p-5 rounded-xl border text-xs font-mono ${
                verification.valid
                  ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-200'
                  : 'bg-rose-950/30 border-rose-800/60 text-rose-200'
              }`}
            >
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <div className="flex items-center gap-2 font-bold text-sm">
                  {verification.valid ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  ) : (
                    <ShieldAlert className="w-5 h-5 text-rose-400" />
                  )}
                  <span>
                    VERIFICATION OUTCOME: {verification.failure_reason}
                  </span>
                </div>
                <span className="text-[11px] text-slate-400">
                  Kernel Consistency: {verification.control_result_consistent ? 'MATCH' : 'MISMATCH'}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3">
                <div>
                  <span className="text-[10px] text-slate-400 block">EXPECTED MERKLE ROOT</span>
                  <span className="text-[11px] text-slate-300 font-mono break-all">
                    {verification.merkle_root_expected}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block">COMPUTED MERKLE ROOT</span>
                  <span className="text-[11px] text-slate-300 font-mono break-all">
                    {verification.merkle_root_computed}
                  </span>
                </div>
              </div>

              {verification.metadata?.detail && (
                <div className="mt-3 p-2.5 bg-black/40 rounded border border-white/10 text-slate-300 text-[11px]">
                  Detail: {verification.metadata.detail}
                </div>
              )}
            </div>
          )}

          {/* Truthful Merkle Tree Visualization */}
          <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-bold text-slate-100">
                  Authoritative Merkle Structure (Backend Verified)
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                Algorithm: SHA-256 binary tree with odd-leaf duplicate rule
              </span>
            </div>

            {/* Tree Diagram */}
            <div className="p-6 bg-slate-950/60 rounded-xl border border-[#1e2638] space-y-6">
              {/* Root Level */}
              <div className="flex flex-col items-center">
                <span className="text-[10px] font-mono text-slate-500 uppercase">Merkle Root (Level N)</span>
                <div className="mt-1 px-4 py-2 rounded-lg bg-emerald-950/60 border border-emerald-600/50 text-emerald-300 font-mono text-xs font-bold shadow-lg shadow-emerald-950/30 max-w-md truncate">
                  {proof.merkle_root}
                </div>
                <ArrowDown className="w-4 h-4 text-slate-600 my-2" />
              </div>

              {/* Event Leaves Level */}
              <div>
                <div className="text-center text-[10px] font-mono text-slate-500 uppercase mb-2">
                  Committed Canonical Event Leaves ({proof.event_count})
                </div>
                <div className="flex items-center justify-center gap-3 flex-wrap">
                  {proof.event_ids.map((eventId) => (
                    <div
                      key={eventId}
                      onClick={() => {
                        setSelectedEventId(eventId);
                        membershipMutation.mutate(eventId);
                      }}
                      className={`cursor-pointer px-3 py-2 rounded-lg border text-xs font-mono transition-all ${
                        selectedEventId === eventId
                          ? 'bg-blue-600/20 border-blue-500 text-blue-200'
                          : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <GitCommit className="w-3.5 h-3.5 text-blue-400" />
                        <span className="font-semibold">{eventId}</span>
                      </div>
                      <span className="text-[10px] text-slate-500 block mt-0.5">Click for membership</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Merkle Membership Proof Inspector */}
          <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
            <div className="flex items-center justify-between pb-3 border-b border-[#1e2638]">
              <div>
                <h3 className="text-sm font-bold text-slate-100">Merkle Membership Path Inspector</h3>
                <p className="text-[11px] font-mono text-slate-400">
                  Cryptographically proves individual event inclusion in the root without revealing unrelated events.
                </p>
              </div>

              {/* Event selector */}
              <div className="flex items-center gap-2">
                <select
                  value={selectedEventId || proof.event_ids[0] || ''}
                  onChange={(e) => {
                    setSelectedEventId(e.target.value);
                    membershipMutation.mutate(e.target.value);
                  }}
                  className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  <option value="" disabled>Select event...</option>
                  {proof.event_ids.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => {
                    const target = selectedEventId || proof.event_ids[0];
                    if (target) membershipMutation.mutate(target);
                  }}
                  disabled={membershipMutation.isPending}
                  className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-medium disabled:opacity-50"
                >
                  {membershipMutation.isPending ? 'Verifying...' : 'Verify Membership'}
                </button>
              </div>
            </div>

            {/* Membership Path Display */}
            {membership ? (
              <div className="mt-4 space-y-3 text-xs font-mono">
                <div className="p-3 bg-emerald-950/30 border border-emerald-800/50 rounded-lg flex items-center justify-between text-emerald-300">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>
                      EVENT {membership.event_id} INCLUSION VERIFIED: {membership.verified ? 'TRUE' : 'FALSE'}
                    </span>
                  </div>
                  <span className="text-[11px] text-slate-400">
                    Steps: {membership.proof_steps.length}
                  </span>
                </div>

                <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 space-y-2">
                  <div>
                    <span className="text-[10px] text-slate-500 block">LEAF SHA-256 HASH</span>
                    <span className="text-slate-200 break-all">{membership.leaf_hash}</span>
                  </div>

                  <div className="pt-2 border-t border-slate-800">
                    <span className="text-[10px] text-slate-500 block mb-1">
                      SIBLING AUTHENTICATION STEPS
                    </span>
                    {membership.proof_steps.length > 0 ? (
                      <div className="space-y-1.5">
                        {membership.proof_steps.map((step, idx) => (
                          <div
                            key={idx}
                            className="p-2 bg-black/40 rounded border border-slate-800 flex items-center justify-between gap-3 text-[11px]"
                          >
                            <span className="text-slate-400">Step {idx + 1}:</span>
                            <span className="text-slate-300 truncate font-mono">{step.sibling_hash}</span>
                            <span className="px-1.5 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800 text-[10px] font-bold shrink-0">
                              POSITION: {step.position}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span className="text-slate-500 text-[11px]">
                        Single-leaf tree; root equals leaf hash.
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-4 text-center py-6 text-xs text-slate-400 font-mono">
                Select an event from the committed event set to inspect its cryptographic inclusion path.
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-12 text-center text-xs font-mono text-slate-400 space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto text-emerald-400">
            <KeyRound className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-bold text-slate-200">No Control Proof Selected</h3>
          <p className="max-w-md mx-auto text-slate-400 leading-relaxed text-[11px]">
            {availableProofs.length > 0
              ? 'Select an available control proof from the repository list above to inspect its Merkle tree structure, verify against the kernel, and test individual event membership.'
              : 'Cryptographic control proofs are tamper-evident SHA-256 Merkle commitments generated upon successful revalidation. Run the Missing-Payout Demo in the Overview or approve an investigation in the Approval Center to generate a proof.'}
          </p>
        </div>
      )}
    </div>
  );
};
