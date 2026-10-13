import React, { useEffect, useState } from 'react';
import { X, CheckCircle2, AlertCircle, Loader2, GitPullRequest, ExternalLink, Terminal } from 'lucide-react';
import { Execution } from '../types';

interface ExecutionDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  executionId: string | null;
  onViewDiff: () => void;
}

interface StepLog {
  title: string;
  desc: string;
  status: 'pending' | 'active' | 'completed' | 'error';
}

export const ExecutionDrawer: React.FC<ExecutionDrawerProps> = ({
  isOpen,
  onClose,
  executionId,
  onViewDiff,
}) => {
  const [logs, setLogs] = useState<string[]>([]);
  const [currentStep, setCurrentStep] = useState<string>('STARTING');
  const [execStatus, setExecStatus] = useState<string>('RUNNING');
  const [prUrl, setPrUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !executionId) return;

    setLogs(['[00.0s] Initializing habit pipeline and verifying repository permissions...']);
    setCurrentStep('STARTING');
    setExecStatus('RUNNING');
    setPrUrl(null);
    setErrorMessage(null);

    const token = typeof window !== 'undefined' ? localStorage.getItem('commitflow_token') : null;
    const url = `/api/executions/${executionId}/stream/`;

    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/executions/${executionId}/`, {
          headers: token ? { Authorization: `Token ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          setExecStatus(data.status);
          const val = data.validation_results || {};
          const step = val.current_step || data.status;
          setCurrentStep(step);

          if (val.step_message) {
            setLogs((prev) => {
              if (!prev.includes(val.step_message)) {
                return [...prev, `[${new Date().toLocaleTimeString()}] ${val.step_message}`];
              }
              return prev;
            });
          }

          if (data.published_change?.pull_request_url) {
            setPrUrl(data.published_change.pull_request_url);
          }

          if (data.error_message) {
            setErrorMessage(data.error_message);
          }

          if (['SUCCESS', 'FAILED', 'REJECTED'].includes(data.status)) {
            clearInterval(pollInterval);
          }
        }
      } catch (e) {
        // Continue polling
      }
    }, 1500);

    return () => clearInterval(pollInterval);
  }, [isOpen, executionId]);

  if (!isOpen) return null;

  const stepsList: StepLog[] = [
    {
      title: 'Repository Context Ingestion',
      desc: 'Recursive tree scan and dependency boundary extraction via GitHub API',
      status: ['FETCHING_CONTEXT', 'STARTING'].includes(currentStep)
        ? 'active'
        : ['GENERATING_CHANGES', 'VALIDATING_SAFETY', 'PUBLISHING_PULL_REQUEST', 'SUCCESS'].includes(currentStep)
        ? 'completed'
        : 'pending',
    },
    {
      title: 'AI Code & Test Generation',
      desc: 'Prompting LLM with anti-duplication memory and structured JSON schema',
      status: currentStep === 'GENERATING_CHANGES'
        ? 'active'
        : ['VALIDATING_SAFETY', 'PUBLISHING_PULL_REQUEST', 'SUCCESS'].includes(currentStep)
        ? 'completed'
        : execStatus === 'REJECTED' && currentStep === 'FAILED'
        ? 'error'
        : 'pending',
    },
    {
      title: 'Security Sandbox & Secret Scan',
      desc: 'Path whitelisting, blacklist check (.env/keys), and diff quality verification',
      status: currentStep === 'VALIDATING_SAFETY'
        ? 'active'
        : ['PUBLISHING_PULL_REQUEST', 'SUCCESS'].includes(currentStep)
        ? 'completed'
        : execStatus === 'REJECTED'
        ? 'error'
        : 'pending',
    },
    {
      title: 'Git Commit & Pull Request Publication',
      desc: 'Dedicated branch ref, blobs creation, tree commit, and PR opened on GitHub',
      status: currentStep === 'PUBLISHING_PULL_REQUEST'
        ? 'active'
        : execStatus === 'SUCCESS'
        ? 'completed'
        : execStatus === 'FAILED'
        ? 'error'
        : 'pending',
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm">
      <div className="mono-panel w-full max-w-xl rounded-xl bg-zinc-950 p-6 shadow-2xl border border-zinc-800">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-white" />
            <h2 className="text-sm font-mono uppercase tracking-wider font-semibold text-white">
              Real-Time Execution Pipeline
            </h2>
          </div>
          <button onClick={onClose} className="p-1 rounded text-zinc-400 hover:text-white hover:bg-zinc-900">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Step Progress Checklist */}
        <div className="mt-4 space-y-2.5">
          {stepsList.map((step, idx) => (
            <div
              key={idx}
              className={`p-3 rounded border text-xs font-mono transition-all flex items-start gap-3 ${
                step.status === 'completed'
                  ? 'bg-zinc-900/60 border-zinc-800 text-zinc-200'
                  : step.status === 'active'
                  ? 'bg-zinc-900 border-zinc-600 text-white'
                  : step.status === 'error'
                  ? 'bg-zinc-950 border-zinc-800 text-zinc-400'
                  : 'bg-black/60 border-zinc-900 text-zinc-600'
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {step.status === 'completed' && <CheckCircle2 className="w-4 h-4 text-white" />}
                {step.status === 'active' && <Loader2 className="w-4 h-4 text-white animate-spin" />}
                {step.status === 'error' && <AlertCircle className="w-4 h-4 text-zinc-400" />}
                {step.status === 'pending' && <span className="w-4 h-4 block rounded-full border border-zinc-800" />}
              </div>
              <div>
                <span className="font-semibold block">{step.title}</span>
                <span className="text-[11px] text-zinc-400 block mt-0.5">{step.desc}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Error Callout */}
        {errorMessage && (
          <div className="mt-3 p-3 rounded bg-zinc-900 border border-zinc-700 text-xs font-mono text-zinc-300">
            <span className="font-bold text-white block mb-1">EXECUTION ERROR:</span>
            {errorMessage}
          </div>
        )}

        {/* Success Action */}
        {prUrl && (
          <div className="mt-3 p-3 rounded bg-zinc-900 border border-zinc-600 text-xs font-mono flex items-center justify-between">
            <span className="text-white">Pull Request successfully created on GitHub!</span>
            <a
              href={prUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1 bg-white text-black font-semibold rounded text-xs hover:bg-zinc-200 transition-colors"
            >
              <span>OPEN PR</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        )}

        <div className="flex items-center justify-between pt-4 mt-4 border-t border-zinc-800">
          <span className="text-[10px] font-mono text-zinc-500 uppercase">
            STATUS: <span className="text-white font-bold">{execStatus}</span>
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => {
                onViewDiff();
                onClose();
              }}
              className="px-3 py-1.5 text-xs font-mono text-zinc-300 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded transition-colors"
            >
              INSPECT DIFF
            </button>
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-xs font-mono font-medium text-black bg-white hover:bg-zinc-200 rounded"
            >
              CLOSE
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
