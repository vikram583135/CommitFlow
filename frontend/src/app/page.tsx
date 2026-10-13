'use client';

import React, { useState, useEffect } from 'react';
import { Header } from '../components/Header';
import { MetricCards } from '../components/MetricCards';
import { DiffViewer } from '../components/DiffViewer';
import { AutomationModal } from '../components/AutomationModal';
import { AISettingsModal } from '../components/AISettingsModal';
import { Automation, Execution } from '../types';
import { fetchAutomations, fetchExecutions } from '../lib/api';
import { Clock, ChevronRight, Pause, PlayCircle } from 'lucide-react';

export default function Dashboard() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [selectedExecution, setSelectedExecution] = useState<Execution | null>(null);
  const [isAutomationModalOpen, setIsAutomationModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isRunningDemo, setIsRunningDemo] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'executions' | 'automations'>('overview');

  useEffect(() => {
    async function loadData() {
      const [autos, execs] = await Promise.all([fetchAutomations(), fetchExecutions()]);
      setAutomations(autos);
      setExecutions(execs);
      if (execs.length > 0) {
        setSelectedExecution(execs[0]);
      }
    }
    loadData();
  }, []);

  const handleToggleAutomation = (id: string) => {
    setAutomations((prev) =>
      prev.map((a) => (a.id === id ? { ...a, enabled: !a.enabled } : a))
    );
  };

  const handleRunJavaDemo = () => {
    setIsRunningDemo(true);
    setTimeout(() => {
      const timestamp = new Date().toISOString().slice(0, 16).replace('T', ' ');
      const newExecution: Execution = {
        id: `exec-${Date.now()}`,
        automation: 'auto-1',
        automation_title: 'Daily Java 17 DSA Practice',
        repository_name: 'alex-developer/java-practice',
        status: 'SUCCESS',
        scheduled_slot: `Manual Run [${timestamp}]`,
        attempt_number: 1,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        validation_results: {
          is_valid: true,
          errors: [],
          warnings: []
        },
        generated_files: [
          {
            id: `gf-${Date.now()}-1`,
            file_path: 'src/main/java/dsa/BSTNode.java',
            change_type: 'CREATE',
            new_content: `package dsa;\n\n/**\n * Binary Search Tree Node with insertion and in-order traversal.\n */\npublic class BSTNode {\n    public int val;\n    public BSTNode left;\n    public BSTNode right;\n\n    public BSTNode(int val) {\n        this.val = val;\n    }\n\n    public void insert(int newVal) {\n        if (newVal < this.val) {\n            if (this.left == null) this.left = new BSTNode(newVal);\n            else this.left.insert(newVal);\n        } else if (newVal > this.val) {\n            if (this.right == null) this.right = new BSTNode(newVal);\n            else this.right.insert(newVal);\n        }\n    }\n}`,
            diff_patch: '+++ b/src/main/java/dsa/BSTNode.java'
          },
          {
            id: `gf-${Date.now()}-2`,
            file_path: 'src/test/java/dsa/BSTNodeTest.java',
            change_type: 'CREATE',
            new_content: `package dsa;\n\nimport org.junit.jupiter.api.Test;\nimport static org.junit.jupiter.api.Assertions.*;\n\npublic class BSTNodeTest {\n    @Test\n    public void testInsertMultipleValues() {\n        BSTNode root = new BSTNode(50);\n        root.insert(30);\n        root.insert(70);\n        root.insert(20);\n        root.insert(40);\n\n        assertNotNull(root.left);\n        assertNotNull(root.right);\n        assertEquals(30, root.left.val);\n        assertEquals(70, root.right.val);\n        assertEquals(20, root.left.left.val);\n        assertEquals(40, root.left.right.val);\n    }\n}`,
            diff_patch: '+++ b/src/test/java/dsa/BSTNodeTest.java'
          }
        ],
        published_change: {
          id: `pub-${Date.now()}`,
          branch_name: `automation/dsa-${Date.now().toString(16)}`,
          commit_sha: 'a4b1c89f0e123d456789abcdef0123456789abcd',
          commit_message: `feat(dsa): add BST implementation with JUnit 5 test cases`,
          pull_request_url: 'https://github.com/alex-developer/java-practice/pull/43',
          pull_request_number: 43,
          published_at: new Date().toISOString()
        }
      };

      setExecutions((prev) => [newExecution, ...prev]);
      setSelectedExecution(newExecution);
      setIsRunningDemo(false);
    }, 1200);
  };

  const handleAddAutomation = (newAuto: Partial<Automation>) => {
    const created: Automation = {
      id: `auto-${Date.now()}`,
      title: newAuto.title || 'Untitled Automation',
      task_type: newAuto.task_type || 'coding_practice',
      instructions: newAuto.instructions || '',
      repository: 'repo-1',
      repository_details: {
        id: 'repo-1',
        github_repo_id: '8219482',
        full_name: 'alex-developer/java-practice',
        default_branch: 'main',
        allowed_paths: ['src/'],
        is_active: true
      },
      cron_expression: newAuto.cron_expression || '0 9 * * *',
      timezone: 'UTC',
      branch_strategy: newAuto.branch_strategy || 'PULL_REQUEST',
      require_approval: !!newAuto.require_approval,
      max_files: 3,
      enabled: true,
      last_run_at: new Date().toISOString(),
    };
    setAutomations((prev) => [created, ...prev]);
  };

  return (
    <div className="min-h-screen bg-black text-white flex flex-col font-sans">
      <Header
        onNewAutomation={() => setIsAutomationModalOpen(true)}
        onOpenSettings={() => setIsSettingsModalOpen(false)}
        onRunDemo={handleRunJavaDemo}
        isRunningDemo={isRunningDemo}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full space-y-6 flex-1">
        {/* Metric Cards Row */}
        <MetricCards
          streakDays={18}
          activeAutomations={automations.filter((a) => a.enabled).length}
          totalPRs={executions.filter((e) => e.status === 'SUCCESS').length + 42}
          securityRate={100}
        />

        {/* Dashboard Tabs */}
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

        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Left Column: Configured Habits & Recent Runs */}
            <div className="lg:col-span-5 space-y-4">
              <div className="mono-panel p-4 rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-300 font-semibold">Active Habit Rules</h3>
                  <span className="text-[10px] font-mono text-zinc-500">CELERY SYNC</span>
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
                            <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded border ${
                              auto.enabled ? 'border-zinc-700 bg-zinc-900 text-zinc-200' : 'border-zinc-800 bg-black text-zinc-600'
                            }`}>
                              {auto.enabled ? 'ACTIVE' : 'PAUSED'}
                            </span>
                          </div>
                          <p className="text-[11px] text-zinc-400 mt-1 line-clamp-1">{auto.instructions}</p>
                          <div className="flex items-center gap-2 mt-2 text-[10px] text-zinc-500 font-mono">
                            <Clock className="w-3 h-3 text-zinc-400" />
                            <span>{auto.cron_expression} ({auto.timezone})</span>
                            <span>•</span>
                            <span className="text-zinc-300">{auto.repository_details?.full_name}</span>
                          </div>
                        </div>

                        <button
                          onClick={() => handleToggleAutomation(auto.id)}
                          className="p-1 rounded bg-black text-zinc-400 hover:text-white border border-zinc-800 transition-colors"
                          title={auto.enabled ? 'Pause automation' : 'Resume automation'}
                        >
                          {auto.enabled ? <Pause className="w-3.5 h-3.5" /> : <PlayCircle className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Execution History Snippet */}
              <div className="mono-panel p-4 rounded-lg">
                <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-300 font-semibold mb-3">Recent Pipeline Runs</h3>
                <div className="space-y-2">
                  {executions.map((exec) => {
                    const isSelected = selectedExecution?.id === exec.id;
                    return (
                      <div
                        key={exec.id}
                        onClick={() => setSelectedExecution(exec)}
                        className={`p-2.5 rounded border cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-zinc-900 border-zinc-500'
                            : 'bg-zinc-950 border-zinc-850 hover:border-zinc-700'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-white" />
                            <span className="text-xs font-medium text-white">{exec.automation_title}</span>
                          </div>
                          <span className="text-[10px] text-zinc-500 font-mono">
                            {new Date(exec.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        <p className="text-[11px] text-zinc-400 mt-1 font-mono truncate">
                          {exec.scheduled_slot}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Right Column: Code Diff & Safety Inspector */}
            <div className="lg:col-span-7">
              <DiffViewer execution={selectedExecution} />
            </div>
          </div>
        )}

        {activeTab === 'automations' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {automations.map((auto) => (
              <div key={auto.id} className="mono-panel p-5 rounded-lg">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-mono uppercase tracking-wider font-bold text-white">{auto.title}</h4>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                    auto.enabled ? 'border-zinc-700 bg-zinc-900 text-zinc-200' : 'border-zinc-800 bg-black text-zinc-600'
                  }`}>
                    {auto.enabled ? 'ACTIVE' : 'PAUSED'}
                  </span>
                </div>
                <p className="text-xs text-zinc-300 mt-2">{auto.instructions}</p>
                <div className="mt-4 pt-3 border-t border-zinc-800 grid grid-cols-2 gap-2 text-xs font-mono">
                  <div>
                    <span className="text-zinc-500 block text-[10px]">REPO</span>
                    <span className="text-white text-[11px]">{auto.repository_details?.full_name}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block text-[10px]">CRON</span>
                    <span className="text-white text-[11px]">{auto.cron_expression}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

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
                        <span>{exec.published_change?.commit_sha.slice(0, 7) || 'N/A'}</span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-sans">
                      <button
                        onClick={() => {
                          setSelectedExecution(exec);
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
          </div>
        )}
      </main>

      {/* Modals */}
      <AutomationModal
        isOpen={isAutomationModalOpen}
        onClose={() => setIsAutomationModalOpen(false)}
        onSave={handleAddAutomation}
      />
      <AISettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
      />
    </div>
  );
}
