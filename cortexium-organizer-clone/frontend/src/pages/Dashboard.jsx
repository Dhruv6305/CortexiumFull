import React, { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../layouts/DashboardLayout';
import { CameraFeed } from '../features/CameraFeed';
import { DetectedObjectsTable } from '../features/DetectedObjectsTable';
import { LearningPanel } from '../features/LearningPanel';
import { ModelMetrics } from '../features/ModelMetrics';
import { PredictionPanel } from '../features/PredictionPanel';
import { Controls } from '../features/Controls';
import { api, useLiveStream } from '../services/apiService';

export function Dashboard() {
  const [dashData, setDashData] = useState({ stats: null, learningData: null, metrics: null });
  const [loadError, setLoadError] = useState(null);

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

  const handleControlAction = useCallback(async (actionId) => {
    try {
      switch (actionId) {
        case 'start_camera':    await api.startCamera(); break;
        case 'stop_camera':     await api.stopCamera();  break;
        case 'learn_mode':      await api.setMode('learn');   break;
        case 'predict_mode':    await api.setMode('predict'); break;
        case 'reset_learning':
          if (window.confirm('Reset all learned rules? This cannot be undone.')) {
            await api.resetLearning();
            api.fetchDashboardData().then(setDashData).catch(() => {});
          }
          break;
        case 'export_data': api.exportDataset(); break;
        default: break;
      }
    } catch (err) {
      console.error(`Action ${actionId} failed:`, err);
    }
  }, []);

  const headerMode   = mode === 'learn' ? 'Learn' : 'Predict';
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
          mode={mode}
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
          <div className="px-4 py-2.5 rounded-xl text-red-600 text-xs"
            style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}>
            {loadError}
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
                mode={mode}
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
    </DashboardLayout>
  );
}
