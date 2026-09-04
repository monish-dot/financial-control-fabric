import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navbar } from './components/common/Navbar';
import { OverviewPage } from './pages/OverviewPage';
import { TransactionsPage } from './pages/TransactionsPage';
import { ExceptionCenterPage } from './pages/ExceptionCenterPage';
import { ReconciliationPage } from './pages/ReconciliationPage';
import { InvestigationPage } from './pages/InvestigationPage';
import { ApprovalCenterPage } from './pages/ApprovalCenterPage';
import { ControlProofPage } from './pages/ControlProofPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5000,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-[#0a0d14] text-slate-200 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
          <Navbar />
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <Routes>
              <Route path="/" element={<OverviewPage />} />
              <Route path="/transactions" element={<TransactionsPage />} />
              <Route path="/exceptions" element={<ExceptionCenterPage />} />
              <Route path="/reconciliation" element={<ReconciliationPage />} />
              <Route path="/investigations" element={<InvestigationPage />} />
              <Route path="/approvals" element={<ApprovalCenterPage />} />
              <Route path="/proofs" element={<ControlProofPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <footer className="border-t border-[#1e2638] bg-[#0c101a] py-4 text-center text-xs text-slate-500 font-mono">
            FINANCIAL CONTROL FABRIC · DETERMINISTIC CONTROL KERNEL & TAMPER-EVIDENT CRYPTOGRAPHIC PROOFS
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
};
