import React from 'react';
import { GlassCard } from '../components/GlassCard';
import { ScrollText, Info, AlertTriangle, CheckCircle, BrainCircuit } from 'lucide-react';
import { cn } from '../utils/cn';

export function EventLog({ events }) {
  const getIcon = (type) => {
    switch (type) {
      case 'info': return <Info className="w-4 h-4 text-brand-blue" />;
      case 'warning': return <AlertTriangle className="w-4 h-4 text-brand-orange" />;
      case 'error': return <AlertTriangle className="w-4 h-4 text-brand-red" />;
      case 'success': return <CheckCircle className="w-4 h-4 text-brand-green" />;
      case 'learning': return <BrainCircuit className="w-4 h-4 text-brand-purple" />;
      default: return <Info className="w-4 h-4 text-slate-400" />;
    }
  };

  return (
    <GlassCard className="h-full flex flex-col col-span-2 xl:col-span-3">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center">
          <ScrollText className="w-5 h-5 text-slate-400 mr-2" />
          <h2 className="text-lg font-semibold text-slate-200">System Event Log</h2>
        </div>
        <span className="text-xs text-slate-400 font-mono">Live</span>
      </div>
      
      <div className="flex-1 overflow-auto pr-2 custom-scrollbar space-y-3">
        {events?.length > 0 ? (
          events.map((event, i) => (
            <div 
              key={i} 
              className={cn(
                "p-3 rounded-lg border bg-slate-900/40 text-sm flex items-start space-x-3 transition-all",
                i === 0 ? "border-slate-600 bg-slate-800/40" : "border-slate-800"
              )}
            >
              <div className="mt-0.5">{getIcon(event.type)}</div>
              <div className="flex-1">
                <p className="text-slate-300">{event.message}</p>
                <p className="text-xs text-slate-400 mt-1 font-mono">{event.timestamp}</p>
              </div>
            </div>
          ))
        ) : (
          <div className="text-center text-slate-400 py-8 text-sm">
            Waiting for system events...
          </div>
        )}
      </div>
    </GlassCard>
  );
}
