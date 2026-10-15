import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Line,
  ComposedChart,
} from 'recharts';
import { Award, Clock, ShieldCheck, AlertTriangle, ArrowRight, CheckCircle2, XCircle, Info, FileText } from 'lucide-react';
import { RecoveryPlan } from '../types';

interface RecoveryDecisionStudioProps {
  plans: RecoveryPlan[];
  recommendedPlan: RecoveryPlan | null;
  assumptions?: string[];
  rationale?: string;
}

export const RecoveryDecisionStudio: React.FC<RecoveryDecisionStudioProps> = ({
  plans,
  recommendedPlan,
  assumptions = [],
  rationale = '',
}) => {
  const [selectedPlanId1, setSelectedPlanId1] = useState<string>(
    plans[0]?.plan_id || ''
  );
  const [selectedPlanId2, setSelectedPlanId2] = useState<string>(
    plans[1]?.plan_id || plans[0]?.plan_id || ''
  );

  if (!plans || plans.length === 0) {
    return <div className="text-slate-500 text-sm py-8 text-center">No recovery plans evaluated.</div>;
  }

  const p1 = plans.find((p) => p.plan_id === selectedPlanId1) || plans[0];
  const p2 = plans.find((p) => p.plan_id === selectedPlanId2) || plans[1] || plans[0];

  const chartData = plans.map((p, idx) => ({
    name: `#${idx + 1} ${p.plan_id}`,
    score: p.composite_benefit_score,
    hours: p.total_estimated_hours,
    criticalProtected: p.unique_critical_services_protected,
  }));

  const renderPlanCard = (plan: RecoveryPlan, isWinner: boolean) => {
    return (
      <div
        className={`bg-surface rounded-xl border p-5 flex flex-col justify-between space-y-4 ${
          isWinner ? 'border-emerald-500/60 shadow-lg shadow-emerald-500/5' : 'border-border'
        }`}
      >
        <div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              {plan.plan_id}
            </span>
            {isWinner && (
              <span 
                className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                title="Optimal candidate under stated in-memory simulation model (not an operational field dispatch order)"
              >
                <Award className="h-3 w-3" />
                Top Ranked in Simulation #1
              </span>
            )}
          </div>
          <h3 className="text-base font-bold text-white mt-1">{plan.plan_name}</h3>
          <p className="text-xs text-slate-400 mt-1">{plan.feasibility_summary}</p>
        </div>

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 rounded-lg bg-surface-elevated border border-border text-xs">
          <div>
            <div className="text-slate-400 text-[11px]">Composite Benefit</div>
            <div className="text-lg font-bold font-mono text-cyan-300">{plan.composite_benefit_score.toFixed(1)} pts</div>
          </div>
          <div>
            <div className="text-slate-400 text-[11px]">Restoration Window</div>
            <div className="text-lg font-bold font-mono text-amber-300">{plan.total_estimated_hours.toFixed(1)} hrs</div>
          </div>
          <div>
            <div className="text-slate-400 text-[11px]">Critical Services</div>
            <div className="text-lg font-bold font-mono text-emerald-400">
              {plan.unique_critical_services_protected} protected
            </div>
          </div>
          <div>
            <div className="text-slate-400 text-[11px]">Residual Affected</div>
            <div className="text-lg font-bold font-mono text-rose-400">{plan.residual_affected_count} assets</div>
          </div>
        </div>

        {/* Protection Breakdown Chips */}
        <div className="space-y-2 text-xs">
          <div>
            <span className="text-emerald-400 font-semibold flex items-center gap-1 text-[11px]">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Fully Protected ({plan.fully_protected_asset_ids.length}):
            </span>
            <div className="flex flex-wrap gap-1 mt-1">
              {plan.fully_protected_asset_ids.length > 0 ? (
                plan.fully_protected_asset_ids.map((id) => (
                  <span
                    key={id}
                    className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 text-[10px] font-mono border border-emerald-500/30"
                  >
                    {id}
                  </span>
                ))
              ) : (
                <span className="text-slate-500 text-[11px]">None</span>
              )}
            </div>
          </div>

          <div>
            <span className="text-amber-400 font-semibold flex items-center gap-1 text-[11px]">
              <AlertTriangle className="h-3.5 w-3.5" />
              Partially Mitigated ({plan.partially_mitigated_asset_ids.length}):
            </span>
            <div className="flex flex-wrap gap-1 mt-1">
              {plan.partially_mitigated_asset_ids.length > 0 ? (
                plan.partially_mitigated_asset_ids.map((id) => (
                  <span
                    key={id}
                    className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 text-[10px] font-mono border border-amber-500/30"
                  >
                    {id}
                  </span>
                ))
              ) : (
                <span className="text-slate-500 text-[11px]">None</span>
              )}
            </div>
          </div>

          <div>
            <span className="text-rose-400 font-semibold flex items-center gap-1 text-[11px]">
              <XCircle className="h-3.5 w-3.5" />
              Unresolved Residual Exposure ({plan.unresolved_asset_ids.length}):
            </span>
            <div className="flex flex-wrap gap-1 mt-1">
              {plan.unresolved_asset_ids.length > 0 ? (
                plan.unresolved_asset_ids.map((id) => (
                  <span
                    key={id}
                    className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 text-[10px] font-mono border border-rose-500/30"
                  >
                    {id}
                  </span>
                ))
              ) : (
                <span className="text-slate-500 text-[11px]">None</span>
              )}
            </div>
          </div>
        </div>

        {/* Tradeoffs and residual risks */}
        <div className="pt-3 border-t border-border/80">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
            Key Trade-offs &amp; Residual Risks:
          </div>
          <ul className="space-y-1 text-xs text-slate-300">
            {plan.tradeoffs_and_risks.map((t, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <span className="text-primary mt-1">&bull;</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Strategy comparison chart */}
      <div className="bg-surface rounded-xl border border-border p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-3 flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5 text-primary" />
          <span>Recovery Plan Evaluation &bull; Composite Benefit vs Time to Restore</span>
        </h3>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 20, right: 35, left: 25, bottom: 25 }}>
              <XAxis dataKey="name" stroke="#94A3B8" fontSize={11} fontFamily="monospace" />
              <YAxis
                yAxisId="left"
                stroke="#06B6D4"
                fontSize={11}
                tickLine={false}
                label={{
                  value: 'Composite Benefit (pts)',
                  angle: -90,
                  position: 'insideLeft',
                  offset: -12,
                  fill: '#06B6D4',
                  style: { textAnchor: 'middle', fontSize: '11px', fontWeight: 500 },
                }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                stroke="#F59E0B"
                fontSize={11}
                tickLine={false}
                label={{
                  value: 'Restoration (Hours)',
                  angle: 90,
                  position: 'insideRight',
                  offset: 12,
                  fill: '#F59E0B',
                  style: { textAnchor: 'middle', fontSize: '11px', fontWeight: 500 },
                }}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#1E293B', borderColor: '#334155', borderRadius: '8px' }}
                itemStyle={{ color: '#E2E8F0', fontSize: '12px' }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
              <Bar yAxisId="left" dataKey="score" name="Composite Benefit Score" fill="#06B6D4" radius={[4, 4, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="hours" name="Restoration Time (hrs)" stroke="#F59E0B" strokeWidth={2.5} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Side-by-Side Comparison Selectors */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-surface p-3 rounded-xl border border-border">
          <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Side-by-Side Strategy Comparison
          </div>
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <select
              value={selectedPlanId1}
              onChange={(e) => setSelectedPlanId1(e.target.value)}
              className="bg-surface-elevated border border-border rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary"
            >
              {plans.map((p, i) => (
                <option key={p.plan_id} value={p.plan_id}>
                  Primary: #{i + 1} {p.plan_id} ({p.composite_benefit_score.toFixed(1)} pts)
                </option>
              ))}
            </select>
            <span className="text-slate-500 text-xs">vs</span>
            <select
              value={selectedPlanId2}
              onChange={(e) => setSelectedPlanId2(e.target.value)}
              className="bg-surface-elevated border border-border rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-primary"
            >
              {plans.map((p, i) => (
                <option key={p.plan_id} value={p.plan_id}>
                  Comparison: #{i + 1} {p.plan_id} ({p.composite_benefit_score.toFixed(1)} pts)
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {renderPlanCard(p1, recommendedPlan ? p1.plan_id === recommendedPlan.plan_id : false)}
          {renderPlanCard(p2, recommendedPlan ? p2.plan_id === recommendedPlan.plan_id : false)}
        </div>

        {/* Simulation Scope & Mathematical Grounding Card */}
        <div className="bg-surface rounded-xl border border-border p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-primary-light text-xs font-semibold uppercase tracking-wider">
              <Info className="h-4 w-4" />
              <span>Simulation Truthfulness, Protection Assumptions &amp; Scope</span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/30 font-medium">
              In-Memory Consequence Model
            </span>
          </div>

          {rationale && (
            <div className="text-xs text-slate-300 bg-surface-elevated p-3 rounded-lg border border-border/80 leading-relaxed">
              <strong className="text-white block mb-1">Optimizer Recommendation Rationale:</strong>
              {rationale}
            </div>
          )}

          {assumptions && assumptions.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Grounded Graph Assumptions ({assumptions.length}):
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                {assumptions.map((a, i) => (
                  <div key={i} className="p-2.5 rounded-lg bg-surface-elevated/70 border border-border/70 text-slate-300 flex items-start gap-2">
                    <span className="text-primary mt-0.5 font-bold">&bull;</span>
                    <span className="leading-snug">{a}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="pt-2 border-t border-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[11px] text-slate-500">
            <span className="font-mono">
              Formula: 30 &times; (Crit Bonus) + 10 &times; (Total Protected) &minus; 3 &times; (Hours) &minus; Penalties &nbsp;
              <span className="text-slate-400 font-sans">[Equiv: 40 &times; Crit + 10 &times; Standard &minus; 3 &times; Hours &minus; Penalties]</span>
            </span>
            <span className="text-amber-400/90 font-medium">
              Simulation benchmark ranking &bull; Requires physical field crew &amp; switchgear verification.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
