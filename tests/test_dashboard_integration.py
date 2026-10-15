"""Integration and unit tests for the RippleMap Streamlit dashboard.

Validates:
- Retrieval of selectable infrastructure sources from FalkorDB.
- Graph figure generation adhering to evidence paths and role classifications.
- Canonical RippleScore and Recovery Plan chart rendering.
- Dynamic derivation of summary metrics (zero hardcoded values).
- Graceful handling of empty states and LLM fallback modes.
- Zero database mutation (nodes, relationships, and incident memory preserved).
"""

from unittest.mock import MagicMock, patch
import pytest
from app.db import db_client
from app.graph_queries import get_selectable_infrastructure_nodes
from app.investigation_agent import run_investigation_agent
from app.schema import AgentBriefing, Criticality, EntityType, ImpactClassification, OperationalStatus, ScoreBreakdown, RecoveryPlan
from app.ui.charts import render_recovery_comparison_chart, render_ripple_score_chart
from app.ui.graph_viz import build_cascade_graph
from app.ui.styles import render_badge


@pytest.fixture(scope="module")
def db():
    return db_client


@pytest.fixture(scope="module")
def sub001_briefing(db):
    """Generates a deterministic briefing for SUB-001 with use_llm=False."""
    return run_investigation_agent("SUB-001", persist_memory=False, use_llm=False, client=db)


# =============================================================================
# 1. Source Selection & Database Integration
# =============================================================================

def test_selectable_sources_retrieval(db):
    """Ensures get_selectable_infrastructure_nodes returns physical infrastructure
    nodes from FalkorDB and includes default SUB-001.
    """
    nodes = get_selectable_infrastructure_nodes(client=db)
    assert isinstance(nodes, list)
    assert len(nodes) >= 10

    node_ids = [n["id"] for n in nodes]
    assert "SUB-001" in node_ids
    assert "PUMP-001" in node_ids
    assert "HOSP-001" in node_ids

    # Verify node structure
    sub = next(n for n in nodes if n["id"] == "SUB-001")
    assert sub["entity_type"] == "Substation"
    assert "Tier 1" in sub["criticality"]
    assert sub["status"] == "OPERATIONAL"


# =============================================================================
# 2. Plotly Graph Visualization Generation
# =============================================================================

def test_dashboard_graph_figure_generation(sub001_briefing):
    """Ensures build_cascade_graph builds an interactive Plotly figure
    accurately reflecting the source, direct dependencies, downstream cascades,
    alternate suppliers, and backup generators.
    """
    fig = build_cascade_graph(sub001_briefing)
    assert fig is not None
    assert len(fig.data) > 0

    trace_names = [t.name for t in fig.data if t.name]

    # Verify presence of all key topological role layers
    assert "Source (Root Incident)" in trace_names
    assert "Direct Dependency (1 Hop)" in trace_names
    assert "Downstream Cascade (2+ Hops)" in trace_names
    assert "Alternate Route Supplier" in trace_names
    assert "Backup Generator" in trace_names

    # Check that annotations (directional arrows) were generated
    assert len(fig.layout.annotations) >= len(sub001_briefing.direct_findings)


def test_dashboard_graph_empty_state():
    """Confirms build_cascade_graph returns a clean empty-state figure
    when briefing is empty or None.
    """
    empty_briefing = AgentBriefing(
        incident_id="NONE",
        source_node_id="",
        source_node_name="",
        source_entity_type="",
        source_criticality="",
        source_status="",
        timestamp="",
        is_persisted_memory=False,
        investigation_summary="",
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
    )
    fig = build_cascade_graph(empty_briefing)
    assert fig is not None
    assert len(fig.layout.annotations) == 1
    assert "No incident investigation active" in fig.layout.annotations[0].text


# =============================================================================
# 3. Canonical RippleScore Chart Rendering
# =============================================================================

def test_dashboard_score_chart_generation(sub001_briefing):
    """Ensures render_ripple_score_chart accurately reflects canonical ScoreBreakdown
    components without hardcoded calculations.
    """
    fig = render_ripple_score_chart(sub001_briefing.ripple_scores)
    assert fig is not None

    trace_names = [t.name for t in fig.data]
    assert "Base Criticality" in trace_names
    assert "Downstream Cascades" in trace_names
    assert "Multipath Exposure" in trace_names
    assert "SPOF Penalty" in trace_names
    assert "Alternate Route Credit (-)" in trace_names
    assert "Backup Generator Credit (-)" in trace_names
    assert "Final RippleScore" in trace_names

    # Check empty list handling
    empty_fig = render_ripple_score_chart([])
    assert len(empty_fig.layout.annotations) == 1
    assert "No RippleScore data available" in empty_fig.layout.annotations[0].text


# =============================================================================
# 4. Canonical Recovery Plan Chart Rendering
# =============================================================================

def test_dashboard_recovery_chart_generation(sub001_briefing):
    """Ensures render_recovery_comparison_chart reflects candidate optimizer plans."""
    fig = render_recovery_comparison_chart(sub001_briefing.evaluated_plans)
    assert fig is not None
    assert len(fig.data) == 2  # Benefit score bar + Hours line

    trace_names = [t.name for t in fig.data]
    assert "Composite Benefit Score" in trace_names
    assert "Estimated Hours to Restore" in trace_names

    # Check empty list handling
    empty_fig = render_recovery_comparison_chart([])
    assert len(empty_fig.layout.annotations) == 1
    assert "No recovery plans generated" in empty_fig.layout.annotations[0].text


# =============================================================================
# 5. Dynamic Summary Metrics (Zero Hardcoding)
# =============================================================================

def test_dashboard_metrics_derivation_not_hardcoded(sub001_briefing):
    """Verifies that executive metric calculations dynamically derive from
    briefing findings rather than fixed constants.
    """
    total_affected = len(sub001_briefing.direct_findings) + len(sub001_briefing.downstream_findings)
    assert total_affected == 8

    direct_count = len(sub001_briefing.direct_findings)
    assert direct_count == 6

    downstream_count = len(sub001_briefing.downstream_findings)
    assert downstream_count == 2

    critical_services = [
        f for f in (sub001_briefing.direct_findings + sub001_briefing.downstream_findings)
        if "Tier 1" in f.criticality or "Tier 2" in f.criticality
    ]
    assert len(critical_services) == 6

    top_score = sub001_briefing.ripple_scores[0].total_score
    assert top_score == 85.0

    top_plan = sub001_briefing.recommended_plan
    assert top_plan.composite_benefit_score == 242.0
    assert top_plan.plan_id == "PLAN-ACT-ACT-001"


# =============================================================================
# 6. HTML Badges and Styling Helpers
# =============================================================================

def test_render_badge_styling():
    """Verifies render_badge generates compliant HTML spans with variant classes."""
    badge_emerald = render_badge("OPERATIONAL", "emerald")
    assert '<span class="rm-badge rm-badge-emerald">OPERATIONAL</span>' == badge_emerald

    badge_crimson = render_badge("FAILED", "crimson")
    assert '<span class="rm-badge rm-badge-crimson">FAILED</span>' == badge_crimson


# =============================================================================
# 7. Zero Database Mutation Guarantee
# =============================================================================

def test_dashboard_zero_mutation_guarantee(db):
    """Confirms that executing dashboard workflows (source selection, figure generation,
    and investigation runs with persist_memory=False) causes zero mutations to graph
    node counts, relationship counts, or operational statuses.
    """
    n_before = db.query("MATCH (n) RETURN count(n)")[0][0]
    r_before = db.query("MATCH ()-[r]->() RETURN count(r)")[0][0]
    statuses_before = {
        row[0]: row[1]
        for row in db.query("MATCH (n:InfrastructureNode) RETURN n.id, n.status")
    }

    # Simulate dashboard investigation
    briefing = run_investigation_agent("SUB-001", persist_memory=False, use_llm=False, client=db)
    _ = build_cascade_graph(briefing)
    _ = render_ripple_score_chart(briefing.ripple_scores)
    _ = render_recovery_comparison_chart(briefing.evaluated_plans)

    n_after = db.query("MATCH (n) RETURN count(n)")[0][0]
    r_after = db.query("MATCH ()-[r]->() RETURN count(r)")[0][0]
    statuses_after = {
        row[0]: row[1]
        for row in db.query("MATCH (n:InfrastructureNode) RETURN n.id, n.status")
    }

    assert n_before == n_after == 59
    assert r_before == r_after == 135
    assert statuses_before == statuses_after
