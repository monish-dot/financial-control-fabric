import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Search,
  CheckCircle2,
  XCircle,
  FileText,
  Calculator,
  History,
  ArrowRight,
  ShieldAlert,
  Layers,
} from 'lucide-react';
import {
  getInvestigation,
  getInvestigationEvidence,
  getInvestigationHypotheses,
  getInvestigationAudit,
  requestRecommendation,
} from '../api/agent';
import { getTrackedInvestigations, trackInvestigation } from '../lib/storage';
import { formatCurrency, formatTimestamp } from '../lib/formatters';
import { deriveAuthoritativeState } from '../lib/workflowState';
import { WorkflowStepper } from '../components/common/WorkflowStepper';
import { StatusBadge } from '../components/common/StatusBadge';

interface EpistemicBlock {
  tag: string;
  content: string;
}

function parseEpistemicBlocks(text: string): EpistemicBlock[] | null {
  if (!text) return null;
  const regex = /(FACT|INFERENCE|UNCERTAINTY|ROOT CAUSE|RECOMMENDATION):/g;
  const matches: { tag: string; index: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text)) !== null) {
    matches.push({ tag: m[1], index: m.index });
  }
  if (matches.length === 0) return null;

  const blocks: EpistemicBlock[] = [];
  for (let i = 0; i < matches.length; i++) {
    const current = matches[i];
    const startIndex = current.index + current.tag.length + 1;
    const endIndex = i + 1 < matches.length ? matches[i + 1].index : text.length;
    const content = text.substring(startIndex, endIndex).trim();
    if (content) {
      blocks.push({ tag: current.tag, content });
    }
  }
  return blocks.length > 0 ? blocks : null;
}

export const InvestigationPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const trackedIds = getTrackedInvestigations();
  const selectedId = searchParams.get('id') || trackedIds[0] || '';
  const [inputInvId, setInputInvId] = useState(selectedId);

  // 1. Fetch Investigation Report
  const { data: report, isLoading: reportLoading, error: reportError } = useQuery({
    queryKey: ['investigation', selectedId],
    queryFn: () => (selectedId ? getInvestigation(selectedId) : null),
    enabled: !!selectedId,
  });

  // 2. Fetch Evidence
  const { data: evidence } = useQuery({
    queryKey: ['investigation-evidence', selectedId],
    queryFn: () => (selectedId ? getInvestigationEvidence(selectedId) : []),
    enabled: !!selectedId && !!report,
  });

  // 3. Fetch Hypotheses
  const { data: hypotheses } = useQuery({
    queryKey: ['investigation-hypotheses', selectedId],
    queryFn: () => (selectedId ? getInvestigationHypotheses(selectedId) : []),
    enabled: !!selectedId && !!report,
  });

  // 4. Fetch Audit
  const { data: audit } = useQuery({
    queryKey: ['investigation-audit', selectedId],
    queryFn: () => (selectedId ? getInvestigationAudit(selectedId) : []),
    enabled: !!selectedId && !!report,
  });

  // 5. Mutation: Request Recommendation
  const recMutation = useMutation({
    mutationFn: () => requestRecommendation(selectedId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['investigation', selectedId] });
      queryClient.invalidateQueries({ queryKey: ['investigation-audit', selectedId] });
    },
  });

  const handleSelect = (id: string) => {
    trackInvestigation(id);
    setInputInvId(id);
    setSearchParams({ id });
  };

  // Authoritative lifecycle state derived strictly from backend report and audit
  const lifecycleState = deriveAuthoritativeState(report, audit);
  const rootCause = report?.root_causes?.[0];

  return (
    <div className="space-y-6">
      {/* Header & Investigation Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 text-xs font-mono font-medium border border-blue-800/50">
              AI ROOT-CAUSE INVESTIGATION
            </span>
            <span className="text-xs text-slate-400">Bounded Read-Only Evidence & Hypothesis Verification</span>
          </div>
          <h2 className="text-xl font-bold text-slate-100 mt-1">AI Controller Investigation</h2>
          <p className="text-xs text-slate-400 mt-0.5 max-w-3xl">
            Bounded evidence retrieval + hypothesis testing + deterministic calculation + human approval boundary + deterministic revalidation.
          </p>
        </div>

        {/* Search / Selector */}
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={inputInvId}
              onChange={(e) => setInputInvId(e.target.value)}
              placeholder="Investigation ID..."
              className="bg-[#101522] border border-[#1e2638] rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 font-mono w-48 sm:w-64 focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            onClick={() => handleSelect(inputInvId)}
            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-medium"
          >
            Load
          </button>
        </div>
      </div>

      {/* Tracked investigations quick pills */}
      {trackedIds.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs font-mono">
          <span className="text-slate-500 text-[11px]">Recent Cases:</span>
          {trackedIds.map((id) => (
            <button
              key={id}
              onClick={() => handleSelect(id)}
              className={`px-2.5 py-0.5 rounded text-xs transition-all ${
                selectedId === id
                  ? 'bg-blue-600/30 text-blue-200 border border-blue-500/40 font-semibold'
                  : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
              }`}
            >
              {id}
            </button>
          ))}
        </div>
      )}

      {/* Investigation Details if selected */}
      {selectedId ? (
        reportLoading ? (
          <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-12 text-center text-xs font-mono text-slate-400">
            Fetching investigation report for {selectedId}...
          </div>
        ) : reportError ? (
          <div className="bg-[#101522] border border-rose-900/40 rounded-xl p-8 text-center text-xs font-mono text-rose-300">
            Investigation '{selectedId}' not found in active controller memory. Select an existing case or run the demo from Overview.
          </div>
        ) : report ? (
          <div className="space-y-6">
            {/* Top Status Banner with Authoritative Lifecycle State */}
            <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5 space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2.5">
                    <h3 className="text-lg font-bold text-slate-100 font-mono">{report.investigation_id}</h3>
                    {/* Unified authoritative lifecycle badge */}
                    <StatusBadge status={lifecycleState} size="sm" />
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                      {report.domain}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 mt-2 font-mono leading-relaxed max-w-3xl">
                    {report.summary}
                  </p>
                </div>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  {/* Contextual Action Button depending strictly on lifecycle state */}
                  {lifecycleState === 'RECOMMENDATION_READY' && (
                    <button
                      onClick={() => recMutation.mutate()}
                      disabled={recMutation.isPending}
                      className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow border border-blue-400/40 font-mono disabled:opacity-50"
                    >
                      {recMutation.isPending ? 'Requesting...' : 'Request Recommendation'}
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}

                  {lifecycleState === 'AWAITING_APPROVAL' && (
                    <button
                      onClick={() => navigate(`/approvals?id=${report.investigation_id}`)}
                      className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow border border-amber-400/40 font-mono"
                    >
                      Proceed to Approval Center <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}

                  {(lifecycleState === 'APPROVED' || lifecycleState === 'REVALIDATING') && (
                    <button
                      onClick={() => navigate(`/approvals?id=${report.investigation_id}`)}
                      className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow border border-emerald-400/40 font-mono"
                    >
                      Open Revalidation Workbench <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}

                  {(lifecycleState === 'RESOLVED' || lifecycleState === 'CONTROL_PROOF' || lifecycleState === 'VERIFIED') && (
                    <button
                      onClick={() => {
                        if (report.proof_id) {
                          navigate(`/control-proofs?id=${report.proof_id}`);
                        } else {
                          navigate(`/approvals?id=${report.investigation_id}`);
                        }
                      }}
                      className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold shadow border border-blue-400/30 font-mono"
                    >
                      {report.proof_id ? 'Inspect Cryptographic Proof' : 'Generate Control Proof'}
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {/* Authoritative Workflow Stepper */}
              <div className="pt-3 border-t border-[#1e2638]">
                <WorkflowStepper currentState={lifecycleState} />
              </div>
            </div>

            {/* Root Cause Finding Card */}
            {rootCause && (
              <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-rose-400" />
                    <h3 className="text-sm font-bold text-slate-200">Verified Root Cause Finding</h3>
                  </div>
                  <span className="text-xs font-mono text-slate-400">
                    Confidence: {(parseFloat(rootCause.confidence || '1') * 100).toFixed(0)}%
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
                  <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">ROOT CAUSE CATEGORY</span>
                    <span className="text-sm font-bold text-rose-300">{rootCause.category}</span>
                  </div>
                  <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">FINANCIAL IMPACT</span>
                    <span className="text-sm font-bold text-slate-100">
                      {formatCurrency(rootCause.impact_amount, rootCause.currency)}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">REASONING STATUS</span>
                    <span className="text-sm font-bold text-emerald-300">{rootCause.reasoning_status}</span>
                  </div>
                </div>

                {/* Epistemic Reasoning Chain */}
                <div className="mt-4 pt-3 border-t border-slate-800 space-y-2">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
                    <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider">
                      Cognitive Reasoning Chain (FACT ➔ INFERENCE ➔ UNCERTAINTY)
                    </span>
                  </div>

                  {(() => {
                    const blocks = parseEpistemicBlocks(rootCause.description);
                    if (!blocks) {
                      return (
                        <p className="text-xs text-slate-300 font-mono p-3 bg-slate-900/40 rounded-lg border border-slate-800/80 leading-relaxed">
                          {rootCause.description}
                        </p>
                      );
                    }

                    return (
                      <div className="space-y-2 font-mono text-xs">
                        {blocks.map((b, idx) => {
                          const tagColor =
                            b.tag === 'FACT'
                              ? 'bg-blue-950/80 text-blue-300 border-blue-800/60'
                              : b.tag === 'INFERENCE'
                              ? 'bg-purple-950/80 text-purple-300 border-purple-800/60'
                              : b.tag === 'UNCERTAINTY'
                              ? 'bg-amber-950/80 text-amber-300 border-amber-800/60'
                              : b.tag === 'ROOT CAUSE'
                              ? 'bg-rose-950/80 text-rose-300 border-rose-800/60'
                              : 'bg-emerald-950/80 text-emerald-300 border-emerald-800/60';

                          return (
                            <div
                              key={idx}
                              className="p-3 bg-slate-900/50 rounded-lg border border-slate-800/80 flex flex-col sm:flex-row sm:items-baseline gap-2.5 leading-relaxed"
                            >
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold border shrink-0 ${tagColor}`}
                              >
                                {b.tag}
                              </span>
                              <span className="text-slate-300 text-xs">{b.content}</span>
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}
                </div>
              </div>
            )}

            {/* Two Column: Hypotheses Tested vs Deterministic Calculations */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Hypothesis Ledger */}
              <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <Layers className="w-4 h-4 text-blue-400" />
                  <h3 className="text-sm font-bold text-slate-200">
                    Hypothesis Ledger ({hypotheses?.length || report.hypotheses?.length || 0})
                  </h3>
                </div>
                <div className="space-y-2.5">
                  {(hypotheses?.length ? hypotheses : report.hypotheses)?.map((h) => {
                    const isSupported =
                      h.status === 'SUPPORTED' || h.reasoning_status === 'CONSISTENT' || h.reasoning_status === 'SUPPORTED';
                    return (
                      <div
                        key={h.hypothesis_id}
                        className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg text-xs font-mono space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-200">{h.description}</span>
                          <div className="flex items-center gap-1.5">
                            {isSupported ? (
                              <span className="flex items-center gap-1 text-emerald-400 text-[11px] font-bold">
                                <CheckCircle2 className="w-3.5 h-3.5" /> SUPPORTED
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-slate-500 text-[11px]">
                                <XCircle className="w-3.5 h-3.5" /> {h.status || 'REJECTED'}
                              </span>
                            )}
                          </div>
                        </div>
                        <p className="text-slate-400 text-[11px] leading-relaxed">
                          {h.explanation || h.notes || 'Evaluated against bounded evidence store.'}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Deterministic Calculator Trace */}
              <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
                <div className="flex items-center gap-2 mb-3">
                  <Calculator className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-bold text-slate-200">
                    Deterministic Calculator Trace ({report.calculations?.length || 0})
                  </h3>
                </div>
                <div className="space-y-2.5">
                  {report.calculations?.map((calc) => (
                    <div
                      key={calc.calculation_id}
                      className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg text-xs font-mono space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-200">{calc.name || calc.calculation_id}</span>
                        <span className="font-bold text-emerald-300">
                          {formatCurrency(calc.result, calc.currency)}
                        </span>
                      </div>
                      <div className="p-2 bg-black/40 rounded text-slate-400 text-[11px] font-mono">
                        Formula: {calc.formula}
                      </div>
                      {calc.calculation_trace && calc.calculation_trace.length > 0 && (
                        <div className="p-2 bg-slate-950/60 rounded text-[10px] text-slate-400 space-y-0.5 border border-slate-800/80">
                          {calc.calculation_trace.map((step, idx) => (
                            <div key={idx}>▸ {step}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Evidence Vault */}
            <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-4 h-4 text-blue-400" />
                <h3 className="text-sm font-bold text-slate-200">
                  Bounded Evidence Vault ({evidence?.length || report.evidence?.length || 0} Items Retrieved)
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="border-b border-[#1e2638] text-slate-400 bg-slate-900/40">
                    <tr>
                      <th className="py-2.5 px-3">Evidence ID</th>
                      <th className="py-2.5 px-3">Source Type</th>
                      <th className="py-2.5 px-3">Source ID</th>
                      <th className="py-2.5 px-3">Field</th>
                      <th className="py-2.5 px-3">Timestamp</th>
                      <th className="py-2.5 px-3 text-right">Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1e2638]/50">
                    {(evidence?.length ? evidence : report.evidence)?.map((item) => (
                      <tr key={item.evidence_id} className="hover:bg-slate-800/30">
                        <td className="py-2.5 px-3 font-semibold text-slate-200">{item.evidence_id}</td>
                        <td className="py-2.5 px-3 text-blue-400">{item.source_type}</td>
                        <td className="py-2.5 px-3 text-slate-300">{item.source_id}</td>
                        <td className="py-2.5 px-3 text-slate-400">{item.field}</td>
                        <td className="py-2.5 px-3 text-slate-400">{formatTimestamp(item.timestamp)}</td>
                        <td className="py-2.5 px-3 text-right font-semibold text-slate-200">{item.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Immutable Agent Audit Trail */}
            <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <History className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-bold text-slate-200">
                  Chronological Control & Investigation Timeline ({audit?.length || 0} Audit Events)
                </h3>
              </div>
              <div className="space-y-2">
                {audit?.map((item) => (
                  <div
                    key={item.audit_id}
                    className="p-2.5 bg-slate-900/40 border border-[#1e2638]/70 rounded-lg text-xs font-mono flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="flex items-center gap-3">
                      <span className="px-2 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-800/40 text-[10px] font-bold">
                        {item.action}
                      </span>
                      <span className="text-slate-300 font-semibold">{item.output_summary}</span>
                    </div>
                    <div className="text-slate-500 text-[11px] shrink-0">
                      {formatTimestamp(item.timestamp)} · <span className="text-slate-400">{item.actor}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : null
      ) : (
        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-12 text-center text-xs font-mono text-slate-400">
          No investigation selected. Click "Run Missing-Payout Demo" in Overview or launch an investigation from the Exception Center.
        </div>
      )}
    </div>
  );
};
