import React from 'react';
import { Activity, AlertTriangle, ShieldCheck, Zap, Sparkles, RefreshCw } from 'lucide-react';
import { HealthResponse, SourceNode } from '../types';

interface HeaderProps {
  health: HealthResponse | null;
  sources: SourceNode[];
  selectedSourceId: string;
  onSelectSource: (id: string) => void;
  onInvestigate: () => void;
  isLoading: boolean;
  useLlm: boolean;
  onToggleLlm: (val: boolean) => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  sources,
  selectedSourceId,
  onSelectSource,
  onInvestigate,
  isLoading,
  useLlm,
  onToggleLlm,
}) => {
  const selectedSource = sources.find((s) => s.id === selectedSourceId);

  return (
    <header className="border-b border-border bg-surface/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5">
        {/* Top bar: Branding & Status */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary to-teal flex items-center justify-center shadow-glow">
              <Activity className="h-6 w-6 text-background stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                  RippleMap
                  <span className="text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-primary/15 text-primary-light border border-primary/30">
                    Infrastructure Intelligence
                  </span>
                </h1>
              </div>
              <p className="text-xs text-slate-400">
                Deterministic Cascading Dependency Analysis &bull; RippleScore Risk Ranking &bull; Grounded Recovery Optimizer
              </p>
            </div>
          </div>

          {/* Right badges: Health & Simulation context */}
          <div className="flex items-center gap-2.5">
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-surface-elevated border border-border text-xs">
              <span className="relative flex h-2 w-2">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${health?.database_connected ? 'bg-emerald-400' : 'bg-red-400'} opacity-75`}></span>
                <span className={`relative inline-flex rounded-full h-2 w-2 ${health?.database_connected ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
              </span>
              <span className="text-slate-300 font-medium">
                {health?.database_connected ? `FalkorDB Graph Live (${health.node_count} nodes, ${health.relationship_count} edges)` : 'Database Offline'}
              </span>
            </div>

            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium">
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>Simulated Consequence Model</span>
            </div>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="mt-3.5 pt-3 border-t border-border/60 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Root Failure Source:
            </label>
            <div className="relative min-w-[280px]">
              <select
                value={selectedSourceId}
                onChange={(e) => onSelectSource(e.target.value)}
                disabled={isLoading}
                className="w-full bg-surface-elevated border border-border rounded-lg px-3 py-1.5 text-sm font-mono text-white focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50"
              >
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.id} — {s.name} ({s.criticality.split(' - ')[0]})
                  </option>
                ))}
              </select>
            </div>

            {selectedSource && (
              <div className="hidden lg:flex items-center gap-2 text-xs text-slate-400 bg-surface-elevated px-2.5 py-1.5 rounded-lg border border-border">
                <span>Type: <strong className="text-slate-200">{selectedSource.entity_type}</strong></span>
                <span>&bull;</span>
                <span>Zone: <strong className="text-slate-200">{selectedSource.zone}</strong></span>
                <span>&bull;</span>
                <span>Status: <strong className="text-emerald-400">{selectedSource.status}</strong></span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* LLM Toggle */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-elevated border border-border">
              <Sparkles className={`h-4 w-4 ${useLlm ? 'text-primary-light' : 'text-slate-500'}`} />
              <span className="text-xs font-medium text-slate-300">Groq AI Narrative</span>
              <button
                type="button"
                onClick={() => onToggleLlm(!useLlm)}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                  useLlm ? 'bg-primary' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                    useLlm ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* Investigate Action Button */}
            <button
              onClick={onInvestigate}
              disabled={isLoading}
              className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-primary hover:bg-primary-hover active:bg-primary-dark text-background font-semibold text-sm transition-all shadow-glow hover:shadow-cyan-500/40 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin text-background" />
                  <span>Evaluating Graph...</span>
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4 fill-current text-background" />
                  <span>Investigate Incident</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
