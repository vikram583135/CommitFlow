'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Header } from '../components/Header';
import { MetricCards } from '../components/MetricCards';
import { DiffViewer } from '../components/DiffViewer';
import { AutomationModal } from '../components/AutomationModal';
import { AISettingsModal } from '../components/AISettingsModal';
import { AuthModal } from '../components/AuthModal';
import { ExecutionDrawer } from '../components/ExecutionDrawer';
import { OnboardingHero } from '../components/OnboardingHero';
import { Automation, Execution, Repository, AIProviderConfig } from '../types';
import {
  fetchAutomations,
  fetchExecutions,
  fetchRepositories,
  syncRepositories,
  fetchAIConfigs,
  createAutomation,
  toggleAutomation,
  triggerAutomation,
  getMe,
  logoutUser,
  getStoredToken,
  fetchExecution, fetchExecutionPage, fetchMetrics, Metrics, approveExecution, retryExecution,
} from '../lib/api';
import { Clock, ChevronRight, Pause, PlayCircle, Play } from 'lucide-react';

export default function Dashboard() {
  const [user, setUser] = useState<any | null>(null);
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [aiConfigs, setAiConfigs] = useState<AIProviderConfig[]>([]);
  const [selectedExecution, setSelectedExecution] = useState<Execution | null>(null);

  // Modals & Drawers State
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isAutomationModalOpen, setIsAutomationModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null);
  const [isSyncingRepos, setIsSyncingRepos] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'executions' | 'automations'>('overview');
  const [error,setError] = useState('');
  const [hasMore,setHasMore] = useState(false);
  const [loadingMore,setLoadingMore] = useState(false);
  const [metrics,setMetrics] = useState<Metrics>({streak_days:0,active_automations:0,total_prs:0,validation_pass_rate:null});
  const loadVersion=useRef(0);
  const startingRun=useRef(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  async function loadInitialData() {
    const version=++loadVersion.current;
    if(!getStoredToken()) return;
    setError('');
    try {
      const [profile,autos,page,repos,configs,stats]=await Promise.all([
        getMe(),fetchAutomations(),fetchExecutionPage(),fetchRepositories(),fetchAIConfigs(),fetchMetrics(),
      ]);
      if(version!==loadVersion.current) return;
      setUser(profile);setAutomations(autos);setExecutions(page.results);setRepositories(repos);setAiConfigs(configs);setMetrics(stats);setHasMore(!!page.next);
      if(page.results[0]) await selectExecution(page.results[0]);
    } catch(err) {if(version===loadVersion.current) setError((err as Error).message);}
  }

  async function selectExecution(execution:Execution) {
    setSelectedExecution(execution);
    try {const detail=await fetchExecution(execution.id);setSelectedExecution(current=>current?.id===detail.id?detail:current);}
    catch(err) {setError((err as Error).message);}
  }
  const updateExecution=useCallback((run:Execution)=>{
    setExecutions(previous=>previous.map(item=>item.id===run.id?run:item));
    setSelectedExecution(previous=>previous?.id===run.id?run:previous);
    if(['SUCCESS','FAILED','REJECTED','CANCELLED','AWAITING_APPROVAL'].includes(run.status)) {
      fetchMetrics().then(setMetrics).catch(err=>setError((err as Error).message));
    }
  },[]);
  async function resumeExecution(run:Execution,approve:boolean) {
    const result=approve?await approveExecution(run.id,run.proposal_hash || ''):await retryExecution(run.id);
    updateExecution(result);setActiveExecutionId(result.id);setIsDrawerOpen(true);
  }
  async function loadMore() {
    const version=loadVersion.current;
    setLoadingMore(true);
    try {const page=await fetchExecutionPage(executions.length);if(version!==loadVersion.current)return;setExecutions(previous=>[
      ...previous,...page.results.filter(item=>!previous.some(existing=>existing.id===item.id))]);setHasMore(!!page.next);}
    catch(err){setError((err as Error).message);}finally{setLoadingMore(false);}
  }

  const handleLogout = async () => {
    ++loadVersion.current;
    try{await logoutUser();}catch(err){setError((err as Error).message);}
    setUser(null);
    setAutomations([]);
    setExecutions([]);
    setRepositories([]);
    setSelectedExecution(null);
    setAiConfigs([]);setIsDrawerOpen(false);setActiveExecutionId(null);setHasMore(false);
    setMetrics({streak_days:0,active_automations:0,total_prs:0,validation_pass_rate:null});
  };

  const handleSyncRepos = async () => {
    setIsSyncingRepos(true);
    try {
      const repos = await syncRepositories();
      setRepositories(repos);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsSyncingRepos(false);
    }
  };

  const handleToggleAutomation = async (id: string, currentEnabled: boolean) => {
    try {
      const updated = await toggleAutomation(id, !currentEnabled);
      setAutomations((prev) => prev.map((a) => (a.id === id ? updated : a)));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleTriggerRun = async (automationId?: string) => {
    if(startingRun.current) return;
    const targetId = automationId || automations[0]?.id;
    if (!targetId) {
      setIsAutomationModalOpen(true);
      return;
    }

    try {
      startingRun.current=true;
      const run = await triggerAutomation(targetId);
      setActiveExecutionId(run.id);
      setIsDrawerOpen(true);

      // Refresh executions after starting run
      const execs = await fetchExecutions();
      setExecutions(execs);
    } catch (err: any) {
      alert(err.message || 'Failed to trigger run');
    } finally {startingRun.current=false;}
  };

  const handleSaveAutomation = async (newAuto: Partial<Automation>) => {
      const created = await createAutomation(newAuto);
      setAutomations((prev) => [created, ...prev]);
      setRepositories(await fetchRepositories());
      setMetrics(await fetchMetrics());
  };

  return (
    <div className="min-h-screen bg-black text-white flex flex-col font-sans">
      <Header
        user={user}
        onOpenAuth={() => setIsAuthModalOpen(true)}
        onLogout={handleLogout}
        onNewAutomation={() => user?setIsAutomationModalOpen(true):setIsAuthModalOpen(true)}
        onOpenSettings={() => user?setIsSettingsModalOpen(true):setIsAuthModalOpen(true)}
        onSyncRepos={handleSyncRepos}
        isSyncingRepos={isSyncingRepos}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full space-y-6 flex-1">
        {error && <div role="alert" className="p-3 text-xs text-red-300 border border-zinc-700 rounded">{error}</div>}
        {/* Metric Cards Row */}
        <MetricCards
          streakDays={metrics.streak_days}
          activeAutomations={automations.filter((a) => a.enabled).length}
          totalPRs={metrics.total_prs}
          securityRate={metrics.validation_pass_rate}
        />

        {/* If no automations configured yet: Show Onboarding Hero */}
        {automations.length === 0 ? (
          <OnboardingHero
            hasGitHub={repositories.length > 0}
            hasAIConfig={aiConfigs.some(config=>config.is_active)}
            onConnectGitHub={() => setIsAuthModalOpen(true)}
            onOpenAIConfig={() => user?setIsSettingsModalOpen(true):setIsAuthModalOpen(true)}
            onCreateAutomation={() => user?setIsAutomationModalOpen(true):setIsAuthModalOpen(true)}
          />
        ) : (
          <>
            {/* Dashboard Navigation Tabs */}
            <div className="flex border-b border-zinc-800 gap-6 text-xs font-mono">
              <button
                onClick={() => setActiveTab('overview')}
                className={`pb-2.5 transition-colors border-b-2 uppercase tracking-wider ${
                  activeTab === 'overview'
                    ? 'border-white text-white font-semibold'
                    : 'border-transparent text-zinc-500 hover:text-zinc-300'
                }`}
              >
                Diff Inspector
              </button>
              <button
                onClick={() => setActiveTab('automations')}
                className={`pb-2.5 transition-colors border-b-2 uppercase tracking-wider ${
                  activeTab === 'automations'
                    ? 'border-white text-white font-semibold'
                    : 'border-transparent text-zinc-500 hover:text-zinc-300'
                }`}
              >
                Active Rules ({automations.length})
              </button>
              <button
                onClick={() => setActiveTab('executions')}
                className={`pb-2.5 transition-colors border-b-2 uppercase tracking-wider ${
                  activeTab === 'executions'
                    ? 'border-white text-white font-semibold'
                    : 'border-transparent text-zinc-500 hover:text-zinc-300'
                }`}
              >
                Audit Log ({executions.length})
              </button>
            </div>

            {/* Tab 1: Overview & Diff Viewer */}
            {activeTab === 'overview' && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                {/* Left Column: Configured Rules & Run Triggers */}
                <div className="lg:col-span-5 space-y-4">
                  <div className="mono-panel p-4 rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-300 font-semibold">
                        Habit Workflows
                      </h3>
                      <button
                        onClick={() => handleTriggerRun()}
                        className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono text-black bg-white hover:bg-zinc-200 rounded font-medium transition-colors"
                      >
                        <Play className="w-3 h-3 text-black fill-black" />
                        <span>RUN NOW</span>
                      </button>
                    </div>

                    <div className="space-y-2">
                      {automations.map((auto) => (
                        <div
                          key={auto.id}
                          className="p-3 rounded bg-zinc-950 border border-zinc-800/90 hover:border-zinc-700 transition-all"
                        >
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-xs text-white">{auto.title}</span>
                                <span
                                  className={`text-[10px] font-mono px-1.5 py-0.2 rounded border ${
                                    auto.enabled
                                      ? 'border-zinc-700 bg-zinc-900 text-zinc-200'
                                      : 'border-zinc-800 bg-black text-zinc-600'
                                  }`}
                                >
                                  {auto.enabled ? 'ACTIVE' : 'PAUSED'}
                                </span>
                              </div>
                              <p className="text-[11px] text-zinc-400 mt-1 line-clamp-1">{auto.instructions}</p>
                              <div className="flex items-center gap-2 mt-2 text-[10px] text-zinc-500 font-mono">
                                <Clock className="w-3 h-3 text-zinc-400" />
                                <span>{auto.cron_expression} ({auto.timezone})</span>
                                <span>•</span>
                                <span className="text-zinc-300">
                                  {auto.repository_details?.full_name || 'Authorized Repo'}
                                </span>
                              </div>
                            </div>

                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => handleTriggerRun(auto.id)}
                                title="Run this habit workflow now"
                                className="p-1 rounded bg-black text-zinc-400 hover:text-white border border-zinc-800 transition-colors"
                              >
                                <Play className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleToggleAutomation(auto.id, auto.enabled)}
                                className="p-1 rounded bg-black text-zinc-400 hover:text-white border border-zinc-800 transition-colors"
                                title={auto.enabled ? 'Pause automation' : 'Resume automation'}
                              >
                                {auto.enabled ? <Pause className="w-3.5 h-3.5" /> : <PlayCircle className="w-3.5 h-3.5" />}
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Recent Pipeline Runs List */}
                  <div className="mono-panel p-4 rounded-lg">
                    <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-300 font-semibold mb-3">
                      Recent Pipeline Runs
                    </h3>
                    {executions.length === 0 ? (
                      <div className="p-4 rounded border border-dashed border-zinc-850 text-center text-xs font-mono text-zinc-500">
                        No execution records yet. Click "RUN NOW" to trigger your first habit run.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {executions.slice(0, 5).map((exec) => {
                          const isSelected = selectedExecution?.id === exec.id;
                          return (
                            <div
                              key={exec.id}
                              onClick={() => selectExecution(exec)}
                              className={`p-2.5 rounded border cursor-pointer transition-all ${
                                isSelected
                                  ? 'bg-zinc-900 border-zinc-500'
                                  : 'bg-zinc-950 border-zinc-850 hover:border-zinc-700'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span
                                    className={`w-1.5 h-1.5 rounded-full ${
                                      exec.status === 'SUCCESS' ? 'bg-white' : 'bg-zinc-500'
                                    }`}
                                  />
                                  <span className="text-xs font-medium text-white">{exec.automation_title}</span>
                                </div>
                                <span className="text-[10px] text-zinc-500 font-mono">
                                  {new Date(exec.started_at).toLocaleTimeString([], {
                                    hour: '2-digit',
                                    minute: '2-digit',
                                  })}
                                </span>
                              </div>
                              <p className="text-[11px] text-zinc-400 mt-1 font-mono truncate">
                                {exec.scheduled_slot}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right Column: Code Diff & Safety Inspector */}
                <div className="lg:col-span-7">
                  <DiffViewer execution={selectedExecution} onApprove={run=>resumeExecution(run,true)} onRetry={run=>resumeExecution(run,false)}/>
                </div>
              </div>
            )}

            {/* Tab 2: Automations Grid */}
            {activeTab === 'automations' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {automations.map((auto) => (
                  <div key={auto.id} className="mono-panel p-5 rounded-lg">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-mono uppercase tracking-wider font-bold text-white">{auto.title}</h4>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                          auto.enabled
                            ? 'border-zinc-700 bg-zinc-900 text-zinc-200'
                            : 'border-zinc-800 bg-black text-zinc-600'
                        }`}
                      >
                        {auto.enabled ? 'ACTIVE' : 'PAUSED'}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-300 mt-2">{auto.instructions}</p>
                    <div className="mt-4 pt-3 border-t border-zinc-800 grid grid-cols-2 gap-2 text-xs font-mono">
                      <div>
                        <span className="text-zinc-500 block text-[10px]">REPO</span>
                        <span className="text-white text-[11px]">
                          {auto.repository_details?.full_name || 'Configured Repo'}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[10px]">SCHEDULE</span>
                        <span className="text-white text-[11px]">{auto.cron_expression}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Tab 3: Execution History Table */}
            {activeTab === 'executions' && (
              <div className="mono-panel rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs text-zinc-300">
                  <thead className="bg-zinc-950 border-b border-zinc-800 text-zinc-500 uppercase text-[10px] font-mono">
                    <tr>
                      <th className="py-3 px-4">SLOT</th>
                      <th className="py-3 px-4">AUTOMATION</th>
                      <th className="py-3 px-4">STATUS</th>
                      <th className="py-3 px-4">PULL REQUEST</th>
                      <th className="py-3 px-4">ACTION</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-900 font-mono text-[11px]">
                    {executions.map((exec) => (
                      <tr key={exec.id} className="hover:bg-zinc-950">
                        <td className="py-3 px-4">{exec.scheduled_slot}</td>
                        <td className="py-3 px-4 font-sans text-white">{exec.automation_title}</td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded bg-zinc-900 text-zinc-200 border border-zinc-800">
                            {exec.status}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          {exec.published_change?.pull_request_url ? (
                            <a
                              href={exec.published_change.pull_request_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-white underline"
                            >
                              PR #{exec.published_change.pull_request_number}
                            </a>
                          ) : (
                            <span>{exec.published_change?.commit_sha?.slice(0, 7) || 'N/A'}</span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-sans">
                          <button
                            onClick={() => {
                              selectExecution(exec);
                              setActiveTab('overview');
                            }}
                            className="text-zinc-300 hover:text-white flex items-center gap-1 font-mono text-[10px] uppercase"
                          >
                            DIFF <ChevronRight className="w-3 h-3" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {hasMore && <button disabled={loadingMore} onClick={loadMore} className="p-4 text-xs text-zinc-300">{loadingMore?'Loading...':'Load more executions'}</button>}
              </div>
            )}
          </>
        )}
      </main>

      {/* Modals & Live Execution Drawer */}
      <AuthModal
        linking={!!user}
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onSuccess={(loggedUser) => {
          setUser(loggedUser);
          loadInitialData();
        }}
      />
      <AutomationModal
        isOpen={isAutomationModalOpen}
        onClose={() => setIsAutomationModalOpen(false)}
        repositories={repositories}
        onSave={handleSaveAutomation}
      />
      <AISettingsModal
        configs={aiConfigs}
        onSaved={async()=>{setAiConfigs(await fetchAIConfigs());}}
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
      />
      <ExecutionDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        executionId={activeExecutionId}
        onUpdate={updateExecution}
        onViewDiff={async (id) => {
          try {setSelectedExecution(await fetchExecution(id));setActiveTab('overview');}catch(err){setError((err as Error).message);}
        }}
      />
    </div>
  );
}
