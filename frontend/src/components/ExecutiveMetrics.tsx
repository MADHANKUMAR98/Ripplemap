import React from 'react';
import { motion } from 'framer-motion';
import { AlertOctagon, Layers, Flame, ShieldAlert, Award, Cpu } from 'lucide-react';
import { AgentBriefing } from '../types';

interface ExecutiveMetricsProps {
  briefing: AgentBriefing | null;
  isLoading: boolean;
}

export const ExecutiveMetrics: React.FC<ExecutiveMetricsProps> = ({ briefing, isLoading }) => {
  if (isLoading || !briefing) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5 mb-6">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-28 rounded-xl bg-surface border border-border animate-pulse p-4 flex flex-col justify-between">
            <div className="h-3 w-20 bg-slate-700/60 rounded"></div>
            <div className="h-7 w-14 bg-slate-700/80 rounded"></div>
            <div className="h-3 w-24 bg-slate-700/50 rounded"></div>
          </div>
        ))}
      </div>
    );
  }

  const directCount = briefing.direct_findings.length;
  const downstreamCount = briefing.downstream_findings.length;
  const totalAffected = directCount + downstreamCount;

  const criticalServicesCount = (briefing.direct_findings.concat(briefing.downstream_findings)).filter(
    (f) => f.criticality.includes('Tier 1') || f.criticality.includes('Tier 2')
  ).length;

  const topScore = briefing.ripple_scores.length > 0 ? briefing.ripple_scores[0].total_score : 0;
  const topAssetId = briefing.ripple_scores.length > 0 ? briefing.ripple_scores[0].asset_id : 'N/A';

  const bestPlan = briefing.recommended_plan;
  const planScore = bestPlan ? `${bestPlan.composite_benefit_score.toFixed(1)} pts` : '0.0 pts';
  const planLabel = bestPlan ? bestPlan.plan_id : 'None';

  const isLlmActive = briefing.llm_explanation_status === 'SUCCESS';
  const isFallback = briefing.llm_explanation_status === 'FALLBACK_DETERMINISTIC';

  const cards = [
    {
      label: 'Incident Source',
      value: briefing.source_node_id,
      sub: `${briefing.source_entity_type} &bull; ${briefing.source_criticality.split(' - ')[0]}`,
      icon: AlertOctagon,
      valueColor: 'text-rose-400',
      borderColor: 'hover:border-rose-500/50',
    },
    {
      label: 'Total Affected Assets',
      value: totalAffected.toString(),
      sub: `${directCount} Direct &bull; ${downstreamCount} Downstream`,
      icon: Layers,
      valueColor: 'text-white',
      borderColor: 'hover:border-primary/50',
    },
    {
      label: 'Critical Services At Risk',
      value: criticalServicesCount.toString(),
      sub: 'Tier 1 &amp; Tier 2 Essential',
      icon: Flame,
      valueColor: 'text-amber-400',
      borderColor: 'hover:border-amber-500/50',
    },
    {
      label: 'Max RippleScore',
      value: topScore.toFixed(1),
      sub: `High Exposure: ${topAssetId}`,
      icon: ShieldAlert,
      valueColor: 'text-primary-light',
      borderColor: 'hover:border-cyan-500/50',
    },
    {
      label: 'Recommended Strategy',
      value: planLabel,
      sub: bestPlan ? `#1 Ranked &bull; ${planScore}` : 'None Evaluated',
      icon: Award,
      valueColor: 'text-emerald-400',
      borderColor: 'hover:border-emerald-500/50',
    },
    {
      label: 'Intelligence Mode',
      value: isLlmActive ? 'Groq AI Active' : isFallback ? 'Fallback Active' : 'Deterministic',
      sub: isLlmActive ? 'Natural Language Grounded' : 'FalkorDB Graph Truth',
      icon: Cpu,
      valueColor: isLlmActive ? 'text-emerald-400' : isFallback ? 'text-amber-400' : 'text-slate-300',
      borderColor: 'hover:border-teal/50',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5 mb-6">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        const isLongText = card.value.length > 13;
        return (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: idx * 0.04 }}
            className={`bg-surface border border-border rounded-xl p-3.5 flex flex-col justify-between transition-all duration-200 shadow-sm ${card.borderColor}`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                {card.label}
              </span>
              <Icon className="h-4 w-4 text-slate-500" />
            </div>
            <div className="my-1.5" title={card.value}>
              <div
                className={`font-bold tracking-tight font-mono ${card.valueColor} ${
                  isLongText ? 'text-sm lg:text-[15px]' : 'text-xl'
                } truncate`}
              >
                {card.value}
              </div>
            </div>
            <div
              className="text-[11px] text-slate-400 truncate"
              title={card.sub.replace(/&bull;/g, '•')}
              dangerouslySetInnerHTML={{ __html: card.sub }}
            />
          </motion.div>
        );
      })}
    </div>
  );
};
