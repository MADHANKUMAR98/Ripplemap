import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from 'recharts';
import { ShieldAlert, Info, TrendingUp } from 'lucide-react';
import { ScoreBreakdown } from '../types';

interface RiskIntelligenceProps {
  scores: ScoreBreakdown[];
}

export const RiskIntelligence: React.FC<RiskIntelligenceProps> = ({ scores }) => {
  if (!scores || scores.length === 0) {
    return <div className="text-slate-500 text-sm py-8 text-center">No RippleScore data calculated.</div>;
  }

  // Prepare chart data (top 8 assets)
  const chartData = scores.slice(0, 8).map((s) => ({
    name: s.asset_id,
    fullName: s.asset_name,
    total: s.total_score,
    inherent: s.inherent_score,
    downstream: s.downstream_impact_score,
    multipath: s.multipath_vulnerability_score,
    spof: s.spof_penalty,
    penalties: s.capacity_penalty + s.failed_contingency_penalty,
    mitigation: -s.mitigation_credit,
    backup: -s.backup_credit,
  }));

  const topScore = scores[0];

  return (
    <div className="space-y-6">
      {/* Overview header */}
      <div className="bg-surface rounded-xl border border-border p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-primary-light text-xs font-semibold uppercase tracking-wider">
            <ShieldAlert className="h-4 w-4" />
            <span>Canonical Risk Intelligence &bull; Formula Grounding</span>
          </div>
          <h2 className="text-lg font-bold text-white mt-1">
            Explainable RippleScore Decomposition
          </h2>
          <p className="text-xs text-slate-400 max-w-2xl mt-0.5">
            The RippleScore [0, 100] is calculated using strictly transparent physical dependency factors:
            inherent asset criticality, reachable downstream critical services, multi-path exposure, and SPOF penalties,
            offset by verified alternate feeds and operational standby generators.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0 bg-surface-elevated px-4 py-2 rounded-xl border border-border">
          <div className="text-right">
            <div className="text-[10px] uppercase font-bold text-slate-400">Highest Exposure</div>
            <div className="text-xs font-bold text-white font-mono">{topScore.asset_id}</div>
          </div>
          <div className="text-2xl font-bold font-mono text-rose-400">
            {topScore.total_score.toFixed(1)}
          </div>
        </div>
      </div>

      {/* Recharts Component Breakdown */}
      <div className="bg-surface rounded-xl border border-border p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-3 flex items-center gap-1.5">
          <TrendingUp className="h-3.5 w-3.5 text-primary" />
          <span>Top Exposed Assets &bull; Score Contributions &amp; Deductions</span>
        </h3>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              stackOffset="sign"
              margin={{ top: 20, right: 30, left: 10, bottom: 20 }}
            >
              <XAxis dataKey="name" stroke="#94A3B8" fontSize={11} fontFamily="monospace" />
              <YAxis stroke="#94A3B8" fontSize={11} domain={[-20, 100]} />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    const item = chartData.find((d) => d.name === label);
                    return (
                      <div className="bg-surface-elevated/95 backdrop-blur-md border border-border p-3 rounded-lg text-xs shadow-xl space-y-1">
                        <div className="font-bold text-white font-mono">
                          {label} — {item?.fullName}
                        </div>
                        <div className="text-rose-400 font-bold font-mono">
                          Final RippleScore: {item?.total.toFixed(1)} / 100
                        </div>
                        <div className="pt-1.5 border-t border-border/80 space-y-0.5 text-[11px] text-slate-300">
                          <div>Base Criticality: +{item?.inherent.toFixed(1)}</div>
                          <div>Downstream Cascades: +{item?.downstream.toFixed(1)}</div>
                          <div>Multipath Penalty: +{item?.multipath.toFixed(1)}</div>
                          <div>SPOF Penalty: +{item?.spof.toFixed(1)}</div>
                          {item && item.penalties > 0 && (
                            <div className="text-red-400">Contingency Penalties: +{item.penalties.toFixed(1)}</div>
                          )}
                          <div className="text-emerald-400">Alt Route Credit: {item?.mitigation.toFixed(1)}</div>
                          <div className="text-purple-400">Backup Gen Credit: {item?.backup.toFixed(1)}</div>
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
                iconType="circle"
              />
              <ReferenceLine y={0} stroke="#475569" strokeWidth={1.5} />
              <Bar dataKey="inherent" name="Base Criticality" fill="#38BDF8" stackId="stack" />
              <Bar dataKey="downstream" name="Downstream Cascades" fill="#0284C7" stackId="stack" />
              <Bar dataKey="multipath" name="Multipath Exposure" fill="#F59E0B" stackId="stack" />
              <Bar dataKey="spof" name="SPOF Penalty" fill="#EF4444" stackId="stack" />
              <Bar dataKey="penalties" name="Capacity/Backup Penalty" fill="#DC2626" stackId="stack" />
              <Bar dataKey="mitigation" name="Alt Route Credit (-)" fill="#10B981" stackId="stack" />
              <Bar dataKey="backup" name="Backup Credit (-)" fill="#8B5CF6" stackId="stack" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top 3 Breakdown Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {scores.slice(0, 3).map((s, idx) => (
          <div key={s.asset_id} className="bg-surface rounded-xl border border-border p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span>Rank #{idx + 1}</span>
                <span className="font-mono text-[11px] text-cyan-300">{(s.confidence * 100).toFixed(0)}% Confidence</span>
              </div>
              <h4 className="text-sm font-bold font-mono text-white">{s.asset_id}</h4>
              <p className="text-xs text-slate-300 mt-0.5 truncate">{s.asset_name}</p>
              <div className="text-2xl font-bold font-mono text-rose-400 my-2">
                {s.total_score.toFixed(1)} <span className="text-xs text-slate-500 font-sans">/ 100</span>
              </div>
            </div>

            <div className="space-y-1 text-xs text-slate-300 pt-3 border-t border-border/80">
              <div className="flex justify-between">
                <span className="text-slate-400">Criticality:</span>
                <span className="text-white font-medium">{s.criticality.split(' - ')[0]}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Downstream Impact:</span>
                <span className="text-cyan-300 font-mono">+{s.downstream_impact_score.toFixed(1)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Mitigation Credit:</span>
                <span className="text-emerald-400 font-mono">-{s.mitigation_credit.toFixed(1)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Backup Credit:</span>
                <span className="text-purple-400 font-mono">-{s.backup_credit.toFixed(1)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
