import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Layers,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Clock,
} from 'lucide-react';
import { listEvents } from '../api/events';
import { formatCurrency, formatTimestamp } from '../lib/formatters';
import { EventType } from '../types/events';

export const TransactionsPage: React.FC = () => {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [selectedType, setSelectedType] = useState<string>('');
  const [merchantFilter, setMerchantFilter] = useState<string>('');
  const [entityFilter, setEntityFilter] = useState<string>('');

  const { data: events, isLoading, isFetching } = useQuery({
    queryKey: ['events', page, pageSize, selectedType, merchantFilter, entityFilter],
    queryFn: () =>
      listEvents({
        limit: pageSize,
        offset: page * pageSize,
        event_type: selectedType || undefined,
        merchant_id: merchantFilter.trim() || undefined,
        entity_id: entityFilter.trim() || undefined,
      }),
    staleTime: 10000,
  });

  const eventTypes: EventType[] = [
    'PAYMENT',
    'PAYOUT',
    'FEE',
    'TAX',
    'REFUND',
    'ADJUSTMENT',
    'BANK_CREDIT',
    'BANK_DEBIT',
    'SETTLEMENT' as any,
    'REVENUE_RECOGNITION',
    'INTERCOMPANY_TRANSFER',
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 text-xs font-mono font-medium border border-blue-800/50">
              POPULATION SCALE (1,000+ EVENTS)
            </span>
            <span className="text-xs text-slate-400 font-mono">Streaming Server-Side Repository</span>
          </div>
          <h2 className="text-xl font-bold text-slate-100 mt-1">Canonical Financial Events</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Streaming and paginated access across evaluated transaction populations. Queries are pushed to the backend SQLite store.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400">Page Size:</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(0);
            }}
            className="bg-[#101522] border border-[#1e2638] rounded-lg px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-4 flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          {/* Event Type Filter */}
          <select
            value={selectedType}
            onChange={(e) => {
              setSelectedType(e.target.value);
              setPage(0);
            }}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Event Types</option>
            {eventTypes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>

          {/* Merchant Filter */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter by merchant..."
              value={merchantFilter}
              onChange={(e) => {
                setMerchantFilter(e.target.value);
                setPage(0);
              }}
              className="bg-slate-900 border border-slate-700 rounded-lg pl-8 pr-2.5 py-1 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 w-44"
            />
          </div>

          {/* Entity Filter */}
          <input
            type="text"
            placeholder="Filter by entity..."
            value={entityFilter}
            onChange={(e) => {
              setEntityFilter(e.target.value);
              setPage(0);
            }}
            className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 w-36"
          />
        </div>

        {/* Pagination Navigation */}
        <div className="flex items-center gap-2 justify-end font-mono text-xs text-slate-400">
          <span>Page {page + 1}</span>
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0 || isLoading}
            className="p-1 rounded bg-slate-900 border border-slate-700 hover:bg-slate-800 disabled:opacity-40"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!events || events.length < pageSize || isLoading}
            className="p-1 rounded bg-slate-900 border border-slate-700 hover:bg-slate-800 disabled:opacity-40"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
          {isFetching && <span className="text-[10px] text-blue-400 animate-pulse">Querying...</span>}
        </div>
      </div>

      {/* Events Table */}
      <div className="bg-[#101522] border border-[#1e2638] rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-bold text-slate-200">
              Paginated Event Stream ({events?.length || 0} items displayed)
            </h3>
          </div>
        </div>

        {isLoading ? (
          <div className="py-12 text-center text-xs text-slate-400 font-mono">
            Loading events from backend repository...
          </div>
        ) : events && events.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-[#1e2638] text-slate-400 bg-slate-900/40">
                <tr>
                  <th className="py-2.5 px-3">Event ID</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Source & ID</th>
                  <th className="py-2.5 px-3">Scope (Entity / Merchant / Partner)</th>
                  <th className="py-2.5 px-3">Effective Timestamp</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2638]/50">
                {events.map((ev) => (
                  <tr key={ev.event_id} className="hover:bg-slate-800/30 transition-all">
                    <td className="py-2.5 px-3 font-semibold text-slate-200">{ev.event_id}</td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 border border-blue-800/40 text-[10px] font-bold">
                        {ev.event_type}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      <span className="text-slate-300">{ev.source_system}</span> / {ev.source_id}
                    </td>
                    <td className="py-2.5 px-3 text-slate-300">
                      {ev.merchant_id ? (
                        <span className="text-amber-300/90">{ev.merchant_id}</span>
                      ) : ev.partner_id ? (
                        <span className="text-purple-300/90">{ev.partner_id}</span>
                      ) : (
                        <span className="text-slate-400">{ev.entity_id || '-'}</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-500" />
                        {formatTimestamp(ev.effective_timestamp)}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-right font-bold text-slate-100">
                      {formatCurrency(ev.amount, ev.currency)}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-bold uppercase">
                        {ev.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12 text-slate-500 text-xs font-mono">
            No events found matching the active filters.
          </div>
        )}
      </div>
    </div>
  );
};
