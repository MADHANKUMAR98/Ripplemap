import React, { useEffect, useState } from 'react';
import {
  Activity,
  Layers,
  ShieldAlert,
  Award,
  History,
  Sparkles,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import { Header } from './components/Header';
import { ExecutiveMetrics } from './components/ExecutiveMetrics';
import { DependencyGraph } from './components/DependencyGraph';
import { EvidenceExplorer } from './components/EvidenceExplorer';
import { RiskIntelligence } from './components/RiskIntelligence';
import { RecoveryDecisionStudio } from './components/RecoveryDecisionStudio';
import { IncidentMemoryView } from './components/IncidentMemoryView';
import { GroqExplanationDrawer } from './components/GroqExplanationDrawer';
import { fetchHealth, fetchSelectableSources, runInvestigation } from './services/api';
import { AgentBriefing, HealthResponse, SourceNode } from './types';

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [sources, setSources] = useState<SourceNode[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string>('SUB-001');
  const [useLlm, setUseLlm] = useState<boolean>(true);
  const [briefing, setBriefing] = useState<AgentBriefing | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | undefined>(undefined);

  type TabType = 'graph' | 'evidence' | 'scores' | 'recovery' | 'memory' | 'groq';
  const [activeTab, setActiveTab] = useState<TabType>('graph');

  // Initial load: Health and Sources
  useEffect(() => {
    async function init() {
      try {
        const [hData, sData] = await Promise.all([fetchHealth(), fetchSelectableSources()]);
        setHealth(hData);
        setSources(sData);
        setUseLlm(hData.groq_configured);

        // Run default investigation on SUB-001
        executeInvestigation('SUB-001', hData.groq_configured);
      } catch (err: any) {
        console.error('Initialization error:', err);
        setError('Failed to connect to RippleMap backend service. Ensure the FastAPI server is running.');
      }
    }
    init();
  }, []);

  const executeInvestigation = async (sourceId: string, withLlm: boolean) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await runInvestigation(sourceId, withLlm);
      setBriefing(data);
      if (data.direct_findings.length > 0) {
        setSelectedAssetId(data.direct_findings[0].asset_id);
      }
    } catch (err: any) {
      console.error('Investigation error:', err);
      setError(err.message || `Investigation failed for ${sourceId}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleInvestigateClick = () => {
    executeInvestigation(selectedSourceId, useLlm);
  };

  const tabs = [
    { id: 'graph' as TabType, label: 'Dependency Graph', icon: Activity, count: null },
    {
      id: 'evidence' as TabType,
      label: 'Evidence Explorer',
      icon: Layers,
      count: briefing ? briefing.direct_findings.length + briefing.downstream_findings.length : null,
    },
    { id: 'scores' as TabType, label: 'Risk Intelligence', icon: ShieldAlert, count: briefing?.ripple_scores?.length },
    {
      id: 'recovery' as TabType,
      label: 'Recovery Decision Studio',
      icon: Award,
      count: briefing?.evaluated_plans?.length,
    },
    { id: 'memory' as TabType, label: 'Incident Memory', icon: History, count: briefing?.historical_incidents?.length },
    {
      id: 'groq' as TabType,
      label: 'AI Explanation & Q&A',
      icon: Sparkles,
      count: briefing?.llm_narrative ? '✓' : null,
    },
  ];

  return (
    <div className="min-h-screen bg-background text-slate-100 flex flex-col font-sans">
      <Header
        health={health}
        sources={sources}
        selectedSourceId={selectedSourceId}
        onSelectSource={(id) => {
          setSelectedSourceId(id);
          executeInvestigation(id, useLlm);
        }}
        onInvestigate={handleInvestigateClick}
        isLoading={isLoading}
        useLlm={useLlm}
        onToggleLlm={(val) => {
          setUseLlm(val);
          executeInvestigation(selectedSourceId, val);
        }}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-5">
        {error && (
          <div className="mb-4 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              onClick={handleInvestigateClick}
              className="px-2.5 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-white font-medium text-xs transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Executive Metrics Overview */}
        <ExecutiveMetrics briefing={briefing} isLoading={isLoading} />

        {/* Navigation Tabs Bar */}
        <div className="border-b border-border/80 mb-5 flex items-center gap-1 overflow-x-auto no-scrollbar">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
                  isActive
                    ? 'border-primary text-primary-light bg-primary/5'
                    : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-primary' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
                {tab.count !== null && (
                  <span
                    className={`ml-1 text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                      isActive ? 'bg-primary/20 text-primary-light font-bold' : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Active Tab Content */}
        <div>
          {activeTab === 'graph' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-white">Signature Dependency Topology</h2>
                  <p className="text-xs text-slate-400">
                    Interactive multi-hop cascade graph with real-time flow paths, alternate routes, and backup generators.
                  </p>
                </div>
                <div className="text-xs text-slate-500 font-mono hidden sm:block">
                  Click node to inspect verifiable paths
                </div>
              </div>
              <DependencyGraph briefing={briefing} onSelectAsset={(id) => setSelectedAssetId(id)} />
            </div>
          )}

          {activeTab === 'evidence' && (
            <EvidenceExplorer
              briefing={briefing}
              selectedAssetId={selectedAssetId}
              onSelectAsset={(id) => setSelectedAssetId(id)}
            />
          )}

          {activeTab === 'scores' && <RiskIntelligence scores={briefing?.ripple_scores || []} />}

          {activeTab === 'recovery' && (
            <RecoveryDecisionStudio
              plans={briefing?.evaluated_plans || []}
              recommendedPlan={briefing?.recommended_plan || null}
              assumptions={briefing?.missing_data_and_assumptions || []}
              rationale={briefing?.recommendation_rationale || ''}
            />
          )}

          {activeTab === 'memory' && (
            <IncidentMemoryView incidents={briefing?.historical_incidents || []} />
          )}

          {activeTab === 'groq' && <GroqExplanationDrawer briefing={briefing} useLlm={useLlm} />}
        </div>
      </main>

      <footer className="border-t border-border/60 bg-surface/40 py-3 text-center text-xs text-slate-500">
        RippleMap Municipal Infrastructure Intelligence &bull; Powered by FalkorDB Graph &bull; Zero Real-World Mutation Mode
      </footer>
    </div>
  );
};

export default App;
