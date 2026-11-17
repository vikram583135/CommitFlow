import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { AIProviderConfig } from '../types';
import { saveAIConfig, testAIConfig } from '../lib/api';

interface Props { isOpen:boolean; onClose:()=>void; configs:AIProviderConfig[]; onSaved:()=>Promise<void> }
const defaultModels = {openai:'gpt-4o-mini',anthropic:'claude-3-5-sonnet-20241022',gemini:'gemini-2.5-flash'};
export const AISettingsModal:React.FC<Props> = ({isOpen,onClose,configs,onSaved}) => {
  const [provider,setProvider] = useState<AIProviderConfig['provider']>('openai');
  const [model,setModel] = useState(defaultModels.openai);
  const [apiKey,setApiKey] = useState('');
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState('');
  const [error,setError] = useState('');
  useEffect(() => {
    if (isOpen) {const config=configs.find(c=>c.is_active);setProvider(config?.provider || 'openai');setModel(config?.model_name || defaultModels.openai);}
    setApiKey('');setMessage('');setError('');
  },[isOpen]);
  if(!isOpen) return null;
  const existing = configs.find(c=>c.provider===provider);
  const save = async (test:boolean) => {
    setBusy(true);setError('');setMessage('');
    try {
      if (!apiKey.trim() && !existing?.masked_api_key) throw new Error('Enter a provider API key.');
      if (!model.trim()) throw new Error('Enter a model identifier.');
      const config=await saveAIConfig(provider,model.trim(),apiKey.trim(),existing?.id);
      setApiKey('');await onSaved();
      if (test) {
        if (!await testAIConfig(config.id)) throw new Error('Provider rejected the credentials or model. Check the key and model identifier.');
        setMessage('Provider connection and model access confirmed.');
      } else {onClose();}
    } catch(err) {setError((err as Error).message);} finally {setBusy(false);}
  };
  return <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
    <div role="dialog" aria-modal="true" aria-label="AI credentials" className="mono-panel w-full max-w-md rounded-xl bg-zinc-950 p-6 space-y-4">
      <div className="flex justify-between"><h2>AI Engine Credentials</h2><button onClick={onClose} disabled={busy} aria-label="Close"><X className="w-4 h-4"/></button></div>
      <label className="block text-xs">Provider<select disabled={busy} value={provider} onChange={e=>{
        const next=e.target.value as AIProviderConfig['provider'];setProvider(next);
        setModel(configs.find(c=>c.provider===next)?.model_name || defaultModels[next]);setApiKey('');setMessage('');
      }} className="block w-full mt-1 p-2 bg-black border border-zinc-700 rounded">
        <option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="gemini">Google Gemini</option>
      </select></label>
      <label className="block text-xs">Model identifier<input disabled={busy} value={model} onChange={e=>setModel(e.target.value)}
        className="block w-full mt-1 p-2 bg-black border border-zinc-700 rounded"/></label>
      <label className="block text-xs">API key<input disabled={busy} type="password" autoComplete="off" value={apiKey}
        placeholder={existing?.masked_api_key ? 'Leave blank to keep '+existing.masked_api_key : 'Provider API key'}
        onChange={e=>setApiKey(e.target.value)} className="block w-full mt-1 p-2 bg-black border border-zinc-700 rounded"/></label>
      <p className="text-xs text-zinc-400">Your key is encrypted before storage.</p>
      {message && <p role="status" className="text-xs">{message}</p>}{error && <p role="alert" className="text-xs text-red-300">{error}</p>}
      <div className="flex justify-between"><button disabled={busy} onClick={()=>save(true)} className="text-xs border border-zinc-700 rounded p-2">{busy?'Working...':'Save & Test'}</button>
        <button disabled={busy} onClick={()=>save(false)} className="text-xs bg-white text-black rounded p-2">Save Credentials</button></div>
    </div>
  </div>;
};
