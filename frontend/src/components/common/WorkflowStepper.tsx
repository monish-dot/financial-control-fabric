import React from 'react';
import { Check, AlertCircle, XCircle } from 'lucide-react';
import { UnifiedWorkflowState, WORKFLOW_PIPELINE, getWorkflowStepIndex } from '../../lib/workflowState';

interface WorkflowStepperProps {
  currentState: UnifiedWorkflowState;
  className?: string;
}

export const WorkflowStepper: React.FC<WorkflowStepperProps> = ({ currentState, className = '' }) => {
  const currentIndex = getWorkflowStepIndex(currentState);
  const isError = currentState === 'REJECTED' || currentState === 'INCONCLUSIVE';

  return (
    <div className={`w-full overflow-x-auto py-2 ${className}`}>
      <div className="flex items-center min-w-[780px] justify-between relative">
        {WORKFLOW_PIPELINE.map((step, idx) => {
          const isCompleted = idx < currentIndex || currentState === 'VERIFIED';
          const isCurrent = idx === currentIndex && !isError;
          const isFailedCurrent = idx === currentIndex && isError;

          return (
            <div key={step} className="flex-1 flex flex-col items-center relative group">
              {/* Connector line */}
              {idx > 0 && (
                <div
                  className={`absolute top-3 right-1/2 left-[-50%] h-[2px] -z-0 transition-all ${
                    idx <= currentIndex
                      ? isError && idx === currentIndex
                        ? 'bg-rose-600'
                        : 'bg-emerald-500'
                      : 'bg-slate-800'
                  }`}
                />
              )}

              {/* Node indicator */}
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono font-bold z-10 transition-all ${
                  isCompleted
                    ? 'bg-emerald-600 text-white shadow-sm shadow-emerald-950'
                    : isCurrent
                    ? 'bg-blue-600 text-white ring-4 ring-blue-500/30 animate-pulse'
                    : isFailedCurrent
                    ? 'bg-rose-600 text-white ring-4 ring-rose-500/30'
                    : 'bg-slate-900 border border-slate-700 text-slate-500'
                }`}
              >
                {isCompleted ? (
                  <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                ) : isFailedCurrent ? (
                  <XCircle className="w-3.5 h-3.5" />
                ) : (
                  idx + 1
                )}
              </div>

              {/* Step label */}
              <span
                className={`text-[9px] font-mono uppercase tracking-tight text-center mt-1.5 whitespace-nowrap ${
                  isCompleted
                    ? 'text-emerald-400 font-medium'
                    : isCurrent
                    ? 'text-blue-300 font-bold'
                    : isFailedCurrent
                    ? 'text-rose-400 font-bold'
                    : 'text-slate-500'
                }`}
              >
                {step.replace(/_/g, ' ')}
              </span>
            </div>
          );
        })}
      </div>

      {isError && (
        <div className="mt-2.5 px-3 py-1.5 rounded bg-rose-950/40 border border-rose-800/60 text-[11px] font-mono text-rose-300 flex items-center gap-2">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>Workflow halted: Current status is {currentState}. Further lifecycle transitions require intervention.</span>
        </div>
      )}
    </div>
  );
};
