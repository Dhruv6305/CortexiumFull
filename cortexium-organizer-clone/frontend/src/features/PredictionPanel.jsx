import React from 'react';
import { GlassCard } from '../components/GlassCard';
import { ArrowRight, CheckCircle2, AlertCircle } from 'lucide-react';

export function PredictionPanel({ misplacedObject, cameraActive, connected }) {
  if (!connected || !cameraActive) {
    return (
      <GlassCard className="flex items-center justify-center py-4">
        <div className="text-center">
          <p className="text-sm font-medium text-slate-400">Camera is not running</p>
          <p className="text-xs text-gray-400 mt-1">Start the camera to begin placement analysis.</p>
        </div>
      </GlassCard>
    );
  }

  if (!misplacedObject) {
    return (
      <GlassCard className="flex items-center gap-3 py-4" accent="#34d399">
        <div className="grid grid-cols-1 xl:grid-cols-[10%_90%] gap-4">
        <div className="flex flex-col gap-4">
        <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
        </div>
        <div className="flex flex-col gap-4">
          <p className="text-sm font-semibold text-emerald-300">All objects correctly placed</p>
          <p className="text-xs text-slate-400 mt-0.5">No misplacements detected</p>
        </div>
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="flex flex-col gap-1" accent="#f43f5e">
      {/* Title */}
      <div className="flex items-center gap-1.5">
        <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
        <span className="text-sm font-semibold text-rose-300">Misplacement Detected</span>
        <span className="ml-auto text-[10px] text-slate-400 font-mono">
          {(misplacedObject.confidence * 100).toFixed(0)}% conf
        </span>
      </div>

      {/* Object → Surface flow */}
      <div className="flex items-center gap-3 rounded-xl px-3 py-1 border"
        style={{ background: 'rgba(244,63,94,0.06)', borderColor: 'rgba(244,63,94,0.20)' }}>
        <div className="flex-1 text-center">
          <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Object</p>
          <p className="text-base font-semibold text-slate-100 capitalize">{misplacedObject.name}</p>
        </div>
        <div className="flex flex-col items-center gap-1">
          <ArrowRight className="w-4 h-4 text-slate-500" />
        </div>
        <div className="flex-1 text-center">
          <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-1">Move To</p>
          <p className="text-base font-semibold text-amber-300 capitalize">{misplacedObject.recommendedSurface}</p>
        </div>
      </div>

      {/* Current surface */}
      <p className="text-xs text-slate-400">
        Currently on <span className="text-white font-medium">{misplacedObject.currentSurface}</span>.{' '}
        {misplacedObject.explanation}
      </p>
    </GlassCard>
  );
}
