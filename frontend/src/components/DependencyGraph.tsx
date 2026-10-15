import React, { useMemo, useState } from 'react';
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  Handle,
  Position,
  MarkerType,
  Node,
  Edge,
  NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Zap,
  Droplet,
  Building2,
  Radio,
  Navigation,
  Shield,
  Stethoscope,
  BatteryCharging,
  Info,
  X,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react';
import { AgentBriefing, AffectedAssetFinding } from '../types';

// Helper icon selector based on entity type
function getEntityIcon(type: string) {
  switch (type.toLowerCase()) {
    case 'substation':
      return Zap;
    case 'waterpump':
      return Droplet;
    case 'hospital':
      return Building2;
    case 'mobiletower':
    case 'celltower':
      return Radio;
    case 'road':
      return Navigation;
    case 'emergencycenter':
      return Shield;
    case 'clinic':
      return Stethoscope;
    case 'backupgenerator':
      return BatteryCharging;
    default:
      return Info;
  }
}

interface CustomNodeData extends Record<string, unknown> {
  id: string;
  name: string;
  entityType: string;
  criticality: string;
  status: string;
  role: 'source' | 'direct' | 'downstream' | 'alternate' | 'backup';
  finding?: AffectedAssetFinding;
  capacityRating?: string;
  bufferHours?: number;
}

// Custom Node Component
const CustomAssetNode: React.FC<NodeProps> = (props) => {
  const data = props.data as unknown as CustomNodeData;
  const Icon = getEntityIcon(data.entityType || '');
  const isSource = data.role === 'source';
  const isDirect = data.role === 'direct';
  const isDownstream = data.role === 'downstream';
  const isAlternate = data.role === 'alternate';
  const isBackup = data.role === 'backup';

  let borderStyle = 'border-slate-700 hover:border-slate-500';
  let badgeBg = 'bg-slate-800 text-slate-300';
  let roleLabel = 'Asset';

  if (isSource) {
    borderStyle = 'border-rose-500 bg-rose-950/30 animate-pulse-glow';
    badgeBg = 'bg-rose-500/20 text-rose-300 border border-rose-500/40';
    roleLabel = 'ROOT FAILURE';
  } else if (isDirect) {
    borderStyle = 'border-amber-500/80 bg-surface-elevated';
    badgeBg = 'bg-amber-500/15 text-amber-300 border border-amber-500/30';
    roleLabel = 'DIRECT (1 HOP)';
  } else if (isDownstream) {
    borderStyle = 'border-cyan-500/80 bg-surface-elevated';
    badgeBg = 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30';
    roleLabel = 'DOWNSTREAM';
  } else if (isAlternate) {
    borderStyle = 'border-emerald-500/80 bg-surface-elevated';
    badgeBg = 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30';
    roleLabel = 'ALTERNATE FEED';
  } else if (isBackup) {
    borderStyle = 'border-purple-500/80 bg-surface-elevated';
    badgeBg = 'bg-purple-500/15 text-purple-300 border border-purple-500/30';
    roleLabel = 'BACKUP GEN';
  }

  return (
    <div
      className={`min-w-[210px] max-w-[240px] rounded-xl border p-3 shadow-lg transition-all duration-200 cursor-pointer ${borderStyle}`}
    >
      <Handle type="target" position={Position.Left} id="left-target" className="w-2.5 h-2.5 bg-primary border-2 border-background" />
      <Handle type="source" position={Position.Right} id="right-source" className="w-2.5 h-2.5 bg-primary border-2 border-background" />
      <Handle type="target" position={Position.Top} id="top-target" className="w-2.5 h-2.5 bg-emerald-400 border-2 border-background" />
      <Handle type="source" position={Position.Bottom} id="bottom-source" className="w-2.5 h-2.5 bg-purple-400 border-2 border-background" />

      <div className="flex items-center justify-between gap-1 mb-2">
        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${badgeBg}`}>
          {roleLabel}
        </span>
        <span className="text-[10px] font-mono text-slate-400">{String(data.status || '')}</span>
      </div>

      <div className="flex items-start gap-2.5">
        <div className="p-2 rounded-lg bg-surface border border-border/80 shrink-0">
          <Icon className="h-4 w-4 text-primary-light" />
        </div>
        <div className="overflow-hidden">
          <div className="text-xs font-bold font-mono text-white truncate">{String(data.id || '')}</div>
          <div className="text-[11px] text-slate-300 truncate" title={String(data.name || '')}>
            {String(data.name || '')}
          </div>
        </div>
      </div>

      <div className="mt-2.5 pt-2 border-t border-border/60 flex items-center justify-between text-[10px] text-slate-400">
        <span>{String(data.entityType || '')}</span>
        <span className="font-medium text-slate-300">{String(data.criticality || '').split(' - ')[0]}</span>
      </div>
    </div>
  );
};

const nodeTypes = {
  assetNode: CustomAssetNode,
};

interface DependencyGraphProps {
  briefing: AgentBriefing | null;
  onSelectAsset?: (assetId: string) => void;
}

export const DependencyGraph: React.FC<DependencyGraphProps> = ({ briefing, onSelectAsset }) => {
  const [selectedNodeData, setSelectedNodeData] = useState<any | null>(null);

  // Construct React Flow Nodes and Edges from actual backend findings
  const { nodes, edges } = useMemo(() => {
    if (!briefing || !briefing.source_node_id) {
      return { nodes: [], edges: [] };
    }

    const nList: Node[] = [];
    const eList: Edge[] = [];
    const seenEdges = new Set<string>();

    // 1. Source Node (x=60, y=350)
    nList.push({
      id: briefing.source_node_id,
      type: 'assetNode',
      position: { x: 60, y: 350 },
      data: {
        id: briefing.source_node_id,
        name: briefing.source_node_name,
        entityType: briefing.source_entity_type,
        criticality: briefing.source_criticality,
        status: `${briefing.source_status} (SIMULATED ROOT)`,
        role: 'source',
      },
    });

    // 2. Direct Findings (Layer 1: x=500)
    const direct = briefing.direct_findings;
    const directCount = direct.length;
    direct.forEach((f, idx) => {
      const y = directCount > 1 ? 50 + idx * 135 : 350;
      nList.push({
        id: f.asset_id,
        type: 'assetNode',
        position: { x: 500, y },
        data: {
          id: f.asset_id,
          name: f.asset_name,
          entityType: f.entity_type,
          criticality: f.criticality,
          status: f.status,
          role: 'direct',
          finding: f,
        },
      });
    });

    // 3. Downstream Findings (Layer 2: x=960)
    const downstream = briefing.downstream_findings;
    const downstreamCount = downstream.length;
    downstream.forEach((f, idx) => {
      const y = downstreamCount > 1 ? 180 + idx * 220 : 350;
      nList.push({
        id: f.asset_id,
        type: 'assetNode',
        position: { x: 960, y },
        data: {
          id: f.asset_id,
          name: f.asset_name,
          entityType: f.entity_type,
          criticality: f.criticality,
          status: f.status,
          role: 'downstream',
          finding: f,
        },
      });
    });

    // 4. Alternate Suppliers and Backup Generators
    const allFindings = direct.concat(downstream);
    const addedNodeIds = new Set(nList.map((n) => n.id));

    let altIndex = 0;
    let bkpIndex = 0;

    allFindings.forEach((f) => {
      // Alternate routes
      f.alternate_supply_details.forEach((alt) => {
        if (!addedNodeIds.has(alt.supplier_id)) {
          addedNodeIds.add(alt.supplier_id);
          nList.push({
            id: alt.supplier_id,
            type: 'assetNode',
            position: { x: 440 + altIndex * 280, y: -160 },
            data: {
              id: alt.supplier_id,
              name: alt.supplier_name,
              entityType: alt.supplier_type,
              criticality: 'Auxiliary Redundant Supply',
              status: alt.supplier_status,
              role: 'alternate',
            },
          });
          altIndex++;
        }

        const edgeKey = `alt-${alt.supplier_id}->${f.asset_id}`;
        if (!seenEdges.has(edgeKey)) {
          seenEdges.add(edgeKey);
          eList.push({
            id: edgeKey,
            source: alt.supplier_id,
            target: f.asset_id,
            sourceHandle: 'bottom-source',
            targetHandle: 'top-target',
            type: 'smoothstep',
            animated: true,
            label: `${alt.rel_type} (Alt)`,
            style: { stroke: '#10B981', strokeWidth: 2, strokeDasharray: '5,5' },
            labelStyle: { fill: '#34D399', fontSize: 10, fontFamily: 'monospace', fontWeight: 600 },
            labelBgStyle: { fill: '#0F172A', fillOpacity: 0.95, stroke: '#10B981', strokeWidth: 1, rx: 4, ry: 4 },
            labelBgPadding: [6, 3],
            markerEnd: { type: MarkerType.ArrowClosed, color: '#10B981' },
          });
        }
      });

      // Backup generators
      f.backup_details.forEach((bkp) => {
        if (!addedNodeIds.has(bkp.generator_id)) {
          addedNodeIds.add(bkp.generator_id);
          nList.push({
            id: bkp.generator_id,
            type: 'assetNode',
            position: { x: 440 + bkpIndex * 280, y: 920 },
            data: {
              id: bkp.generator_id,
              name: bkp.generator_name,
              entityType: 'BackupGenerator',
              criticality: 'Onsite Contingency',
              status: bkp.status,
              role: 'backup',
              capacityRating: bkp.capacity_rating,
              bufferHours: bkp.buffer_hours,
            },
          });
          bkpIndex++;
        }

        const edgeKey = `bkp-${f.asset_id}->${bkp.generator_id}`;
        if (!seenEdges.has(edgeKey)) {
          seenEdges.add(edgeKey);
          eList.push({
            id: edgeKey,
            source: f.asset_id,
            target: bkp.generator_id,
            sourceHandle: 'bottom-source',
            targetHandle: 'top-target',
            type: 'smoothstep',
            animated: false,
            label: 'HAS_BACKUP',
            style: { stroke: '#8B5CF6', strokeWidth: 1.8, strokeDasharray: '3,3' },
            labelStyle: { fill: '#A78BFA', fontSize: 10, fontFamily: 'monospace', fontWeight: 600 },
            labelBgStyle: { fill: '#0F172A', fillOpacity: 0.95, stroke: '#8B5CF6', strokeWidth: 1, rx: 4, ry: 4 },
            labelBgPadding: [6, 3],
            markerEnd: { type: MarkerType.ArrowClosed, color: '#8B5CF6' },
          });
        }
      });
    });

    // 5. Cascade Edges from verified EvidencePaths
    briefing.evidence_paths.forEach((p) => {
      for (let i = 0; i < p.node_ids.length - 1; i++) {
        const u = p.node_ids[i];
        const v = p.node_ids[i + 1];
        const rtype = p.relationship_types[i] || 'SUPPLIES';
        const edgeKey = `cascade-${u}->${v}`;

        if (!seenEdges.has(edgeKey) && addedNodeIds.has(u) && addedNodeIds.has(v)) {
          seenEdges.add(edgeKey);
          const isDirectFromSource = u === briefing.source_node_id;
          eList.push({
            id: edgeKey,
            source: u,
            target: v,
            sourceHandle: 'right-source',
            targetHandle: 'left-target',
            type: 'smoothstep',
            animated: true,
            label: rtype,
            style: {
              stroke: isDirectFromSource ? '#EF4444' : '#06B6D4',
              strokeWidth: 2.2,
            },
            labelStyle: {
              fill: isDirectFromSource ? '#FCA5A5' : '#7DD3FC',
              fontSize: 10,
              fontFamily: 'monospace',
              fontWeight: 600,
            },
            labelBgStyle: {
              fill: '#0F172A',
              fillOpacity: 0.95,
              stroke: isDirectFromSource ? '#EF4444' : '#06B6D4',
              strokeWidth: 1,
              rx: 4,
              ry: 4,
            },
            labelBgPadding: [6, 3],
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: isDirectFromSource ? '#EF4444' : '#06B6D4',
            },
          });
        }
      }
    });

    return { nodes: nList, edges: eList };
  }, [briefing]);

  const onNodeClick = (_: React.MouseEvent, node: Node) => {
    setSelectedNodeData(node.data);
    if (onSelectAsset && node.data?.id) {
      onSelectAsset(node.data.id as string);
    }
  };

  return (
    <div className="relative w-full h-[580px] bg-background border border-border rounded-xl overflow-hidden shadow-inner">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.2}
        maxZoom={1.5}
      >
        <Controls className="!bg-surface-elevated/90 !border !border-border !rounded-lg overflow-hidden shadow-lg !text-white" />
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#334155" />
      </ReactFlow>

      {/* Floating Legend */}
      <div className="absolute bottom-4 left-4 bg-surface/90 backdrop-blur-md border border-border rounded-lg p-3 text-xs shadow-lg max-w-sm">
        <div className="font-semibold text-slate-200 mb-2 flex items-center gap-1.5">
          <Info className="h-3.5 w-3.5 text-primary" />
          <span>Dependency Graph Legend</span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
            <span>Simulated Root Failure</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
            <span>Direct Dependency (1 Hop)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-500"></span>
            <span>Downstream Cascade (2+ Hops)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
            <span>Alternate Supply Route</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
            <span>Backup Generator</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-0.5 bg-cyan-400"></span>
            <span>Physical Cascade Edge</span>
          </div>
        </div>
      </div>

      {/* Node Detail Drawer / Popover */}
      {selectedNodeData && (
        <div className="absolute top-4 right-4 w-96 max-h-[520px] overflow-y-auto bg-surface/95 backdrop-blur-md border border-primary/40 rounded-xl p-4 shadow-2xl z-20">
          <div className="flex items-center justify-between pb-3 border-b border-border">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-primary-light">
                {selectedNodeData.role}
              </span>
              <h3 className="text-sm font-bold text-white font-mono">{selectedNodeData.id}</h3>
            </div>
            <button
              onClick={() => setSelectedNodeData(null)}
              className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-surface-elevated transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-3 space-y-3 text-xs text-slate-300">
            <div>
              <span className="text-slate-400">Name:</span> <strong>{selectedNodeData.name}</strong>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-slate-400">Type:</span> <div>{selectedNodeData.entityType}</div>
              </div>
              <div>
                <span className="text-slate-400">Status:</span>{' '}
                <div className="text-emerald-400 font-semibold">{selectedNodeData.status}</div>
              </div>
            </div>

            {selectedNodeData.finding && (
              <>
                <div className="pt-2 border-t border-border/80">
                  <span className="text-slate-400">Finding Classification:</span>
                  <div className="font-mono text-cyan-300 font-semibold mt-0.5">
                    {selectedNodeData.finding.classification}
                  </div>
                </div>

                <div>
                  <span className="text-slate-400">Simulated Outcome:</span>
                  <div className="text-slate-200 mt-0.5">{selectedNodeData.finding.simulated_outcome}</div>
                </div>

                {selectedNodeData.finding.evidence_paths?.length > 0 && (
                  <div className="pt-2 border-t border-border/80">
                    <span className="text-slate-400 font-semibold">
                      Verifiable Evidence Paths ({selectedNodeData.finding.evidence_paths.length}):
                    </span>
                    <div className="mt-1.5 space-y-1.5 max-h-36 overflow-y-auto font-mono text-[11px]">
                      {selectedNodeData.finding.evidence_paths.map((p: any, i: number) => (
                        <div key={i} className="p-2 rounded bg-surface-elevated border border-border text-slate-300">
                          <div className="text-primary-light font-bold">Path {i + 1} ({p.hops} hops)</div>
                          <div className="text-slate-400">{p.summary}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {selectedNodeData.capacityRating && (
              <div className="pt-2 border-t border-border/80">
                <span className="text-slate-400">Backup Rating:</span>
                <div>{selectedNodeData.capacityRating}</div>
                <div className="text-slate-400 mt-1">
                  Buffer Runway: <strong>{selectedNodeData.bufferHours} hours</strong>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
