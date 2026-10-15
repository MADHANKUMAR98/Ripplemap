"""UI component renderers for RippleMap dashboard."""

from typing import Any, Optional
import pandas as pd
import streamlit as st
from app.schema import AgentBriefing, AffectedAssetFinding, RecoveryPlan, ScoreBreakdown
from app.ui.styles import render_badge


def render_header():
    """Renders the top branding header with system status and simulation notice."""
    st.markdown(
        """
        <div class="rm-header">
            <div>
                <h1 class="rm-header-title">
                    <span style="color:#06B6D4;">&#x29BF;</span> RippleMap
                    <span style="font-size:0.9rem; font-weight:500; color:#38BDF8; background:rgba(6,182,212,0.15); padding:2px 8px; border-radius:12px; border:1px solid rgba(6,182,212,0.3);">
                        INFRASTRUCTURE INTELLIGENCE
                    </span>
                </h1>
                <div class="rm-header-subtitle">
                    Deterministic Cascading Failure Analysis &bull; RippleScore Exposure Ranking &bull; Grounded Recovery Optimizer
                </div>
            </div>
            <div style="text-align:right;">
                <span class="rm-badge rm-badge-emerald">FalkorDB Graph Live</span>
                <div style="font-size:0.75rem; color:#94A3B8; margin-top:4px;">Ripple City Municipal Topology</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="rm-sim-banner">
            <strong>&#x26A0; SIMULATION ENVIRONMENT:</strong> Results represent modeled physical dependency consequences and hypothetical cascading exposures, not verified live outages or field failures.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_executive_metrics(briefing: AgentBriefing):
    """Renders the 6 key executive metric cards."""
    total_affected = len(briefing.direct_findings) + len(briefing.downstream_findings)
    direct_count = len(briefing.direct_findings)
    downstream_count = len(briefing.downstream_findings)

    # Count exposed critical services (Tier 1 & Tier 2)
    critical_services = [
        f for f in (briefing.direct_findings + briefing.downstream_findings)
        if "Tier 1" in f.criticality or "Tier 2" in f.criticality
    ]
    crit_count = len(critical_services)

    top_score = briefing.ripple_scores[0].total_score if briefing.ripple_scores else 0.0
    top_asset = briefing.ripple_scores[0].asset_id if briefing.ripple_scores else "N/A"

    best_plan = briefing.recommended_plan
    plan_label = best_plan.plan_id if best_plan else "None"
    plan_score = f"{best_plan.composite_benefit_score:.1f} pts" if best_plan else "0.0"

    llm_status = briefing.llm_explanation_status
    if llm_status == "SUCCESS":
        llm_badge = render_badge("Groq AI Active", "emerald")
    elif llm_status == "FALLBACK_DETERMINISTIC":
        llm_badge = render_badge("Deterministic Fallback", "amber")
    else:
        llm_badge = render_badge("Deterministic Engine", "cyan")

    cols = st.columns(6)

    with cols[0]:
        st.markdown(
            f"""
            <div class="rm-metric-card">
                <div class="rm-metric-label">Incident Source</div>
                <div class="rm-metric-value" style="color:#EF4444;">{briefing.source_node_id}</div>
                <div class="rm-metric-sub">{briefing.source_entity_type} &bull; {briefing.source_criticality.split(' - ')[0]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[1]:
        st.markdown(
            f"""
            <div class="rm-metric-card">
                <div class="rm-metric-label">Total Affected</div>
                <div class="rm-metric-value">{total_affected}</div>
                <div class="rm-metric-sub">{direct_count} Direct &bull; {downstream_count} Downstream</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[2]:
        st.markdown(
            f"""
            <div class="rm-metric-card">
                <div class="rm-metric-label">Critical Services</div>
                <div class="rm-metric-value" style="color:#F59E0B;">{crit_count}</div>
                <div class="rm-metric-sub">Tier 1 &amp; Tier 2 Essential Assets</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[3]:
        st.markdown(
            f"""
            <div class="rm-metric-card">
                <div class="rm-metric-label">Max RippleScore</div>
                <div class="rm-metric-value" style="color:#38BDF8;">{top_score:.1f}</div>
                <div class="rm-metric-sub">Highest Exposure: {top_asset}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[4]:
        st.markdown(
            f"""
            <div class="rm-metric-card">
                <div class="rm-metric-label">Recommended Plan</div>
                <div class="rm-metric-value" style="font-size:1.25rem; color:#10B981;">{plan_label}</div>
                <div class="rm-metric-sub">Composite Score: {plan_score}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[5]:
        st.markdown(
            f"""
            <div class="rm-metric-card">
                <div class="rm-metric-label">Explanation Mode</div>
                <div style="margin-top:0.35rem;">{llm_badge}</div>
                <div class="rm-metric-sub" style="color:#94A3B8;">Grounded Fact Source</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_evidence_table(briefing: AgentBriefing):
    """Renders the searchable evidence and cascade findings table with deep dive inspector."""
    all_findings = briefing.direct_findings + briefing.downstream_findings
    if not all_findings:
        st.info("No affected assets found for this incident source.")
        return

    # Build dataframe for display
    rows = []
    for f in all_findings:
        alt_status = (
            f"Available ({f.alternate_supply_details[0].get('supplier_id')})"
            if f.alternate_supply_available and f.alternate_supply_details
            else "None"
        )
        bkp_status = (
            f"Ready ({f.backup_details[0].get('generator_id')})"
            if f.backup_available and f.backup_details and f.backup_details[0].get("is_ready")
            else (
                f"Degraded ({f.backup_details[0].get('generator_id')})"
                if f.backup_details
                else "None"
            )
        )
        path_summary = f.evidence_paths[0].summary if f.evidence_paths else "Direct"

        rows.append({
            "Asset ID": f.asset_id,
            "Name": f.asset_name,
            "Type": f.entity_type,
            "Criticality": f.criticality.split(" - ")[0],
            "Hops": f.direct_distance,
            "Classification": f.classification.value,
            "Alt Supply": alt_status,
            "Backup Generator": bkp_status,
            "Evidence Path": path_summary,
        })

    df = pd.DataFrame(rows)

    c1, c2 = st.columns([2, 1])
    with c1:
        search_query = st.text_input(
            "Filter assets by name or ID:",
            placeholder="e.g. HOSP-001, WaterPump, Tier 1...",
            key="asset_search",
        )
    with c2:
        class_filter = st.selectbox(
            "Filter by classification:",
            options=["ALL"] + sorted(list({r["Classification"] for r in rows})),
            key="class_filter",
        )

    filtered_df = df
    if search_query:
        q = search_query.lower()
        filtered_df = filtered_df[
            filtered_df["Asset ID"].str.lower().str.contains(q)
            | filtered_df["Name"].str.lower().str.contains(q)
            | filtered_df["Type"].str.lower().str.contains(q)
            | filtered_df["Criticality"].str.lower().str.contains(q)
        ]
    if class_filter != "ALL":
        filtered_df = filtered_df[filtered_df["Classification"] == class_filter]

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Asset ID": st.column_config.TextColumn(width="small"),
            "Hops": st.column_config.NumberColumn(width="small"),
            "Evidence Path": st.column_config.TextColumn(width="large"),
        },
    )

    # Detailed Asset Inspector
    st.markdown("#### Evidence Path Deep Dive Inspector")
    selected_asset_id = st.selectbox(
        "Select an exposed asset to inspect full verifiable evidence paths:",
        options=[f.asset_id for f in all_findings],
        format_func=lambda x: f"{x} - {next((f.asset_name for f in all_findings if f.asset_id == x), '')}",
        key="selected_asset_inspector",
    )

    target_finding = next((f for f in all_findings if f.asset_id == selected_asset_id), None)
    if target_finding:
        ic1, ic2 = st.columns([3, 2])
        with ic1:
            st.markdown(f"**Verifiable Evidence Paths for `{target_finding.asset_id}` ({len(target_finding.evidence_paths)} paths):**")
            for idx, path in enumerate(target_finding.evidence_paths, 1):
                st.markdown(
                    f"""
                    <div style="background:#1E293B; border-left:3px solid #06B6D4; padding:8px 12px; margin-bottom:8px; border-radius:4px; font-family:'JetBrains Mono', monospace; font-size:0.85rem;">
                        <strong>Path {idx} ({path.hops} hops):</strong><br>
                        <span style="color:#38BDF8;">{path.summary}</span><br>
                        <span style="color:#94A3B8; font-size:0.75rem;">Relationship sequence: {', '.join(path.relationship_types)}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        with ic2:
            st.markdown(f"**Contingency &amp; Alternate Supply Telemetry:**")
            st.markdown(f"- **Finding Classification:** `{target_finding.classification.value}`")
            st.markdown(f"- **Simulated Outcome:** {target_finding.simulated_outcome}")
            if target_finding.alternate_supply_details:
                for alt in target_finding.alternate_supply_details:
                    st.markdown(
                        f"- **Alternate Route:** `{alt.get('supplier_id')}` via `{alt.get('rel_type')}` "
                        f"(Est: {alt.get('estimated_restoration_hours')}h, Viable: {alt.get('is_viable')})"
                    )
            else:
                st.markdown("- **Alternate Route:** None identified in property graph.")

            if target_finding.backup_details:
                for bkp in target_finding.backup_details:
                    st.markdown(
                        f"- **Backup Generator:** `{bkp.get('generator_id')}` "
                        f"({bkp.get('capacity_rating')}, Buffer: {bkp.get('buffer_hours')}h, Status: {bkp.get('status')})"
                    )
            else:
                st.markdown("- **Backup Generator:** None configured.")


def render_recovery_comparison_section(briefing: AgentBriefing):
    """Renders the recovery plan comparison section."""
    plans = briefing.evaluated_plans
    if not plans:
        st.info("No recovery plans generated for this incident.")
        return

    st.markdown(
        f"**Optimizer Evaluation:** {len(plans)} recovery plans generated and compared against current graph topology."
    )

    # Side by side plan selector
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        p1_idx = st.selectbox(
            "Primary Plan:",
            range(len(plans)),
            format_func=lambda i: f"#{i+1} {plans[i].plan_id} (Score: {plans[i].composite_benefit_score:.1f})",
            index=0,
            key="p1_select",
        )
    with col_p2:
        p2_idx = st.selectbox(
            "Comparison Plan:",
            range(len(plans)),
            format_func=lambda i: f"#{i+1} {plans[i].plan_id} (Score: {plans[i].composite_benefit_score:.1f})",
            index=min(1, len(plans) - 1),
            key="p2_select",
        )

    p1, p2 = plans[p1_idx], plans[p2_idx]

    def render_plan_card(plan: RecoveryPlan, is_recommended: bool):
        rec_tag = " <span class='rm-badge rm-badge-emerald'>RECOMMENDED #1</span>" if is_recommended else ""
        st.markdown(
            f"""
            <div class="rm-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="font-weight:700; font-size:1.1rem; color:#F8FAFC;">{plan.plan_id}{rec_tag}</div>
                    <div style="font-weight:700; font-size:1.25rem; color:#06B6D4;">{plan.composite_benefit_score:.1f} pts</div>
                </div>
                <div style="color:#94A3B8; font-size:0.85rem; margin-top:4px;">{plan.plan_name}</div>
                <hr style="border-color:#334155; margin:10px 0;">
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:0.85rem;">
                    <div><strong>Restoration Time:</strong> {plan.total_estimated_hours:.1f} hours</div>
                    <div><strong>Critical Services:</strong> {plan.unique_critical_services_protected} protected</div>
                    <div><strong>Residual Affected:</strong> {plan.residual_affected_count} assets</div>
                    <div><strong>Residual Critical:</strong> {plan.residual_critical_count} assets</div>
                </div>
                <div style="margin-top:10px; font-size:0.8rem;">
                    <strong>Asset Protection Breakdown:</strong><br>
                    <span style="color:#10B981;">&#x2714; Fully Protected ({len(plan.fully_protected_asset_ids)}):</span> {', '.join(plan.fully_protected_asset_ids) or 'None'}<br>
                    <span style="color:#F59E0B;">&#x26A0; Partially Mitigated ({len(plan.partially_mitigated_asset_ids)}):</span> {', '.join(plan.partially_mitigated_asset_ids) or 'None'}<br>
                    <span style="color:#EF4444;">&#x2718; Unresolved ({len(plan.unresolved_asset_ids)}):</span> {', '.join(plan.unresolved_asset_ids) or 'None'}
                </div>
                <div style="margin-top:10px; font-size:0.8rem; color:#CBD5E1;">
                    <strong>Key Trade-offs &amp; Residual Risks:</strong>
                    <ul style="margin:4px 0 0 18px; padding:0;">
                        {''.join([f"<li>{t}</li>" for t in plan.tradeoffs_and_risks[:3]])}
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        render_plan_card(p1, is_recommended=(briefing.recommended_plan and p1.plan_id == briefing.recommended_plan.plan_id))
    with c2:
        render_plan_card(p2, is_recommended=(briefing.recommended_plan and p2.plan_id == briefing.recommended_plan.plan_id))


def render_incident_memory_section(briefing: AgentBriefing):
    """Renders historical incident matches from FalkorDB incident memory."""
    incidents = briefing.historical_incidents
    if not incidents:
        st.info("No prior incident memory records found involving this component.")
        return

    st.markdown(
        f"**Incident Provenance:** {len(incidents)} relevant historical incident records retrieved from FalkorDB graph memory."
    )

    for inc in incidents:
        sim_tag = (
            "<span class='rm-badge rm-badge-amber'>SIMULATED INCIDENT</span>"
            if inc.simulated
            else "<span class='rm-badge rm-badge-emerald'>HISTORICAL EVENT</span>"
        )
        st.markdown(
            f"""
            <div class="rm-card" style="margin-bottom:8px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="font-weight:600; color:#F8FAFC;">
                        {inc.title} <span style="font-size:0.8rem; color:#94A3B8;">({inc.incident_id})</span>
                    </div>
                    <div>{sim_tag}</div>
                </div>
                <div style="font-size:0.85rem; color:#CBD5E1; margin-top:6px;">
                    <strong>Relevance:</strong> {inc.relevance_reason} &bull; <strong>Severity:</strong> {inc.severity}
                </div>
                <div style="font-size:0.85rem; color:#94A3B8; margin-top:4px;">
                    <strong>Action Taken:</strong> {inc.recovery_action_name or 'None recorded'} &bull; 
                    <strong>Outcome:</strong> <span style="color:#38BDF8;">{inc.outcome_type.value}</span>
                </div>
                <div style="font-size:0.8rem; color:#64748B; margin-top:4px;">
                    Path Evidence: {inc.evidence_path_summary or 'Direct graph association'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_groq_panel(briefing: AgentBriefing):
    """Renders the optional Groq natural-language explanation and grounded inquiry panel."""
    st.markdown("#### Groq AI Executive Narrative & Grounded Inquiry")

    # Display LLM narrative if available
    if briefing.llm_narrative:
        st.markdown(
            f"""
            <div style="background:rgba(6, 182, 212, 0.06); border:1px solid rgba(6, 182, 212, 0.25); border-radius:8px; padding:16px; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <strong style="color:#06B6D4;">Executive Synthesis (Grounded in FalkorDB Graph Evidence)</strong>
                    <span class="rm-badge rm-badge-emerald">Live Groq {briefing.llm_explanation_status}</span>
                </div>
                <div style="color:#E2E8F0; font-size:0.92rem; line-height:1.6;">
                    {briefing.llm_narrative.replace(chr(10), '<br>')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif briefing.llm_explanation_status == "FALLBACK_DETERMINISTIC":
        st.warning(
            "Groq LLM explanation unavailable (rate limit, model availability check, or network timeout). "
            "Falling back cleanly to deterministic graph engine findings."
        )
    else:
        st.info("LLM explanation is disabled or no GROQ_API_KEY configured. Running 100% deterministically.")
