"""Plotly analytical charts for RippleScore explanations and recovery plan comparison."""

from typing import Optional
import plotly.graph_objects as go
from app.schema import ScoreBreakdown, RecoveryPlan


def render_ripple_score_chart(scores: list[ScoreBreakdown], max_items: int = 9) -> go.Figure:
    """Renders a Plotly stacked bar chart displaying the canonical component breakdown
    of RippleScores across exposed assets.
    """
    if not scores:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#162032",
            plot_bgcolor="#162032",
            annotations=[
                dict(
                    text="No RippleScore data available.",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    font=dict(color="#94A3B8", size=13),
                )
            ],
            height=320,
        )
        return fig

    # Top N scores ordered descending (reverse for horizontal bar chart)
    items = list(reversed(scores[:max_items]))

    labels = [f"<b>{s.asset_id}</b> ({s.asset_name[:18]})" for s in items]
    inherent = [s.inherent_score for s in items]
    downstream = [s.downstream_impact_score for s in items]
    multipath = [s.multipath_vulnerability_score for s in items]
    spof = [s.spof_penalty for s in items]
    penalties = [s.capacity_penalty + s.failed_contingency_penalty for s in items]
    # Credits are negative or subtractions
    mitigation_credits = [-s.mitigation_credit for s in items]
    backup_credits = [-s.backup_credit for s in items]
    totals = [s.total_score for s in items]

    fig = go.Figure()

    # Stack positive risk drivers
    fig.add_trace(go.Bar(
        y=labels, x=inherent, name="Base Criticality",
        orientation="h", marker=dict(color="#38BDF8"),
        hoverinfo="y+x+name"
    ))
    fig.add_trace(go.Bar(
        y=labels, x=downstream, name="Downstream Cascades",
        orientation="h", marker=dict(color="#0284C7"),
        hoverinfo="y+x+name"
    ))
    fig.add_trace(go.Bar(
        y=labels, x=multipath, name="Multipath Exposure",
        orientation="h", marker=dict(color="#F59E0B"),
        hoverinfo="y+x+name"
    ))
    fig.add_trace(go.Bar(
        y=labels, x=spof, name="SPOF Penalty",
        orientation="h", marker=dict(color="#EF4444"),
        hoverinfo="y+x+name"
    ))
    fig.add_trace(go.Bar(
        y=labels, x=penalties, name="Capacity / Failed Backup Penalty",
        orientation="h", marker=dict(color="#DC2626"),
        hoverinfo="y+x+name"
    ))

    # Credits (displayed to left / negative offset or credited deductions)
    fig.add_trace(go.Bar(
        y=labels, x=mitigation_credits, name="Alternate Route Credit (-)",
        orientation="h", marker=dict(color="#10B981"),
        hoverinfo="y+x+name"
    ))
    fig.add_trace(go.Bar(
        y=labels, x=backup_credits, name="Backup Generator Credit (-)",
        orientation="h", marker=dict(color="#8B5CF6"),
        hoverinfo="y+x+name"
    ))

    # Add total score marker overlay
    fig.add_trace(go.Scatter(
        y=labels, x=totals, name="Final RippleScore",
        mode="markers+text",
        marker=dict(color="#F8FAFC", size=10, symbol="diamond", line=dict(color="#06B6D4", width=2)),
        text=[f" {t:.1f}" for t in totals],
        textposition="middle right",
        textfont=dict(color="#F8FAFC", size=11, family="JetBrains Mono"),
        hoverinfo="y+x+name"
    ))

    fig.update_layout(
        barmode="relative",
        template="plotly_dark",
        paper_bgcolor="#162032",
        plot_bgcolor="#162032",
        margin=dict(l=10, r=40, t=30, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=10, color="#CBD5E1"),
        ),
        xaxis=dict(
            title="Score Contributions (0 - 100)",
            gridcolor="#334155",
            zerolinecolor="#64748B",
            zerolinewidth=1.5,
        ),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(color="#E2E8F0", size=11),
        ),
        height=380,
    )

    return fig


def render_recovery_comparison_chart(plans: list[RecoveryPlan]) -> go.Figure:
    """Renders a Plotly comparison chart contrasting composite benefit score
    against restoration time for candidate recovery plans.
    """
    if not plans:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#162032",
            plot_bgcolor="#162032",
            annotations=[
                dict(
                    text="No recovery plans generated.",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    font=dict(color="#94A3B8", size=13),
                )
            ],
            height=300,
        )
        return fig

    plan_names = [f"#{i+1} {p.plan_id}" for i, p in enumerate(plans)]
    benefit_scores = [p.composite_benefit_score for p in plans]
    hours = [p.total_estimated_hours for p in plans]
    protected_counts = [p.unique_critical_services_protected for p in plans]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=plan_names,
        y=benefit_scores,
        name="Composite Benefit Score",
        marker=dict(color="#06B6D4"),
        text=[f"{s:.1f} pts" for s in benefit_scores],
        textposition="outside",
        yaxis="y",
    ))

    fig.add_trace(go.Scatter(
        x=plan_names,
        y=hours,
        name="Estimated Hours to Restore",
        mode="lines+markers+text",
        line=dict(color="#F59E0B", width=2.5),
        marker=dict(size=8, color="#F59E0B"),
        text=[f"{h:.1f}h" for h in hours],
        textposition="top center",
        yaxis="y2",
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#162032",
        plot_bgcolor="#162032",
        margin=dict(l=40, r=40, t=30, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#CBD5E1"),
        ),
        xaxis=dict(showgrid=False),
        yaxis=dict(
            title=dict(text="Benefit Score", font=dict(color="#06B6D4")),
            tickfont=dict(color="#06B6D4"),
            gridcolor="#334155",
        ),
        yaxis2=dict(
            title=dict(text="Restoration Window (Hours)", font=dict(color="#F59E0B")),
            tickfont=dict(color="#F59E0B"),
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        height=320,
    )

    return fig
