import React from 'react';
import { GitPullRequest, CheckCircle2, ShieldCheck, Flame } from 'lucide-react';

interface MetricCardsProps {
  streakDays: number;
  activeAutomations: number;
  totalPRs: number;
  securityRate: number;
}

export const MetricCards: React.FC<MetricCardsProps> = ({
  streakDays,
  activeAutomations,
  totalPRs,
  securityRate,
}) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <div className="mono-panel p-4 rounded-lg">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">Habit Streak</span>
          <div className="p-1.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
            <Flame className="w-3.5 h-3.5" />
          </div>
        </div>
        <div className="mt-2.5 flex items-baseline gap-2">
          <span className="text-2xl font-bold font-mono tracking-tight text-white">{streakDays} DAYS</span>
          <span className="text-[10px] font-mono text-zinc-400">VERIFIED</span>
        </div>
        <p className="text-[11px] text-zinc-400 mt-1">Authentic daily contributions</p>
      </div>

      <div className="mono-panel p-4 rounded-lg">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">Active Rules</span>
          <div className="p-1.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
            <CheckCircle2 className="w-3.5 h-3.5" />
          </div>
        </div>
        <div className="mt-2.5 flex items-baseline gap-2">
          <span className="text-2xl font-bold font-mono tracking-tight text-white">{activeAutomations}</span>
          <span className="text-[10px] font-mono text-zinc-400">SYNCED</span>
        </div>
        <p className="text-[11px] text-zinc-400 mt-1">Targeted repository pipelines</p>
      </div>

      <div className="mono-panel p-4 rounded-lg">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">PRs Published</span>
          <div className="p-1.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
            <GitPullRequest className="w-3.5 h-3.5" />
          </div>
        </div>
        <div className="mt-2.5 flex items-baseline gap-2">
          <span className="text-2xl font-bold font-mono tracking-tight text-white">{totalPRs}</span>
          <span className="text-[10px] font-mono text-zinc-400">TESTED</span>
        </div>
        <p className="text-[11px] text-zinc-400 mt-1">Automated feature branches</p>
      </div>

      <div className="mono-panel p-4 rounded-lg">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">Safety & Sandboxing</span>
          <div className="p-1.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
            <ShieldCheck className="w-3.5 h-3.5" />
          </div>
        </div>
        <div className="mt-2.5 flex items-baseline gap-2">
          <span className="text-2xl font-bold font-mono tracking-tight text-white">{securityRate}%</span>
          <span className="text-[10px] font-mono text-zinc-400">ENFORCED</span>
        </div>
        <p className="text-[11px] text-zinc-400 mt-1">Path whitelists & secret scanning</p>
      </div>
    </div>
  );
};
