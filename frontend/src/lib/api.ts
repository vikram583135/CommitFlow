import { Automation, Execution, Repository, AIProviderConfig } from '../types';

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
export function getStoredToken(): string | null {
  return typeof window === 'undefined' ? null : localStorage.getItem('commitflow_token');
}
export function setAuthToken(token: string) { localStorage.setItem('commitflow_token', token); }
export function clearAuthToken() { localStorage.removeItem('commitflow_token'); }
function errorText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(errorText).join(' ');
  if (value && typeof value === 'object') return Object.values(value).map(errorText).join(' ');
  return 'Request failed. Please try again.';
}
export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init, headers: { ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Token ${token}` } : {}), ...init.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) clearAuthToken();
    throw new Error(errorText(data.error || data.error_message || data.detail || data));
  }
  return data as T;
}
interface AuthResult { token?: string; user?: any; message?: string; verification_required?: boolean }
export async function loginWithEmail(email: string, password: string) {
  const data = await apiRequest<AuthResult>('/api/auth/login/', {method:'POST',body:JSON.stringify({email,password})});
  if (data.token) setAuthToken(data.token);
  return data;
}
export async function registerWithEmail(email: string, password: string, name: string) {
  return apiRequest<AuthResult>('/api/auth/register/', {method:'POST',body:JSON.stringify({email,password,name})});
}
export async function requestPasswordReset(email: string) {
  return apiRequest<{message:string}>('/api/auth/password-reset/', {method:'POST',body:JSON.stringify({email})});
}
function base64url(bytes: Uint8Array) {
  return btoa(String.fromCharCode(...Array.from(bytes))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
}
export async function getOAuthUrl(provider: 'github' | 'google') {
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(48)));
  const challenge = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
  const redirectUri = `${window.location.origin}/auth/callback`;
  const params = new URLSearchParams({provider,redirect_uri:redirectUri,code_challenge:challenge});
  const data = await apiRequest<{url:string;state:string}>(`/api/auth/oauth/url/?${params}`);
  sessionStorage.setItem('commitflow_oauth',JSON.stringify({provider,state:data.state,verifier,expires:Date.now()+600000}));
  return data;
}
export async function handleOAuthCallback(provider: 'github' | 'google', code: string, state: string) {
  const stored = JSON.parse(sessionStorage.getItem('commitflow_oauth') || 'null');
  if (!stored || stored.provider !== provider || stored.state !== state || stored.expires < Date.now()) {
    throw new Error('Sign-in attempt is invalid or expired. Start sign-in again.');
  }
  try {
    const data = await apiRequest<AuthResult>('/api/auth/oauth/callback/', {method:'POST',body:JSON.stringify({
      provider,code,state,code_verifier:stored.verifier,redirect_uri:`${window.location.origin}/auth/callback`,
    })});
    if (data.token) setAuthToken(data.token);
    return data;
  } finally { sessionStorage.removeItem('commitflow_oauth'); }
}
export function getMe() { return apiRequest<any>('/api/auth/me/'); }
export async function logoutUser() {
  try { await apiRequest('/api/auth/logout/',{method:'POST'}); } finally { clearAuthToken(); }
}
interface Page<T> { count:number; next:string|null; previous:string|null; results:T[] }
async function listAll<T>(path: string): Promise<T[]> {
  const results:T[]=[];
  for (let offset=0; offset<10000; offset+=100) {
    const page = await apiRequest<Page<T>>(`${path}?limit=100&offset=${offset}`);
    results.push(...page.results);
    if (!page.next) return results;
  }
  throw new Error('Too many records to display. Narrow the selection.');
}
export function fetchAutomations() { return listAll<Automation>('/api/automations/'); }
export function createAutomation(data: Partial<Automation>) {
  return apiRequest<Automation>('/api/automations/',{method:'POST',body:JSON.stringify(data)});
}
export function toggleAutomation(id: string, enabled: boolean) {
  return apiRequest<Automation>(`/api/automations/${id}/`,{method:'PATCH',body:JSON.stringify({enabled})});
}
export function triggerAutomation(id: string) {
  return apiRequest<Execution>(`/api/automations/${id}/run/`,{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()}});
}
export function fetchExecutionPage(offset=0) {
  return apiRequest<Page<Execution>>(`/api/executions/?limit=25&offset=${offset}`);
}
export async function fetchExecutions() { return (await fetchExecutionPage()).results; }
export function fetchExecution(id:string, signal?:AbortSignal) { return apiRequest<Execution>(`/api/executions/${id}/`,{signal}); }
export function approveExecution(id: string, proposal_hash: string) {
  return apiRequest<Execution>(`/api/executions/${id}/approve/`,{method:'POST',body:JSON.stringify({proposal_hash})});
}
export function retryExecution(id:string) { return apiRequest<Execution>(`/api/executions/${id}/retry/`,{method:'POST'}); }
export function fetchRepositories() { return listAll<Repository>('/api/github/repositories/'); }
export function syncRepositories() { return apiRequest<Repository[]>('/api/github/repositories/sync/',{method:'POST'}); }
export function fetchAIConfigs() { return listAll<AIProviderConfig>('/api/ai-configs/'); }
export function saveAIConfig(provider:string,model_name:string,api_key:string,id?:string) {
  return apiRequest<AIProviderConfig>(`/api/ai-configs/${id ? id+'/' : ''}`,{method:id?'PATCH':'POST',
    body:JSON.stringify({provider,model_name,...(api_key ? {api_key} : {}),is_active:true})});
}
export async function testAIConfig(id:string) {
  return (await apiRequest<{success:boolean}>(`/api/ai-configs/${id}/test/`,{method:'POST'})).success;
}
export interface Metrics { streak_days:number;active_automations:number;total_prs:number;validation_pass_rate:number|null }
export function fetchMetrics() {
  return apiRequest<Metrics>(`/api/executions/metrics/?timezone=${encodeURIComponent(Intl.DateTimeFormat().resolvedOptions().timeZone)}`);
}
