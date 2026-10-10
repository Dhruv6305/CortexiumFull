import React from 'react';
import { GlassCard } from '../components/GlassCard';
import { Target, Layers, CheckCircle, AlertTriangle, Zap, Clock, Activity } from 'lucide-react';

export function LiveAnalytics({ stats }) {
  const statCards = [
    { label: 'Total Objects', value: stats?.totalObjects || 0, icon: Target, color: 'text-brand-cyan' },
    { label: 'Surfaces', value: stats?.totalSurfaces || 0, icon: Layers, color: 'text-brand-orange' },
    { label: 'Correctly Placed', value: stats?.correctlyPlaced || 0, icon: CheckCircle, color: 'text-brand-green' },
    { label: 'Misplaced', value: stats?.misplaced || 0, icon: AlertTriangle, color: 'text-brand-red' },
    { label: 'Current FPS', value: stats?.fps || 0, icon: Activity, color: 'text-brand-purple' },
    { label: 'Inference Time', value: `${stats?.inferenceTime || 0}ms`, icon: Zap, color: 'text-brand-purple' },
    { label: 'Avg Confidence', value: `${Math.round((stats?.avgConfidence || 0) * 100)}%`, icon: Clock, color: 'text-brand-blue' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 mb-6">
      {statCards.map((stat, idx) => {
        const Icon = stat.icon;
        return (
          <GlassCard key={idx} className="p-4" glowColor="#06b6d4">
            <div className="flex flex-col">
              <span className="text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">{stat.label}</span>
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold text-white">{stat.value}</span>
                <Icon className={`w-5 h-5 ${stat.color} opacity-80`} />
              </div>
            </div>
          </GlassCard>
        );
      })}
    </div>
  );
}
