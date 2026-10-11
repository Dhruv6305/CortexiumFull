import React from 'react';
import { cn } from '../utils/cn';

const variants = {
  ghost:
    'bg-white/[0.04] hover:bg-white/[0.08] border-white/[0.08] hover:border-white/[0.15] text-slate-300 hover:text-white',

  green:
    'bg-emerald-500/10 hover:bg-emerald-500/20 border-emerald-500/25 hover:border-emerald-500/40 text-emerald-300 font-semibold shadow-sm',

  orange:
    'bg-amber-500/10 hover:bg-amber-500/20 border-amber-500/25 hover:border-amber-500/40 text-amber-300 font-semibold shadow-sm',

  red:
    'bg-rose-500/10 hover:bg-rose-500/20 border-rose-500/25 hover:border-rose-500/40 text-rose-300',

  white:
    'bg-white/[0.06] hover:bg-white/[0.12] border-white/[0.1] hover:border-white/[0.2] text-white',

  primary:
    'bg-emerald-500/10 hover:bg-emerald-500/20 border-emerald-500/25 text-emerald-300',

  secondary:
    'bg-white/[0.04] hover:bg-white/[0.08] border-white/[0.08] text-slate-300',

  danger:
    'bg-rose-500/10 hover:bg-rose-500/20 border-rose-500/25 text-rose-300',

  success:
    'bg-emerald-500/10 hover:bg-emerald-500/20 border-emerald-500/25 text-emerald-300',
};

export function Button({ children, onClick, variant = 'ghost', className, icon: Icon, disabled = false }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'inline-flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium',
        'rounded-xl border backdrop-blur-sm transition-all duration-200',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        'shadow-sm',
        variants[variant] ?? variants.ghost,
        className
      )}
    >
      {Icon && <Icon className="w-3.5 h-3.5 shrink-0" />}
      {children}
    </button>
  );
}
