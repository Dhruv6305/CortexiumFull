import React from 'react';
import { GlassCard } from '../components/GlassCard';
import { BrainCircuit } from 'lucide-react';

function StatRow({ label, value, accentClass }) {
  return (
    <div className="flex items-center justify-between py-1.5" style={{ borderBottom: '1px solid rgba(0,0,0,0.05)' }}>
      <span className="text-xs text-slate-400">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${accentClass || 'text-slate-100'}`}>
        {value ?? '—'}
      </span>
    </div>
  );
}

export function LearningPanel({ learningData, modelStatus }) {
  const threshold  = learningData?.retrainThreshold ?? 5;
  const newSamples = learningData?.newSamples ?? 0;
  const nextAt     = Math.max(0, threshold - newSamples);
  const progress   = Math.min(1, newSamples / threshold);
  const isTraining = modelStatus === 'Training';

  return (
    <GlassCard className="flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1">
          <BrainCircuit className="w-4 h-4 text-slate-300" />
          <span className="text-sm font-semibold text-slate-100">Adaptive Learning</span>
        </div>
        <span className={`flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border ${
          isTraining
            ? 'bg-orange-50 border-orange-200 text-orange-600'
            : 'bg-gray-50 border-gray-200 text-slate-400'
        }`}>
          <span className={`w-1 h-1 rounded-full ${isTraining ? 'bg-orange-400 animate-pulse' : 'bg-gray-400'}`} />
          {isTraining ? 'Training…' : (modelStatus || 'Ready')}
        </span>
      </div>

      {/* Stats */}
      <div className="flex-1">
        <StatRow label="Learned Relationships"     value={learningData?.totalRelationships ?? 0} />
        <StatRow label="Total Training Samples"    value={learningData?.datasetSize ?? 0} />
        <StatRow label="New Samples (this session)" value={newSamples} accentClass="text-green-600" />
        <StatRow
          label="Last Retraining"
          value={learningData?.lastRetrainTime || 'Never'}
          accentClass="text-slate-400"
        />
      </div>

      {/* Auto-retrain progress */}
      <div className="mt-4 pt-4" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] text-gray-400 uppercase tracking-wider">Next Auto-Retrain</span>
          <span className="text-[10px] text-slate-400 font-mono">
            {isTraining ? 'In progress…' : `${nextAt} samples remaining`}
          </span>
        </div>
        <div className="progress-track">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${progress * 100}%`,
              background: isTraining
                ? 'linear-gradient(90deg, #f97316, #fb923c)'
                : 'linear-gradient(90deg, #6b7280, #9ca3af)',
            }}
          />
        </div>
      </div>
    </GlassCard>
  );
}
