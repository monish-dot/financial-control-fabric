import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  GitCompare,
  ArrowRight,
  Play,
} from 'lucide-react';
import { reconcileSettlement } from '../api/reconciliation';
import { formatCurrency } from '../lib/formatters';
import { StatusBadge } from '../components/common/StatusBadge';
import { ReconciliationItem, ReconciliationResult } from '../types/reconciliation';

export const ReconciliationPage: React.FC = () => {
  const [activeReconciliation, setActiveReconciliation] = useState<ReconciliationResult | null>(null);

  // Default scenario items representing many-to-many allocation
  const defaultInternal: ReconciliationItem[] = [
    {
      item_id: 'obl-001',
      side: 'INTERNAL',
      item_type: 'SETTLEMENT_OBLIGATION',
      amount: '100.00',
      currency: 'INR',
      timestamp: '2026-09-03T12:00:00Z',
      entity_id: 'entity-corp',
      partner_id: 'partner-hdfc',
    },
    {
      item_id: 'obl-002',
      side: 'INTERNAL',
      item_type: 'SETTLEMENT_OBLIGATION',
      amount: '200.00',
      currency: 'INR',
      timestamp: '2026-09-03T12:00:00Z',
      entity_id: 'entity-corp',
      partner_id: 'partner-hdfc',
    },
    {
      item_id: 'obl-003',
      side: 'INTERNAL',
      item_type: 'SETTLEMENT_OBLIGATION',
      amount: '300.00',
      currency: 'INR',
      timestamp: '2026-09-03T12:00:00Z',
      entity_id: 'entity-corp',
      partner_id: 'partner-hdfc',
    },
  ];

  const defaultExternal: ReconciliationItem[] = [
    {
      item_id: 'bank-cred-001',
      side: 'EXTERNAL',
      item_type: 'BANK_SETTLEMENT',
      amount: '250.00',
      currency: 'INR',
      timestamp: '2026-09-03T12:00:00Z',
      entity_id: 'entity-corp',
      partner_id: 'partner-hdfc',
    },
    {
      item_id: 'bank-cred-002',
      side: 'EXTERNAL',
      item_type: 'BANK_SETTLEMENT',
      amount: '350.00',
      currency: 'INR',
      timestamp: '2026-09-03T12:00:00Z',
      entity_id: 'entity-corp',
      partner_id: 'partner-hdfc',
    },
  ];

  const [internalItems] = useState<ReconciliationItem[]>(defaultInternal);
  const [externalItems] = useState<ReconciliationItem[]>(defaultExternal);

  // Mutation: Run OR-Tools CP-SAT Many-to-Many Reconciliation
  const reconMutation = useMutation({
    mutationFn: () =>
      reconcileSettlement({
        internal_items: internalItems,
        external_items: externalItems,
        constraints: {
          normalize_references: true,
          minimum_compatibility_score: '0',
        },
      }),
    onSuccess: (data) => {
      setActiveReconciliation(data);
    },
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 text-xs font-mono font-medium border border-blue-800/50">
              OR-TOOLS CP-SAT SOLVER
            </span>
            <span className="text-xs text-slate-400">Deterministic Many-to-Many Optimization</span>
          </div>
          <h2 className="text-xl font-bold text-slate-100 mt-1">Settlement Reconciliation Workbench</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Exact mathematical constraint optimization for multi-bank obligations and batched settlements. Backend allocations are authoritative.
          </p>
        </div>

        <button
          onClick={() => reconMutation.mutate()}
          disabled={reconMutation.isPending}
          className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold shadow border border-blue-400/30 transition-all disabled:opacity-60 font-mono"
        >
          <Play className="w-3.5 h-3.5 fill-current" />
          {reconMutation.isPending ? 'Solving Invariants...' : 'Run Many-to-Many Solver'}
        </button>
      </div>

      {/* KPI Cards (when reconciliation run) */}
      {activeReconciliation && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4">
            <span className="text-[10px] font-mono text-slate-500 block uppercase">Matched Amount</span>
            <span className="text-2xl font-bold font-mono text-emerald-300">
              {formatCurrency(activeReconciliation.matched_amount, activeReconciliation.currency)}
            </span>
            <span className="text-[11px] text-slate-400 font-mono block mt-1">
              Match rate: {(parseFloat(activeReconciliation.match_rate) * 100).toFixed(0)}%
            </span>
          </div>

          <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4">
            <span className="text-[10px] font-mono text-slate-500 block uppercase">Unmatched Internal</span>
            <span className="text-2xl font-bold font-mono text-slate-200">
              {formatCurrency(activeReconciliation.unmatched_internal_amount, activeReconciliation.currency)}
            </span>
            <span className="text-[11px] text-slate-400 font-mono block mt-1">Residual internal obligation</span>
          </div>

          <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4">
            <span className="text-[10px] font-mono text-slate-500 block uppercase">Unmatched External</span>
            <span className="text-2xl font-bold font-mono text-slate-200">
              {formatCurrency(activeReconciliation.unmatched_external_amount, activeReconciliation.currency)}
            </span>
            <span className="text-[11px] text-slate-400 font-mono block mt-1">Residual bank settlement</span>
          </div>

          <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4">
            <span className="text-[10px] font-mono text-slate-500 block uppercase">Solver Outcome</span>
            <div className="mt-1">
              <StatusBadge status={activeReconciliation.status} size="sm" />
            </div>
            <span className="text-[11px] text-slate-400 font-mono block mt-1">
              {activeReconciliation.allocation_count} discrete allocations
            </span>
          </div>
        </div>
      )}

      {/* Visual Many-to-Many Allocation Diagram */}
      <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
        <div className="flex items-center justify-between pb-3 border-b border-[#1e2638] mb-4">
          <div className="flex items-center gap-2">
            <GitCompare className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-bold text-slate-200">
              Visual Allocation Flow (Internal Obligations ➔ External Settlements)
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-500">
            Backend OR-Tools Optimization
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
          {/* Internal Obligations Column */}
          <div className="space-y-3">
            <div className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>Internal Items ({internalItems.length})</span>
              <span>₹600.00</span>
            </div>
            <div className="space-y-2.5">
              {internalItems.map((item) => (
                <div
                  key={item.item_id}
                  className="p-3 bg-slate-900/80 border border-slate-800 rounded-lg font-mono text-xs hover:border-blue-500/40 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-200">{item.item_id}</span>
                    <span className="font-bold text-blue-300">
                      {formatCurrency(item.amount, item.currency)}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500 block mt-1">{item.item_type}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Allocations Column */}
          <div className="space-y-3">
            <div className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider text-center">
              <span>OR-Tools Allocations ({activeReconciliation?.allocations.length || 0})</span>
            </div>
            {activeReconciliation && activeReconciliation.allocations.length > 0 ? (
              <div className="space-y-2.5">
                {activeReconciliation.allocations.map((alloc) => (
                  <div
                    key={alloc.allocation_id}
                    className="p-3 bg-blue-950/30 border border-blue-800/50 rounded-lg font-mono text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-blue-300 font-bold">{alloc.internal_item_id}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                      <span className="text-emerald-300 font-bold">{alloc.external_item_id}</span>
                    </div>
                    <div className="flex items-center justify-between pt-1 border-t border-blue-900/40">
                      <span className="text-slate-400 text-[10px]">Allocated:</span>
                      <span className="font-bold text-emerald-400">
                        {formatCurrency(alloc.allocated_amount, alloc.currency)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-slate-500">
                      <span>Conf: {(parseFloat(alloc.confidence) * 100).toFixed(0)}%</span>
                      <span className="text-emerald-400">Satisfied</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center bg-slate-900/30 rounded-lg border border-dashed border-slate-800 text-xs font-mono text-slate-500">
                Click "Run Many-to-Many Solver" above to compute deterministic allocations.
              </div>
            )}
          </div>

          {/* External Settlements Column */}
          <div className="space-y-3">
            <div className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>External Items ({externalItems.length})</span>
              <span>₹600.00</span>
            </div>
            <div className="space-y-2.5">
              {externalItems.map((item) => (
                <div
                  key={item.item_id}
                  className="p-3 bg-slate-900/80 border border-slate-800 rounded-lg font-mono text-xs hover:border-emerald-500/40 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-200">{item.item_id}</span>
                    <span className="font-bold text-emerald-300">
                      {formatCurrency(item.amount, item.currency)}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500 block mt-1">{item.item_type}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {activeReconciliation && (
          <div className="mt-5 p-3.5 bg-slate-900/60 rounded-lg border border-slate-800 text-xs font-mono text-slate-300">
            <span className="font-bold text-slate-400 block mb-1">SOLVER EXPLANATION:</span>
            {activeReconciliation.explanation}
          </div>
        )}

        {/* Explicit Visual Allocation Results */}
        {activeReconciliation && activeReconciliation.allocations.length > 0 && (
          <div className="mt-6 p-5 bg-[#0e1320] border border-blue-900/50 rounded-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <h4 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider">
                  Deterministic Allocations Ledger (Backend OR-Tools Optimization)
                </h4>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                Formula: Internal Item ➔ External Item ➔ Allocated Amount
              </span>
            </div>

            <div className="grid grid-cols-1 gap-2.5">
              {activeReconciliation.allocations.map((alloc) => (
                <div
                  key={alloc.allocation_id}
                  className="p-3 bg-slate-900/90 border border-slate-800 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3 font-mono text-xs hover:border-blue-500/40 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <span className="px-2.5 py-1 rounded bg-blue-950/80 text-blue-300 font-bold border border-blue-800/50">
                      {alloc.internal_item_id}
                    </span>
                    <ArrowRight className="w-4 h-4 text-slate-500 shrink-0" />
                    <span className="px-2.5 py-1 rounded bg-emerald-950/80 text-emerald-300 font-bold border border-emerald-800/50">
                      {alloc.external_item_id}
                    </span>
                  </div>

                  <div className="flex items-center gap-4 justify-between sm:justify-end">
                    <span className="text-[11px] text-slate-400">
                      Confidence: {(parseFloat(alloc.confidence) * 100).toFixed(0)}%
                    </span>
                    <span className="font-bold text-sm text-emerald-400 bg-emerald-950/40 px-3 py-1 rounded border border-emerald-800/40">
                      {formatCurrency(alloc.allocated_amount, alloc.currency)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
