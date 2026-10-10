import React from 'react';
import { GlassCard } from '../components/GlassCard';
import { BarChart2 } from 'lucide-react';

// ─────────────────────────────────────────────────────
// Column 1: Metric progress bars
// ─────────────────────────────────────────────────────
const METRIC_DEFS = [
  { key: 'accuracy',  label: 'Accuracy',              color: '#22c55e', bg: 'rgba(34,197,94,0.12)' },
  { key: 'precision', label: 'Precision',             color: '#f97316', bg: 'rgba(249,115,22,0.12)' },
  { key: 'recall',    label: 'Recall',                color: '#64748b', bg: 'rgba(100,116,139,0.12)' },
  { key: 'f1Score',   label: 'F1 Score',              color: '#374151', bg: 'rgba(55,65,81,0.12)' },
  { key: 'cvScore',   label: 'Cross Val Score',       color: '#6b7280', bg: 'rgba(107,114,128,0.12)' },
];

function MetricBar({ label, value, color, bg }) {
  const pct = Math.round((value ?? 0) * 100);
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium text-slate-300">{label}</span>
        <span className="text-sm font-bold tabular-nums text-slate-100">{pct}%</span>
      </div>
      <div className="progress-track">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: color, boxShadow: `0 0 8px ${color}40` }}
        />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────
// Column 2: Confusion matrix
// ─────────────────────────────────────────────────────
function ConfusionMatrix({ matrix, classes }) {
  if (!matrix || matrix.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-300 text-xs">
        No data yet
      </div>
    );
  }
  const maxVal = Math.max(...matrix.flat(), 1);
  const labels = classes || matrix[0].map((_, i) => `C${i}`);

  return (
    <div className="overflow-auto">
      <table className="text-xs border-collapse w-full" style={{ minWidth: `${(labels.length + 1) * 52}px` }}>
        <thead>
          <tr>
            {/* top-left empty corner */}
            <th className="p-1 text-[10px] text-gray-400 font-normal text-right pr-2">Actual →</th>
            {labels.map((c, i) => (
              <th key={i} className="p-1 text-[10px] font-medium text-slate-400 text-center capitalize">
                {String(c).length > 6 ? String(c).slice(0, 5) + '…' : c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, ri) => (
            <tr key={ri}>
              <td className="pr-2 py-1 text-[10px] font-medium text-slate-400 capitalize text-right">
                {labels[ri] && (String(labels[ri]).length > 6 ? String(labels[ri]).slice(0, 5) + '…' : labels[ri])}
              </td>
              {row.map((val, ci) => {
                const intensity = val / maxVal;
                const isDiag = ri === ci;
                const bg = isDiag
                  ? `rgba(34,197,94,${0.08 + intensity * 0.55})`
                  : `rgba(239,68,68,${intensity * 0.35})`;
                const textColor = val > 0 ? (isDiag ? '#166534' : '#991b1b') : '#d1d5db';
                return (
                  <td
                    key={ci}
                    className="text-center font-mono font-semibold py-1.5 px-1 rounded text-sm"
                    style={{ background: bg, color: textColor, minWidth: '44px' }}
                    title={`Predicted: ${labels[ci]}, Actual: ${labels[ri]} → ${val}`}
                  >
                    {val}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[10px] text-gray-400 mt-2 text-center">
        ↕ Predicted (rows) vs Actual (cols)
      </p>
    </div>
  );
}

// ─────────────────────────────────────────────────────
// Column 3: Feature importance
// ─────────────────────────────────────────────────────
function FeatureImportance({ importance }) {
  if (!importance || Object.keys(importance).length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-300 text-xs">
        No data yet
      </div>
    );
  }

  const sorted = Object.entries(importance)
    .sort(([, a], [, b]) => b - a);
  const max = sorted[0]?.[1] ?? 1;

  const colors = [
    '#f97316', '#ea580c', '#6b7280', '#9ca3af',
    '#374151', '#4b5563', '#64748b', '#94a3b8',
    '#d1d5db', '#e5e7eb', '#f3f4f6', '#111827', '#374151',
  ];

  return (
    <div className="space-y-2.5">
      {sorted.map(([name, val], idx) => {
        const pct = (val / max) * 100;
        const color = colors[idx % colors.length];
        return (
          <div key={name}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-300 truncate max-w-[140px]" title={name.replace(/_/g, ' ')}>
                {name.replace(/_/g, ' ')}
              </span>
              <span className="text-xs font-semibold text-white font-mono ml-2 shrink-0">
                {(val * 100).toFixed(1)}%
              </span>
            </div>
            <div className="progress-track">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{ width: `${pct}%`, background: color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────
export function ModelMetrics({ metrics, activeModel }) {
  const hasData = METRIC_DEFS.some(m => (metrics?.[m.key] ?? 0) > 0);

  const modelLabel = activeModel === 'personalized_model'
    ? 'Personalized CatBoost'
    : activeModel === 'baseline_model'
    ? 'Baseline CatBoost'
    : 'Default Rules';

  const modelBadgeStyle = activeModel === 'personalized_model'
    ? { background: 'rgba(34,197,94,0.12)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.25)' }
    : { background: 'rgba(249,115,22,0.10)', color: '#f97316', border: '1px solid rgba(249,115,22,0.20)' };

  // Map backend field names: total_samples / train_samples / test_samples
  const totalSamples = metrics?.total_samples ?? metrics?.totalSamples;
  const trainSamples = metrics?.train_samples ?? metrics?.trainSamples;
  const testSamples  = metrics?.test_samples  ?? metrics?.testSamples;

  return (
    <div className="w-full">
      {/* Section header */}
      <div className="flex items-center gap-2 mb-4">
        <BarChart2 className="w-4 h-4 text-slate-400" />
        <span className="text-base font-bold text-slate-100">Model Performance</span>
        {/* Active model badge */}
        <span className="ml-2 text-[10px] font-medium px-2 py-0.5 rounded-full"
          style={modelBadgeStyle}>
          {modelLabel}
        </span>
        {!hasData && (
          <span className="ml-auto text-[10px] text-gray-400 italic">Run retrain to populate</span>
        )}
      </div>

      {/* Three-column grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* ── Column 1: Score bars ── */}
        <GlassCard className="flex flex-col">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Evaluation Scores</p>
          {hasData ? (
            <div>
              {METRIC_DEFS.map((m) => (
                <MetricBar
                  key={m.key}
                  label={m.label}
                  value={metrics?.[m.key]}
                  color={m.color}
                  bg={m.bg}
                />
              ))}
              {/* Sample info */}
              <div className="mt-2 pt-3 text-[10px] text-gray-400 space-y-1" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                {totalSamples != null && (
                  <div className="flex justify-between">
                    <span>Train / Test</span>
                    <span className="font-mono">{trainSamples ?? '—'} / {testSamples ?? '—'}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>Classes</span>
                  <span className="font-mono">{metrics?.classes?.length ?? '—'}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-300 text-xs">
              No metrics available
            </div>
          )}
        </GlassCard>

        {/* ── Column 2: Confusion matrix ── */}
        <GlassCard className="flex flex-col">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Confusion Matrix</p>
          <ConfusionMatrix
            matrix={metrics?.confusionMatrix}
            classes={metrics?.classes}
          />
        </GlassCard>

        {/* ── Column 3: Feature importance ── */}
        <GlassCard className="flex flex-col">
          <div className="max-h-[320px] overflow-y-auto pr-2">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Feature Importance</p>
          <FeatureImportance importance={metrics?.featureImportance} />
          </div>
        </GlassCard>

      </div>
    </div>
  );
}
