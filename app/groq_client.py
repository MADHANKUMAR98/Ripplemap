"""Optional Groq LLM integration layer for RippleMap.

Provides natural-language explanation and narrative synthesis grounded strictly in
deterministic graph evidence, RippleScores, recovery plans, and incident memory.
Zero arbitrary Cypher execution, zero database mutation, and graceful fallback to
deterministic responses if unconfigured, rate-limited, or unavailable.
"""

import json
import logging
from typing import Any, Optional
from groq import Groq
from app.config import config
from app.schema import AgentBriefing, GroundedAnswer

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_BRIEFING = """You are the RippleMap Infrastructure AI Narrator. Your role is to explain complex interconnected graph cascade findings, transparent risk rankings (RippleScores), and recovery optimizer decisions in clear, executive-grade language for municipal and utility emergency coordinators.

CRITICAL GROUNDING CONSTRAINTS:
1. Ground Truth Only: You must ONLY use the provided deterministic facts, evidence paths, RippleScores, and recovery plans.
2. Zero Fabrication: DO NOT invent, hallucinate, or extrapolate any unstated graph connections, failure cascades, operational outages, or repair durations.
3. Strict Outcome Rigor: DO NOT claim that proposed or simulated recovery actions are completed or confirmed in the real world. Distinguish confirmed historical outcomes from in-memory simulated plans.
4. Deterministic Scores: DO NOT alter, recalculate, or approximate any scores or rankings.
5. Executive Clarity: Structure your explanation into clear sections:
   - Executive Incident Summary
   - Cascading Exposures & Critical Service Vulnerabilities
   - Historical Memory & Precedent
   - Recommended Recovery Action & Key Trade-offs
"""

SYSTEM_PROMPT_QUESTION = """You are the RippleMap Infrastructure AI Narrator. Your role is to provide a concise, factual, and well-structured natural language answer to an inquiry about an infrastructure incident.

CRITICAL GROUNDING CONSTRAINTS:
1. Strict Factual Grounding: Base your answer EXCLUSIVELY on the provided deterministic answer, supporting assets, and graph evidence paths.
2. Zero Fabrication: Never invent unmentioned components, routes, or failure mechanisms.
3. Insufficient Evidence: If the graph evidence is flagged as insufficient, clearly state that the query cannot be answered from property graph data and list the supported question types.
"""


def get_groq_client(api_key: Optional[str] = None) -> Optional[Groq]:
    """Initializes and returns a Groq SDK client if an API key is available.
    Never prints, logs, or exposes the API key.
    """
    key = api_key or config.groq_api_key
    if not key:
        return None
    try:
        return Groq(api_key=key)
    except Exception as e:
        logger.warning(f"Failed to initialize Groq client: {e}")
        return None


_verified_models_cache: set[str] = set()


def verify_model_availability(
    model_name: str,
    client: Optional[Groq] = None,
    use_cache: bool = True,
) -> bool:
    """Verifies whether the configured model is supported in Groq's model catalog.
    Never logs or exposes the API key.
    """
    if use_cache and model_name in _verified_models_cache:
        return True

    groq_cli = client or get_groq_client()
    if not groq_cli:
        return False

    try:
        models_resp = groq_cli.models.list()
        items = getattr(models_resp, "data", models_resp)
        available_ids = {getattr(m, "id", str(m)) for m in items}
        if model_name in available_ids:
            if use_cache:
                _verified_models_cache.add(model_name)
            return True
        logger.warning(f"Configured model '{model_name}' is not supported in Groq's active model catalog.")
        return False
    except Exception as e:
        logger.warning(f"Groq model availability check failed for '{model_name}': {e}")
        return False


def generate_briefing_narrative(
    briefing: AgentBriefing,
    client: Optional[Groq] = None,
    model: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """Generates an executive natural-language briefing from structured agent findings.
    
    Returns:
        tuple[Optional[str], str]: (narrative_text, status)
        where status is one of: 'SUCCESS', 'DETERMINISTIC_ONLY', 'FALLBACK_DETERMINISTIC'.
    """
    groq_cli = client or get_groq_client()
    if not groq_cli:
        return None, "DETERMINISTIC_ONLY"

    target_model = model or config.groq_model

    # Verify model availability against Groq model catalog
    if not verify_model_availability(target_model, client=groq_cli):
        return None, "FALLBACK_DETERMINISTIC"

    # Compile strictly bounded, structured facts from deterministic briefing
    structured_payload = {
        "source": {
            "id": briefing.source_node_id,
            "name": briefing.source_node_name,
            "type": briefing.source_entity_type,
            "criticality": briefing.source_criticality,
            "status": briefing.source_status,
        },
        "cascade_scope": {
            "total_affected": len(briefing.direct_findings) + len(briefing.downstream_findings),
            "direct_dependencies": [
                {"id": f.asset_id, "name": f.asset_name, "criticality": f.criticality}
                for f in briefing.direct_findings
            ],
            "downstream_cascades": [
                {"id": f.asset_id, "name": f.asset_name, "criticality": f.criticality, "distance": f.direct_distance}
                for f in briefing.downstream_findings
            ],
        },
        "ripple_score_rankings": [
            {
                "asset_id": s.asset_id,
                "asset_name": s.asset_name,
                "total_score": s.total_score,
                "criticality": s.criticality,
                "explanation": s.formula_explanation,
            }
            for s in briefing.ripple_scores[:5]
        ],
        "historical_memory": [
            {
                "incident_id": m.incident_id,
                "title": m.title,
                "relevance": m.relevance_reason,
                "outcome_type": m.outcome_type.value,
                "outcome_description": m.outcome_description,
                "action_taken": m.recovery_action_name,
            }
            for m in briefing.historical_incidents
        ],
        "recommended_recovery_plan": {
            "plan_name": briefing.recommended_plan.plan_name if briefing.recommended_plan else "None",
            "composite_benefit_score": briefing.recommended_plan.composite_benefit_score if briefing.recommended_plan else 0.0,
            "estimated_hours": briefing.recommended_plan.total_estimated_hours if briefing.recommended_plan else 0.0,
            "critical_services_protected": briefing.recommended_plan.unique_critical_services_protected if briefing.recommended_plan else 0,
            "rationale": briefing.recommendation_rationale,
            "tradeoffs": briefing.recommended_plan.tradeoffs_and_risks if briefing.recommended_plan else [],
        },
        "assumptions_and_missing_data": briefing.missing_data_and_assumptions[:4],
    }

    user_prompt = f"Explain the following deterministic investigation findings:\n{json.dumps(structured_payload, indent=2)}"

    try:
        response = groq_cli.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_BRIEFING},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        narrative = response.choices[0].message.content
        if narrative:
            return narrative.strip(), "SUCCESS"
        return None, "FALLBACK_DETERMINISTIC"
    except Exception as e:
        logger.warning(f"Groq API briefing explanation failed: {e}. Gracefully falling back to deterministic.")
        return None, "FALLBACK_DETERMINISTIC"


def generate_question_narrative(
    question: str,
    grounded_answer: GroundedAnswer,
    client: Optional[Groq] = None,
    model: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """Synthesizes a fluent natural-language answer to an investigation question,
    constrained strictly to deterministic GroundedAnswer facts and evidence paths.
    
    Returns:
        tuple[Optional[str], str]: (narrative_answer, status)
    """
    groq_cli = client or get_groq_client()
    if not groq_cli:
        return None, "DETERMINISTIC_ONLY"

    target_model = model or config.groq_model

    # Verify model availability against Groq model catalog
    if not verify_model_availability(target_model, client=groq_cli):
        return None, "FALLBACK_DETERMINISTIC"

    answer_payload = {
        "question": question,
        "deterministic_answer": grounded_answer.answer,
        "evidence_sufficient": grounded_answer.evidence_sufficient,
        "supporting_asset_ids": grounded_answer.supporting_asset_ids,
        "graph_paths": grounded_answer.graph_paths,
        "relationship_types": grounded_answer.relationship_types,
        "relevant_properties": grounded_answer.relevant_properties,
        "unresolved_assumptions": grounded_answer.unresolved_assumptions,
    }

    user_prompt = f"Synthesize a clear, concise executive response for this question using only the provided facts:\n{json.dumps(answer_payload, indent=2)}"

    try:
        response = groq_cli.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_QUESTION},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=512,
        )
        narrative = response.choices[0].message.content
        if narrative:
            return narrative.strip(), "SUCCESS"
        return None, "FALLBACK_DETERMINISTIC"
    except Exception as e:
        logger.warning(f"Groq API question explanation failed: {e}. Gracefully falling back to deterministic.")
        return None, "FALLBACK_DETERMINISTIC"
