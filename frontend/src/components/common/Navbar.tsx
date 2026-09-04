import React from 'react';
import { NavLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ShieldCheck,
  AlertOctagon,
  Search,
  FileCheck,
  KeyRound,
  Activity,
  Layers,
  GitCompare,
} from 'lucide-react';
import { request } from '../../api/client';

export const Navbar: React.FC = () => {
  const { data: healthData, isSuccess } = useQuery({
    queryKey: ['health'],
    queryFn: () => request<{ status: string }>('/health'),
    refetchInterval: 5000,
  });

  const navItems = [
    { to: '/', label: 'Overview', icon: Activity },
    { to: '/transactions', label: 'Transactions', icon: Layers },
    { to: '/exceptions', label: 'Exceptions', icon: AlertOctagon },
    { to: '/reconciliation', label: 'Reconciliation', icon: GitCompare },
    { to: '/investigations', label: 'AI Investigation', icon: Search },
    { to: '/approvals', label: 'Approvals', icon: FileCheck },
    { to: '/proofs', label: 'Control Proof', icon: KeyRound },
  ];

  return (
    <header className="border-b border-[#1e2638] bg-[#0c101a]/95 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <NavLink to="/" className="flex items-center gap-3 group">
          <div className="w-9 h-9 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 group-hover:bg-blue-600/30 transition-all">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-bold text-xs sm:text-sm text-slate-100 tracking-tight leading-none">
              FINANCIAL CONTROL FABRIC
            </h1>
            <p className="text-[10px] text-slate-400 font-mono tracking-wider mt-0.5">
              DETERMINISTIC CRYPTOGRAPHIC CORE
            </p>
          </div>
        </NavLink>

        {/* Screen Nav Tabs */}
        <nav className="hidden lg:flex items-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30 font-semibold'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon className="w-3.5 h-3.5" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        {/* Health status */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                isSuccess && healthData?.status === 'ok'
                  ? 'bg-emerald-400 animate-pulse'
                  : 'bg-rose-400'
              }`}
            />
            <span className="font-mono text-[11px] text-slate-300">
              {isSuccess && healthData?.status === 'ok' ? 'KERNEL ONLINE' : 'KERNEL OFFLINE'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
