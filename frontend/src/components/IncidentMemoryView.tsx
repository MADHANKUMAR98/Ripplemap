import React from 'react';
import { History, ShieldAlert, CheckCircle, AlertTriangle, FileText, Bookmark } from 'lucide-react';
import { HistoricalIncidentMatch } from '../types';

interface IncidentMemoryViewProps {
  incidents: HistoricalIncidentMatch[];
}

export const IncidentMemoryView: React.FC<IncidentMemoryViewProps> = ({ incidents }) => {
  if (!incidents || incidents.length === 0) {
    return (
      <div className="bg-surface rounded-xl border border-border p-8 text-center text-slate-500 text-sm">
        No prior incident memory records associated with this infrastructure component.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-surface rounded-xl border border-border p-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-primary-light text-xs font-semibold uppercase tracking-wider">
            <History className="h-4 w-4" />
            <span>FalkorDB Property Graph Incident Memory</span>
          </div>
          <h2 className="text-base font-bold text-white mt-0.5">
            Historical Incident Provenance &amp; Recorded Actions ({incidents.length} Records)
          </h2>
        </div>
        <div className="text-xs text-slate-400">
          Prior interventions retrieved from <code className="text-primary font-mono">:Incident</code> nodes.
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {incidents.map((inc) => {
          const isSimulated = inc.simulated;

          return (
            <div
              key={inc.incident_id}
              className="bg-surface rounded-xl border border-border p-4 flex flex-col justify-between space-y-3 hover:border-slate-600 transition-colors"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-cyan-300">{inc.incident_id}</span>
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                      isSimulated
                        ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                        : 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                    }`}
                  >
                    {isSimulated ? 'Simulated Incident' : 'Historical Event'}
                  </span>
                </div>
                <h3 className="text-sm font-bold text-white mt-1.5">{inc.title}</h3>
                <div className="text-xs text-slate-400 mt-0.5">
                  Timestamp: <span className="font-mono text-slate-300">{inc.timestamp}</span> &bull; Severity:{' '}
                  <strong className="text-rose-400">{inc.severity}</strong>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-surface-elevated border border-border text-xs space-y-2.5">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                    Graph Relevance Rationale:
                  </span>
                  <div className="space-y-1.5">
                    {inc.relevance_reason
                      ? inc.relevance_reason
                          .split(';')
                          .map((r) => r.trim())
                          .filter(Boolean)
                          .map((reason, rIdx) => {
                            let badgeColor = 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30';
                            let prefix = 'Context';
                            let text = reason;

                            if (reason.toLowerCase().includes('root cause match')) {
                              badgeColor = 'bg-rose-500/15 text-rose-300 border-rose-500/30';
                              prefix = 'Root Cause';
                            } else if (reason.toLowerCase().includes('overlapping affected service')) {
                              badgeColor = 'bg-amber-500/15 text-amber-300 border-amber-500/30';
                              prefix = 'Shared Asset';
                            } else if (reason.toLowerCase().includes('shared dependency path')) {
                              badgeColor = 'bg-purple-500/15 text-purple-300 border-purple-500/30';
                              prefix = 'Cascade Path';
                            }

                            return (
                              <div key={rIdx} className="flex items-start gap-2 bg-surface/60 p-2 rounded border border-border/60">
                                <span className={`text-[9px] font-mono font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border shrink-0 ${badgeColor}`}>
                                  {prefix}
                                </span>
                                <span className="text-slate-200 text-[11px] leading-snug">{text}</span>
                              </div>
                            );
                          })
                      : <span className="text-slate-400">No specific relevance match recorded.</span>}
                  </div>
                </div>

                <div className="pt-2 border-t border-border/60 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Recorded Recovery Action:</span>
                    <strong className="text-white font-medium text-right">{inc.recovery_action_name || 'No formal action recorded'}</strong>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Outcome Classification:</span>
                    <span
                      title={inc.outcome_description}
                      className={`font-mono font-semibold px-2 py-0.5 rounded border text-[11px] ${
                        inc.outcome_type === 'SIMULATED_OUTCOME'
                          ? 'text-cyan-300 bg-cyan-500/10 border-cyan-500/30'
                          : inc.outcome_type === 'CONFIRMED_SUCCESSFUL'
                          ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                          : inc.outcome_type === 'CONFIRMED_FAILED'
                          ? 'text-rose-400 bg-rose-500/10 border-rose-500/30'
                          : 'text-amber-300 bg-amber-500/10 border-amber-500/30'
                      }`}
                    >
                      {inc.outcome_type === 'SIMULATED_OUTCOME' ? 'RECORDED_SIMULATION_BENCHMARK' : inc.outcome_type}
                    </span>
                  </div>
                  {inc.outcome_description && (
                    <div className="text-[10px] text-slate-400 italic">
                      {inc.outcome_description}
                    </div>
                  )}
                </div>
              </div>

              <div className="text-[11px] text-slate-500 border-t border-border/80 pt-2 flex items-center justify-between">
                <span>Failure Source: <strong className="text-slate-400 font-mono">{inc.failure_source}</strong></span>
                <span>{inc.matching_assets?.length || 0} matching assets</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
