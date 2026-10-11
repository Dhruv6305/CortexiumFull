import React, { useRef, useCallback } from 'react';
import { GlassCard } from '../components/GlassCard';
import { Maximize2, Minimize2, VideoOff } from 'lucide-react';

export function CameraFeed({ streamUrl, isConnected, mode, cameraStatus, modelStatus, cameraSource }) {
  const containerRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = React.useState(false);

  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  }, []);

  const [streamKey, setStreamKey] = React.useState(() => Date.now());

  React.useEffect(() => {
    if (isConnected) {
      setStreamKey(Date.now());
    }
  }, [isConnected]);

  React.useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handler);
    return () => document.removeEventListener('fullscreenchange', handler);
  }, []);

  return (
    <GlassCard className="flex flex-col h-full min-h-[360px]" accent="#22c55e">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={isConnected ? 'dot-live' : 'dot-error'} />
          <span className="text-sm font-semibold text-slate-100">Live Spatial Feed</span>
          {isConnected && (
            <span className="text-[10px] text-gray-400 font-mono uppercase tracking-wider">LIVE</span>
          )}
        </div>
        <button
          onClick={toggleFullscreen}
          className="p-1.5 rounded-lg bg-black/5 hover:bg-black/10 border border-black/8 text-slate-400 hover:text-slate-100 transition-all"
          title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
        >
          {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Stream */}
      <div
        ref={containerRef}
        className="relative flex-1 rounded-xl overflow-hidden flex items-center justify-center"
        style={{ minHeight: 0, background: 'rgba(0,0,0,0.06)' }}
      >
        {isConnected ? (
          <img
            key={streamKey}
            src={`${streamUrl}?t=${streamKey}`}
            alt="Live YOLO annotated feed"
            className="w-full h-full object-contain"
            style={{ display: 'block' }}
          />
        ) : (
          <div className="flex flex-col items-center gap-3 text-gray-400">
            <VideoOff className="w-10 h-10 opacity-30" />
            <p className="text-sm text-slate-400">Camera not connected</p>
            <p className="text-xs text-gray-400">Click Start Camera to begin</p>
          </div>
        )}

        {/* Subtle grid overlay */}
        <div className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: 'linear-gradient(rgba(0,0,0,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.03) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />

        {/* Corner brackets */}
        {isConnected && (
          <>
            <div className="absolute top-3 left-3 w-5 h-5 border-t-2 border-l-2 border-green-500/50 rounded-tl" />
            <div className="absolute top-3 right-3 w-5 h-5 border-t-2 border-r-2 border-green-500/50 rounded-tr" />
            <div className="absolute bottom-3 left-3 w-5 h-5 border-b-2 border-l-2 border-green-500/50 rounded-bl" />
            <div className="absolute bottom-3 right-3 w-5 h-5 border-b-2 border-r-2 border-green-500/50 rounded-br" />
          </>
        )}
      </div>

      <div className="flex items-center justify-center flex-wrap gap-2 pt-4 border-t border-white/10">

      {/* Mode */}
      <div
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold transition-all ${
          mode === "learn"
            ? "bg-amber-500/15 border-amber-500/30 text-amber-300"
            : "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
        }`}
      >
        <span
          className={`w-2 h-2 rounded-full ${
            mode === "learn" ? "bg-amber-400 animate-pulse" : "bg-emerald-400"
          }`}
        />
        {mode === "learn" ? "Learn Mode Active" : "Predict Mode Active"}
      </div>

      {/* Camera */}
      <div
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/[0.08] bg-white/[0.04] text-xs font-medium text-slate-300"
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            cameraStatus === "Connected" ? "bg-emerald-400" : "bg-rose-400"
          }`}
        />
        Camera {cameraStatus}
      </div>

      {/* Camera source badge */}
      {cameraSource !== undefined && (
        <div
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium font-mono"
          style={{
            background: cameraSource === '0' || cameraSource === 0
              ? 'rgba(255,255,255,0.06)'
              : 'rgba(34,211,238,0.08)',
            border: cameraSource === '0' || cameraSource === 0
              ? '1px solid rgba(255,255,255,0.10)'
              : '1px solid rgba(34,211,238,0.25)',
            color: cameraSource === '0' || cameraSource === 0
              ? 'rgb(148,163,184)'
              : 'rgb(103,232,249)',
          }}
          title={String(cameraSource)}
        >
          {cameraSource === '0' || cameraSource === 0
            ? 'Local Cam'
            : (() => {
                try {
                  const u = new URL(String(cameraSource));
                  return `IP: ${u.hostname}`;
                } catch {
                  return `Src: ${String(cameraSource).slice(0, 12)}`;
                }
              })()
          }
        </div>
      )}

      {/* Model */}
      <div
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium ${
          modelStatus === "Training"
            ? "bg-white/10 border-white/10 text-slate-200"
            : "bg-white/10 border-white/10 text-slate-200"
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            modelStatus === "Training"
              ? "bg-orange-400 animate-pulse"
              : "bg-cyan-400"
          }`}
        />
        Model {modelStatus}
      </div>

    </div>
    </GlassCard>
  );
}
