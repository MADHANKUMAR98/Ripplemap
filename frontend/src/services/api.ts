/**
 * API service for fetching data from the RippleMap FastAPI backend.
 */

import { AgentBriefing, GroundedAnswer, HealthResponse, SourceNode } from '../types';

const API_BASE = '/api';

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchSelectableSources(): Promise<SourceNode[]> {
  const res = await fetch(`${API_BASE}/sources`);
  if (!res.ok) {
    throw new Error(`Failed to fetch sources: ${res.statusText}`);
  }
  const data = await res.json();
  return data.sources || [];
}

export async function runInvestigation(
  sourceId: string,
  useLlm: boolean = true,
  question?: string
): Promise<AgentBriefing> {
  const res = await fetch(`${API_BASE}/investigate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      source_id: sourceId,
      use_llm: useLlm,
      question: question || null,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Investigation execution failed');
  }

  return res.json();
}

export async function askQuestion(
  sourceId: string,
  question: string,
  useLlm: boolean = true
): Promise<GroundedAnswer> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      source_id: sourceId,
      question: question,
      use_llm: useLlm,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Question evaluation failed');
  }

  return res.json();
}
