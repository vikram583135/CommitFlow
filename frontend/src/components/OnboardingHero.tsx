import React from 'react';
import { Github, Key, Sparkles, ShieldCheck, CheckCircle2 } from 'lucide-react';

interface OnboardingHeroProps {
  hasGitHub: boolean;
  hasAIConfig: boolean;
  onConnectGitHub: () => void;
  onOpenAIConfig: () => void;
  onCreateAutomation: () => void;
}

export const OnboardingHero: React.FC<OnboardingHeroProps> = ({
  hasGitHub,
  hasAIConfig,
  onConnectGitHub,
  onOpenAIConfig,
  onCreateAutomation,
}) => {
  return (
    <div className="mono-panel p-8 rounded-xl border border-zinc-800 bg-zinc-950 text-white">
      <div className="max-w-2xl">
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-300 mb-3">
          <Sparkles className="w-3.5 h-3.5 text-white" />
          <span>PRODUCTION ONBOARDING</span>
        </div>
        <h2 className="text-xl font-bold tracking-tight text-white font-mono uppercase">
          Welcome to CommitFlow
        </h2>
        <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">
          CommitFlow maintains authentic, reviewable developer habits by automatically creating validated
          code, tests, and documentation on dedicated feature branches with GitHub Pull Requests.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 mt-6">
        {/* Step 1: GitHub */}
        <div className="p-4 rounded-lg bg-black border border-zinc-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-zinc-500 uppercase">STEP 1</span>
              {hasGitHub ? (
                <CheckCircle2 className="w-4 h-4 text-white" />
              ) : (
                <Github className="w-4 h-4 text-zinc-400" />
              )}
            </div>
            <h3 className="text-xs font-mono font-semibold text-white">Connect GitHub</h3>
            <p className="text-[11px] text-zinc-400 mt-1">
              Authorize repositories via the CommitFlow GitHub App with scoped permissions.
            </p>
          </div>
          <button
            onClick={onConnectGitHub}
            className={`mt-4 w-full py-1.5 text-xs font-mono rounded transition-colors ${
              hasGitHub
                ? 'bg-zinc-900 text-zinc-400 border border-zinc-850'
                : 'bg-white text-black font-semibold hover:bg-zinc-200'
            }`}
          >
            {hasGitHub ? 'CONNECTED' : 'CONNECT GITHUB'}
          </button>
        </div>

        {/* Step 2: AI Config */}
        <div className="p-4 rounded-lg bg-black border border-zinc-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-zinc-500 uppercase">STEP 2</span>
              {hasAIConfig ? (
                <CheckCircle2 className="w-4 h-4 text-white" />
              ) : (
                <Key className="w-4 h-4 text-zinc-400" />
              )}
            </div>
            <h3 className="text-xs font-mono font-semibold text-white">Add AI Provider</h3>
            <p className="text-[11px] text-zinc-400 mt-1">
              Supply your OpenAI, Claude, or Gemini key. Encrypted at rest using Fernet keys.
            </p>
          </div>
          <button
            onClick={onOpenAIConfig}
            className={`mt-4 w-full py-1.5 text-xs font-mono rounded transition-colors ${
              hasAIConfig
                ? 'bg-zinc-900 text-zinc-400 border border-zinc-850'
                : 'bg-white text-black font-semibold hover:bg-zinc-200'
            }`}
          >
            {hasAIConfig ? 'CONFIGURED' : 'ADD AI KEY'}
          </button>
        </div>

        {/* Step 3: Create Rule */}
        <div className="p-4 rounded-lg bg-black border border-zinc-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-zinc-500 uppercase">STEP 3</span>
              <ShieldCheck className="w-4 h-4 text-zinc-400" />
            </div>
            <h3 className="text-xs font-mono font-semibold text-white">Create Habit Rule</h3>
            <p className="text-[11px] text-zinc-400 mt-1">
              Select allowed directory paths, define your daily coding goal, and set a schedule.
            </p>
          </div>
          <button
            onClick={onCreateAutomation}
            className="mt-4 w-full py-1.5 text-xs font-mono font-semibold bg-white text-black hover:bg-zinc-200 rounded transition-colors"
          >
            CREATE FIRST RULE
          </button>
        </div>
      </div>
    </div>
  );
};
