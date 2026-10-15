import React, { useState } from 'react';
import { Sparkles, MessageSquare, Send, CheckCircle2, AlertTriangle, HelpCircle, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AgentBriefing, GroundedAnswer } from '../types';
import { askQuestion } from '../services/api';

interface GroqExplanationDrawerProps {
  briefing: AgentBriefing | null;
  useLlm: boolean;
}

export const GroqExplanationDrawer: React.FC<GroqExplanationDrawerProps> = ({
  briefing,
  useLlm,
}) => {
  const [questionText, setQuestionText] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [currentAnswer, setCurrentAnswer] = useState<GroundedAnswer | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!briefing) {
    return <div className="text-slate-500 text-sm py-8 text-center">No active incident investigation.</div>;
  }

  const presetQuestions = [
    'Why is this recovery plan ranked first?',
    `What could be affected if ${briefing.source_node_id} fails?`,
    'Which critical services have no viable alternate supply?',
    'What previous incidents involved this component?',
    'Which risks remain after the proposed intervention?',
    'What information is missing before we can recommend an action confidently?',
  ];

  const handleAsk = async (q: string) => {
    if (!q.trim()) return;
    setIsAsking(true);
    setErrorMsg(null);
    try {
      const res = await askQuestion(briefing.source_node_id, q, useLlm);
      setCurrentAnswer(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to evaluate question.');
    } finally {
      setIsAsking(false);
    }
  };

  const status = briefing.llm_explanation_status;
  const isSuccess = status === 'SUCCESS';
  const isFallback = status === 'FALLBACK_DETERMINISTIC';

  return (
    <div className="space-y-6">
      {/* Executive Narrative Section */}
      <div className="bg-surface rounded-xl border border-border p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-primary-light text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="h-4 w-4" />
            <span>Executive Narrative Synthesis</span>
          </div>

          <span
            className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border ${
              isSuccess
                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                : isFallback
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                : 'bg-slate-700 text-slate-300 border-slate-600'
            }`}
          >
            {isSuccess ? 'Live Groq (openai/gpt-oss-120b)' : isFallback ? 'Deterministic Fallback' : 'Deterministic Engine'}
          </span>
        </div>

        {briefing.llm_narrative ? (
          <div className="p-4 rounded-xl bg-surface-elevated/70 border border-primary/20 text-slate-200 text-sm leading-relaxed font-sans overflow-x-auto">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h2: ({ ...props }) => <h2 className="text-base font-bold text-white mt-3 mb-1.5" {...props} />,
                h3: ({ ...props }) => <h3 className="text-sm font-bold text-cyan-300 mt-3 mb-1" {...props} />,
                h4: ({ ...props }) => <h4 className="text-xs font-semibold text-slate-200 mt-2 mb-1" {...props} />,
                p: ({ ...props }) => <p className="mb-2 text-slate-300 text-xs sm:text-sm leading-relaxed" {...props} />,
                ul: ({ ...props }) => <ul className="list-disc pl-5 mb-2 space-y-1 text-xs text-slate-300" {...props} />,
                ol: ({ ...props }) => <ol className="list-decimal pl-5 mb-2 space-y-1 text-xs text-slate-300" {...props} />,
                li: ({ ...props }) => <li className="text-xs text-slate-300" {...props} />,
                strong: ({ ...props }) => <strong className="font-semibold text-white" {...props} />,
                em: ({ ...props }) => <em className="text-cyan-200 not-italic font-medium" {...props} />,
                table: ({ ...props }) => (
                  <div className="overflow-x-auto my-3 border border-border rounded-lg shadow-sm">
                    <table className="w-full text-xs text-left" {...props} />
                  </div>
                ),
                thead: ({ ...props }) => (
                  <thead className="bg-surface-elevated text-slate-300 uppercase tracking-wider text-[11px] font-semibold border-b border-border" {...props} />
                ),
                tbody: ({ ...props }) => <tbody className="divide-y divide-border/60" {...props} />,
                th: ({ ...props }) => <th className="px-3 py-2 font-medium" {...props} />,
                td: ({ ...props }) => <td className="px-3 py-2 text-slate-300 font-mono text-[11px]" {...props} />,
                hr: ({ ...props }) => <hr className="my-3 border-border/80" {...props} />,
              }}
            >
              {briefing.llm_narrative}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-surface-elevated text-slate-400 text-xs">
            {isFallback
              ? 'Groq LLM explanation temporarily unavailable (rate limit, model verification, or timeout). Reverted strictly to deterministic graph findings without errors.'
              : 'AI narrative synthesis is disabled or no GROQ_API_KEY configured. Running in 100% deterministic graph mode.'}
          </div>
        )}
      </div>

      {/* Grounded Inquiry & Q&A Panel */}
      <div className="bg-surface rounded-xl border border-border p-5 space-y-4">
        <div>
          <div className="flex items-center gap-2 text-primary-light text-xs font-semibold uppercase tracking-wider">
            <MessageSquare className="h-4 w-4" />
            <span>Evidence-Grounded Question Investigation</span>
          </div>
          <h3 className="text-base font-bold text-white mt-1">
            Ask Grounded Infrastructure Questions
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Answers are calculated directly from property graph evidence paths, with optional Groq executive framing.
          </p>
        </div>

        {/* Preset quick buttons */}
        <div className="space-y-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Suggested Inquiries:
          </span>
          <div className="flex flex-wrap gap-2">
            {presetQuestions.map((q) => (
              <button
                key={q}
                onClick={() => {
                  setQuestionText(q);
                  handleAsk(q);
                }}
                disabled={isAsking}
                className="px-3 py-1.5 rounded-lg bg-surface-elevated hover:bg-slate-700 active:bg-slate-600 border border-border text-xs text-slate-300 transition-colors text-left"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Custom Input */}
        <div className="flex items-center gap-2 pt-2">
          <input
            type="text"
            value={questionText}
            onChange={(e) => setQuestionText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk(questionText)}
            placeholder="Type a custom inquiry (e.g. Which critical services have no alternate supply?)..."
            disabled={isAsking}
            className="flex-1 bg-surface-elevated border border-border rounded-lg px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-primary font-sans"
          />
          <button
            onClick={() => handleAsk(questionText)}
            disabled={isAsking || !questionText.trim()}
            className="px-4 py-2 rounded-lg bg-primary hover:bg-primary-hover text-background font-semibold text-xs transition-colors flex items-center gap-1.5 disabled:opacity-50"
          >
            {isAsking ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
            <span>Ask</span>
          </button>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            {errorMsg}
          </div>
        )}

        {/* Answer Display */}
        {currentAnswer && (
          <div className="p-4 rounded-xl bg-surface-elevated border-l-4 border-primary text-xs space-y-3">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Question:</span>
              <div className="text-sm font-bold text-white mt-0.5">{currentAnswer.question}</div>
            </div>

            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Grounded Graph Fact:
              </span>
              <div className="text-slate-200 mt-1 leading-relaxed whitespace-pre-line text-sm">
                {currentAnswer.answer}
              </div>
            </div>

            {currentAnswer.llm_explanation && (
              <div className="p-3 rounded-lg bg-surface border border-primary/30 text-slate-300 text-xs space-y-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-primary-light">
                  Groq Natural-Language Synthesis:
                </span>
                <div className="leading-relaxed mt-0.5">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ ...props }) => <p className="mb-1 text-xs text-slate-300 leading-relaxed" {...props} />,
                      strong: ({ ...props }) => <strong className="font-semibold text-white" {...props} />,
                      ul: ({ ...props }) => <ul className="list-disc pl-4 space-y-0.5 text-xs text-slate-300" {...props} />,
                      li: ({ ...props }) => <li className="text-xs text-slate-300" {...props} />,
                    }}
                  >
                    {currentAnswer.llm_explanation}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            <div className="pt-2 border-t border-border/80 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
              <div>
                Supporting Assets:{' '}
                <strong className="text-cyan-300 font-mono">
                  {currentAnswer.supporting_asset_ids?.join(', ') || 'General topology'}
                </strong>
              </div>
              <div>
                Evidence Sufficient:{' '}
                <strong className={currentAnswer.evidence_sufficient ? 'text-emerald-400' : 'text-amber-400'}>
                  {currentAnswer.evidence_sufficient ? 'Yes' : 'No'}
                </strong>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
