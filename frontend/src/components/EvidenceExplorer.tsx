import React, { useState } from 'react';
import { Search, Filter, ShieldCheck, AlertTriangle, ArrowRight, Layers, FileText } from 'lucide-react';
import { AffectedAssetFinding, AgentBriefing } from '../types';

interface EvidenceExplorerProps {
  briefing: AgentBriefing | null;
  selectedAssetId?: string;
  onSelectAsset?: (id: string) => void;
}

export const EvidenceExplorer: React.FC<EvidenceExplorerProps> = ({
  briefing,
  selectedAssetId,
  onSelectAsset,
}) => {
  const [search, setSearch] = useState('');
  const [filterClass, setFilterClass] = useState('ALL');

  if (!briefing) {
    return <div className="text-slate-500 text-sm py-8 text-center">No active investigation findings.</div>;
  }

  const allFindings = briefing.direct_findings.concat(briefing.downstream_findings);
  const activeSelected = selectedAssetId
    ? allFindings.find((f) => f.asset_id === selectedAssetId) || allFindings[0]
    : allFindings[0];

  // Distinct classifications
  const classifications = Array.from(new Set(allFindings.map((f) => f.classification)));

  // Filter
  const filtered = allFindings.filter((f) => {
    const q = search.toLowerCase();
    const matchesSearch =
      f.asset_id.toLowerCase().includes(q) ||
      f.asset_name.toLowerCase().includes(q) ||
      f.entity_type.toLowerCase().includes(q) ||
      f.criticality.toLowerCase().includes(q);
    const matchesClass = filterClass === 'ALL' || f.classification === filterClass;
    return matchesSearch && matchesClass;
  });

  return (
    <div className="space-y-4">
      {/* Search & Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-surface p-3 rounded-xl border border-border">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search affected assets by ID, name, or facility type..."
            className="w-full bg-surface-elevated border border-border rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-primary"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400 shrink-0" />
          <select
            value={filterClass}
            onChange={(e) => setFilterClass(e.target.value)}
            className="bg-surface-elevated border border-border rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-primary"
          >
            <option value="ALL">All Classifications ({allFindings.length})</option>
            {classifications.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Table View (2 Cols) */}
        <div className="lg:col-span-2 bg-surface rounded-xl border border-border overflow-hidden">
          <div className="max-h-[500px] overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-elevated text-slate-400 uppercase tracking-wider font-semibold border-b border-border sticky top-0 z-10">
                <tr>
                  <th className="px-3.5 py-2.5">Asset</th>
                  <th className="px-3.5 py-2.5">Criticality</th>
                  <th className="px-3.5 py-2.5">Hops</th>
                  <th className="px-3.5 py-2.5">Classification</th>
                  <th className="px-3.5 py-2.5">Contingency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {filtered.map((f) => {
                  const isSelected = activeSelected && activeSelected.asset_id === f.asset_id;
                  const hasAlt = f.alternate_supply_available;
                  const hasBkp = f.backup_available;

                  return (
                    <tr
                      key={f.asset_id}
                      onClick={() => onSelectAsset && onSelectAsset(f.asset_id)}
                      className={`hover:bg-surface-elevated/70 cursor-pointer transition-colors ${
                        isSelected ? 'bg-primary/10 border-l-2 border-primary' : ''
                      }`}
                    >
                      <td className="px-3.5 py-3">
                        <div className="font-mono font-bold text-white">{f.asset_id}</div>
                        <div className="text-[11px] text-slate-400 truncate max-w-[180px]">{f.asset_name}</div>
                      </td>
                      <td className="px-3.5 py-3">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                            f.criticality.includes('Tier 1')
                              ? 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                              : f.criticality.includes('Tier 2')
                              ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                              : 'bg-slate-700 text-slate-300'
                          }`}
                        >
                          {f.criticality.split(' - ')[0]}
                        </span>
                      </td>
                      <td className="px-3.5 py-3 font-mono text-slate-300">{f.direct_distance}</td>
                      <td className="px-3.5 py-3 font-mono text-[11px] text-cyan-300">
                        {f.classification}
                      </td>
                      <td className="px-3.5 py-3">
                        <div className="flex flex-col gap-0.5 text-[10px]">
                          <span className={hasAlt ? 'text-emerald-400' : 'text-slate-500'}>
                            {hasAlt ? `✓ Alt: ${f.alternate_supply_details[0]?.supplier_id}` : '✗ No Alt'}
                          </span>
                          <span className={hasBkp ? 'text-purple-400' : 'text-slate-500'}>
                            {hasBkp ? `✓ Backup Ready` : '✗ No Backup'}
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Selected Asset Deep Dive Card (1 Col) */}
        <div className="bg-surface rounded-xl border border-border p-4 flex flex-col justify-between">
          {activeSelected ? (
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-primary-light">
                    Asset Evidence Detail
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    {activeSelected.direct_distance} hop(s)
                  </span>
                </div>
                <h3 className="text-base font-bold text-white font-mono mt-0.5">
                  {activeSelected.asset_id}
                </h3>
                <p className="text-xs text-slate-300 mt-0.5">{activeSelected.asset_name}</p>
              </div>

              <div className="p-2.5 rounded-lg bg-surface-elevated border border-border text-xs space-y-1.5">
                <div>
                  <span className="text-slate-400">Classification:</span>{' '}
                  <strong className="text-cyan-300 font-mono">{activeSelected.classification}</strong>
                </div>
                <div>
                  <span className="text-slate-400">Simulated Outcome:</span>{' '}
                  <span className="text-slate-200">{activeSelected.simulated_outcome}</span>
                </div>
              </div>

              {/* Evidence Paths */}
              <div>
                <div className="text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
                  <Layers className="h-3.5 w-3.5 text-primary" />
                  <span>Verifiable Evidence Paths ({activeSelected.evidence_paths.length})</span>
                </div>
                <div className="space-y-2 max-h-56 overflow-y-auto">
                  {activeSelected.evidence_paths.map((p, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-surface-elevated border-l-2 border-primary text-xs space-y-1 font-mono"
                    >
                      <div className="flex items-center justify-between text-[11px] text-primary-light">
                        <span>Path #{idx + 1}</span>
                        <span>{p.hops} hops</span>
                      </div>
                      <div className="text-[11px] text-slate-200 break-all">{p.summary}</div>
                      <div className="text-[10px] text-slate-400">
                        {p.relationship_types.join(' → ')}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Contingency details */}
              <div className="pt-2 border-t border-border text-xs space-y-2">
                <div>
                  <div className="text-slate-400 font-semibold mb-1">Alternate Supply Routes:</div>
                  {activeSelected.alternate_supply_details.length > 0 ? (
                    activeSelected.alternate_supply_details.map((alt, i) => (
                      <div key={i} className="text-slate-300 text-[11px]">
                        &bull; <strong className="text-white">{alt.supplier_id}</strong> via {alt.rel_type} ({alt.estimated_restoration_hours}h)
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-500 text-[11px]">None modeled in graph.</div>
                  )}
                </div>
                <div>
                  <div className="text-slate-400 font-semibold mb-1">Backup Generator:</div>
                  {activeSelected.backup_details.length > 0 ? (
                    activeSelected.backup_details.map((b, i) => (
                      <div key={i} className="text-slate-300 text-[11px]">
                        &bull; <strong className="text-white">{b.generator_id}</strong> ({b.capacity_rating}, {b.buffer_hours}h buffer)
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-500 text-[11px]">No backup generator connected.</div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-slate-500 text-xs text-center py-10">Select an asset to view evidence paths.</div>
          )}
        </div>
      </div>
    </div>
  );
};
