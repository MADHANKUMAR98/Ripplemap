"""Plotly interactive dependency graph visualization for RippleMap."""

import math
from typing import Any, Optional
import plotly.graph_objects as go
from app.schema import AgentBriefing, AffectedAssetFinding


def build_cascade_graph(briefing: AgentBriefing) -> go.Figure:
    """Builds a responsive, interactive Plotly dependency graph representing
    the investigated incident cascade, alternate routes, and backup generators.
    """
    if not briefing or not briefing.source_node_id:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#162032",
            plot_bgcolor="#162032",
            annotations=[
                dict(
                    text="No incident investigation active.<br>Select a source asset above to trace cascading dependencies.",
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    font=dict(color="#94A3B8", size=14),
                )
            ],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=420,
        )
        return fig

    # 1. Collect all nodes and their role/metadata
    nodes: dict[str, dict[str, Any]] = {}

    # Source node
    nodes[briefing.source_node_id] = {
        "id": briefing.source_node_id,
        "name": briefing.source_node_name,
        "type": briefing.source_entity_type,
        "criticality": briefing.source_criticality,
        "status": f"{briefing.source_status} (SIMULATED ROOT FAILURE)",
        "role": "Source (Root Incident)",
        "layer": 0,
        "classification": "INCIDENT_SOURCE",
        "details": "Simulated primary failure point initiating cascading dependency exposures.",
    }

    # Direct findings (Layer 1)
    for f in briefing.direct_findings:
        nodes[f.asset_id] = {
            "id": f.asset_id,
            "name": f.asset_name,
            "type": f.entity_type,
            "criticality": f.criticality,
            "status": f.status,
            "role": "Direct Dependency (1 Hop)",
            "layer": 1,
            "classification": f.classification.value,
            "details": f"Directly supplied by source. Alt Supply: {'Yes' if f.alternate_supply_available else 'None'} | Backup: {'Yes' if f.backup_available else 'None'}",
        }

    # Downstream findings (Layer 2)
    for f in briefing.downstream_findings:
        nodes[f.asset_id] = {
            "id": f.asset_id,
            "name": f.asset_name,
            "type": f.entity_type,
            "criticality": f.criticality,
            "status": f.status,
            "role": "Downstream Cascade (2+ Hops)",
            "layer": 2,
            "classification": f.classification.value,
            "details": f"Multi-hop propagation. Alt Supply: {'Yes' if f.alternate_supply_available else 'None'} | Backup: {'Yes' if f.backup_available else 'None'}",
        }

    # Alternate suppliers and Backup generators
    all_findings = briefing.direct_findings + briefing.downstream_findings
    for f in all_findings:
        for alt in f.alternate_supply_details:
            supplier_id = alt.get("supplier_id")
            if supplier_id and supplier_id not in nodes:
                nodes[supplier_id] = {
                    "id": supplier_id,
                    "name": alt.get("supplier_name", supplier_id),
                    "type": alt.get("supplier_type", "AlternateSupplier"),
                    "criticality": "External Auxiliary Feed",
                    "status": alt.get("supplier_status", "OPERATIONAL"),
                    "role": "Alternate Route Supplier",
                    "layer": -1,  # Positioned top
                    "classification": "ALTERNATE_ROUTE_SUPPLIER",
                    "details": f"Viable alternate route restoring {f.asset_id} in {alt.get('estimated_restoration_hours', 1.0)}h",
                }
        for bkp in f.backup_details:
            gen_id = bkp.get("generator_id")
            if gen_id and gen_id not in nodes:
                nodes[gen_id] = {
                    "id": gen_id,
                    "name": bkp.get("generator_name", gen_id),
                    "type": "BackupGenerator",
                    "criticality": "Contingency Power",
                    "status": bkp.get("status", "OPERATIONAL"),
                    "role": "Backup Generator",
                    "layer": -2,  # Positioned bottom
                    "classification": "BACKUP_GENERATOR",
                    "details": f"Capacity: {bkp.get('capacity_rating', 'Unknown')} | Runway: {bkp.get('buffer_hours', 0.0)}h | Ready: {bkp.get('is_ready', False)}",
                }

    # 2. Position nodes by layer
    # Layer 0: x=0
    # Layer 1: x=2.5
    # Layer 2: x=5.0
    # Alternate suppliers (Layer -1): distributed across top (y > 2.5)
    # Backup generators (Layer -2): distributed across bottom (y < -2.5)
    layer_groups: dict[int, list[str]] = {0: [], 1: [], 2: [], -1: [], -2: []}
    for nid, data in nodes.items():
        layer_groups[data["layer"]].append(nid)

    pos: dict[str, tuple[float, float]] = {}

    # Source
    pos[briefing.source_node_id] = (0.0, 0.0)

    # Layer 1
    l1 = layer_groups[1]
    n1 = len(l1)
    for i, nid in enumerate(l1):
        y = (i - (n1 - 1) / 2.0) * 1.5 if n1 > 1 else 0.0
        pos[nid] = (2.6, y)

    # Layer 2
    l2 = layer_groups[2]
    n2 = len(l2)
    for i, nid in enumerate(l2):
        y = (i - (n2 - 1) / 2.0) * 2.2 if n2 > 1 else 0.0
        pos[nid] = (5.2, y)

    # Alternate suppliers (Top)
    l_alt = layer_groups[-1]
    n_alt = len(l_alt)
    for i, nid in enumerate(l_alt):
        x = 1.8 + (i * 1.6)
        pos[nid] = (x, 3.2)

    # Backup generators (Bottom)
    l_bkp = layer_groups[-2]
    n_bkp = len(l_bkp)
    for i, nid in enumerate(l_bkp):
        x = 2.0 + (i * 1.5)
        pos[nid] = (x, -3.2)

    # 3. Construct Edges
    # Edge types: cascade (primary), alternate (dashed green), backup (dotted purple)
    cascade_edges: list[tuple[str, str, str]] = []
    alternate_edges: list[tuple[str, str, str]] = []
    backup_edges: list[tuple[str, str, str]] = []

    seen_cascade = set()
    for p in briefing.evidence_paths:
        for i in range(len(p.node_ids) - 1):
            u, v = p.node_ids[i], p.node_ids[i + 1]
            rtype = p.relationship_types[i] if i < len(p.relationship_types) else "SUPPLIES"
            if (u, v) not in seen_cascade and u in pos and v in pos:
                cascade_edges.append((u, v, rtype))
                seen_cascade.add((u, v))

    for f in all_findings:
        for alt in f.alternate_supply_details:
            sup = alt.get("supplier_id")
            if sup and sup in pos and f.asset_id in pos:
                alternate_edges.append((sup, f.asset_id, alt.get("rel_type", "ALTERNATE_ROUTE")))
        for bkp in f.backup_details:
            gen = bkp.get("generator_id")
            if gen and gen in pos and f.asset_id in pos:
                backup_edges.append((f.asset_id, gen, "HAS_BACKUP"))

    # 4. Build Plotly Trace Elements
    fig = go.Figure()

    # Edge traces
    def add_edge_trace(edges, color, dash, name, width=1.5):
        if not edges:
            return
        edge_x, edge_y = [], []
        mid_x, mid_y, mid_text = [], [], []
        for u, v, rtype in edges:
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            mid_x.append((x0 + x1) / 2.0)
            mid_y.append((y0 + y1) / 2.0)
            mid_text.append(f"{u} &rarr; {v}<br>Type: <b>{rtype}</b>")

        fig.add_trace(
            go.Scatter(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line=dict(color=color, width=width, dash=dash),
                hoverinfo="none",
                showlegend=False,
            )
        )
        # Midpoint hover markers
        fig.add_trace(
            go.Scatter(
                x=mid_x,
                y=mid_y,
                mode="markers",
                marker=dict(size=6, color=color, opacity=0.0),
                hoverinfo="text",
                hovertext=mid_text,
                name=name,
                showlegend=False,
            )
        )

    add_edge_trace(cascade_edges, "#06B6D4", "solid", "Cascade Dependency Path", width=2.2)
    add_edge_trace(alternate_edges, "#10B981", "dash", "Alternate Supply Route", width=1.8)
    add_edge_trace(backup_edges, "#8B5CF6", "dot", "Backup Generator Link", width=1.8)

    # Add Directional Arrows
    annotations = []
    for u, v, _ in cascade_edges:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        # Calculate midpoint slightly offset toward destination
        annotations.append(
            dict(
                ax=x0,
                ay=y0,
                x=x0 + (x1 - x0) * 0.65,
                y=y0 + (y1 - y0) * 0.65,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.2,
                arrowwidth=1.5,
                arrowcolor="rgba(6, 182, 212, 0.7)",
            )
        )
    for u, v, _ in alternate_edges:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        annotations.append(
            dict(
                ax=x0,
                ay=y0,
                x=x0 + (x1 - x0) * 0.65,
                y=y0 + (y1 - y0) * 0.65,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.2,
                arrowwidth=1.5,
                arrowcolor="rgba(16, 185, 129, 0.7)",
            )
        )

    # 5. Node Traces grouped by category for clean legend
    role_configs = [
        ("Source (Root Incident)", "INCIDENT_SOURCE", "#EF4444", "hexagon", 26),
        ("Direct Dependency (1 Hop)", "DIRECT", "#F59E0B", "circle", 20),
        ("Downstream Cascade (2+ Hops)", "DOWNSTREAM", "#06B6D4", "circle", 20),
        ("Alternate Route Supplier", "ALTERNATE", "#10B981", "diamond", 18),
        ("Backup Generator", "BACKUP", "#8B5CF6", "square", 18),
    ]

    for role_name, key, color, symbol, size in role_configs:
        matching_nodes = [n for n in nodes.values() if (
            (key == "INCIDENT_SOURCE" and n["role"] == "Source (Root Incident)")
            or (key == "DIRECT" and n["role"] == "Direct Dependency (1 Hop)")
            or (key == "DOWNSTREAM" and n["role"] == "Downstream Cascade (2+ Hops)")
            or (key == "ALTERNATE" and n["role"] == "Alternate Route Supplier")
            or (key == "BACKUP" and n["role"] == "Backup Generator")
        )]

        if not matching_nodes:
            continue

        nx = [pos[n["id"]][0] for n in matching_nodes]
        ny = [pos[n["id"]][1] for n in matching_nodes]
        hover_texts = []
        node_labels = []

        for n in matching_nodes:
            node_labels.append(n["id"])
            hover_html = (
                f"<b>{n['name']}</b> ({n['id']})<br>"
                f"Role: <b>{n['role']}</b><br>"
                f"Type: {n['type']} | Criticality: {n['criticality']}<br>"
                f"Operational Status: <i>{n['status']}</i><br>"
                f"Classification: <b>{n['classification']}</b><br>"
                f"Details: {n['details']}"
            )
            hover_texts.append(hover_html)

        fig.add_trace(
            go.Scatter(
                x=nx,
                y=ny,
                mode="markers+text",
                name=role_name,
                marker=dict(
                    symbol=symbol,
                    size=size,
                    color=color,
                    line=dict(color="#FFFFFF", width=1.5),
                ),
                text=node_labels,
                textposition="top center",
                textfont=dict(color="#F8FAFC", size=10, family="JetBrains Mono"),
                hoverinfo="text",
                hovertext=hover_texts,
            )
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#162032",
        plot_bgcolor="#162032",
        margin=dict(l=40, r=40, t=30, b=30),
        hovermode="closest",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#E2E8F0"),
            bgcolor="rgba(15, 23, 42, 0.8)",
            bordercolor="#334155",
            borderwidth=1,
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.8, 6.0]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-4.2, 4.2]),
        annotations=annotations,
        height=540,
    )

    return fig
