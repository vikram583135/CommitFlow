'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { handleOAuthCallback } from '../../../lib/api';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import Link from 'next/link';

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const providerParam = searchParams.get('provider');
    const errorParam = searchParams.get('error') || searchParams.get('error_description');

    if (errorParam) {
      setStatus('error');
      setErrorMessage(errorParam);
      return;
    }

    if (!code) {
      setStatus('error');
      setErrorMessage('No authorization code was provided in the OAuth callback.');
      return;
    }

    // Determine provider from state or query param
    const provider: 'github' | 'google' =
      state === 'google' || providerParam === 'google' ? 'google' : 'github';

    handleOAuthCallback(provider, code)
      .then(() => {
        setStatus('success');
        setTimeout(() => {
          router.push('/');
        }, 1200);
      })
      .catch((err: any) => {
        setStatus('error');
        setErrorMessage(err.message || 'OAuth token exchange failed');
      });
  }, [searchParams, router]);

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-xl bg-zinc-950 p-6 border border-zinc-800 shadow-2xl text-center">
        {status === 'loading' && (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 text-zinc-400 animate-spin" />
            <h2 className="text-sm font-mono uppercase tracking-wider font-semibold text-white">
              Authenticating with OAuth...
            </h2>
            <p className="text-xs text-zinc-400">Verifying credentials and establishing session</p>
          </div>
        )}

        {status === 'success' && (
          <div className="flex flex-col items-center gap-3">
            <CheckCircle2 className="w-8 h-8 text-zinc-100" />
            <h2 className="text-sm font-mono uppercase tracking-wider font-semibold text-white">
              Authentication Successful
            </h2>
            <p className="text-xs text-zinc-400">Redirecting to your dashboard...</p>
          </div>
        )}

        {status === 'error' && (
          <div className="flex flex-col items-center gap-3">
            <AlertCircle className="w-8 h-8 text-red-400" />
            <h2 className="text-sm font-mono uppercase tracking-wider font-semibold text-white">
              Authentication Failed
            </h2>
            <p className="text-xs text-zinc-400 font-mono mt-1">{errorMessage}</p>
            <Link
              href="/"
              className="mt-4 px-4 py-2 text-xs font-mono font-medium text-black bg-white hover:bg-zinc-200 rounded transition-colors"
            >
              Return to Dashboard
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-black text-white flex items-center justify-center">
          <Loader2 className="w-6 h-6 text-zinc-400 animate-spin" />
        </div>
      }
    >
      <CallbackHandler />
    </Suspense>
  );
}
