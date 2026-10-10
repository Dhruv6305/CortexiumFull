import React from 'react';
import { cn } from '../utils/cn';

export function GlassCard({ children, className, accent }) {
  return (
    <div
    className={cn(
      'relative overflow-hidden rounded-3xl p-5 border border-white/5 backdrop-blur-2xl bg-white/[0.035] shadow-xl',
      className
    )}
    style={{
      borderColor: accent ? `${accent}40` : 'rgba(255,255,255,0.05)',
      boxShadow:
        '0 10px 35px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.06)',
    }}
    >
      {/* Subtle top-edge highlight */}
      <div
      className="absolute top-0 left-0 right-0 h-px"
      style={{
        background:
          accent
              ? `linear-gradient(90deg, transparent, ${accent}80, transparent)`
              : "linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent)"
        }}
      />
      <div className="relative z-10">{children}</div>
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.03] via-transparent to-transparent pointer-events-none" />
    </div>
  );
}
