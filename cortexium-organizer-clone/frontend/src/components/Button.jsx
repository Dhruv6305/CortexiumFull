import React from 'react';
import { cn } from '../utils/cn';

const variants = {
  ghost:
    'bg-white/8 hover:bg-white/12 border-white/10 hover:border-white/20 text-slate-200 hover:text-white',

  green:
    'bg-green-500/15 hover:bg-green-500/25 border-green-400/25 hover:border-green-400/40 text-green-200',

  orange:
    'bg-orange-500/15 hover:bg-orange-500/25 border-orange-400/25 hover:border-orange-400/40 text-orange-200',

  red:
    'bg-red-500/15 hover:bg-red-500/25 border-red-400/25 hover:border-red-400/40 text-red-200',

  white:
    'bg-white/8 hover:bg-white/12 border-white/10 hover:border-white/20 text-white',

  primary:
    'bg-orange-500/15 hover:bg-orange-500/25 border-orange-400/25 text-orange-200',

  secondary:
    'bg-white/8 hover:bg-white/12 border-white/10 text-slate-200',

  danger:
    'bg-red-500/15 hover:bg-red-500/25 border-red-400/25 text-red-200',

  success:
    'bg-green-500/15 hover:bg-green-500/25 border-green-400/25 text-green-200',
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
