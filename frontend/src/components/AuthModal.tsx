import React, { useState } from 'react';
import { X, Github, Mail, ArrowRight } from 'lucide-react';
import { loginWithEmail, registerWithEmail, getOAuthUrl, requestPasswordReset, apiRequest } from '../lib/api';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: any) => void;
  linking?: boolean;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess, linking=false }) => {
  const [mode, setMode] = useState<'login' | 'register' | 'reset'>('login');
  const [notice, setNotice] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setNotice(null);
    try {
      let data;
      if (mode === 'login') {
        data = await loginWithEmail(email, password);
      } else if (mode === 'register') {
        data = await registerWithEmail(email, password, name);
      } else {
        const result = await requestPasswordReset(email);
        setNotice(result.message);
        return;
      }
      setPassword('');
      if (!data.token) { setNotice(data.message || 'Check your email.'); return; }
      onSuccess(data.user);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOAuthLogin = async (provider: 'github' | 'google') => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getOAuthUrl(provider);
      window.location.href = data.url;
    } catch (err: any) {
      setError(err.message || `Failed to sign in with ${provider}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm">
      <div className="mono-panel w-full max-w-sm rounded-xl bg-zinc-950 p-6 shadow-2xl border border-zinc-800">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div>
            <h2 className="text-sm font-mono uppercase tracking-wider font-semibold text-white">
              {linking ? 'Connect a social account' : mode === 'login' ? 'Sign In to CommitFlow' : mode === 'reset' ? 'Reset Password' : 'Create Account'}
            </h2>
            <p className="text-[11px] text-zinc-400">Authentic Habit Engineering Platform</p>
          </div>
          <button onClick={onClose} className="p-1 rounded text-zinc-400 hover:text-white hover:bg-zinc-900">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <div className="mt-3 p-2.5 rounded bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-300">
            {error}
          </div>
        )}
        {notice && <p role="status" className="mt-3 text-xs text-zinc-300">{notice}</p>}

        <div className="mt-4 space-y-2">
          {/* GitHub Social Auth */}
          <button
            type="button"
            onClick={() => handleOAuthLogin('github')}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-mono font-medium text-black bg-white hover:bg-zinc-200 rounded transition-colors"
          >
            <Github className="w-4 h-4 fill-black" />
            <span>CONTINUE WITH GITHUB</span>
          </button>

          {/* Google Social Auth */}
          <button
            type="button"
            onClick={() => handleOAuthLogin('google')}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-mono font-medium text-white bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 rounded transition-colors"
          >
            <Mail className="w-4 h-4" />
            <span>CONTINUE WITH GOOGLE</span>
          </button>
        </div>

        {!linking && <><div className="relative my-4">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-zinc-900" />
          </div>
          <div className="relative flex justify-center text-[10px] uppercase font-mono">
            <span className="bg-zinc-950 px-2 text-zinc-500">OR EMAIL</span>
          </div>
        </div></>}

        {/* Email/Password Form */}
        {!linking && <form onSubmit={handleSubmit} className="space-y-3">
          {mode === 'register' && (
            <div>
              <label className="block text-[10px] font-mono text-zinc-400 mb-1">FULL NAME</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Developer"
                className="w-full px-3 py-1.5 text-xs rounded bg-black border border-zinc-800 text-white font-mono focus:outline-none focus:border-zinc-500"
                required
              />
            </div>
          )}

          <div>
            <label className="block text-[10px] font-mono text-zinc-400 mb-1">EMAIL ADDRESS</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="developer@example.com"
              className="w-full px-3 py-1.5 text-xs rounded bg-black border border-zinc-800 text-white font-mono focus:outline-none focus:border-zinc-500"
              required
            />
          </div>

          {mode !== 'reset' && <div>
            <label className="block text-[10px] font-mono text-zinc-400 mb-1">PASSWORD</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full px-3 py-1.5 text-xs rounded bg-black border border-zinc-800 text-white font-mono focus:outline-none focus:border-zinc-500"
              required
            />
          </div>}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 mt-2 text-xs font-mono font-medium text-white bg-zinc-800 hover:bg-zinc-700 rounded transition-colors"
          >
            <span>{mode === 'login' ? 'SIGN IN' : mode === 'reset' ? 'SEND RESET LINK' : 'CREATE ACCOUNT'}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
          <button type="button" onClick={() => {setMode('reset');setError(null);setNotice(null);}}
            className="block mx-auto mt-3 text-[11px] text-zinc-400">Forgot password?</button>
          <button type="button" disabled={isLoading || !email} onClick={async()=>{
            setIsLoading(true);setError(null);
            try {const result=await apiRequest<{message:string}>('/api/auth/resend-verification/',{method:'POST',body:JSON.stringify({email})});setNotice(result.message);}
            catch(err){setError((err as Error).message);}finally{setIsLoading(false);}
          }} className="block mx-auto mt-3 text-[11px] text-zinc-400">Resend verification email</button>
        </form>}

        {!linking && <div className="mt-4 pt-3 border-t border-zinc-900 text-center">
          <button
            type="button"
            onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
            className="text-[11px] font-mono text-zinc-400 hover:text-white"
          >
            {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
          </button>
        </div>}
      </div>
    </div>
  );
};
