import React from 'react';
import { cn } from '../utils/cn';

const variants = {
  default:  'bg-gray-50    text-slate-400   border-gray-200',
  orange:   'bg-orange-50  text-orange-600 border-orange-200',
  green:    'bg-green-50   text-green-700  border-green-200',
  red:      'bg-red-50     text-red-600    border-red-200',
  white:    'bg-white/10      text-white  border-gray-200',
  cyan:     'bg-cyan-50    text-cyan-700   border-cyan-200',
  purple:   'bg-violet-50  text-violet-600 border-violet-200',
  blue:     'bg-blue-50    text-blue-600   border-blue-200',
};

export function Badge({ children, variant = 'default', className }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border',
        variants[variant] ?? variants.default,
        className
      )}
    >
      {children}
    </span>
  );
}
