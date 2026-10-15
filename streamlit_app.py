"""RippleMap - Interactive Infrastructure Intelligence & Consequence-Analysis Dashboard.

Main entry point for Streamlit application.
Run via: streamlit run streamlit_app.py
"""

import logging
from typing import Optional
import streamlit as st

# Configure page metadata and layout
st.set_page_config(
    page_title="RippleMap | Infrastructure Intelligence",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.config import config
from app.db import db_client
from app.graph_queries import get_selectable_infrastructure_nodes
from app.investigation_agent import run_investigation_agent
from app.schema import AgentBriefing
from app.ui.charts import render_recovery_comparison_chart, render_ripple_score_chart
from app.ui.components import (
    render_evidence_table,
    render_executive_metrics,
    render_groq_panel,
    render_header,
    render_incident_memory_section,
    render_recovery_comparison_section,
)
from app.ui.graph_viz import build_cascade_graph
from app.ui.styles import CUSTOM_CSS, render_badge

logger = logging.getLogger(__name__)

# Apply custom CSS design system
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def check_database_health() -> bool:
    """Verifies that FalkorDB is reachable."""
    try:
        return db_client.is_healthy()
    except Exception:
        return False


def get_selectable_sources():
    """Retrieves selectable infrastructure assets from FalkorDB with safe fallback."""
    try:
        nodes = get_selectable_infrastructure_nodes(client=db_client)
        if nodes:
            return nodes
    except Exception as e:
        logger.warning(f"Failed to fetch selectable nodes from FalkorDB: {e}")
    # Minimal fallback list if database query fails
    return [
        {"id": "SUB-001", "name": "Metro Central Substation", "entity_type": "Substation", "criticality": "Tier 1", "status": "OPERATIONAL", "zone": "Downtown"}
    ]


# Initialize Session State
if "current_briefing" not in st.session_state:
    st.session_state["current_briefing"] = None
if "last_investigated_source" not in st.session_state:
    st.session_state["last_investigated_source"] = None
if "last_investigated_llm_state" not in st.session_state:
    st.session_state["last_investigated_llm_state"] = None


def main():
    # Render top branding and simulation disclaimer
    render_header()

    # Database Preflight Check
    is_db_connected = check_database_health()
    if not is_db_connected:
        st.error(
            "⚠️ **FalkorDB Connection Offline:** Could not establish connection to FalkorDB on "
            f"{config.host}:{config.port} (graph: `{config.graph_name}`). "
            "Please ensure the FalkorDB Docker container is running (`docker ps`)."
        )
        st.stop()

    # Load selectable infrastructure sources
    selectable_nodes = get_selectable_sources()
    node_ids = [n["id"] for n in selectable_nodes]
    default_idx = node_ids.index("SUB-001") if "SUB-001" in node_ids else 0

    # -------------------------------------------------------------------------
    # Sidebar: Incident Control Panel & Groq Configuration
    # -------------------------------------------------------------------------
    with st.sidebar:
        st.markdown("### 🎛️ Incident Control")
        st.markdown(
            "<div style='font-size:0.85rem; color:#94A3B8; margin-bottom:12px;'>"
            "Select a municipal asset to simulate a root outage and evaluate cascading interdependencies."
            "</div>",
            unsafe_allow_html=True,
        )

        selected_source_id = st.selectbox(
            "Select Incident Source Asset:",
            options=node_ids,
            index=default_idx,
            format_func=lambda nid: f"{nid} - {next((n['name'] for n in selectable_nodes if n['id'] == nid), '')}",
            key="source_selector",
        )

        selected_node_info = next((n for n in selectable_nodes if n["id"] == selected_source_id), None)
        if selected_node_info:
            st.markdown(
                f"""
                <div style="background:#162032; border:1px solid #334155; border-radius:6px; padding:10px; font-size:0.8rem; margin-bottom:12px;">
                    <div><strong>Type:</strong> {selected_node_info['entity_type']}</div>
                    <div><strong>Criticality:</strong> {selected_node_info['criticality'].split(' - ')[0]}</div>
                    <div><strong>Zone:</strong> {selected_node_info['zone']}</div>
                    <div><strong>Graph Status:</strong> <span style="color:#10B981;">{selected_node_info['status']}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown("### 🤖 Narrative Synthesis")

        groq_key_present = config.is_groq_configured
        use_llm = st.toggle(
            "Enable Groq AI Narrative",
            value=groq_key_present,
            help="Generates executive briefings and grounded explanations using Groq (openai/gpt-oss-120b). Deterministic fallback is always active.",
            key="llm_toggle",
        )

        if use_llm and not groq_key_present:
            st.warning("⚠️ No GROQ_API_KEY found in environment or .env. Agent will operate in deterministic-only mode.")
        elif use_llm:
            st.caption(f"Configured Model: `{config.groq_model}`")

        st.markdown("---")

        investigate_clicked = st.button(
            "⚡ Investigate Incident",
            type="primary",
            use_container_width=True,
            key="btn_investigate",
        )

        st.markdown(
            "<div style='font-size:0.75rem; color:#64748B; margin-top:14px; text-align:center;'>"
            "RippleMap Decision Engine v1.0<br>Zero database mutation during analysis."
            "</div>",
            unsafe_allow_html=True,
        )

    # -------------------------------------------------------------------------
    # Investigation Execution (Triggers on click or initial load)
    # -------------------------------------------------------------------------
    needs_run = (
        investigate_clicked
        or st.session_state["current_briefing"] is None
        or st.session_state["last_investigated_source"] != selected_source_id
        or st.session_state["last_investigated_llm_state"] != use_llm
    )

    if needs_run:
        with st.spinner(f"Simulating root failure for {selected_source_id} & tracing cascading interdependencies..."):
            try:
                briefing: AgentBriefing = run_investigation_agent(
                    source_id=selected_source_id,
                    persist_memory=False,  # Strict read-only: never mutate graph from UI
                    use_llm=use_llm,
                    client=db_client,
                )
                st.session_state["current_briefing"] = briefing
                st.session_state["last_investigated_source"] = selected_source_id
                st.session_state["last_investigated_llm_state"] = use_llm
            except Exception as e:
                st.error(f"Investigation failed for '{selected_source_id}': {e}")
                logger.error(f"Investigation execution error: {e}", exc_info=True)
                return

    briefing: AgentBriefing = st.session_state["current_briefing"]

    # -------------------------------------------------------------------------
    # Section B: Executive Impact Summary
    # -------------------------------------------------------------------------
    render_executive_metrics(briefing)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # Section C: Interactive Dependency Graph
    # -------------------------------------------------------------------------
    st.markdown("### 🌐 Interactive Dependency Graph & Cascades")
    st.markdown(
        "<div style='font-size:0.85rem; color:#94A3B8; margin-bottom:8px;'>"
        "Topology map tracing physical supply links (solid cyan), verified alternate routes (dashed green), and backup generators (dotted purple)."
        "</div>",
        unsafe_allow_html=True,
    )

    cascade_fig = build_cascade_graph(briefing)
    st.plotly_chart(cascade_fig, use_container_width=True)

    # -------------------------------------------------------------------------
    # Tabs for In-depth Intelligence Modules
    # -------------------------------------------------------------------------
    tab_evidence, tab_score, tab_recovery, tab_memory, tab_qa = st.tabs([
        "📋 Evidence & Cascade Explorer",
        "📊 RippleScore Breakdown",
        "🛠️ Recovery Plan Optimizer",
        "🏛️ Incident Memory",
        "💬 AI Narrative & Grounded Q&A",
    ])

    # Tab 1: Evidence and Cascade Explorer
    with tab_evidence:
        render_evidence_table(briefing)

    # Tab 2: RippleScore Explanation
    with tab_score:
        st.markdown("#### Canonical RippleScore Component Breakdown")
        st.markdown(
            "The **RippleScore** is a deterministic [0, 100] index measuring exposure based on inherent criticality, "
            "downstream critical services, single-point-of-failure (SPOF) risks, and unmitigated failure vectors, "
            "offset by verified alternate routes and operational backup generators."
        )

        score_fig = render_ripple_score_chart(briefing.ripple_scores)
        st.plotly_chart(score_fig, use_container_width=True)

        st.markdown("##### Highest Exposure Component Audit")
        top_scores = briefing.ripple_scores[:3]
        score_cols = st.columns(len(top_scores)) if top_scores else []
        for idx, score_col in enumerate(score_cols):
            sb = top_scores[idx]
            with score_col:
                st.markdown(
                    f"""
                    <div class="rm-card">
                        <div style="font-weight:700; color:#38BDF8; font-size:1.1rem;">#{idx+1} {sb.asset_id}</div>
                        <div style="font-size:0.85rem; color:#F8FAFC; margin-bottom:8px;">{sb.asset_name}</div>
                        <div style="font-size:1.4rem; font-weight:700; color:#EF4444;">{sb.total_score:.1f} <span style="font-size:0.8rem; color:#94A3B8;">/ 100</span></div>
                        <hr style="border-color:#334155; margin:8px 0;">
                        <div style="font-size:0.8rem; line-height:1.5;">
                            <div>Base Criticality: <b>+{sb.inherent_score:.1f}</b></div>
                            <div>Downstream Cascade: <b>+{sb.downstream_impact_score:.1f}</b></div>
                            <div>Multipath Exposure: <b>+{sb.multipath_vulnerability_score:.1f}</b></div>
                            <div>SPOF Penalty: <b>+{sb.spof_penalty:.1f}</b></div>
                            <div>Contingency Penalty: <b>+{sb.capacity_penalty + sb.failed_contingency_penalty:.1f}</b></div>
                            <div style="color:#10B981;">Alternate Route Credit: <b>-{sb.mitigation_credit:.1f}</b></div>
                            <div style="color:#8B5CF6;">Backup Credit: <b>-{sb.backup_credit:.1f}</b></div>
                        </div>
                        <div style="font-size:0.75rem; color:#94A3B8; margin-top:8px;">
                            Confidence: {sb.confidence * 100:.0f}%
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # Tab 3: Recovery Plan Comparison
    with tab_recovery:
        st.markdown("#### Candidate Recovery Plan Evaluation")
        st.markdown(
            "The **Recovery Optimizer** generates candidate interventions (full component repair, auxiliary tie-line switching, "
            "mobile generator dispatch) and ranks them using a normalized composite benefit formula: "
            "<code>Score = (protected_assets &times; 10) + (critical_services &times; 20) + (mitigation_ratio &times; 30) - (hours &times; 3) - residual_penalties</code>."
        )

        rec_fig = render_recovery_comparison_chart(briefing.evaluated_plans)
        st.plotly_chart(rec_fig, use_container_width=True)

        render_recovery_comparison_section(briefing)

    # Tab 4: Incident Memory
    with tab_memory:
        render_incident_memory_section(briefing)

    # Tab 5: Groq AI Narrative & Grounded Q&A
    with tab_qa:
        render_groq_panel(briefing)

        st.markdown("---")
        st.markdown("#### 🔍 Grounded Question Investigation")
        st.markdown(
            "Select or submit an infrastructure inquiry. Answers are strictly grounded in deterministic graph facts, "
            "with optional natural-language synthesis."
        )

        preset_questions = [
            "Why is this recovery plan ranked first?",
            f"What could be affected if {selected_source_id} fails?",
            "Which critical services have no viable alternate supply?",
            "What previous incidents involved this component?",
            "Which risks remain after the proposed intervention?",
            "What information is missing before we can recommend an action confidently?",
        ]

        q_col1, q_col2 = st.columns([3, 1])
        with q_col1:
            chosen_preset = st.selectbox(
                "Preset Grounded Inquiry:",
                options=preset_questions,
                key="preset_question_picker",
            )
        with q_col2:
            custom_q = st.text_input("Or enter custom question:", placeholder="e.g. HOSP-001 backup status", key="custom_q_input")

        active_question = custom_q.strip() if custom_q.strip() else chosen_preset

        if st.button("Submit Inquiry", key="btn_ask_question"):
            with st.spinner("Evaluating grounded graph answer..."):
                q_briefing = run_investigation_agent(
                    source_id=selected_source_id,
                    question=active_question,
                    persist_memory=False,
                    use_llm=use_llm,
                    client=db_client,
                )
                if q_briefing.grounded_answers:
                    ans = q_briefing.grounded_answers[0]
                    st.markdown(
                        f"""
                        <div class="rm-card" style="margin-top:12px; border-left:4px solid #06B6D4;">
                            <div style="font-weight:600; color:#38BDF8; margin-bottom:6px;">Q: {ans.question}</div>
                            <div style="color:#F8FAFC; font-size:0.95rem; line-height:1.5;">{ans.answer}</div>
                            <div style="margin-top:8px; font-size:0.8rem; color:#94A3B8;">
                                Supporting Assets: <b>{', '.join(ans.supporting_asset_ids) or 'None'}</b> &bull; 
                                Evidence Sufficient: <b>{'Yes' if ans.evidence_sufficient else 'No'}</b>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if ans.llm_explanation:
                        st.markdown(
                            f"""
                            <div style="background:rgba(6,182,212,0.06); border:1px solid rgba(6,182,212,0.25); border-radius:6px; padding:12px; margin-top:8px;">
                                <strong style="color:#06B6D4; font-size:0.85rem;">Groq Narrative Explanation:</strong>
                                <div style="color:#CBD5E1; font-size:0.9rem; margin-top:4px;">{ans.llm_explanation}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )


if __name__ == "__main__":
    main()
