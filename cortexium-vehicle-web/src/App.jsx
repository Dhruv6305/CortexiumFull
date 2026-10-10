import React, { useState, useEffect, useRef } from 'react'
import {
  Car,
  Shield,
  AlertTriangle,
  Compass,
  Navigation,
  Activity,
  FileText,
  Download,
  Play,
  Square,
  RefreshCw,
  Eye,
  SlidersHorizontal,
  Radio,
  Zap,
  CheckCircle2,
  Cpu,
  ArrowLeft,
  Sun,
  Layers,
  Upload,
  Video,
  Film,
  Check,
  RotateCcw,
  Power,
  Terminal,
  Monitor,
  ExternalLink
} from 'lucide-react'

export default function App() {
  // ── State ──────────────────────────────────────────────────
  const [speed, setSpeed] = useState(68)
  const [safetyScore, setSafetyScore] = useState(94)
  const [distanceToLead, setDistanceToLead] = useState(24.5)
  const [laneOffset, setLaneOffset] = useState(0.04)
  const [route, setRoute] = useState('Downtown Expressway')
  const [weather, setWeather] = useState('Clear / Daylight')
  const [isFCWActive, setIsFCWActive] = useState(false)
  const [isLaneDriftActive, setIsLaneDriftActive] = useState(false)

  // Default Driving Sample Videos
  const DEFAULT_VIDEOS = [
    { name: 'Dashcam_Video.mp4', size_mb: 67.9, is_active: true },
    { name: 'NavTesting_2.mp4', size_mb: 448.6, is_active: false },
    { name: 'NavTesting_3.mp4', size_mb: 447.9, is_active: false },
    { name: 'NavVideoForTesting.mp4', size_mb: 67.9, is_active: false },
  ]

  // Video Source & Subprocess State
  const [videos, setVideos] = useState(DEFAULT_VIDEOS)
  const [activeVideo, setActiveVideo] = useState('Dashcam_Video.mp4')
  const [uploading, setUploading] = useState(false)
  const [isProcessRunning, setIsProcessRunning] = useState(false)
  const [processPid, setProcessPid] = useState(null)
  const [startingProcess, setStartingProcess] = useState(false)

  // Backend Integration State
  const [backendStatus, setBackendStatus] = useState('Connecting...')
  const [reports, setReports] = useState([])
  const [generatingReport, setGeneratingReport] = useState(false)
  const [events, setEvents] = useState([
    { id: 1, time: new Date().toLocaleTimeString(), type: 'INFO', message: 'Cortexium 2.0 Vehicle Module Dashboard initialized.' },
    { id: 2, time: new Date().toLocaleTimeString(), type: 'INFO', message: 'CAN-Bus Telemetry & Native OpenCV 3D AR HUD engine ready.' },
  ])

  const fileInputRef = useRef(null)

  // ── Initial Data Fetch ─────────────────────────────────────
  useEffect(() => {
    fetchBackendStatus()
    fetchSampleVideos()
    fetchReports()

    const interval = setInterval(fetchBackendStatus, 3000)
    return () => clearInterval(interval)
  }, [])

  const fetchBackendStatus = async () => {
    try {
      const res = await fetch('/api/vehicle/status')
      if (res.ok) {
        const data = await res.json()
        setBackendStatus(data.status === 'active' ? 'ONLINE' : 'DEGRADED')
        if (data.active_video) setActiveVideo(data.active_video)
        setIsProcessRunning(!!data.is_process_running)
        setProcessPid(data.process_pid || null)
      } else {
        setBackendStatus('OFFLINE (Mock Mode)')
      }
    } catch (err) {
      setBackendStatus('OFFLINE (Mock Mode)')
    }
  }

  const fetchSampleVideos = async () => {
    try {
      const res = await fetch('/api/vehicle/sample-videos')
      if (res.ok) {
        const data = await res.json()
        if (data.videos && data.videos.length > 0) {
          setVideos(data.videos)
          return
        }
      }
    } catch (err) {
      console.log('Sample videos fetch fallback:', err)
    }
    setVideos(prev => (prev && prev.length > 0) ? prev : DEFAULT_VIDEOS)
  }

  const fetchReports = async () => {
    try {
      const res = await fetch('/api/vehicle/reports')
      if (res.ok) {
        const data = await res.json()
        if (data.reports) setReports(data.reports)
      }
    } catch (err) {
      console.log('PDF reports fetch fallback:', err)
    }
  }

  // ── Dynamic Telemetry Stream for Selected Video ─────────────
  useEffect(() => {
    let elapsedSec = 0
    const telemetryInterval = setInterval(async () => {
      elapsedSec += 0.6
      try {
        const res = await fetch(`/api/vehicle/telemetry?elapsed=${elapsedSec.toFixed(1)}`)
        if (res.ok) {
          const data = await res.json()
          if (data.speed_kmh !== undefined) setSpeed(data.speed_kmh)
          if (data.safety_score !== undefined) setSafetyScore(data.safety_score)
          if (data.min_distance_m !== undefined) setDistanceToLead(data.min_distance_m)
          if (data.lane_offset_m !== undefined) setLaneOffset(data.lane_offset_m)
          if (data.collision_risk !== undefined) setIsFCWActive(data.collision_risk)
          if (Math.abs(data.lane_offset_m || 0) > 0.4) setIsLaneDriftActive(true)
          else setIsLaneDriftActive(false)
        }
      } catch (err) {
        // Fallback simulation if backend offline
        setDistanceToLead(prev => parseFloat((Math.max(5.0, Math.min(60.0, prev + (Math.random() - 0.48) * 1.5))).toFixed(1)))
        setLaneOffset(prev => parseFloat((Math.max(-0.8, Math.min(0.8, prev + (Math.random() - 0.5) * 0.08))).toFixed(2)))
      }
    }, 600)

    return () => clearInterval(telemetryInterval)
  }, [activeVideo])

  // ── Start Native Main.py Process Window ─────────────────────
  const handleStartProcess = async (videoName = activeVideo) => {
    setStartingProcess(true)
    setActiveVideo(videoName)

    setEvents(prev => [{
      id: Date.now(),
      time: new Date().toLocaleTimeString(),
      type: 'INFO',
      message: `Launching native Cortexium main.py window for '${videoName}'...`
    }, ...prev])

    try {
      const res = await fetch('/api/vehicle/start-process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_name: videoName })
      })

      if (res.ok) {
        const data = await res.json()
        setIsProcessRunning(true)
        if (data.details && data.details.pid) setProcessPid(data.details.pid)
        setEvents(prev => [{
          id: Date.now(),
          time: new Date().toLocaleTimeString(),
          type: 'SUCCESS',
          message: `Native OpenCV 'CORTEXIUM OS' window opened! (PID: ${data.details?.pid || 'ACTIVE'})`
        }, ...prev])
      }
    } catch (err) {
      console.log('Start process error:', err)
      setEvents(prev => [{
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        type: 'ALERT',
        message: `Failed to launch native process: ${err.message}`
      }, ...prev])
    } finally {
      setStartingProcess(false)
      fetchBackendStatus()
    }
  }

  // ── Stop Process Window ─────────────────────────────────────
  const handleStopProcess = async () => {
    try {
      await fetch('/api/vehicle/stop-process', { method: 'POST' })
      setIsProcessRunning(false)
      setProcessPid(null)
      setEvents(prev => [{
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        type: 'INFO',
        message: 'Stopped native Cortexium main.py vision window.'
      }, ...prev])
    } catch (err) {
      console.log('Stop process error:', err)
    }
  }

  // ── Select Video Source ────────────────────────────────────
  const handleSelectVideo = async (videoName) => {
    setActiveVideo(videoName)
    setEvents(prev => [{
      id: Date.now(),
      time: new Date().toLocaleTimeString(),
      type: 'INFO',
      message: `Selected driving video source: '${videoName}'`
    }, ...prev])

    try {
      await fetch('/api/vehicle/select-video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_name: videoName })
      })
      fetchSampleVideos()
    } catch (err) {
      console.log('Select video error:', err)
    }
  }

  // ── Upload Custom Video ────────────────────────────────────
  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/vehicle/upload-video', {
        method: 'POST',
        body: formData
      })
      if (res.ok) {
        const data = await res.json()
        setActiveVideo(data.filename)
        setEvents(prev => [{
          id: Date.now(),
          time: new Date().toLocaleTimeString(),
          type: 'SUCCESS',
          message: `Uploaded new video: '${data.filename}'`
        }, ...prev])
        fetchSampleVideos()
      }
    } catch (err) {
      setEvents(prev => [{
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        type: 'ALERT',
        message: `Upload error: ${err.message}`
      }, ...prev])
    } finally {
      setUploading(false)
    }
  }

  // ── Generate PDF Report ─────────────────────────────────────
  const handleGenerateReport = async () => {
    setGeneratingReport(true)
    setEvents(prev => [{
      id: Date.now(),
      time: new Date().toLocaleTimeString(),
      type: 'INFO',
      message: `Compiling post-trip PDF report for '${activeVideo}'...`
    }, ...prev])

    try {
      const res = await fetch('/api/vehicle/report', { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        setEvents(prev => [{
          id: Date.now(),
          time: new Date().toLocaleTimeString(),
          type: 'SUCCESS',
          message: `Generated PDF Report: ${data.filename}`
        }, ...prev])
        fetchReports()
      }
    } catch (err) {
      console.log('Report error:', err)
    } finally {
      setGeneratingReport(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans hud-scanline">

      {/* ── HEADER ────────────────────────────────────────────────────── */}
      <header className="h-16 border-b border-cyan-500/20 bg-slate-900/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-4">
          <a
            href="/"
            className="flex items-center gap-2 text-cyan-400 hover:text-cyan-300 transition-colors bg-cyan-950/60 border border-cyan-500/30 px-3 py-1.5 rounded-lg text-xs font-semibold"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>GATEWAY DASHBOARD</span>
          </a>

          <div className="h-5 w-px bg-slate-800" />

          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Car className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-hud text-base font-bold tracking-wider text-slate-100">
                  CORTEXIUM 2.0
                </h1>
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">
                  MODULE III
                </span>
              </div>
              <p className="text-xs text-slate-400">Vehicle Telemetry & 3D AR HUD Perception Control Panel</p>
            </div>
          </div>
        </div>

        {/* Status & Quick Control */}
        <div className="flex items-center gap-4 text-xs font-mono">
          {isProcessRunning ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-950/80 border border-emerald-500/60 text-emerald-300">
              <Monitor className="w-3.5 h-3.5 animate-pulse text-emerald-400" />
              <span>NATIVE WINDOW ACTIVE (PID: {processPid || 'ACTIVE'})</span>
              <button
                onClick={handleStopProcess}
                className="ml-2 bg-rose-500/20 hover:bg-rose-500/40 text-rose-300 px-2.5 py-0.5 rounded text-[10px] font-bold transition-all"
              >
                STOP
              </button>
            </div>
          ) : (
            <button
              onClick={() => handleStartProcess(activeVideo)}
              disabled={startingProcess}
              className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/50 text-cyan-300 font-bold transition-all"
            >
              {startingProcess ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-cyan-300" />}
              <span>LAUNCH NATIVE VISION WINDOW</span>
            </button>
          )}

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-950 border border-slate-800">
            <Zap className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-slate-300">BACKEND: <strong className="text-cyan-400">{backendStatus}</strong></span>
          </div>
        </div>
      </header>

      {/* ── MAIN CONTENT ──────────────────────────────────────────────── */}
      <main className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 max-w-[1700px] mx-auto w-full">

        {/* ── LEFT & CENTER: VIDEO SELECTOR & LAUNCH CONTROL PANEL (8 Cols) ─ */}
        <div className="lg:col-span-8 flex flex-col gap-6">

          {/* 1. NATIVE WINDOW LAUNCH CONTROL HERO CARD */}
          <div className="hud-panel p-6 flex flex-col gap-6 border-cyan-500/40 relative overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-cyan-500/20 pb-4">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                  <Monitor className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="font-hud text-lg font-bold text-slate-100 tracking-wider">
                    NATIVE OPENCV 3D AR HUD WINDOW
                  </h2>
                  <p className="text-xs text-slate-400">Runs full-screen native perception engine with YOLOv8, 3D AR chevrons, & audio warnings.</p>
                </div>
              </div>

              {/* Status Badge */}
              <div className="flex items-center gap-2">
                <span className={`px-3 py-1 rounded-full text-xs font-mono font-bold flex items-center gap-2 border ${isProcessRunning
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                    : 'bg-slate-900 text-slate-400 border-slate-800'
                  }`}>
                  <span className={`w-2 h-2 rounded-full ${isProcessRunning ? 'bg-emerald-400 animate-ping' : 'bg-slate-600'}`} />
                  {isProcessRunning ? `RUNNING (PID: ${processPid})` : 'READY TO LAUNCH'}
                </span>
              </div>
            </div>

            {/* Launch Control Banner */}
            <div className="bg-slate-950/80 border border-cyan-500/30 p-6 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2 text-cyan-400 font-hud text-sm font-bold">
                  <Video className="w-4 h-4" />
                  <span>ACTIVE DRIVING VIDEO SOURCE:</span>
                </div>
                <div className="font-hud text-xl font-bold text-slate-100 glow-cyan truncate max-w-md">
                  {activeVideo}
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  Matched Telemetry: <span className="text-cyan-300">
                    {activeVideo.includes('NavTesting_2') ? 'data/telemetry_nav2.csv' :
                      activeVideo.includes('NavTesting_3') ? 'data/telemetry_nav3.csv' :
                        activeVideo.includes('NavVideo') ? 'data/telemetry_raw.csv' : 'data/telemetry.csv'}
                  </span> | Resolution: 540x960 AR HUD
                </div>
              </div>

              <div className="flex items-center gap-3 w-full md:w-auto">
                {isProcessRunning ? (
                  <button
                    onClick={handleStopProcess}
                    className="w-full md:w-auto flex items-center justify-center gap-3 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/50 px-6 py-3.5 rounded-xl font-hud font-bold text-sm transition-all shadow-lg shadow-rose-900/30"
                  >
                    <Square className="w-5 h-5 fill-rose-300" />
                    <span>STOP NATIVE WINDOW</span>
                  </button>
                ) : (
                  <button
                    onClick={() => handleStartProcess(activeVideo)}
                    disabled={startingProcess}
                    className="w-full md:w-auto flex items-center justify-center gap-3 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/50 px-8 py-3.5 rounded-xl font-hud font-bold text-sm transition-all shadow-lg shadow-cyan-500/20"
                  >
                    {startingProcess ? (
                      <>
                        <RefreshCw className="w-5 h-5 animate-spin" />
                        <span>LAUNCHING WINDOW...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-5 h-5 fill-cyan-300" />
                        <span>LAUNCH NATIVE VISION WINDOW</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Architecture Details Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
              <div className="bg-slate-950/60 border border-slate-800 p-3.5 rounded-xl flex items-center gap-3">
                <Cpu className="w-5 h-5 text-cyan-400 shrink-0" />
                <div>
                  <div className="text-slate-400">YOLOv8 PERCEPTION</div>
                  <div className="text-slate-200 font-bold">Vehicle & Ranging Detection</div>
                </div>
              </div>

              <div className="bg-slate-950/60 border border-slate-800 p-3.5 rounded-xl flex items-center gap-3">
                <Layers className="w-5 h-5 text-emerald-400 shrink-0" />
                <div>
                  <div className="text-slate-400">3D AR HUD PROJECTOR</div>
                  <div className="text-slate-200 font-bold">Perspective Lane Chevrons</div>
                </div>
              </div>

              <div className="bg-slate-950/60 border border-slate-800 p-3.5 rounded-xl flex items-center gap-3">
                <Shield className="w-5 h-5 text-purple-400 shrink-0" />
                <div>
                  <div className="text-slate-400">SAFETY RULE ENGINE</div>
                  <div className="text-slate-200 font-bold">FCW & Lane Drift Audio Alerts</div>
                </div>
              </div>
            </div>
          </div>

          {/* 2. VIDEO SELECTION & UPLOAD CARDS */}
          <div className="hud-panel p-5 flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-cyan-500/20 pb-3">
              <div className="flex items-center gap-2">
                <Film className="w-4 h-4 text-cyan-400" />
                <h2 className="font-hud text-sm font-bold text-cyan-400 tracking-wider">
                  SELECT DRIVING VIDEO & LAUNCH
                </h2>
              </div>

              {/* Custom Upload Button */}
              <div>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept="video/mp4,video/avi,video/mov"
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="flex items-center gap-2 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all"
                >
                  {uploading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  <span>{uploading ? 'UPLOADING...' : 'UPLOAD CUSTOM VIDEO'}</span>
                </button>
              </div>
            </div>

            {/* Video Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {videos.map((vid, idx) => {
                const isActive = vid.name === activeVideo
                return (
                  <div
                    key={vid.name}
                    className={`p-4 rounded-xl border flex flex-col justify-between gap-3 transition-all ${isActive
                        ? 'bg-cyan-950/60 border-cyan-400 shadow-lg shadow-cyan-500/20'
                        : 'bg-slate-950/70 border-slate-800 hover:border-slate-700'
                      }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="p-2 rounded-lg bg-slate-900 text-cyan-400">
                        <Video className="w-4 h-4" />
                      </div>
                      {isActive && (
                        <span className="px-2 py-0.5 rounded-full bg-cyan-400/20 border border-cyan-400 text-cyan-300 text-[10px] font-mono font-bold flex items-center gap-1">
                          <Check className="w-3 h-3 stroke-[3]" />
                          ACTIVE
                        </span>
                      )}
                    </div>

                    <div>
                      <div className="font-hud text-xs font-bold text-slate-100 truncate" title={vid.name}>
                        {vid.name}
                      </div>
                      <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                        VIDEO #{idx + 1} • {vid.size_mb} MB
                      </div>
                    </div>

                    <div className="flex flex-col gap-1.5 pt-1">
                      <button
                        onClick={() => handleSelectVideo(vid.name)}
                        className={`w-full py-1.5 rounded-lg text-[11px] font-semibold transition-all border ${isActive
                            ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                            : 'bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700'
                          }`}
                      >
                        {isActive ? 'SELECTED SOURCE' : 'SELECT SOURCE'}
                      </button>

                      <button
                        onClick={() => handleStartProcess(vid.name)}
                        disabled={startingProcess}
                        className="w-full flex items-center justify-center gap-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 py-1.5 rounded-lg text-[11px] font-bold transition-all"
                      >
                        <Play className="w-3 h-3 fill-emerald-300" />
                        <span>LAUNCH NATIVE</span>
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

        </div>

        {/* ── RIGHT COLUMN: DYNAMIC TELEMETRY GAUGES & PDF REPORTS (4 Cols) ─ */}
        <div className="lg:col-span-4 flex flex-col gap-6">

          {/* Dynamic Telemetry & Risk Gauges */}
          <div className="hud-panel p-5 flex flex-col gap-5">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
              <h2 className="font-hud text-sm font-bold text-cyan-400 tracking-wider flex items-center gap-2">
                <Activity className="w-4 h-4" />
                DYNAMIC TELEMETRY & RISK GAUGES
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 border border-cyan-500/40 text-cyan-400">
                LIVE CSV SYNC
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Safety Score */}
              <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl flex flex-col items-center justify-center text-center">
                <div className="text-xs font-mono text-slate-400 mb-2">SAFETY SCORE</div>
                <div className={`font-hud text-4xl font-bold transition-colors ${safetyScore >= 85 ? 'text-emerald-400 glow-emerald' :
                    safetyScore >= 70 ? 'text-amber-400' : 'text-rose-500 glow-rose'
                  }`}>
                  {safetyScore}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">DYNAMIC INDEX 0-100</div>
              </div>

              {/* Distance */}
              <div className={`border p-4 rounded-xl flex flex-col items-center justify-center text-center transition-all ${isFCWActive ? 'bg-rose-950/40 border-rose-500/60' : 'bg-slate-950/80 border-slate-800'
                }`}>
                <div className="text-xs font-mono text-slate-400 mb-2">LEAD DISTANCE</div>
                <div className={`font-hud text-3xl font-bold transition-colors ${isFCWActive ? 'text-rose-400 glow-rose' : 'text-cyan-400'}`}>
                  {distanceToLead}m
                </div>
                <div className="text-[10px] font-mono text-slate-400 mt-1">SAFE: &gt;12m</div>
              </div>
            </div>

            {/* Dynamic Speed Gauge */}
            <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl flex flex-col gap-2">
              <div className="flex justify-between items-center text-xs font-mono text-slate-400">
                <span>DYNAMIC SPEED</span>
                <span className="text-cyan-400 font-hud font-bold text-base">{speed} km/h</span>
              </div>
              <div className="relative w-full h-2.5 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all duration-500"
                  style={{ width: `${Math.min(100, (speed / 140) * 100)}%` }}
                />
              </div>
            </div>

            {/* Dynamic Lane Offset Bar Meter */}
            <div className="bg-slate-950/80 border border-slate-800 p-4 rounded-xl">
              <div className="flex justify-between items-center text-xs font-mono text-slate-400 mb-2">
                <span>LANE DRIFT OFFSET</span>
                <span className={`font-bold transition-colors ${isLaneDriftActive ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {laneOffset > 0 ? `+${laneOffset}m (R)` : `${laneOffset}m (L)`}
                </span>
              </div>
              <div className="relative w-full h-3 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-cyan-400/50 -translate-x-1/2" />
                <div
                  className={`absolute top-0 bottom-0 transition-all duration-300 rounded-full ${isLaneDriftActive ? 'bg-rose-500 shadow-lg shadow-rose-500/50' : 'bg-cyan-400'
                    }`}
                  style={{
                    left: `${50 + laneOffset * 40}%`,
                    width: '8px',
                    transform: 'translateX(-50%)'
                  }}
                />
              </div>
            </div>
          </div>

          {/* Event Log & PDF Report Actions */}
          <div className="hud-panel p-5 flex flex-col gap-4 flex-1">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
              <h2 className="font-hud text-sm font-bold text-cyan-400 tracking-wider flex items-center gap-2">
                <Radio className="w-4 h-4" />
                SYSTEM PERCEPTION LOGS
              </h2>
            </div>

            <div className="flex-1 min-h-[140px] max-h-[220px] overflow-y-auto flex flex-col gap-2 font-mono text-xs pr-1">
              {events.map((evt) => (
                <div
                  key={evt.id}
                  className="bg-slate-950/60 border border-slate-800/80 p-2.5 rounded-lg flex items-start gap-2.5"
                >
                  <span className="text-slate-500 text-[10px] shrink-0 mt-0.5">{evt.time}</span>
                  <div className="flex-1">
                    <span className={`font-bold mr-1.5 ${evt.type === 'SUCCESS' ? 'text-emerald-400' :
                        evt.type === 'ALERT' ? 'text-rose-400' : 'text-cyan-400'
                      }`}>
                      [{evt.type}]
                    </span>
                    <span className="text-slate-300">{evt.message}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* PDF Report Generation Button & Downloads */}
            <div className="pt-2 border-t border-cyan-500/20 flex flex-col gap-3">
              <button
                onClick={handleGenerateReport}
                disabled={generatingReport}
                className="w-full flex items-center justify-center gap-2 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 py-2.5 rounded-xl font-hud font-bold text-xs transition-all disabled:opacity-50"
              >
                {generatingReport ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>COMPILING POST-TRIP PDF REPORT...</span>
                  </>
                ) : (
                  <>
                    <FileText className="w-4 h-4" />
                    <span>GENERATE POST-TRIP PDF REPORT</span>
                  </>
                )}
              </button>

              {/* Available PDF Downloads */}
              {reports.length > 0 && (
                <div className="flex flex-col gap-1.5 mt-1">
                  <div className="text-[11px] font-mono text-slate-400">COMPLETED PDF REPORTS:</div>
                  <div className="flex flex-col gap-1 max-h-24 overflow-y-auto">
                    {reports.map((rep, idx) => (
                      <a
                        key={idx}
                        href={typeof rep === 'string' ? `/api/vehicle/pdf/${rep}` : (rep.download_url || `/api/vehicle/pdf/${rep.filename}`)}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center justify-between bg-slate-950 px-3 py-1.5 rounded border border-slate-800 text-xs text-slate-300 hover:text-cyan-400 transition-colors"
                      >
                        <span className="truncate">{typeof rep === 'string' ? rep : (rep.filename || String(rep.name || 'Report'))}</span>
                        <Download className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>
      </main>

    </div>
  )
}
