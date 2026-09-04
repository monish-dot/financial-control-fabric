import React from 'react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md' | 'lg';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const s = (status || '').toUpperCase();

  let colors = 'bg-slate-800 text-slate-300 border-slate-700';

  if (s === 'PASS' || s === 'VALID' || s === 'APPROVED' || s === 'RESOLVED' || s === 'SUCCESS') {
    colors = 'bg-emerald-950/70 text-emerald-300 border-emerald-700/60';
  } else if (s === 'FAIL' || s === 'EVENT_TAMPERED' || s === 'EVENT_MISSING' || s === 'EVENT_ADDED' || s === 'CONTROL_RESULT_MISMATCH' || s === 'CRITICAL' || s === 'REJECTED') {
    colors = 'bg-rose-950/70 text-rose-300 border-rose-700/60';
  } else if (s === 'WATCH' || s === 'ANOMALOUS' || s === 'AWAITING_APPROVAL' || s === 'PENDING' || s === 'REVALIDATING') {
    colors = 'bg-amber-950/70 text-amber-300 border-amber-700/60';
  } else if (s === 'INCONCLUSIVE' || s === 'UNKNOWN' || s === 'DETECTED' || s === 'INVESTIGATING') {
    colors = 'bg-blue-950/70 text-blue-300 border-blue-700/60';
  }

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-xs px-2.5 py-1 font-semibold',
    lg: 'text-sm px-3 py-1.5 font-bold',
  }[size];

  return (
    <span
      className={`inline-flex items-center rounded-md border tracking-wider font-mono uppercase ${sizeClasses} ${colors}`}
    >
      {status}
    </span>
  );
};
