import React from 'react';
import { GitCommit, Play, Plus, Sliders } from 'lucide-react';

interface HeaderProps {
  onNewAutomation: () => void;
  onOpenSettings: () => void;
  onRunDemo: () => void;
  isRunningDemo: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onNewAutomation,
  onOpenSettings,
  onRunDemo,
  isRunningDemo,
}) => {
  return (
    <header className="border-b border-zinc-800/80 bg-black/90 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-zinc-900 border border-zinc-700 flex items-center justify-center">
            <GitCommit className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm tracking-tight text-white uppercase">CommitFlow</span>
              <span className="text-[10px] font-mono tracking-wider bg-zinc-900 text-zinc-300 border border-zinc-700 rounded px-1.5 py-0.5">
                v1.0
              </span>
            </div>
            <p className="text-[11px] text-zinc-400">Autonomous Engineering Habit Pipeline</p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={onRunDemo}
            disabled={isRunningDemo}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-mono font-medium text-zinc-200 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 rounded-md transition-all disabled:opacity-50"
          >
            <Play className={`w-3 h-3 ${isRunningDemo ? 'animate-spin' : ''}`} />
            {isRunningDemo ? 'RUNNING PIPELINE...' : 'EXECUTE HABIT'}
          </button>

          <button
            onClick={onOpenSettings}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-mono font-medium text-zinc-300 hover:text-white bg-zinc-950 hover:bg-zinc-900 border border-zinc-800 rounded-md transition-colors"
          >
            <Sliders className="w-3 h-3 text-zinc-400" />
            AI CONFIG
          </button>

          <button
            onClick={onNewAutomation}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono font-medium text-black bg-white hover:bg-zinc-200 rounded-md transition-colors"
          >
            <Plus className="w-3.5 h-3.5 text-black" />
            NEW RULE
          </button>
        </div>
      </div>
    </header>
  );
};
