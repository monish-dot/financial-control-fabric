import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  AlertOctagon,
  Search,
  Filter,
  BarChart2,
  PlayCircle,
  Activity,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';
import { listResiduals, getResidualDistribution, analyzeResiduals } from '../api/residuals';
import { evaluateControl } from '../api/controls';
import { launchInvestigation } from '../api/agent';
import { trackInvestigation } from '../lib/storage';
import { formatCurrency } from '../lib/formatters';
import { StatusBadge } from '../components/common/StatusBadge';
import { ControlDomain } from '../types/controls';
import { ResidualObservation, ResidualAnalysis } from '../types/residuals';

export const ExceptionCenterPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const selectedDomain = (searchParams.get('domain') as ControlDomain) || undefined;
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [merchantFilter, setMerchantFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [analysisResult, setAnalysisResult] = useState<ResidualAnalysis | null>(null);
  const [investigatingId, setInvestigatingId] = useState<string | null>(null);

  // 1. Fetch residuals from backend with optional filters
  const { data: residuals, isLoading: residualsLoading } = useQuery({
    queryKey: ['residuals', selectedDomain, merchantFilter],
    queryFn: () =>
      listResiduals({
        domain: selectedDomain,
        merchant_id: merchantFilter.trim() || undefined,
        limit: 1000,
      }),
  });

  // 2. Fetch domain distribution stats if domain is selected
  const { data: distribution } = useQuery({
    queryKey: ['residual-distribution', selectedDomain],
    queryFn: () => (selectedDomain ? getResidualDistribution(selectedDomain) : null),
    enabled: !!selectedDomain,
  });

  // 3. Mutation: Run Anomaly & Drift Analysis via Backend Engine
  const analyzeMutation = useMutation({
    mutationFn: async (domain: ControlDomain) => {
      const domainResiduals = residuals?.filter((r) => r.domain === domain) || [];
      return analyzeResiduals(domain, {
        residuals: domainResiduals.length > 0 ? domainResiduals : undefined,
      });
    },
    onSuccess: (data) => {
      setAnalysisResult(data);
    },
  });

  // 4. Mutation: Launch AI Root-Cause Investigation from Residual
  const launchInvestigationMutation = useMutation({
    mutationFn: async (residual: ResidualObservation) => {
      const now = new Date();
      const start = new Date(now.getTime() - 3600000).toISOString();
      const end = now.toISOString();

      let context: Record<string, any> = {
        period_start: start,
        period_end: end,
        currency: residual.currency,
        tolerance: '0.00',
      };
      if (residual.domain === 'MERCHANT_PAYOUT') context.merchant_id = residual.merchant_id || 'merchant-alpha';
      if (residual.domain === 'SETTLEMENT') context.partner_id = residual.partner_id || 'partner-hdfc';
      if (residual.domain === 'NODAL_ESCROW') {
        context.account_id = residual.account_id || 'nodal-escrow-01';
        context.opening_balance = '100000.00';
        context.expected_closing_balance = '100000.00';
      }

      // Evaluate control to get ControlResult
      const evalResult = await evaluateControl(residual.domain, { context });

      // Run backend analysis to get ResidualAnalysis
      const analysis = await analyzeResiduals(residual.domain, {
        residuals: [residual],
      });

      const invId = `inv-${residual.domain.toLowerCase().slice(0, 4)}-${Date.now().toString().slice(-6)}`;
      const report = await launchInvestigation({
        investigation_id: invId,
        control_id: evalResult.control_id,
        domain: residual.domain,
        entity_id: residual.entity_id || 'entity-corp',
        account_id: residual.account_id || 'acct-main',
        merchant_id: residual.merchant_id || undefined,
        partner_id: residual.partner_id || undefined,
        period_start: start,
        period_end: end,
        control_result: evalResult,
        anomaly_score: analysis.anomaly_score,
        residual_summary: analysis,
        metadata: {
          period_start: start,
          period_end: end,
          merchant_id: residual.merchant_id,
        }
      });

      trackInvestigation(report.investigation_id);
      return report;
    },
    onSuccess: (report) => {
      navigate(`/investigations?id=${report.investigation_id}`);
    },
  });

  const domains: ControlDomain[] = [
    'NODAL_ESCROW',
    'SETTLEMENT',
    'MERCHANT_PAYOUT',
    'REVENUE_RECOGNITION',
    'CROSS_ENTITY',
  ];

  // Client-side filtering of already retrieved residuals
  const filteredResiduals = (residuals || []).filter((r) => {
    if (statusFilter && r.status !== statusFilter) return false;
    if (severityFilter && r.metadata?.severity !== severityFilter) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-amber-950/60 text-amber-300 text-xs font-mono font-medium border border-amber-800/50">
              DISCREPANCY WORKBENCH
            </span>
            <span className="text-xs text-slate-400">Residual Intelligence & Exception Clustering</span>
          </div>
          <h2 className="text-xl font-bold text-slate-100 mt-1">Exception Center</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Statistical clustering, distribution moments, and drift detection emitted by the Financial Control Kernel.
          </p>
        </div>

        {/* Domain Filter Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setSearchParams({})}
            className={`px-2.5 py-1 rounded text-xs font-mono transition-all ${
              !selectedDomain
                ? 'bg-blue-600 text-white font-semibold shadow'
                : 'bg-[#101522] text-slate-400 hover:text-slate-200 border border-[#1e2638]'
            }`}
          >
            ALL DOMAINS
          </button>
          {domains.map((dom) => (
            <button
              key={dom}
              onClick={() => setSearchParams({ domain: dom })}
              className={`px-2.5 py-1 rounded text-xs font-mono transition-all ${
                selectedDomain === dom
                  ? 'bg-blue-600 text-white font-semibold shadow'
                  : 'bg-[#101522] text-slate-400 hover:text-slate-200 border border-[#1e2638]'
              }`}
            >
              {dom}
            </button>
          ))}
        </div>
      </div>

      {/* Distribution Statistics & Backend Anomaly Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Statistics from Backend */}
        <div className="lg:col-span-2 bg-[#101522] border border-[#1e2638] rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-blue-400" />
              <h3 className="text-sm font-bold text-slate-200">
                {selectedDomain ? `${selectedDomain} Population Statistics` : 'Statistical Distribution (Select Domain)'}
              </h3>
            </div>
            {selectedDomain && (
              <button
                onClick={() => {
                  analyzeMutation.mutate(selectedDomain);
                }}
                disabled={analyzeMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1 rounded bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 border border-blue-500/40 text-xs font-mono font-medium disabled:opacity-50"
              >
                <PlayCircle className="w-3.5 h-3.5" />
                {analyzeMutation.isPending ? 'Analyzing...' : 'Run Drift Analysis'}
              </button>
            )}
          </div>

          {selectedDomain && distribution?.statistics ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                <div className="p-3 rounded bg-slate-900/60 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">OBSERVATIONS</span>
                  <span className="text-base font-bold text-slate-100">
                    {distribution.statistics.count}
                  </span>
                </div>
                <div className="p-3 rounded bg-slate-900/60 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">MEAN RESIDUAL</span>
                  <span className="text-base font-bold text-slate-100">
                    {distribution.statistics.mean}
                  </span>
                </div>
                <div className="p-3 rounded bg-slate-900/60 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">MEDIAN</span>
                  <span className="text-base font-bold text-slate-100">
                    {distribution.statistics.median}
                  </span>
                </div>
                <div className="p-3 rounded bg-slate-900/60 border border-slate-800">
                  <span className="text-[10px] text-slate-500 block">STD DEVIATION</span>
                  <span className="text-base font-bold text-slate-100 truncate">
                    {distribution.statistics.standard_deviation
                      ? parseFloat(distribution.statistics.standard_deviation).toFixed(3)
                      : '0.000'}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                <div className="p-2.5 rounded bg-slate-900/40 border border-slate-800/80">
                  <span className="text-[10px] text-slate-500 block">P95 VALUE</span>
                  <span className="text-sm font-semibold text-slate-200">{distribution.statistics.p95}</span>
                </div>
                <div className="p-2.5 rounded bg-slate-900/40 border border-slate-800/80">
                  <span className="text-[10px] text-slate-500 block">P99 VALUE</span>
                  <span className="text-sm font-semibold text-slate-200">{distribution.statistics.p99}</span>
                </div>
                <div className="p-2.5 rounded bg-slate-900/40 border border-slate-800/80">
                  <span className="text-[10px] text-slate-500 block">ZERO-RESIDUAL RATIO</span>
                  <span className="text-sm font-semibold text-emerald-400">
                    {distribution.statistics.zero_residual_ratio || '1.00'}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-slate-900/40 border border-slate-800/80">
                  <span className="text-[10px] text-slate-500 block">DIRECTIONAL BIAS</span>
                  <span className="text-sm font-semibold text-slate-300">
                    +{distribution.statistics.positive_ratio || '0'} / -{distribution.statistics.negative_ratio || '0'}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-400 py-8 text-center font-mono">
              Select a control domain from the top pills to inspect population moments and execute drift analysis.
            </div>
          )}
        </div>

        {/* Backend Anomaly Score Card */}
        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <AlertOctagon className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-bold text-slate-200">Backend Anomaly Engine</h3>
            </div>
            {analysisResult ? (
              <div className="space-y-3 text-xs font-mono">
                <div className="flex items-center justify-between pb-2 border-b border-[#1e2638]">
                  <span className="text-slate-400">Severity (Backend Authoritative)</span>
                  <StatusBadge status={analysisResult.anomaly_score.severity} size="sm" />
                </div>
                <div className="flex items-center justify-between pb-2 border-b border-[#1e2638]">
                  <span className="text-slate-400">Anomaly Score</span>
                  <span className="font-bold text-slate-100">{analysisResult.anomaly_score.score}</span>
                </div>
                {analysisResult.distribution_shift && (
                  <div className="flex items-center justify-between pb-2 border-b border-[#1e2638]">
                    <span className="text-slate-400">Wasserstein Dist / PSI</span>
                    <span className="text-slate-200 text-[11px]">
                      {analysisResult.distribution_shift.wasserstein_distance} /{' '}
                      {parseFloat(analysisResult.distribution_shift.population_stability_index || '0').toFixed(2)}
                    </span>
                  </div>
                )}
                {analysisResult.temporal_metrics && (
                  <div className="flex items-center justify-between pb-2 border-b border-[#1e2638]">
                    <span className="text-slate-400">CUSUM Shift Detected</span>
                    <span
                      className={`font-bold ${
                        analysisResult.temporal_metrics.cusum_change_detected
                          ? 'text-rose-400'
                          : 'text-emerald-400'
                      }`}
                    >
                      {analysisResult.temporal_metrics.cusum_change_detected ? 'TRUE' : 'FALSE'}
                    </span>
                  </div>
                )}
                {analysisResult.anomaly_score.signals && analysisResult.anomaly_score.signals.length > 0 && (
                  <div className="pt-1">
                    <span className="text-[10px] text-slate-500 block mb-1 uppercase">Active Signals:</span>
                    <div className="flex flex-wrap gap-1">
                      {analysisResult.anomaly_score.signals.map((sig, i) => (
                        <span key={i} className="px-1.5 py-0.5 rounded bg-amber-950/60 text-amber-300 text-[10px] border border-amber-800/40">
                          {sig}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-400 font-mono py-4 leading-relaxed">
                Run Drift Analysis to evaluate distribution shift, Wasserstein distance, CUSUM change, and severity computed by the backend engine.
              </p>
            )}
          </div>

          <div className="text-[10px] text-slate-500 font-mono mt-3 pt-3 border-t border-[#1e2638]">
            Source: ResidualIntelligenceEngine (Backend Freeze)
          </div>
        </div>
      </div>

      {/* Exception Filtering Controls */}
      <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4 flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="FAIL">FAIL (Exceptions Only)</option>
            <option value="PASS">PASS (Zero Invariant)</option>
          </select>

          {/* Severity filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Severities</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="ANOMALOUS">ANOMALOUS</option>
            <option value="WATCH">WATCH</option>
            <option value="NORMAL">NORMAL</option>
          </select>

          {/* Merchant search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Merchant filter..."
              value={merchantFilter}
              onChange={(e) => setMerchantFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg pl-8 pr-2.5 py-1 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 w-44"
            />
          </div>
        </div>

        <span className="text-xs font-mono text-slate-400">
          Showing {filteredResiduals.length} of {residuals?.length || 0} observations
        </span>
      </div>

      {/* Residual Observations Table */}
      <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-bold text-slate-200">
              Residual Discrepancy Observations ({filteredResiduals.length})
            </h3>
          </div>
        </div>

        {residualsLoading ? (
          <div className="py-12 text-center text-xs text-slate-400 font-mono">
            Loading residual observations from kernel...
          </div>
        ) : filteredResiduals.length > 0 ? (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="border-b border-[#1e2638] text-slate-400 bg-slate-900/40">
                  <tr>
                    <th className="py-2.5 px-3">Residual ID</th>
                    <th className="py-2.5 px-3">Domain</th>
                    <th className="py-2.5 px-3">Scope (Merchant / Partner)</th>
                    <th className="py-2.5 px-3">Root Cause Hint</th>
                    <th className="py-2.5 px-3 text-right">Expected</th>
                    <th className="py-2.5 px-3 text-right">Actual</th>
                    <th className="py-2.5 px-3 text-right">Residual</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                    <th className="py-2.5 px-3 text-right">Investigation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2638]/50">
                  {filteredResiduals.slice(page * pageSize, (page + 1) * pageSize).map((r) => {
                    const isFail = r.status === 'FAIL';
                    const isCritical =
                      isFail &&
                      (r.metadata?.severity === 'CRITICAL' ||
                        Math.abs(parseFloat(r.residual_amount || '0')) >= 5000);

                    return (
                      <tr
                        key={r.residual_id}
                        className={`transition-all ${
                          isCritical
                            ? 'bg-rose-950/20 border-l-4 border-l-rose-500 hover:bg-rose-950/30'
                            : isFail
                            ? 'bg-amber-950/10 border-l-4 border-l-amber-500 hover:bg-amber-950/20'
                            : 'hover:bg-slate-800/30'
                        }`}
                      >
                        <td className="py-3 px-3 font-semibold text-slate-200">
                          <div className="flex items-center gap-1.5">
                            {isCritical && <ShieldAlert className="w-3.5 h-3.5 text-rose-400 shrink-0" />}
                            <span>{r.residual_id}</span>
                          </div>
                        </td>
                        <td className="py-3 px-3 text-slate-300">{r.domain}</td>
                        <td className="py-3 px-3 text-slate-400">
                          {r.merchant_id ? (
                            <span className="text-amber-300/90">{r.merchant_id}</span>
                          ) : r.partner_id ? (
                            <span className="text-purple-300/90">{r.partner_id}</span>
                          ) : (
                            r.entity_id || '-'
                          )}
                        </td>
                        <td className="py-3 px-3">
                          {r.metadata?.root_cause_hint ? (
                            <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-200 border border-slate-700 text-[10px] font-bold">
                              {r.metadata.root_cause_hint}
                            </span>
                          ) : (
                            <span className="text-slate-500 text-[11px]">-</span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-right">{formatCurrency(r.expected_amount, r.currency)}</td>
                        <td className="py-3 px-3 text-right">{formatCurrency(r.actual_amount, r.currency)}</td>
                        <td
                          className={`py-3 px-3 text-right font-bold ${
                            r.residual_amount !== '0.00' && r.residual_amount !== '0'
                              ? 'text-rose-400'
                              : 'text-emerald-400'
                          }`}
                        >
                          {formatCurrency(r.residual_amount, r.currency)}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <StatusBadge status={r.status} size="sm" />
                        </td>
                        <td className="py-3 px-3 text-right">
                          <button
                            onClick={() => {
                              setInvestigatingId(r.residual_id);
                              launchInvestigationMutation.mutate(r);
                            }}
                            disabled={
                              launchInvestigationMutation.isPending &&
                              investigatingId === r.residual_id
                            }
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-all disabled:opacity-50 font-mono font-medium ${
                              isCritical
                                ? 'bg-rose-600/30 hover:bg-rose-600/50 text-rose-200 border border-rose-500/50'
                                : 'bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/40'
                            }`}
                          >
                            <Search className="w-3 h-3" />
                            {launchInvestigationMutation.isPending && investigatingId === r.residual_id
                              ? 'Starting...'
                              : 'Launch AI Investigation'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="mt-4 pt-3 border-t border-[#1e2638] flex flex-col sm:flex-row items-center justify-between gap-3 text-xs font-mono text-slate-400">
              <div className="flex items-center gap-2">
                <span>Rows per page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(0);
                  }}
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-0.5 text-slate-200"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
                <span className="text-slate-500">
                  Showing {filteredResiduals.length > 0 ? page * pageSize + 1 : 0} -{' '}
                  {Math.min((page + 1) * pageSize, filteredResiduals.length)} of {filteredResiduals.length}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="p-1 rounded bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800 disabled:opacity-30"
                  title="Previous page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-slate-300">
                  Page {page + 1} of {Math.max(1, Math.ceil(filteredResiduals.length / pageSize))}
                </span>
                <button
                  onClick={() =>
                    setPage((p) =>
                      (p + 1) * pageSize < filteredResiduals.length ? p + 1 : p
                    )
                  }
                  disabled={(page + 1) * pageSize >= filteredResiduals.length}
                  className="p-1 rounded bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800 disabled:opacity-30"
                  title="Next page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-12 text-slate-500 text-xs font-mono">
            No residual observations found matching the selected filters.
          </div>
        )}
      </div>
    </div>
  );
};
