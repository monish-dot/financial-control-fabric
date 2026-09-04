import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  UserCheck,
  ArrowRight,
  KeyRound,
  RotateCcw,
} from 'lucide-react';
import {
  getInvestigation,
  getInvestigationAudit,
  approveInvestigation,
  revalidateInvestigation,
  attachProofToInvestigation,
} from '../api/agent';
import { createEvent, getEvent } from '../api/events';
import { evaluateControl } from '../api/controls';
import { generateProof } from '../api/proofs';
import { getTrackedInvestigations, trackProof } from '../lib/storage';
import { deriveAuthoritativeState } from '../lib/workflowState';
import { WorkflowStepper } from '../components/common/WorkflowStepper';
import { StatusBadge } from '../components/common/StatusBadge';
import { RevalidationResult } from '../types/agent';

export const ApprovalCenterPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const trackedIds = getTrackedInvestigations();
  const selectedId = searchParams.get('id') || trackedIds[0] || '';
  const [approverName, setApproverName] = useState('controller_ops');
  const [revalidationResult, setRevalidationResult] = useState<RevalidationResult | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // 1. Fetch Investigation
  const { data: report, isLoading } = useQuery({
    queryKey: ['investigation', selectedId],
    queryFn: () => (selectedId ? getInvestigation(selectedId) : null),
    enabled: !!selectedId,
  });

  // 2. Fetch Audit
  const { data: audit } = useQuery({
    queryKey: ['investigation-audit', selectedId],
    queryFn: () => (selectedId ? getInvestigationAudit(selectedId) : []),
    enabled: !!selectedId && !!report,
  });

  // Authoritative State derived strictly from backend
  const lifecycleState = deriveAuthoritativeState(report, audit);

  // 3. Mutation: Human Approval Boundary (POST /agent/investigations/{id}/approve)
  const approveMutation = useMutation({
    mutationFn: async ({ approved }: { approved: boolean }) => {
      if (!approverName.trim()) throw new Error('Operator ID is required for human approval');
      return approveInvestigation(selectedId, {
        approved,
        approved_by: approverName.trim(),
      });
    },
    onSuccess: (data) => {
      setStatusMessage(
        `Action recorded: ${data.approval_status} by ${data.approved_by}. Financial mutation was NOT executed by AI Controller.`
      );
      queryClient.invalidateQueries({ queryKey: ['investigation', selectedId] });
      queryClient.invalidateQueries({ queryKey: ['investigation-audit', selectedId] });
    },
    onError: (err: any) => {
      setStatusMessage(`Approval error: ${err.message}`);
    },
  });

  // 4. Mutation: Remediate Ledger & Revalidate deterministically
  const revalidateMutation = useMutation({
    mutationFn: async () => {
      if (!report) throw new Error('No investigation loaded');
      setStatusMessage('Step 1/3: Ingesting missing payout remediation event into ledger...');

      const now = new Date();
      const start = report.metadata?.period_start || new Date(now.getTime() - 3600000).toISOString();
      const end = report.metadata?.period_end || now.toISOString();
      const merchantId = report.metadata?.demo_merchant_id || report.merchant_id || 'merchant-alpha';

      // 1. Ingest remediation payout event
      const payoutRes = await createEvent({
        event_id: `remediation-payout-${Date.now().toString().slice(-6)}`,
        event_type: 'PAYOUT',
        source_system: 'banking_rail',
        source_id: `rem_${Date.now().toString().slice(-6)}`,
        merchant_id: merchantId,
        entity_id: report.entity_id || 'entity-corp',
        account_id: report.account_id || 'acct-main',
        partner_id: report.partner_id || 'partner-hdfc',
        amount: report.root_causes?.[0]?.impact_amount || '10000.00',
        currency: 'INR',
        event_timestamp: end,
        effective_timestamp: end,
        status: 'settled',
        metadata: { remediation: true, for_investigation: selectedId },
      });

      setStatusMessage('Step 2/3: Fetching scoped events for deterministic revalidation...');
      // Get the original payment event from evidence or metadata
      let paymentEvent = null;
      const paymentEvtId =
        report.metadata?.payment_event_id ||
        report.evidence?.find((e) => e.source_type === 'PAYMENT')?.source_id;

      if (paymentEvtId) {
        try {
          paymentEvent = await getEvent(paymentEvtId);
        } catch {
          // If not found individually, proceed with evaluated context
        }
      }

      const scopedEvents = paymentEvent ? [paymentEvent, payoutRes.event] : [payoutRes.event];

      setStatusMessage('Step 3/3: Executing deterministic revalidation in control kernel...');
      const rev = await revalidateInvestigation(selectedId, {
        events: scopedEvents,
        context: {
          merchant_id: merchantId,
          period_start: start,
          period_end: end,
          currency: 'INR',
          tolerance: '0.00',
        },
      });

      setRevalidationResult(rev);
      setStatusMessage(
        `Revalidation complete: resolved = ${rev.resolved}, status = ${rev.new_status}, new residual = ${rev.new_residual} INR.`
      );
      queryClient.invalidateQueries({ queryKey: ['investigation', selectedId] });
      queryClient.invalidateQueries({ queryKey: ['investigation-audit', selectedId] });
      return rev;
    },
    onError: (err: any) => {
      setStatusMessage(`Revalidation error: ${err.message}`);
    },
  });

  // 5. Mutation: Generate & Attach Cryptographic Proof
  const proofMutation = useMutation({
    mutationFn: async () => {
      if (!report) throw new Error('No report loaded');
      setStatusMessage('Generating tamper-evident cryptographic control proof...');

      const now = new Date();
      const start = report.metadata?.period_start || new Date(now.getTime() - 3600000).toISOString();
      const end = report.metadata?.period_end || now.toISOString();
      const merchantId = report.metadata?.demo_merchant_id || report.merchant_id || 'merchant-alpha';

      // Evaluate the remediated control to get PASS result
      const verifiedResult = await evaluateControl(report.domain, {
        context: {
          merchant_id: merchantId,
          period_start: start,
          period_end: end,
          currency: 'INR',
          tolerance: '0.00',
        },
      });

      const proofId = `proof-${Date.now().toString().slice(-8)}`;
      const proof = await generateProof({
        control_result: verifiedResult,
        context: {
          merchant_id: merchantId,
          period_start: start,
          period_end: end,
          currency: 'INR',
          tolerance: '0.00',
        },
        proof_id: proofId,
      });

      trackProof(proof.proof_id);

      setStatusMessage('Attaching verified proof to investigation record in kernel...');
      await attachProofToInvestigation(selectedId, proof.proof_id);

      queryClient.invalidateQueries({ queryKey: ['investigation', selectedId] });
      queryClient.invalidateQueries({ queryKey: ['investigation-audit', selectedId] });
      return proof;
    },
    onSuccess: (proof) => {
      setStatusMessage(`Cryptographic proof ${proof.proof_id} bound successfully! Redirecting...`);
      setTimeout(() => {
        navigate(`/proofs?id=${proof.proof_id}`);
      }, 700);
    },
    onError: (err: any) => {
      setStatusMessage(`Proof attachment error: ${err.message}`);
    },
  });

  const isApproved =
    lifecycleState === 'APPROVED' ||
    lifecycleState === 'REVALIDATING' ||
    lifecycleState === 'RESOLVED' ||
    lifecycleState === 'CONTROL_PROOF' ||
    lifecycleState === 'VERIFIED';

  const isResolved =
    lifecycleState === 'RESOLVED' ||
    lifecycleState === 'CONTROL_PROOF' ||
    lifecycleState === 'VERIFIED' ||
    revalidationResult?.resolved;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-amber-950/60 text-amber-300 text-xs font-mono font-medium border border-amber-800/50">
              GOVERNANCE BOUNDARY
            </span>
            <span className="text-xs text-slate-400">Strict Human Approval & Deterministic Revalidation</span>
          </div>
          <h2 className="text-xl font-bold text-slate-100 mt-1">Approval & Governance Center</h2>
          <p className="text-xs text-slate-400 mt-0.5 max-w-3xl">
            Financial mutations are never executed by the AI Controller. Every recommended action requires explicit human authorization, followed by deterministic revalidation.
          </p>
        </div>

        {/* Case selector */}
        {trackedIds.length > 0 && (
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="text-slate-500">Case:</span>
            <select
              value={selectedId}
              onChange={(e) => setSearchParams({ id: e.target.value })}
              className="bg-[#101522] border border-[#1e2638] rounded-lg px-2.5 py-1 text-xs text-slate-200 font-mono focus:outline-none focus:border-blue-500"
            >
              {trackedIds.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {statusMessage && (
        <div className="p-3 bg-blue-950/40 border border-blue-800/60 rounded-lg text-xs font-mono text-blue-200 flex items-center justify-between">
          <span>{statusMessage}</span>
          {(revalidateMutation.isPending || proofMutation.isPending) && (
            <span className="animate-spin w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full" />
          )}
        </div>
      )}

      {selectedId ? (
        isLoading ? (
          <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-12 text-center text-xs font-mono text-slate-400">
            Loading investigation {selectedId}...
          </div>
        ) : report ? (
          <div className="space-y-6">
            {/* Top Stepper Banner */}
            <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-slate-100 font-mono">{report.investigation_id}</h3>
                    <StatusBadge status={lifecycleState} size="sm" />
                  </div>
                  <span className="text-xs text-slate-400 font-mono mt-1 block">
                    Domain: <strong className="text-slate-200">{report.domain}</strong> · Control:{' '}
                    <strong className="text-slate-200">{report.control_id}</strong>
                  </span>
                </div>

                <div className="text-right font-mono text-xs">
                  <span className="text-slate-500 block text-[10px]">RECOMMENDED ACTION</span>
                  <span className="font-bold text-amber-300">{report.recommended_action}</span>
                </div>
              </div>

              {/* Authoritative Workflow Stepper */}
              <div className="pt-2 border-t border-[#1e2638]">
                <WorkflowStepper currentState={lifecycleState} />
              </div>
            </div>

            {/* Stage 1: Human Approval Boundary */}
            <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <UserCheck className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-slate-200">Human Approval Firewall</h3>
              </div>

              <div className="p-4 bg-amber-950/20 border border-amber-900/40 rounded-lg text-xs font-mono text-amber-200/90 leading-relaxed mb-4">
                <strong>FINANCIAL ISOLATION GUARANTEE:</strong> The AI Controller is strictly read-only. Ledger mutations and remediation disbursements cannot be initiated autonomously. An authorized operator must review the root cause and sign with their Operator ID.
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
                <div className="space-y-1 font-mono text-xs">
                  <label className="text-slate-400 block text-[11px]">Authorized Controller Operator ID:</label>
                  <input
                    type="text"
                    value={approverName}
                    onChange={(e) => setApproverName(e.target.value)}
                    disabled={isApproved}
                    placeholder="e.g. controller_ops_lead"
                    className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 w-full focus:outline-none focus:border-amber-500 font-mono disabled:opacity-60"
                  />
                </div>

                <div className="flex items-center gap-3 justify-end pt-4 md:pt-0">
                  {isApproved ? (
                    <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 text-xs font-mono font-bold">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      OPERATOR APPROVAL RECORDED
                    </div>
                  ) : (
                    <>
                      <button
                        onClick={() => approveMutation.mutate({ approved: false })}
                        disabled={approveMutation.isPending}
                        className="px-4 py-2 rounded-lg bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 text-xs font-mono font-semibold transition-all disabled:opacity-50"
                      >
                        Reject Action
                      </button>
                      <button
                        onClick={() => approveMutation.mutate({ approved: true })}
                        disabled={approveMutation.isPending || !approverName.trim()}
                        className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-mono font-bold shadow-lg transition-all disabled:opacity-50"
                      >
                        {approveMutation.isPending ? 'Signing...' : 'Authorize Action'}
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Stage 2: Deterministic Revalidation Workbench */}
            <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <RotateCcw className="w-4 h-4 text-blue-400" />
                  <h3 className="text-sm font-bold text-slate-200">Deterministic Revalidation Workbench</h3>
                </div>
                {isResolved && (
                  <span className="flex items-center gap-1 text-emerald-400 text-xs font-mono font-bold">
                    <CheckCircle2 className="w-3.5 h-3.5" /> REVALIDATED PASS
                  </span>
                )}
              </div>

              <p className="text-xs text-slate-400 font-mono mb-4 leading-relaxed">
                Once approved, remediation is performed (e.g. ingesting the missing payout event). The control kernel then strictly re-evaluates the invariant to verify that the residual is reduced to 0.00 INR and status transitions to PASS.
              </p>

              <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="font-mono text-xs space-y-1">
                  <div className="text-slate-300">
                    Remediation: <strong className="text-emerald-400">Ingest Missing Payout Event (10,000.00 INR)</strong>
                  </div>
                  <div className="text-slate-500 text-[11px]">
                    Target Invariant: Expected Payout == Actual Payout (Residual: 0.00 INR)
                  </div>
                </div>

                <button
                  onClick={() => revalidateMutation.mutate()}
                  disabled={!isApproved || isResolved || revalidateMutation.isPending}
                  className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-bold shadow transition-all disabled:opacity-40"
                >
                  <RotateCcw className={`w-3.5 h-3.5 ${revalidateMutation.isPending ? 'animate-spin' : ''}`} />
                  {revalidateMutation.isPending
                    ? 'Re-evaluating Kernel...'
                    : isResolved
                    ? 'Discrepancy Resolved'
                    : 'Remediate & Revalidate'}
                </button>
              </div>

              {/* Revalidation Outcome Display */}
              {revalidationResult && (
                <div className="mt-4 p-4 bg-emerald-950/20 border border-emerald-900/50 rounded-lg font-mono text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Previous Residual:</span>
                    <span className="text-rose-400 font-bold">{revalidationResult.previous_residual} INR ({revalidationResult.previous_status})</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">New Residual:</span>
                    <span className="text-emerald-400 font-bold">{revalidationResult.new_residual} INR ({revalidationResult.new_status})</span>
                  </div>
                  <div className="flex items-center justify-between pt-1 border-t border-emerald-900/40">
                    <span className="text-slate-400">Resolved:</span>
                    <span className="text-emerald-300 font-bold">{revalidationResult.resolved ? 'TRUE' : 'FALSE'}</span>
                  </div>
                  <p className="text-[11px] text-slate-300 pt-1">{revalidationResult.explanation}</p>
                </div>
              )}
            </div>

            {/* Stage 3: Control Proof Generation */}
            <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <KeyRound className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-bold text-slate-200">Tamper-Evident Cryptographic Control Proof</h3>
                </div>
                {report.proof_id && (
                  <span className="text-xs font-mono text-emerald-400 font-bold">
                    Proof Attached: {report.proof_id}
                  </span>
                )}
              </div>

              <p className="text-xs text-slate-400 font-mono mb-4 leading-relaxed">
                Seal the verified financial control outcome with a deterministic SHA-256 Merkle root. Binds the exact evaluated events and control result into an immutable audit proof.
              </p>

              <div className="flex items-center justify-end">
                {report.proof_id ? (
                  <button
                    onClick={() => navigate(`/proofs?id=${report.proof_id}`)}
                    className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold shadow transition-all"
                  >
                    View Sealed Merkle Proof <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                ) : (
                  <button
                    onClick={() => proofMutation.mutate()}
                    disabled={!isResolved || proofMutation.isPending}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-mono font-bold shadow-lg transition-all disabled:opacity-40"
                  >
                    <KeyRound className="w-3.5 h-3.5" />
                    {proofMutation.isPending ? 'Generating Proof...' : 'Generate Control Proof'}
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : null
      ) : (
        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-12 text-center text-xs font-mono text-slate-400">
          No investigation selected for approval.
        </div>
      )}
    </div>
  );
};
