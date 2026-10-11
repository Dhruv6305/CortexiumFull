import React from 'react';
import { GlassCard } from '../components/GlassCard';
import { ScanSearch } from 'lucide-react';

function StatusDot({ status }) {
  if (status === 'Correct') {
    return (
      <span className="inline-flex items-center gap-1.5 text-emerald-400 text-xs font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Correct
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-rose-400 text-xs font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-rose-400" /> Misplaced
    </span>
  );
}

export function DetectedObjectsTable({ objects }) {
  return (
    <GlassCard className="flex flex-col h-full" accent="#22d3ee">
      <div className="flex items-center gap-1.5 mb-4">
        <ScanSearch className="w-4 h-4 text-cyan-400" />
        <span className="text-sm font-semibold text-slate-100">Alternate Surface Suggestions</span>
        {objects?.length > 0 && (
          <span className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded-full text-slate-400"
            style={{ background: 'rgba(0,0,0,0.06)', border: '1px solid rgba(0,0,0,0.08)' }}>
            {objects.length}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-auto min-h-0">
        {objects?.length > 0 ? (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-400 uppercase tracking-wider" style={{ borderBottom: '1px solid rgba(0,0,0,0.07)' }}>
                <th className="text-left pb-2 font-medium">Object</th>
                <th className="text-left pb-2 font-medium">Current</th>
                <th className="text-left pb-2 font-medium">Expected</th>
                <th className="text-right pb-2 font-medium">Conf</th>
                <th className="text-right pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {objects.map((obj, i) => (
                <tr key={i} className="fade-in transition-colors hover:bg-black/[0.02]"
                  style={{ borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
                  <td className="py-0.5 pr-2 font-medium text-slate-100 capitalize">{obj.name}</td>
                  <td className="py-0.5 pr-2 text-orange-500 capitalize">{obj.currentSurface}</td>
                  <td className="py-0.5 pr-2 text-slate-400 capitalize">{obj.predictedSurface}</td>
                  <td className="py-0.5 pr-2 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <div className="w-12 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.07)' }}>
                        <div
                          className="h-full rounded-full bg-gray-400"
                          style={{ width: `${obj.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-slate-400 tabular-nums w-7 text-right">
                        {(obj.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="py-1 text-right">
                    <StatusDot status={obj.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-1 text-gray-300">
            <ScanSearch className="w-8 h-8 opacity-30" />
            <p className="text-xs text-gray-400">No objects detected</p>
          </div>
        )}
      </div>
    </GlassCard>
  );
}
