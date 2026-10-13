import React, { useState } from 'react';
import { FileCode, ShieldCheck, ExternalLink, GitBranch, Check, Copy } from 'lucide-react';
import { Execution } from '../types';

interface DiffViewerProps {
  execution: Execution | null;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ execution }) => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [copied, setCopied] = useState<boolean>(false);

  if (!execution || !execution.generated_files || execution.generated_files.length === 0) {
    return (
      <div className="mono-panel p-10 rounded-lg text-center border-dashed">
        <FileCode className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
        <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-300">No Diff Loaded</h3>
        <p className="text-[11px] text-zinc-500 mt-1">Select an execution from history or trigger a habit test to inspect code.</p>
      </div>
    );
  }

  const currentFile = execution.generated_files[activeTab] || execution.generated_files[0];

  const handleCopy = () => {
    navigator.clipboard.writeText(currentFile.new_content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mono-panel rounded-lg overflow-hidden">
      {/* Top Banner with Execution Status and PR link */}
      <div className="p-3.5 bg-zinc-950 border-b border-zinc-800 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
              {execution.scheduled_slot}
            </span>
            <span className="text-xs font-semibold text-white tracking-tight">{execution.automation_title}</span>
          </div>
          {execution.published_change && (
            <div className="flex items-center gap-2 mt-1.5 text-[11px] text-zinc-400 font-mono">
              <GitBranch className="w-3.5 h-3.5 text-zinc-300" />
              <span>{execution.published_change.branch_name}</span>
              <span className="text-zinc-600">•</span>
              <span>SHA: {execution.published_change.commit_sha.slice(0, 7)}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Validation Badge */}
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-900 text-zinc-300 text-[10px] font-mono border border-zinc-800">
            <ShieldCheck className="w-3 h-3 text-white" />
            <span>PASSED 4/4 GUARDS</span>
          </div>

          {execution.published_change?.pull_request_url && (
            <a
              href={execution.published_change.pull_request_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-2.5 py-1 bg-white hover:bg-zinc-200 text-black rounded text-[11px] font-mono font-medium transition-colors"
            >
              <span>VIEW PR #{execution.published_change.pull_request_number}</span>
              <ExternalLink className="w-3 h-3 text-black" />
            </a>
          )}
        </div>
      </div>

      {/* File Tabs */}
      <div className="flex border-b border-zinc-800 bg-black px-3 pt-2 gap-1 overflow-x-auto">
        {execution.generated_files.map((file, idx) => (
          <button
            key={file.id || idx}
            onClick={() => setActiveTab(idx)}
            className={`flex items-center gap-2 px-3 py-1.5 text-xs font-mono rounded-t transition-all ${
              activeTab === idx
                ? 'bg-zinc-900 text-white border-t border-x border-zinc-700 font-medium'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-white" />
            <span>{file.file_path}</span>
          </button>
        ))}
      </div>

      {/* Code Viewer */}
      <div className="p-4 bg-black">
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-zinc-900 text-[11px] text-zinc-400 font-mono">
          <span>{currentFile.file_path}</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-white transition-colors"
          >
            {copied ? <Check className="w-3 h-3 text-white" /> : <Copy className="w-3 h-3" />}
            <span>{copied ? 'COPIED' : 'COPY'}</span>
          </button>
        </div>

        <pre className="font-mono text-xs leading-relaxed text-zinc-200 overflow-x-auto p-4 rounded bg-zinc-950 border border-zinc-900">
          <code>{currentFile.new_content}</code>
        </pre>
      </div>
    </div>
  );
};
