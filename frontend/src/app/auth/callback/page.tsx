'use client';
import React, { useEffect, useRef, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { handleOAuthCallback, apiRequest } from '../../../lib/api';
import Link from 'next/link';

function CallbackHandler() {
  const router = useRouter();
  const params = useSearchParams();
  const started = useRef(false);
  const [status,setStatus] = useState('Verifying your sign-in...');
  const [error,setError] = useState('');
  const [password,setPassword] = useState('');
  const [busy,setBusy] = useState(false);
  const isReset = !!params.get('reset_token');
  useEffect(() => {
    if (started.current || isReset) return;
    started.current = true;
    const run = async () => {
      if (params.get('verify')) {
        const result = await apiRequest<{message:string}>('/api/auth/verify-email/',{method:'POST',body:JSON.stringify({ticket:params.get('verify')})});
        setStatus(result.message);
        return;
      }
      if (params.get('error')) throw new Error('Sign-in was cancelled or declined.');
      const code=params.get('code'), state=params.get('state');
      const stored=JSON.parse(sessionStorage.getItem('commitflow_oauth') || 'null');
      if (!code || !state || !stored) throw new Error('No valid sign-in attempt was found. Start again.');
      await handleOAuthCallback(stored.provider,code,state);
      setStatus('Sign-in complete. Returning to your dashboard...');
      router.replace('/');
    };
    run().catch((err:Error) => setError(err.message));
  }, [params,router,isReset]);
  const reset = async (event:React.FormEvent) => {
    event.preventDefault(); setBusy(true);setError('');
    try {
      const result = await apiRequest<{message:string}>('/api/auth/password-reset/confirm/',{method:'POST',body:JSON.stringify({
        user:params.get('reset_user'),token:params.get('reset_token'),password,
      })});
      setStatus(result.message);setPassword('');router.replace('/');
    } catch(err) { setError((err as Error).message); } finally {setBusy(false);}
  };
  return <main className="min-h-screen bg-black text-white flex items-center justify-center p-4">
    <div className="w-full max-w-sm rounded-xl bg-zinc-950 p-6 border border-zinc-800 space-y-4 text-sm">
      {isReset ? <form onSubmit={reset} className="space-y-3"><h1>Choose a new password</h1>
        <input type="password" autoComplete="new-password" minLength={8} required value={password}
          onChange={e=>setPassword(e.target.value)} className="w-full p-2 bg-black border border-zinc-700 rounded" aria-label="New password"/>
        <button disabled={busy} className="px-4 py-2 bg-white text-black rounded">{busy?'Saving...':'Update password'}</button>
      </form> : <p role="status">{status}</p>}
      {error && <p role="alert" className="text-red-300">{error}</p>}
      <Link href="/" className="block text-zinc-400 underline">Return to dashboard</Link>
    </div>
  </main>;
}
export default function OAuthCallbackPage() {
  return <Suspense fallback={<p>Loading...</p>}><CallbackHandler/></Suspense>;
}
