/**
 * apiService.js — Cortexium Organizer API & WebSocket service
 *
 * All routes use /organizer/* prefix, which the dashboard Vite proxy
 * forwards to the unified backend (port 7030 by default).
 *
 * IP Camera support:
 *   getCameraSource()        → GET  /organizer/camera/source
 *   setCameraSource(source)  → POST /organizer/camera/source
 *     source can be:
 *       "0"                              → local webcam index 0
 *       "http://192.168.1.x:8080/video" → Android IP Webcam
 *       "http://192.168.1.x:4747/video" → DroidCam
 *       "rtsp://user:pass@host/stream"  → RTSP stream
 */
import React from 'react';

const BASE = '/organizer';

// ─────────────────────────────────────────────
// HTTP API
// ─────────────────────────────────────────────
export const api = {
  fetchDashboardData: async () => {
    const res = await fetch(`${BASE}/dashboard`);
    if (!res.ok) throw new Error(`Dashboard fetch failed: ${res.status}`);
    return res.json();
  },

  // Camera controls
  startCamera: async () => {
    const res = await fetch(`${BASE}/camera/start`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || data.error || `Failed to start camera (HTTP ${res.status})`);
    }
    return data;
  },
  stopCamera: async () => {
    const res = await fetch(`${BASE}/camera/stop`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || data.error || `Failed to stop camera (HTTP ${res.status})`);
    }
    return data;
  },

  // IP Camera source management
  getCameraSource: () =>
    fetch(`${BASE}/camera/source`).then(r => r.json()),

  setCameraSource: (source) =>
    fetch(`${BASE}/camera/source`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: String(source) }),
    }).then(r => r.json()),

  // Mode switching
  setMode: async (mode) => {
    const res = await fetch(`${BASE}/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === 'error') {
      throw new Error(data.error || `Failed to set mode to ${mode}`);
    }
    return data;
  },

  // Learning controls
  retrainModel:  () => fetch(`${BASE}/retrain`, { method: 'POST' }).then(r => r.json()),
  resetLearning: () => fetch(`${BASE}/reset`,   { method: 'POST' }).then(r => r.json()),

  // Data export
  exportDataset:   () => window.open(`${BASE}/export/dataset`, '_blank'),
  downloadMetrics: () => window.open(`${BASE}/metrics`, '_blank'),
};

// ─────────────────────────────────────────────
// WebSocket hook
// ─────────────────────────────────────────────
const DEFAULT_STATE = {
  objects:        [],
  events:         [],
  misplacedObject: null,
  mode:           'predict',
  cameraActive:   false,
  modelStatus:    'Ready',
  activeModel:    'baseline_model',
  stats: {
    totalObjects: 0, totalSurfaces: 0, correctlyPlaced: 0,
    misplaced: 0, fps: 0, inferenceTime: 0, avgConfidence: 0,
  },
  learningData:  null,
  metrics:       null,
  cameraSource:  '0',
};

export function useLiveStream() {
  const [data, setData]      = React.useState(DEFAULT_STATE);
  const [connected, setConn] = React.useState(false);
  const wsRef    = React.useRef(null);
  const retryRef = React.useRef(null);

  const connect = React.useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    // Connect to unified backend WebSocket at /organizer/ws
    const ws = new WebSocket(`${proto}://${window.location.host}/organizer/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConn(true);
      clearTimeout(retryRef.current);
    };

    ws.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        setData((prev) => ({
          objects:         d.objects         ?? prev.objects,
          events:          d.events          ?? prev.events,
          misplacedObject: d.misplacedObject !== undefined ? d.misplacedObject : prev.misplacedObject,
          mode:            d.mode            ?? prev.mode,
          cameraActive:    d.cameraActive    !== undefined ? d.cameraActive : prev.cameraActive,
          modelStatus:     d.modelStatus     ?? prev.modelStatus,
          activeModel:     d.activeModel     ?? prev.activeModel,
          stats:           d.stats           ?? prev.stats,
          learningData:    d.learningData    !== undefined ? d.learningData : prev.learningData,
          metrics:         d.metrics         !== undefined ? d.metrics : prev.metrics,
          cameraSource:    d.cameraSource    ?? prev.cameraSource,
        }));
      } catch { /* ignore */ }
    };

    ws.onclose = () => {
      setConn(false);
      retryRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  }, []);

  React.useEffect(() => {
    connect();
    return () => {
      clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { ...data, connected };
}
