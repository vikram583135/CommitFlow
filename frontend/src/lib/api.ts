import { Automation, Execution, Repository, AIProviderConfig } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getAuthHeader(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem('commitflow_token');
  return token ? { Authorization: `Token ${token}` } : {};
}

export function setAuthToken(token: string) {
  if (typeof window !== 'undefined') {
    localStorage.setItem('commitflow_token', token);
  }
}

export function clearAuthToken() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('commitflow_token');
  }
}

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('commitflow_token');
}

// ── Auth APIs ──

export async function loginWithEmail(email: string, password: string) {
  const res = await fetch(`${API_BASE}/api/auth/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.non_field_errors?.[0] || 'Invalid credentials');
  }
  const data = await res.json();
  setAuthToken(data.token);
  return data;
}

export async function registerWithEmail(email: string, password: string, name: string) {
  const res = await fetch(`${API_BASE}/api/auth/register/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.email?.[0] || 'Registration failed');
  }
  const data = await res.json();
  setAuthToken(data.token);
  return data;
}

export async function getOAuthUrl(provider: 'github' | 'google') {
  const redirectUri = typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : '';
  const res = await fetch(`${API_BASE}/api/auth/oauth/url/?provider=${provider}&redirect_uri=${encodeURIComponent(redirectUri)}`);
  return await res.json();
}

export async function handleOAuthCallback(provider: 'github' | 'google', code: string) {
  const redirectUri = typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : '';
  const res = await fetch(`${API_BASE}/api/auth/oauth/callback/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, code, redirect_uri: redirectUri }),
  });
  if (!res.ok) throw new Error('OAuth authentication failed');
  const data = await res.json();
  setAuthToken(data.token);
  return data;
}

export async function getMe() {
  const res = await fetch(`${API_BASE}/api/auth/me/`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error('Unauthorized');
  return await res.json();
}

export async function logoutUser() {
  try {
    await fetch(`${API_BASE}/api/auth/logout/`, {
      method: 'POST',
      headers: getAuthHeader(),
    });
  } finally {
    clearAuthToken();
  }
}

// ── Automations APIs ──

export async function fetchAutomations(): Promise<Automation[]> {
  const res = await fetch(`${API_BASE}/api/automations/`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) return [];
  return await res.json();
}

export async function createAutomation(data: Partial<Automation>): Promise<Automation> {
  const res = await fetch(`${API_BASE}/api/automations/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(JSON.stringify(err));
  }
  return await res.json();
}

export async function toggleAutomation(id: string, enabled: boolean): Promise<Automation> {
  const res = await fetch(`${API_BASE}/api/automations/${id}/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error('Failed to toggle automation');
  return await res.json();
}

export async function triggerAutomation(id: string): Promise<Execution> {
  const res = await fetch(`${API_BASE}/api/automations/${id}/run/`, {
    method: 'POST',
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'Failed to trigger run');
  }
  return await res.json();
}

// ── Executions APIs ──

export async function fetchExecutions(): Promise<Execution[]> {
  const res = await fetch(`${API_BASE}/api/executions/`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) return [];
  return await res.json();
}

export async function approveExecution(id: string): Promise<Execution> {
  const res = await fetch(`${API_BASE}/api/executions/${id}/approve/`, {
    method: 'POST',
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error('Approval failed');
  return await res.json();
}

// ── Repositories APIs ──

export async function fetchRepositories(): Promise<Repository[]> {
  const res = await fetch(`${API_BASE}/api/github/repositories/`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) return [];
  return await res.json();
}

export async function syncRepositories(): Promise<Repository[]> {
  const res = await fetch(`${API_BASE}/api/github/repositories/sync/`, {
    method: 'POST',
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error('Repository sync failed');
  return await res.json();
}

// ── AI Configs APIs ──

export async function fetchAIConfigs(): Promise<AIProviderConfig[]> {
  const res = await fetch(`${API_BASE}/api/ai-configs/`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) return [];
  return await res.json();
}

export async function saveAIConfig(provider: string, model_name: string, api_key: string): Promise<AIProviderConfig> {
  const res = await fetch(`${API_BASE}/api/ai-configs/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify({ provider, model_name, api_key, is_active: true }),
  });
  if (!res.ok) throw new Error('Failed to save AI config');
  return await res.json();
}

export async function testAIConfig(id: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/ai-configs/${id}/test/`, {
    method: 'POST',
    headers: getAuthHeader(),
  });
  if (!res.ok) return false;
  const data = await res.json();
  return !!data.success;
}
