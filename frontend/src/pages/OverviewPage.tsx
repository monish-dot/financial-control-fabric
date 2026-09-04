import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  Play,
  ArrowRight,
  TrendingUp,
  FileSpreadsheet,
  AlertTriangle,
  Layers,
} from 'lucide-react';
import { listControls, evaluateControl } from '../api/controls';
import { listResiduals, getResidualDistribution, analyzeResiduals } from '../api/residuals';
import { createEvent, listEvents } from '../api/events';
import { launchInvestigation } from '../api/agent';
import { trackInvestigation } from '../lib/storage';
import { formatCurrency, formatMetric } from '../lib/formatters';
import { StatusBadge } from '../components/common/StatusBadge';
import { ControlDomain } from '../types/controls';

export const OverviewPage: React.FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [evaluatingDomain, setEvaluatingDomain] = useState<ControlDomain | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoMessage, setDemoMessage] = useState<string | null>(null);

  // 1. Fetch registered controls
  const { data: controls, isLoading: controlsLoading } = useQuery({
    queryKey: ['controls'],
    queryFn: listControls,
  });

  // 2. Fetch all residuals for KPI summary
  const { data: residuals } = useQuery({
    queryKey: ['residuals'],
    queryFn: () => listResiduals({ limit: 1000 }),
  });

  // 3. Fetch population sample to check transaction count
  const { data: sampleEvents } = useQuery({
    queryKey: ['events-population-sample'],
    queryFn: () => listEvents({ limit: 1000 }),
  });

  // 4. Quick evaluation mutation
  const evalMutation = useMutation({
    mutationFn: async (domain: ControlDomain) => {
      const start = '2026-09-01T00:00:00Z';
      const end = '2026-09-05T00:00:00Z';

      let context: Record<string, any> = {
        period_start: start,
        period_end: end,
        currency: 'INR',
        tolerance: '0.00',
      };

      if (domain === 'MERCHANT_PAYOUT') {
        context.merchant_id = 'merchant-alpha';
      } else if (domain === 'SETTLEMENT') {
        context.partner_id = 'partner-hdfc';
      } else if (domain === 'NODAL_ESCROW') {
        context.account_id = 'nodal-escrow-01';
        context.opening_balance = '100000.00';
        context.expected_closing_balance = '100000.00';
      } else if (domain === 'REVENUE_RECOGNITION') {
        context.entity_id = 'entity-corp';
      } else if (domain === 'CROSS_ENTITY') {
        context.source_entity_id = 'entity-corp';
        context.destination_entity_id = 'entity-subsidiary-1';
      }

      return evaluateControl(domain, { context });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['residuals'] });
    },
  });

  // 5. Scoped Missing-Payout End-to-End Demo Flow Runner
  const runDemoFlow = async () => {
    setDemoLoading(true);
    setDemoMessage('Step 1/4: Ingesting payment event for isolated merchant...');
    try {
      const demoRunId = Date.now().toString().slice(-6);
      const demoMerchantId = `merchant-demo-${demoRunId}`;
      const now = new Date();
      const start = new Date(now.getTime() - 3600000).toISOString();
      const end = now.toISOString();

      // Ingest payment without payout for this scoped merchant
      const paymentEventId = `payment-demo-${demoRunId}`;
      const paymentRes = await createEvent({
        event_id: paymentEventId,
        event_type: 'PAYMENT',
        source_system: 'gateway',
        source_id: `gw_${demoRunId}`,
        merchant_id: demoMerchantId,
        entity_id: 'entity-corp',
        account_id: 'acct-main',
        partner_id: 'partner-hdfc',
        amount: '10000.00',
        currency: 'INR',
        event_timestamp: start,
        effective_timestamp: start,
        status: 'posted',
        metadata: { channel: 'UPI', scenario: 'missing_payout' },
      });

      setDemoMessage('Step 2/4: Evaluating Merchant Payout Entitlement control in kernel...');
      const evalResult = await evaluateControl('MERCHANT_PAYOUT', {
        events: [paymentRes.event],
        context: {
          merchant_id: demoMerchantId,
          period_start: start,
          period_end: end,
          currency: 'INR',
          tolerance: '0.00',
        },
      });

      setDemoMessage('Step 3/4: Analyzing residual variance and distribution drift...');
      const analysisResult = await analyzeResiduals('MERCHANT_PAYOUT', {
        residuals: [
          {
            residual_id: `res-demo-${demoRunId}`,
            control_id: evalResult.control_id,
            domain: 'MERCHANT_PAYOUT',
            timestamp: start,
            expected_amount: evalResult.expected_amount,
            actual_amount: evalResult.actual_amount,
            residual_amount: evalResult.residual_amount,
            currency: 'INR',
            status: evalResult.status,
          },
        ],
        baseline_residuals: [
          {
            residual_id: 'base-res-001',
            control_id: evalResult.control_id,
            domain: 'MERCHANT_PAYOUT',
            timestamp: start,
            expected_amount: '10000.00',
            actual_amount: '10000.00',
            residual_amount: '0.00',
            currency: 'INR',
            status: 'PASS',
          },
        ],
      });

      setDemoMessage('Step 4/4: Launching bounded AI investigation...');
      const investigationId = `inv-demo-${demoRunId}`;
      const report = await launchInvestigation({
        investigation_id: investigationId,
        control_id: evalResult.control_id,
        domain: 'MERCHANT_PAYOUT',
        entity_id: 'entity-corp',
        account_id: 'acct-main',
        merchant_id: demoMerchantId,
        partner_id: 'partner-hdfc',
        period_start: start,
        period_end: end,
        control_result: evalResult,
        anomaly_score: analysisResult.anomaly_score,
        residual_summary: analysisResult,
        metadata: {
          demo_merchant_id: demoMerchantId,
          payment_event_id: paymentEventId,
          period_start: start,
          period_end: end,
        },
      });

      trackInvestigation(report.investigation_id);
      setDemoMessage('Investigation created successfully! Redirecting to AI Controller Workspace...');
      setTimeout(() => {
        navigate(`/investigations?id=${report.investigation_id}`);
      }, 600);
    } catch (err: any) {
      setDemoMessage(`Error running demo: ${err.message}`);
      setDemoLoading(false);
    }
  };

  const totalEventsCount = sampleEvents?.length || 0;
  const failCount = residuals?.filter((r) => r.status === 'FAIL').length || 0;
  const criticalCount = residuals?.filter(
    (r) => r.metadata?.severity === 'CRITICAL' || Math.abs(parseFloat(r.residual_amount || '0')) >= 5000
  ).length || 0;
  const totalResidualAmount = residuals?.reduce(
    (acc, r) => acc + Math.abs(parseFloat(r.residual_amount || '0')),
    0
  ) || 0;

  return (
    <div className="space-y-6">
      {/* Top Banner & Demo Quick Action */}
      <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 text-xs font-mono font-medium border border-blue-800/50">
              OPERATIONAL COCKPIT
            </span>
            <span className="text-xs text-slate-400">Population-Scale Financial Control Fabric</span>
          </div>
          <h2 className="text-xl font-bold text-slate-100 mt-1">Population Control Health & Invariant Status</h2>
          <p className="text-xs text-slate-400 mt-0.5 max-w-2xl">
            Real-time monitoring across five deterministic financial controls. The AI Controller executes bounded evidence retrieval, hypothesis testing, and deterministic calculations under strict human governance.
          </p>
        </div>

        {/* Demo Launcher */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <button
            onClick={runDemoFlow}
            disabled={demoLoading}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-blue-950/50 border border-blue-400/30 transition-all disabled:opacity-60 font-mono"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            {demoLoading ? 'Running Demo...' : 'Run Missing-Payout Demo'}
          </button>
        </div>
      </div>

      {demoMessage && (
        <div className="p-3 bg-blue-950/40 border border-blue-800/60 rounded-lg text-xs font-mono text-blue-200 flex items-center justify-between">
          <span>{demoMessage}</span>
          {demoLoading && <span className="animate-spin w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full" />}
        </div>
      )}

      {/* Population-Level KPI Hierarchy */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">

        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4 min-w-0 overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] font-medium uppercase tracking-wider">Transaction Population</span>
            <Layers className="w-4 h-4 text-blue-400 shrink-0" />
          </div>
          <div className="text-2xl font-bold font-mono text-slate-100 truncate">
            {totalEventsCount > 0 ? `${totalEventsCount.toLocaleString()}+` : '1,000+'}
          </div>
          <p className="text-[10px] text-slate-500 mt-1 font-mono truncate">Streaming SQLite events</p>
        </div>

        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4 min-w-0 overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] font-medium uppercase tracking-wider">Control Health</span>
            <FileSpreadsheet className="w-4 h-4 text-emerald-400 shrink-0" />
          </div>
          <div className="text-2xl font-bold font-mono text-slate-100 truncate">
            {controlsLoading ? '...' : `${controls?.length || 5} Controls`}
          </div>
          <p className="text-[10px] text-slate-500 mt-1 font-mono truncate">Deterministic invariant checks</p>
        </div>

        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4 min-w-0 overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] font-medium uppercase tracking-wider">Exceptions Detected</span>
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-300 truncate">{failCount}</div>
          <p className="text-[10px] text-slate-500 mt-1 font-mono truncate">Residual discrepancies</p>
        </div>

        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4 min-w-0 overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] font-medium uppercase tracking-wider">Critical Severity</span>
            <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
          </div>
          <div className="text-2xl font-bold font-mono text-rose-300 truncate">{criticalCount}</div>
          <p className="text-[10px] text-slate-500 mt-1 font-mono truncate">Mandatory review threshold</p>
        </div>

        <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4 min-w-0 overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[10px] font-medium uppercase tracking-wider">Residual Exposure</span>
            <TrendingUp className="w-4 h-4 text-purple-400 shrink-0" />
          </div>
          <div
            className="text-2xl font-bold font-mono text-purple-300 truncate"
            title={formatCurrency(totalResidualAmount.toFixed(2), 'INR')}
          >
            {formatCurrency(totalResidualAmount.toFixed(2), 'INR')}
          </div>
          <p className="text-[10px] text-slate-500 mt-1 font-mono truncate">Absolute aggregate residual sum</p>
        </div>
      </div>

      {/* 5 Financial Controls Grid */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
            Deterministic Financial Controls
          </h3>
          <span className="text-xs text-slate-400 font-mono">Click to evaluate or view distribution</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {controls?.map((control) => (
            <ControlCardItem
              key={control.domain}
              control={control}
              onEvaluate={() => {
                setEvaluatingDomain(control.domain);
                evalMutation.mutate(control.domain);
              }}
              isEvaluating={evalMutation.isPending && evaluatingDomain === control.domain}
            />
          ))}
        </div>
      </div>

      {/* Recent Residuals Quick Table */}
      <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-200">Recent Residual Observations</h3>
            <p className="text-xs text-slate-400">Emitted by the Financial Control Kernel</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/transactions')}
              className="text-xs text-slate-400 hover:text-slate-200 font-medium font-mono"
            >
              View All 1,000+ Events ➔
            </button>
            <button
              onClick={() => navigate('/exceptions')}
              className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-medium font-mono"
            >
              Exception Center <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {residuals && residuals.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-[#1e2638] text-slate-400 bg-slate-900/40">
                <tr>
                  <th className="py-2.5 px-3">Residual ID</th>
                  <th className="py-2.5 px-3">Domain</th>
                  <th className="py-2.5 px-3 text-right">Expected</th>
                  <th className="py-2.5 px-3 text-right">Actual</th>
                  <th className="py-2.5 px-3 text-right">Residual</th>
                  <th className="py-2.5 px-3 text-center">Status</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2638]/50">
                {residuals.slice(0, 6).map((r) => (
                  <tr key={r.residual_id} className="hover:bg-slate-800/30">
                    <td className="py-2.5 px-3 font-semibold text-slate-200">{r.residual_id}</td>
                    <td className="py-2.5 px-3 text-slate-300">{r.domain}</td>
                    <td className="py-2.5 px-3 text-right">{formatCurrency(r.expected_amount, r.currency)}</td>
                    <td className="py-2.5 px-3 text-right">{formatCurrency(r.actual_amount, r.currency)}</td>
                    <td
                      className={`py-2.5 px-3 text-right font-bold ${
                        r.residual_amount !== '0.00' && r.residual_amount !== '0'
                          ? 'text-rose-400'
                          : 'text-emerald-400'
                      }`}
                    >
                      {formatCurrency(r.residual_amount, r.currency)}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <StatusBadge status={r.status} size="sm" />
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => navigate(`/exceptions?domain=${r.domain}`)}
                        className="text-xs text-blue-400 hover:text-blue-300 underline"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-slate-500 text-xs font-mono">
            No residuals recorded yet. Click "Run Missing-Payout Demo" above to evaluate events.
          </div>
        )}
      </div>
    </div>
  );
};

interface ControlCardItemProps {
  control: { domain: ControlDomain; control_id: string; description: string };
  onEvaluate: () => void;
  isEvaluating: boolean;
}

const ControlCardItem: React.FC<ControlCardItemProps> = ({ control, onEvaluate, isEvaluating }) => {
  const navigate = useNavigate();
  const { data: dist } = useQuery({
    queryKey: ['residual-dist', control.domain],
    queryFn: () => getResidualDistribution(control.domain),
  });

  return (
    <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4 flex flex-col justify-between hover:border-blue-500/30 transition-all">
      <div>
        <div className="flex items-center justify-between gap-2 mb-2">
          <span className="text-[11px] font-mono font-semibold text-blue-400 bg-blue-950/60 px-2 py-0.5 rounded border border-blue-800/40 shrink-0">
            {control.domain}
          </span>
          <span className="text-[10px] text-slate-500 font-mono truncate" title={control.control_id}>
            {control.control_id}
          </span>
        </div>
        <p className="text-xs text-slate-300 line-clamp-2 mt-1">{control.description}</p>

        {/* Statistical Summary from Backend */}
        <div className="mt-4 pt-3 border-t border-[#1e2638]/70 grid grid-cols-3 gap-2 text-center text-xs font-mono">
          <div className="min-w-0 overflow-hidden">
            <div className="text-[10px] text-slate-500 truncate">OBSERVATIONS</div>
            <div className="text-slate-200 font-semibold truncate">{dist?.statistics?.count ?? 0}</div>
          </div>
          <div className="min-w-0 overflow-hidden">
            <div className="text-[10px] text-slate-500 truncate">MEAN</div>
            <div
              className="text-slate-200 font-semibold truncate"
              title={dist?.statistics?.mean ? `Exact mean: ${dist.statistics.mean}` : undefined}
            >
              {dist?.statistics?.mean ? formatMetric(dist.statistics.mean) : '0.00'}
            </div>
          </div>
          <div className="min-w-0 overflow-hidden">
            <div className="text-[10px] text-slate-500 truncate">P95</div>
            <div
              className="text-slate-200 font-semibold truncate"
              title={dist?.statistics?.p95 ? `Exact P95: ${dist.statistics.p95}` : undefined}
            >
              {dist?.statistics?.p95 ? formatMetric(dist.statistics.p95) : '0.00'}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 pt-3 flex items-center gap-2">
        <button
          onClick={onEvaluate}
          disabled={isEvaluating}
          className="flex-1 px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 transition-all disabled:opacity-50 font-mono"
        >
          {isEvaluating ? 'Evaluating...' : 'Evaluate Invariant'}
        </button>
        <button
          onClick={() => navigate(`/exceptions?domain=${control.domain}`)}
          className="px-2.5 py-1.5 rounded bg-slate-900 border border-slate-800 hover:bg-slate-800 text-xs text-slate-400 hover:text-slate-200"
          title="View Domain Exceptions"
        >
          <ShieldAlert className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
