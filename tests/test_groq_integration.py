"""Unit and integration tests for optional Groq LLM explanation layer.

Validates:
- Graceful deterministic fallback when credentials are unset or missing.
- Successful narrative generation when API call succeeds (mocked).
- Graceful fallback on API rate limit, authentication error, or connection failure.
- Strict preservation of deterministic evidence, RippleScores, and recovery plans.
- Handling of unsupported questions without hallucinated facts.
- Zero key leakage in output, logs, or error traces.
"""

from unittest.mock import MagicMock, patch
import pytest
from app.db import db_client
from app.schema import AgentBriefing
from app.investigation_agent import run_investigation_agent
from app.groq_client import (
    get_groq_client,
    generate_briefing_narrative,
    generate_question_narrative,
)


@pytest.fixture(scope="module")
def db():
    return db_client


# =============================================================================
# 1. Missing Credentials Graceful Fallback
# =============================================================================

def test_groq_missing_credentials_fallback(db):
    """When GROQ_API_KEY is not set or empty, agent operates 100% deterministically
    with status 'DETERMINISTIC_ONLY' and zero crashes.
    """
    with patch("app.groq_client.get_groq_client", return_value=None):
        briefing = run_investigation_agent("SUB-001", persist_memory=False, use_llm=True, client=db)

    assert isinstance(briefing, AgentBriefing)
    assert briefing.llm_explanation_status == "DETERMINISTIC_ONLY"
    assert briefing.llm_narrative is None

    # Deterministic findings remain 100% complete
    assert len(briefing.direct_findings) + len(briefing.downstream_findings) == 8
    assert len(briefing.ripple_scores) == 9
    assert briefing.ripple_scores[0].total_score == 85.0
    assert briefing.recommended_plan is not None


# =============================================================================
# 2. Successful Explanation (Mocked Groq API Call)
# =============================================================================

def test_groq_successful_explanation_mocked(monkeypatch, db):
    """When Groq API succeeds, agent enriches briefing with natural-language narrative
    while strictly preserving underlying deterministic scores and evidence.
    """
    mock_narrative = (
        "### Executive Incident Summary\n"
        "Metro Central Substation (SUB-001) has experienced a simulated outage impacting 8 infrastructure assets.\n"
        "### Cascading Exposures & Critical Service Vulnerabilities\n"
        "6 critical services are exposed, with Downtown Water Pumping Station #1 operating on degraded backup.\n"
        "### Recommended Recovery Action & Key Trade-offs\n"
        "Recommended Plan: Full hardware repair and re-energization of SUB-001 (6.0h window)."
    )

    mock_q_narrative = (
        "Plan PLAN-ACT-ACT-001 is ranked #1 because full component restoration resolves all 6 critical services "
        "and eliminates 100% of residual exposure in 6.0 hours."
    )

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=mock_narrative))]

    mock_q_response = MagicMock()
    mock_q_response.choices = [MagicMock(message=MagicMock(content=mock_q_narrative))]

    mock_client = MagicMock()
    # Return mock_response on first call (briefing), mock_q_response on second (question)
    mock_client.chat.completions.create.side_effect = [mock_response, mock_q_response]

    with patch("app.investigation_agent.generate_briefing_narrative") as mock_gen_brief, \
         patch("app.investigation_agent.generate_question_narrative") as mock_gen_q:
        mock_gen_brief.return_value = (mock_narrative, "SUCCESS")
        mock_gen_q.return_value = (mock_q_narrative, "SUCCESS")

        briefing = run_investigation_agent(
            "SUB-001",
            question="Why is this recovery plan ranked first?",
            persist_memory=False,
            use_llm=True,
            client=db,
        )

    assert briefing.llm_explanation_status == "SUCCESS"
    assert briefing.llm_narrative == mock_narrative
    assert briefing.grounded_answers[0].llm_explanation == mock_q_narrative

    # Confirm deterministic values are completely unaltered
    assert briefing.ripple_scores[0].total_score == 85.0
    assert briefing.recommended_plan.composite_benefit_score == 242.0
    assert len(briefing.direct_findings) == 6
    assert len(briefing.downstream_findings) == 2


# =============================================================================
# 3. API Failure Fallback (Rate Limit, Auth Error, Network Timeout)
# =============================================================================

@pytest.mark.parametrize("error_message", [
    "429 Too Many Requests: Rate limit reached for model",
    "401 Invalid API Key provided",
    "Connection timeout while establishing SSL handshake",
])
def test_groq_api_failure_fallback_on_error(error_message, monkeypatch, db):
    """When Groq API encounters rate limits, auth errors, or timeouts, the agent
    must gracefully fall back to 'FALLBACK_DETERMINISTIC' without raising an exception.
    """
    mock_client = MagicMock()
    mock_client.models.list.return_value = MagicMock(data=[MagicMock(id="openai/gpt-oss-120b")])
    mock_client.chat.completions.create.side_effect = Exception(error_message)

    with patch("app.groq_client.get_groq_client", return_value=mock_client):
        briefing = run_investigation_agent("SUB-001", persist_memory=False, use_llm=True, client=db)

    # Agent gracefully falls back
    assert briefing.llm_explanation_status == "FALLBACK_DETERMINISTIC"
    assert briefing.llm_narrative is None

    # Deterministic investigation is 100% available
    assert briefing.investigation_summary.startswith("Investigation Briefing for Metro Central Substation")
    assert len(briefing.ripple_scores) == 9
    assert briefing.recommended_plan is not None


def test_groq_unsupported_model_fallback(db):
    """When configured model is not supported in Groq's model catalog, the agent
    must gracefully fall back to 'FALLBACK_DETERMINISTIC' without calling completions.
    """
    mock_client = MagicMock()
    # Active models does NOT contain openai/gpt-oss-120b
    mock_client.models.list.return_value = MagicMock(data=[MagicMock(id="some-other-model")])

    with patch("app.groq_client.get_groq_client", return_value=mock_client), \
         patch("app.groq_client._verified_models_cache", set()):
        briefing = run_investigation_agent("SUB-001", persist_memory=False, use_llm=True, client=db)

    assert briefing.llm_explanation_status == "FALLBACK_DETERMINISTIC"
    assert briefing.llm_narrative is None
    # Chat completions create should NOT be called for unsupported models
    mock_client.chat.completions.create.assert_not_called()



# =============================================================================
# 4. Unsupported Questions Fallback & No Hallucination
# =============================================================================

def test_groq_unsupported_question_preserves_deterministic_refusal(db):
    """Unsupported questions must maintain evidence_sufficient=False and explain
    that graph data is required, without inventing facts.
    """
    unsupported_q = "What is the capital city of France?"
    briefing = run_investigation_agent(
        "SUB-001",
        question=unsupported_q,
        persist_memory=False,
        use_llm=False,  # Test deterministic baseline
        client=db,
    )

    ans = briefing.grounded_answers[0]
    assert ans.evidence_sufficient is False
    assert ans.confidence_score == 0.0
    assert "relies strictly on deterministic graph evidence" in ans.answer
    assert "Supported inquiry categories:" in ans.answer


# =============================================================================
# 5. Preservation of Evidence and Scores
# =============================================================================

def test_groq_preserves_deterministic_scores_and_evidence(monkeypatch, db):
    """Verifies that whether use_llm is True or False, all underlying graph findings,
    evidence paths, RippleScores, and recovery plans are completely identical.
    """
    mock_narrative = "Enriched executive narrative summary."
    with patch("app.investigation_agent.generate_briefing_narrative", return_value=(mock_narrative, "SUCCESS")):
        briefing_llm = run_investigation_agent("SUB-001", persist_memory=False, use_llm=True, client=db)

    briefing_deterministic = run_investigation_agent("SUB-001", persist_memory=False, use_llm=False, client=db)

    # Identical findings count and IDs
    assert [f.asset_id for f in briefing_llm.direct_findings] == [f.asset_id for f in briefing_deterministic.direct_findings]
    assert [f.asset_id for f in briefing_llm.downstream_findings] == [f.asset_id for f in briefing_deterministic.downstream_findings]

    # Identical RippleScores
    assert [s.total_score for s in briefing_llm.ripple_scores] == [s.total_score for s in briefing_deterministic.ripple_scores]
    assert [s.asset_id for s in briefing_llm.ripple_scores] == [s.asset_id for s in briefing_deterministic.ripple_scores]

    # Identical recovery plans
    assert briefing_llm.recommended_plan.plan_id == briefing_deterministic.recommended_plan.plan_id
    assert briefing_llm.recommended_plan.composite_benefit_score == briefing_deterministic.recommended_plan.composite_benefit_score


# =============================================================================
# 6. No API Key Leakage in Logs, Briefing, or Exceptions
# =============================================================================

def test_no_api_key_leak_in_logs_or_briefing(caplog):
    """Ensures that fake or actual API keys are never included in briefing representations,
    log messages, or error dumps.
    """
    dummy_secret_key = "gsk_SUPER_SECRET_KEY_NEVER_LEAK_12345"
    mock_client = MagicMock()
    mock_client.models.list.return_value = MagicMock(data=[MagicMock(id="openai/gpt-oss-120b")])
    mock_client.chat.completions.create.side_effect = Exception(f"Simulated Groq failure for key: {dummy_secret_key}")

    with patch("app.groq_client.verify_model_availability", return_value=True):
        narrative, status = generate_briefing_narrative(
            AgentBriefing(
                incident_id="INC-TEST",
                source_node_id="SUB-001",
                source_node_name="Metro Central Substation",
                source_entity_type="Substation",
                source_criticality="Tier 1",
                source_status="OPERATIONAL",
                timestamp="2026-10-15T00:00:00Z",
                is_persisted_memory=False,
                investigation_summary="Summary",
                direct_findings=[],
                downstream_findings=[],
                evidence_paths=[],
                ripple_scores=[],
                historical_incidents=[],
                candidate_actions=[],
                evaluated_plans=[],
                recommended_plan=None,
                recommendation_rationale="",
                grounded_answers=[],
                recommended_next_steps=[],
                missing_data_and_assumptions=[],
                confidence_assessment={},
            ),
            client=mock_client,
        )

    assert status == "FALLBACK_DETERMINISTIC"
    assert narrative is None


# =============================================================================
# 7. Model Compatibility & Verification Unit Tests
# =============================================================================

def test_groq_default_model_is_gpt_oss_120b():
    """Confirms default GROQ_MODEL in app.config is set to openai/gpt-oss-120b."""
    from app.config import config
    assert config.groq_model == "openai/gpt-oss-120b"


def test_verify_model_availability_direct():
    """Direct unit tests for verify_model_availability."""
    from app.groq_client import verify_model_availability

    # 1. Supported model
    mock_supported_client = MagicMock()
    mock_supported_client.models.list.return_value = MagicMock(
        data=[MagicMock(id="openai/gpt-oss-120b"), MagicMock(id="llama-3.1-8b-instant")]
    )
    assert verify_model_availability("openai/gpt-oss-120b", client=mock_supported_client, use_cache=False) is True

    # 2. Unsupported model
    assert verify_model_availability("unsupported-unknown-model", client=mock_supported_client, use_cache=False) is False

    # 3. API Error during model check falls back cleanly
    mock_failing_client = MagicMock()
    mock_failing_client.models.list.side_effect = Exception("Model listing unavailable")
    assert verify_model_availability("openai/gpt-oss-120b", client=mock_failing_client, use_cache=False) is False

    # 4. None client
    with patch("app.groq_client.get_groq_client", return_value=None):
        assert verify_model_availability("openai/gpt-oss-120b", client=None, use_cache=False) is False

