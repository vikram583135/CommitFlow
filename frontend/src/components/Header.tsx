import React from 'react';
import { GitCommit, Play, Plus, Sliders, RefreshCw, User, LogOut, LogIn } from 'lucide-react';

interface HeaderProps {
  user: any | null;
  onOpenAuth: () => void;
  onLogout: () => void;
  onNewAutomation: () => void;
  onOpenSettings: () => void;
  onSyncRepos: () => void;
  isSyncingRepos: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  user,
  onOpenAuth,
  onLogout,
  onNewAutomation,
  onOpenSettings,
  onSyncRepos,
  isSyncingRepos,
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
              <span className="font-semibold text-sm tracking-tight text-white uppercase font-mono">CommitFlow</span>
              <span className="text-[10px] font-mono tracking-wider bg-zinc-900 text-zinc-300 border border-zinc-700 rounded px-1.5 py-0.2">
                PROD
              </span>
            </div>
            <p className="text-[11px] text-zinc-400">Autonomous Engineering Habit Pipeline</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Sync Repositories Button */}
          <button
            onClick={onSyncRepos}
            disabled={isSyncingRepos}
            title="Sync authorized repositories from GitHub"
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-mono text-zinc-400 hover:text-white bg-zinc-950 hover:bg-zinc-900 border border-zinc-850 rounded transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncingRepos ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">SYNC REPOS</span>
          </button>

          {/* AI Config */}
          <button
            onClick={onOpenSettings}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-mono text-zinc-300 hover:text-white bg-zinc-950 hover:bg-zinc-900 border border-zinc-800 rounded transition-colors"
          >
            <Sliders className="w-3 h-3 text-zinc-400" />
            <span className="hidden sm:inline">AI CONFIG</span>
          </button>

          {/* New Automation */}
          <button
            onClick={onNewAutomation}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium text-black bg-white hover:bg-zinc-200 rounded transition-colors"
          >
            <Plus className="w-3.5 h-3.5 text-black" />
            <span>NEW RULE</span>
          </button>

          {/* User Profile / Auth Button */}
          {user ? (
            <div className="flex items-center gap-2 pl-2 border-l border-zinc-800">
              <div className="flex items-center gap-2">
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt={user.name || user.email} className="w-7 h-7 rounded-full border border-zinc-700" />
                ) : (
                  <div className="w-7 h-7 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-xs font-mono text-white">
                    {user.email.slice(0, 2).toUpperCase()}
                  </div>
                )}
                <span className="text-xs font-mono text-zinc-300 hidden md:inline truncate max-w-[120px]">
                  {user.name || user.email}
                </span>
              </div>
              <button
                onClick={onLogout}
                title="Sign out"
                className="p-1.5 rounded text-zinc-400 hover:text-white hover:bg-zinc-900 transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenAuth}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono text-white bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 rounded transition-colors"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>SIGN IN</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
