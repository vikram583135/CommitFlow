import React, { useState, useEffect } from 'react';
import { X, Check, Code, FileText, CheckSquare, BookOpen } from 'lucide-react';
import { Automation, Repository } from '../types';

interface AutomationModalProps {
  isOpen: boolean;
  onClose: () => void;
  repositories: Repository[];
  onSave: (automation: Partial<Automation>) => Promise<void>;
}

export const AutomationModal: React.FC<AutomationModalProps> = ({
  isOpen,
  onClose,
  repositories,
  onSave,
}) => {
  const [selectedRepoId, setSelectedRepoId] = useState<string>(
    repositories[0]?.id || ''
  );
  const [title, setTitle] = useState('Daily Practice & Tests');
  const [taskType, setTaskType] = useState<'coding_practice' | 'documentation' | 'unit_tests' | 'learning_notes'>('coding_practice');
  const [instructions, setInstructions] = useState('Implement a core concept with thorough unit test assertions and documentation.');
  const [allowedPaths, setAllowedPaths] = useState('src/, tests/');
  const [cronTime, setCronTime] = useState('09:00');
  const [branchStrategy, setBranchStrategy] = useState<'PULL_REQUEST' | 'DIRECT_PUSH'>('PULL_REQUEST');
  const [requireApproval, setRequireApproval] = useState(true);
  const [timeZone,setTimeZone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [saving,setSaving] = useState(false);
  const [error,setError] = useState('');
  useEffect(() => {
    if (!repositories.some(repo=>repo.id===selectedRepoId)) setSelectedRepoId(repositories[0]?.id || '');
  },[repositories,selectedRepoId]);
  useEffect(() => {
    const repo=repositories.find(repo=>repo.id===selectedRepoId);
    if (repo) setAllowedPaths(repo.allowed_paths.join(', '));
  },[selectedRepoId,repositories]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);setError('');
    try {
    if (!selectedRepoId) throw new Error('Connect and select a repository first.');
    await onSave({
      title,
      task_type: taskType,
      instructions,
      repository: selectedRepoId || (repositories[0] ? repositories[0].id : ''),
      branch_strategy: branchStrategy,
      require_approval: requireApproval,
      allowed_paths: allowedPaths.split(',').map(path=>path.trim()).filter(Boolean),
      cron_expression: `${parseInt(cronTime.split(':')[1], 10)} ${parseInt(cronTime.split(':')[0], 10)} * * *`,
      timezone: timeZone,
      enabled: true,
    });
    onClose();
    } catch(err) {setError((err as Error).message);} finally {setSaving(false);}
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="mono-panel w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-xl bg-zinc-950 p-6 shadow-2xl border border-zinc-800">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div>
            <h2 className="text-sm font-mono uppercase tracking-wider font-semibold text-white">Create Automation Rule</h2>
            <p className="text-[11px] text-zinc-400">Configure task goal, repository boundary, and PR policy</p>
          </div>
          <button onClick={onClose} className="p-1 rounded text-zinc-400 hover:text-white hover:bg-zinc-900">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {/* Target Repository Picker */}
          <div>
            <label className="block text-[11px] font-mono text-zinc-400 mb-1">TARGET GITHUB REPOSITORY</label>
            {repositories.length > 0 ? (
              <select
                value={selectedRepoId}
                onChange={(e) => setSelectedRepoId(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded bg-black border border-zinc-800 text-white focus:outline-none focus:border-zinc-500 font-mono"
                required
              >
                {repositories.map((repo) => (
                  <option key={repo.id} value={repo.id}>
                    {repo.full_name} ({repo.default_branch})
                  </option>
                ))}
              </select>
            ) : (
              <div className="p-2.5 rounded bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-400">
                No authorized repositories found. Click "Sync Repos" or connect your GitHub account.
              </div>
            )}
          </div>

          <div>
            <label className="block text-[11px] font-mono text-zinc-400 mb-1">RULE TITLE</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded bg-black border border-zinc-800 text-white focus:outline-none focus:border-zinc-500 font-mono"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-zinc-400 mb-1">HABIT TYPE</label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { id: 'coding_practice', label: 'DSA / Code Practice', icon: Code },
                { id: 'unit_tests', label: 'Unit Tests & Coverage', icon: CheckSquare },
                { id: 'documentation', label: 'Documentation / Guides', icon: FileText },
                { id: 'learning_notes', label: 'TIL / Learning Notes', icon: BookOpen },
              ].map((item) => {
                const Icon = item.icon;
                const isSelected = taskType === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setTaskType(item.id as any)}
                    className={`flex items-center gap-2 p-2.5 rounded border text-xs text-left transition-all ${
                      isSelected
                        ? 'border-white bg-white text-black font-medium'
                        : 'border-zinc-800 bg-black text-zinc-400 hover:border-zinc-700'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5 shrink-0" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-mono text-zinc-400 mb-1">TASK INSTRUCTIONS</label>
            <textarea
              rows={3}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded bg-black border border-zinc-800 text-white focus:outline-none focus:border-zinc-500 font-mono"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1">ALLOWED PATHS (BOUNDARY)</label>
              <input
                type="text"
                value={allowedPaths}
                onChange={(e) => setAllowedPaths(e.target.value)}
                placeholder="src/, tests/"
                className="w-full px-3 py-2 text-xs rounded bg-black border border-zinc-800 text-white focus:outline-none focus:border-zinc-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1">DAILY TIME</label>
              <input
                type="time"
                value={cronTime}
                onChange={(e) => setCronTime(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded bg-black border border-zinc-800 text-white focus:outline-none focus:border-zinc-500 font-mono"
              />
            </div>
          </div>

          <label className="block text-[11px] text-zinc-400">TIMEZONE
            <input value={timeZone} onChange={e=>setTimeZone(e.target.value)} required
              className="block w-full mt-1 p-2 bg-black border border-zinc-800 rounded"/>
          </label>
          <p className="text-[11px] text-zinc-500">Allowed paths apply to all rules for this repository.</p>

          <div className="grid grid-cols-2 gap-3 pt-1">
            <div>
              <label className="block text-[11px] font-mono text-zinc-400 mb-1">PUBLISHING MODE</label>
              <select
                value={branchStrategy}
                onChange={(e) => {setBranchStrategy(e.target.value as any);if(e.target.value==='DIRECT_PUSH') setRequireApproval(true);}}
                className="w-full px-3 py-2 text-xs rounded bg-black border border-zinc-800 text-white focus:outline-none focus:border-zinc-500 font-mono"
              >
                <option value="PULL_REQUEST">Pull Request (Default)</option>
                <option value="DIRECT_PUSH">Direct Push (Opt-in)</option>
              </select>
            </div>

            <div className="flex items-center gap-2 pt-5">
              <input
                type="checkbox"
                id="requireApproval"
                checked={requireApproval}
                disabled={branchStrategy==='DIRECT_PUSH'}
                onChange={(e) => setRequireApproval(e.target.checked)}
                className="rounded border-zinc-800 text-white focus:ring-0 bg-black"
              />
              <label htmlFor="requireApproval" className="text-xs text-zinc-300">
                Require Manual Approval
              </label>
            </div>
          </div>
          {error && <p role="alert" className="text-xs text-red-300">{error}</p>}

          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 text-xs font-mono text-zinc-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !selectedRepoId}
              className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-mono font-medium text-black bg-white hover:bg-zinc-200 rounded"
            >
              <Check className="w-3.5 h-3.5" />
              {saving ? 'Saving...' : 'Save Rule'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
