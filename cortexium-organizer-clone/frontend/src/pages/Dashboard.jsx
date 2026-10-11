import React, { useState, useEffect, useCallback } from 'react';
import { RotateCcw, AlertTriangle, CheckCircle2, X } from 'lucide-react';
import { DashboardLayout } from '../layouts/DashboardLayout';
import { CameraFeed } from '../features/CameraFeed';
import { DetectedObjectsTable } from '../features/DetectedObjectsTable';
import { LearningPanel } from '../features/LearningPanel';
import { ModelMetrics } from '../features/ModelMetrics';
import { PredictionPanel } from '../features/PredictionPanel';
import { Controls } from '../features/Controls';
import { api, useLiveStream } from '../services/apiService';

function ResetConfirmModal({ isOpen, onClose, onConfirm, resetting }) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(5px)' }}
      onClick={(e) => { if (e.target === e.currentTarget && !resetting) onClose(); }}
    >
      <div
        className="relative w-full max-w-md rounded-2xl p-6 flex flex-col gap-4 text-left"
        style={{
          background: 'rgba(15,23,42,0.98)',
          border: '1px solid rgba(239,68,68,0.3)',
          boxShadow: '0 24px 80px rgba(0,0,0,0.8), 0 0 25px rgba(239,68,68,0.12)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div
              className="p-2 rounded-xl text-red-400"
              style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.25)' }}
            >
              <RotateCcw className="w-4 h-4" />
            </div>
            <span className="text-sm font-semibold text-slate-100">Reset Learned Rules</span>
          </div>
          <button
            onClick={onClose}
            disabled={resetting}
            className="p-1 rounded-lg text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Description */}
        <p className="text-xs text-slate-300 leading-relaxed">
          Are you sure you want to clear all learned placement rules? This will reset the model to factory baseline rules.
        </p>

        <div
          className="px-3.5 py-2.5 rounded-xl text-xs flex items-center gap-2.5"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.22)', color: 'rgb(252,211,77)' }}
        >
          <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
          <span>New object placements learned in Learn Mode will be cleared and baseline defaults will take over.</span>
        </div>

        {/* Actions */}
        <div className="flex gap-2.5 pt-2">
          <button
            onClick={onClose}
            disabled={resetting}
            className="flex-1 py-2.5 rounded-xl text-xs font-medium text-slate-300 hover:text-white transition-colors"
            style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)' }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={resetting}
            className="flex-1 py-2.5 rounded-xl text-xs font-semibold text-white transition-all flex items-center justify-center gap-1.5 shadow-lg"
            style={{
              background: resetting ? 'rgba(239,68,68,0.4)' : 'rgba(239,68,68,0.9)',
              border: '1px solid rgba(239,68,68,0.8)',
              boxShadow: '0 4px 14px rgba(239,68,68,0.3)',
            }}
          >
            <RotateCcw className={`w-3.5 h-3.5 ${resetting ? 'animate-spin' : ''}`} />
            {resetting ? 'Resetting…' : 'Yes, Reset Rules'}
          </button>
        </div>
      </div>
    </div>
  );
}

export function Dashboard() {
  const [dashData, setDashData] = useState({ stats: null, learningData: null, metrics: null });
  const [loadError, setLoadError] = useState(null);
  const [successNotice, setSuccessNotice] = useState(null);
  const [showResetModal, setShowResetModal] = useState(false);
  const [resetting, setResetting] = useState(false);

  // Live data via WebSocket (now includes cameraSource)
  const {
    objects,
    misplacedObject,
    mode,
    cameraActive,
    modelStatus,
    activeModel:   liveActiveModel,
    stats: liveStats,
    learningData: liveLearning,
    metrics: liveMetrics,
    cameraSource: liveCameraSource,
    connected,
  } = useLiveStream();

  // Local camera source state — initialised from WS data; also fetched once on mount.
  const [cameraSource, setCameraSource] = useState('0');

  // Sync camera source from live WS data
  useEffect(() => {
    if (liveCameraSource !== undefined) {
      setCameraSource(liveCameraSource);
    }
  }, [liveCameraSource]);

  // Initial fetch for dashboard data + camera source (fills in before WS delivers them)
  useEffect(() => {
    api.fetchDashboardData()
      .then((d) => {
        setDashData(d);
        if (d.cameraSource !== undefined) setCameraSource(d.cameraSource);
      })
      .catch((err) => setLoadError(err.message));
  }, []);

  // Re-fetch dashboard data whenever model finishes training
  useEffect(() => {
    if (modelStatus === 'Ready') {
      api.fetchDashboardData().then(setDashData).catch(() => {});
    }
  }, [modelStatus]);

  // Prefer live data; fall back to initial HTTP fetch
  const metrics      = (liveMetrics  && Object.keys(liveMetrics).length)               ? liveMetrics  : dashData.metrics;
  const learningData = (liveLearning && liveLearning.datasetSize !== undefined)         ? liveLearning : dashData.learningData;
  const activeModel  = liveActiveModel ?? dashData.activeModel ?? 'baseline_model';

  // ── IP Camera source change handler ──
  const handleCameraSourceChange = useCallback(async (newSource) => {
    const result = await api.setCameraSource(newSource);
    if (result.status === 'ok' || result.source) {
      setCameraSource(result.source ?? newSource);
    } else {
      throw new Error(result.message ?? result.error ?? 'Failed to update camera source.');
    }
  }, []);

  // Local mode override for instantaneous UI switching
  const [localMode, setLocalMode] = useState(null);

  useEffect(() => {
    if (mode) setLocalMode(mode);
  }, [mode]);

  const activeMode = localMode ?? mode ?? 'predict';

  const handleControlAction = useCallback(async (actionId) => {
    setLoadError(null);
    try {
      switch (actionId) {
        case 'start_camera':    await api.startCamera(); break;
        case 'stop_camera':     await api.stopCamera();  break;
        case 'learn_mode':      setLocalMode('learn');   await api.setMode('learn');   break;
        case 'predict_mode':    setLocalMode('predict'); await api.setMode('predict'); break;
        case 'reset_learning':  setShowResetModal(true); break;
        case 'export_data':     api.exportDataset();     break;
        default: break;
      }
    } catch (err) {
      console.error(`Action ${actionId} failed:`, err);
      setLocalMode(mode);
      setLoadError(err.message ?? `Action ${actionId} failed.`);
    }
  }, [mode]);

  const handleConfirmReset = async () => {
    setResetting(true);
    setLoadError(null);
    try {
      await api.resetLearning();
      await api.fetchDashboardData().then(setDashData).catch(() => {});
      setShowResetModal(false);
      setSuccessNotice('Learned rules cleared successfully. Baseline model is now active.');
      setTimeout(() => setSuccessNotice(null), 5000);
    } catch (err) {
      setLoadError(err.message ?? 'Failed to reset learning.');
    } finally {
      setResetting(false);
    }
  };

  const headerMode   = activeMode === 'learn' ? 'Learn' : 'Predict';
  const cameraStatus = (connected && cameraActive) ? 'Connected' : 'Disconnected';
  const streamUrl    = '/organizer/camera/stream';

  return (
    <DashboardLayout
      mode={headerMode}
      cameraStatus={cameraStatus}
      modelStatus={modelStatus}
      controls={
        <Controls
          onAction={handleControlAction}
          mode={activeMode}
          cameraActive={cameraActive}
          cameraSource={cameraSource}
          onCameraSourceChange={handleCameraSourceChange}
        />
      }
    >
      <div className="flex flex-col gap-5">

        {/* ── Connection banner ── */}
        {!connected && (
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl text-orange-700 text-xs"
            style={{ background: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.2)' }}>
            <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse shrink-0" />
            Backend offline — start{' '}
            <code className="font-mono px-1.5 py-0.5 rounded text-orange-700"
              style={{ background: 'rgba(249,115,22,0.10)' }}>
              python run_backend.py
            </code>
            {' '}from the project root
          </div>
        )}

        {loadError && (
          <div className="flex items-center justify-between px-4 py-2.5 rounded-xl text-red-300 text-xs"
            style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.30)' }}>
            <span><strong>Camera Notice:</strong> {loadError}</span>
            <button onClick={() => setLoadError(null)} className="text-red-400 hover:text-white ml-2 text-sm">✕</button>
          </div>
        )}

        {successNotice && (
          <div className="flex items-center justify-between px-4 py-2.5 rounded-xl text-xs"
            style={{ background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.30)', color: 'rgb(134,239,172)' }}>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
              <span>{successNotice}</span>
            </div>
            <button onClick={() => setSuccessNotice(null)} className="text-green-400 hover:text-white ml-2 text-sm">✕</button>
          </div>
        )}

        {/* ══════════════════════════════════════════
            SECTION 1 — Two-column live application
            Left: 60%   Right: 40%
        ══════════════════════════════════════════ */}
        <div className="grid grid-cols-1 xl:grid-cols-[60%_40%] gap-4">

          {/* ════ LEFT COLUMN (60%) ════ */}
          <div className="flex flex-col gap-4">

            {/* 1. Camera feed — largest element */}
            <div className="h-[340px] sm:h-[440px] lg:h-[540px] shrink-0">              
              <CameraFeed
                isConnected={connected && cameraActive}
                streamUrl={streamUrl}
                mode={activeMode}
                cameraStatus={cameraStatus}
                modelStatus={modelStatus}
                cameraSource={cameraSource}
              />
            </div>

            
          </div>

          {/* ════ RIGHT COLUMN (35%) ════ */}
          <div className="flex flex-col gap-4">
            {/* 2. Misplaced / prediction panel */}
            <div className="shrink-0">
              <PredictionPanel
                misplacedObject={misplacedObject}
                cameraActive={cameraActive}
                connected={connected}
              />
            </div>

            {/* 1. Detected objects table */}
            <div className="flex-1" style={{ minHeight: '220px' }}>
              <DetectedObjectsTable objects={objects} />
            </div>

            {/* 2. Adaptive learning panel */}
            <div className="shrink-0">
              <LearningPanel
                learningData={learningData}
                modelStatus={modelStatus}
              />
            </div>
          </div>
        </div>

        {/* ══════════════════════════════════════════
            SECTION 2 — Full-width Model Performance
        ══════════════════════════════════════════ */}
        <div className="w-full">
          <ModelMetrics metrics={metrics} activeModel={activeModel} />
        </div>

      </div>

      <ResetConfirmModal
        isOpen={showResetModal}
        onClose={() => setShowResetModal(false)}
        onConfirm={handleConfirmReset}
        resetting={resetting}
      />
    </DashboardLayout>
  );
}

