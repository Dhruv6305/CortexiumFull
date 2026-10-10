import React from 'react';

export function Footer() {
  return (
    <footer
      className="flex items-center justify-between px-6 py-2.5 text-[10px] font-mono"
      style={{
      background: "rgba(255,255,255,0.05)",
      backdropFilter: "blur(18px)",
      borderTop: "1px solid rgba(255,255,255,0.06)"
      }}
    >
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500" style={{ boxShadow: '0 0 4px #22c55e' }} />
          YOLOv8s
        </span>
        <span>CatBoost</span>
        <span>FastAPI + WebSocket</span>
      </div>
      <span>Cortexium XR v1.0</span>
    </footer>
  );
}
