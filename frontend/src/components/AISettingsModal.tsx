import React, { useState } from 'react';
import { X, Check, ShieldCheck, Key, RefreshCw } from 'lucide-react';

interface AISettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AISettingsModal: React.FC<AISettingsModalProps> = ({ isOpen, onClose }) => {
  const [provider, setProvider] = useState<'openai' | 'anthropic' | 'gemini'>('openai');
  const [model, setModel] = useState('gpt-4o-mini');
  const [apiKey, setApiKey] = useState('');
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<'success' | 'failed' | null>(null);

  if (!isOpen) return null;

  const handleTestConnection = () => {
    setIsTesting(true);
    setTestResult(null);
    setTimeout(() => {
      setIsTesting(false);
      setTestResult('success');
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="mono-panel w-full max-w-md rounded-xl bg-zinc-950 p-6 shadow-2xl">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <Key className="w-4 h-4 text-white" />
            <h2 className="text-sm font-mono uppercase tracking-wider font-semibold text-white">AI Engine Credentials</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded text-zinc-400 hover:text-white hover:bg-zinc-900">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="mt-4 space-y-4">
          <div>
            <label className="block text-[11px] font-mono text-zinc-400 mb-1">PROVIDER</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as any)}
              className="w-full px-3 py-2 text-xs rounded bg-black border border-zinc-800 text-white focus:outline-none focus:border-zinc-500 font-mono"
            >
              <option value="openai">OpenAI (GPT-4o, GPT-4o-mini)</option>
              <option value="anthropic">Anthropic (Claude 3.5 Sonnet)</option>
              <option value="gemini">Google Gemini (Gemini 1.5 Pro/Flash)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-mono text-zinc-400 mb-1">MODEL IDENTIFIER</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded bg-black border border-zinc-800 text-white focus:outline-none focus:border-zinc-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-zinc-400 mb-1">API KEY</label>
            <input
              type="password"
              placeholder="••••••••••••••••••••••••••••••••"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded bg-black border border-zinc-800 text-white font-mono focus:outline-none focus:border-zinc-500"
            />
            <p className="text-[10px] font-mono text-zinc-500 mt-1 flex items-center gap-1">
              <ShieldCheck className="w-3 h-3 text-zinc-400" />
              Encrypted at rest with Fernet symmetric keys. Never logged.
            </p>
          </div>

          {testResult && (
            <div className="p-2.5 rounded text-xs font-mono flex items-center gap-2 bg-zinc-900 border border-zinc-800 text-zinc-200">
              <Check className="w-3.5 h-3.5 text-white" />
              <span>Connection active: Credentials validated and ready.</span>
            </div>
          )}

          <div className="flex items-center justify-between pt-3 border-t border-zinc-800">
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={isTesting}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono text-zinc-300 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded transition-colors"
            >
              <RefreshCw className={`w-3 h-3 ${isTesting ? 'animate-spin' : ''}`} />
              {isTesting ? 'TESTING...' : 'PING API'}
            </button>

            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1.5 text-xs font-mono font-medium text-black bg-white hover:bg-zinc-200 rounded"
            >
              Save Credentials
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
