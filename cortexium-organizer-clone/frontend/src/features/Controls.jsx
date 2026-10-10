import React, { useState } from 'react';
import { Camera, CameraOff, BrainCircuit, Activity, RotateCcw, Download, Wifi, X, Check } from 'lucide-react';
import { Button } from '../components/Button';

/**
 * IP Camera Source Selector
 *
 * Allows the user to switch between:
 *   - Local webcam (index 0, 1, …)
 *   - IP Webcam (Android app): http://<ip>:8080/video
 *   - DroidCam:                http://<ip>:4747/video
 *   - RTSP stream:             rtsp://…
 */
function IPCameraModal({ currentSource, onSave, onClose }) {
  const [value, setValue] = useState(
    // Pre-fill: if current source is a plain integer, show it as-is;
    // if it's a URL, strip to just the host:port for easier editing
    String(currentSource ?? '0')
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const presets = [
    { label: 'Local Webcam (default)', value: '0' },
    { label: 'IP Webcam — port 8080', value: 'http://192.168.1.x:8080/video' },
    { label: 'IP Webcam — port 8080 (mjpeg)', value: 'http://192.168.1.x:8080/videofeed' },
    { label: 'DroidCam — port 4747', value: 'http://192.168.1.x:4747/video' },
  ];

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed) { setError('Source cannot be empty.'); return; }
    setSaving(true);
    setError('');
    try {
      await onSave(trimmed);
      onClose();
    } catch (e) {
      setError(e.message ?? 'Failed to update camera source.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="relative w-full max-w-md rounded-2xl p-6 flex flex-col gap-4"
        style={{
          background: 'rgba(15,23,42,0.97)',
          border: '1px solid rgba(255,255,255,0.10)',
          boxShadow: '0 24px 80px rgba(0,0,0,0.7)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Wifi className="w-4 h-4 text-cyan-400" />
            <span className="text-sm font-semibold text-slate-100">Camera Source</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Current source */}
        <div className="px-3 py-2 rounded-lg text-xs font-mono text-slate-400"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}>
          Current: <span className="text-cyan-400">{currentSource ?? '0'}</span>
        </div>

        {/* Presets */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Quick Presets</span>
          {presets.map((p) => (
            <button
              key={p.value}
              onClick={() => setValue(p.value)}
              className={`text-left px-3 py-2 rounded-lg text-xs transition-all ${
                value === p.value
                  ? 'text-cyan-300'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              style={{
                background: value === p.value ? 'rgba(34,211,238,0.08)' : 'rgba(255,255,255,0.03)',
                border: value === p.value ? '1px solid rgba(34,211,238,0.25)' : '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <span className="font-medium">{p.label}</span>
              <br />
              <span className="font-mono text-[10px] opacity-70">{p.value}</span>
            </button>
          ))}
        </div>

        {/* Custom input */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">
            Custom Source
          </span>
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder='0  or  http://192.168.1.x:8080/video'
            className="w-full px-3 py-2 rounded-lg text-xs font-mono text-slate-100 outline-none focus:ring-1 focus:ring-cyan-500/50"
            style={{
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.12)',
            }}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') onClose(); }}
            autoFocus
          />
          <p className="text-[10px] text-slate-500 leading-relaxed">
            Use <span className="text-slate-400 font-mono">0</span> for default webcam, 
            {' '}<span className="text-slate-400 font-mono">1</span> for second webcam, or paste a full IP camera URL.
            Replace <span className="text-slate-400 font-mono">192.168.1.x</span> with your device's actual IP.
          </p>
        </div>

        {error && (
          <p className="text-xs text-red-400 px-3 py-2 rounded-lg"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
            {error}
          </p>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-1">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white transition-colors"
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 py-2 rounded-xl text-xs font-semibold text-white transition-all flex items-center justify-center gap-1.5"
            style={{
              background: saving ? 'rgba(34,211,238,0.3)' : 'rgba(34,211,238,0.18)',
              border: '1px solid rgba(34,211,238,0.35)',
            }}
          >
            <Check className="w-3.5 h-3.5" />
            {saving ? 'Saving…' : 'Save & Reconnect'}
          </button>
        </div>
      </div>
    </div>
  );
}

export function Controls({ onAction, mode, cameraActive, cameraSource, onCameraSourceChange }) {
  const isLearn = mode === 'learn';
  const [showIPModal, setShowIPModal] = useState(false);

  const actions = [
    {
      id: 'start_camera',
      label: 'Start Camera',
      icon: Camera,
      variant: cameraActive ? 'ghost' : 'green',
      disabled: cameraActive,
    },
    {
      id: 'stop_camera',
      label: 'Stop Camera',
      icon: CameraOff,
      variant: cameraActive ? 'red' : 'ghost',
      disabled: !cameraActive,
    },
    {
      id: 'learn_mode',
      label: 'Learn Mode',
      icon: BrainCircuit,
      variant: isLearn ? 'white' : 'ghost',
      disabled: isLearn,
    },
    {
      id: 'predict_mode',
      label: 'Predict Mode',
      icon: Activity,
      variant: !isLearn ? 'green' : 'ghost',
      disabled: !isLearn,
    },
    {
      id: 'reset_learning',
      label: 'Reset Learning',
      icon: RotateCcw,
      variant: 'red',
    },
    {
      id: 'export_data',
      label: 'Export Dataset',
      icon: Download,
      variant: 'ghost',
    },
  ];

  return (
    <>
      <div className="flex flex-wrap gap-2 items-center">
        {actions.map((a) => (
          <Button
            key={a.id}
            variant={a.variant}
            icon={a.icon}
            onClick={() => onAction(a.id)}
            disabled={a.disabled}
            className="text-xs"
          >
            {a.label}
          </Button>
        ))}

        {/* IP Camera settings button */}
        <button
          onClick={() => setShowIPModal(true)}
          title={`Camera source: ${cameraSource ?? '0'}`}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
          style={{
            background: 'rgba(34,211,238,0.07)',
            border: '1px solid rgba(34,211,238,0.20)',
            color: 'rgb(103,232,249)',
          }}
        >
          <Wifi className="w-3.5 h-3.5" />
          IP Camera
          {cameraSource && cameraSource !== '0' && (
            <span className="ml-1 px-1.5 py-0.5 rounded-full text-[9px] font-bold"
              style={{ background: 'rgba(34,211,238,0.18)', color: 'rgb(34,211,238)' }}>
              IP
            </span>
          )}
        </button>
      </div>

      {showIPModal && (
        <IPCameraModal
          currentSource={cameraSource}
          onSave={onCameraSourceChange}
          onClose={() => setShowIPModal(false)}
        />
      )}
    </>
  );
}
