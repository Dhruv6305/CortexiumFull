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
  Zap,
  CheckCircle2,
  ArrowLeft,
  Upload,
  Video,
  Film,
  Check,
  RotateCcw,
  Monitor,
  ExternalLink,
  ChevronRight,
  ChevronDown,
  X,
  FileVideo,
  Settings,
  User,
  LayoutDashboard,
  Layers,
  Database,
  Users,
  Box
} from 'lucide-react'

export default function App() {
  // ── State ──────────────────────────────────────────────────
  const [speed, setSpeed] = useState(68)
  const [safetyScore, setSafetyScore] = useState(94)
  const [distanceToLead, setDistanceToLead] = useState(24.5)
  const [laneOffset, setLaneOffset] = useState(0.04)
  const [isFCWActive, setIsFCWActive] = useState(false)
  const [isLaneDriftActive, setIsLaneDriftActive] = useState(false)

  // Default Driving Sample Videos fallback
  const DEFAULT_VIDEOS = [
    { name: 'NavVideoForTesting.mp4', size_mb: 67.9, is_active: true },
    { name: 'NavTesting_2.mp4', size_mb: 448.6, is_active: false },
    { name: 'NavTesting_3.mp4', size_mb: 447.9, is_active: false },
    { name: 'Dashcam_Video.mp4', size_mb: 67.9, is_active: false },
  ]

  // Video Source & Subprocess State
  const [videos, setVideos] = useState(DEFAULT_VIDEOS)
  const [selectedVideo, setSelectedVideo] = useState('NavVideoForTesting.mp4')
  const [activeVideo, setActiveVideo] = useState('NavVideoForTesting.mp4')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadSuccess, setUploadSuccess] = useState(null)
  const [isProcessRunning, setIsProcessRunning] = useState(false)
  const [processPid, setProcessPid] = useState(null)
  const [startingProcess, setStartingProcess] = useState(false)
  const [processError, setProcessError] = useState(null)

  // Active playing elapsed timer
  const [playElapsedSec, setPlayElapsedSec] = useState(0)

  // Backend Integration State
  const [backendStatus, setBackendStatus] = useState('Connecting...')
  const [reports, setReports] = useState([])
  const [generatingReport, setGeneratingReport] = useState(false)
  const [gpsSimActive, setGpsSimActive] = useState(true)

  // Modules Nav Dropdown State
  const [modulesOpen, setModulesOpen] = useState(true)
  const [topModulesOpen, setTopModulesOpen] = useState(false)

  const getModuleUrl = (path) => {
    if (typeof window !== 'undefined' && window.location.port === '3023') {
      return `http://${window.location.hostname}:3020${path}`
    }
    return path
  }

  const getDashboardUrl = () => {
    if (typeof window !== 'undefined' && window.location.port === '3023') {
      return `http://${window.location.hostname}:3020/`
    }
    return '/'
  }

  // Main View Switcher ('workspace' | 'data')
  const [currentView, setCurrentView] = useState('workspace')
  const [telemetryData, setTelemetryData] = useState(null)
  const [loadingTelemetry, setLoadingTelemetry] = useState(false)

  const fetchTelemetryData = async (videoName = selectedVideo) => {
    setLoadingTelemetry(true)
    try {
      const res = await fetch(`/api/vehicle/telemetry-data?video_name=${encodeURIComponent(videoName)}`)
      if (res.ok) {
        const data = await res.json()
        setTelemetryData(data)
      } else {
        setTelemetryData({ has_telemetry: false, video_name: videoName, message: 'Could not load telemetry' })
      }
    } catch (err) {
      setTelemetryData({ has_telemetry: false, video_name: videoName, message: 'Network error loading telemetry' })
    } finally {
      setLoadingTelemetry(false)
    }
  }

  useEffect(() => {
    if (currentView === 'data') {
      fetchTelemetryData(selectedVideo)
    }
  }, [selectedVideo, currentView])

  const fileInputRef = useRef(null)

  // ── Initial Data Fetch ─────────────────────────────────────
  useEffect(() => {
    fetchBackendStatus()
    fetchSampleVideos()
    fetchReports()

    const interval = setInterval(fetchBackendStatus, 2500)
    return () => clearInterval(interval)
  }, [])

  // Timer for active running session
  useEffect(() => {
    let timer = null
    if (isProcessRunning) {
      timer = setInterval(() => {
        setPlayElapsedSec(prev => prev + 1)
      }, 1000)
    } else {
      setPlayElapsedSec(0)
    }
    return () => {
      if (timer) clearInterval(timer)
    }
  }, [isProcessRunning])

  const fetchBackendStatus = async () => {
    try {
      const res = await fetch('/api/vehicle/status')
      if (res.ok) {
        const data = await res.json()
        setBackendStatus(data.status === 'active' ? 'ONLINE' : 'DEGRADED')
        if (data.active_video) {
          setActiveVideo(data.active_video)
        }
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
          // Find currently active
          const active = data.videos.find(v => v.is_active)
          if (active) {
            setSelectedVideo(active.name)
            setActiveVideo(active.name)
          }
          return
        }
      }
    } catch (err) {
      console.log('Sample videos fetch fallback:', err)
    }
    setVideos(prev => (prev && prev.length > 0 ? prev : DEFAULT_VIDEOS))
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
        // Fallback simulation
        setDistanceToLead(prev => parseFloat(Math.max(5.0, Math.min(60.0, prev + (Math.random() - 0.48) * 1.5)).toFixed(1)))
        setLaneOffset(prev => parseFloat(Math.max(-0.8, Math.min(0.8, prev + (Math.random() - 0.5) * 0.08)).toFixed(2)))
      }
    }, 600)

    return () => clearInterval(telemetryInterval)
  }, [activeVideo])

  // ── Start Native Main.py Process Window ─────────────────────
  const handleStartProcess = async (videoName = selectedVideo) => {
    setStartingProcess(true)
    setProcessError(null)
    setActiveVideo(videoName)

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
      } else {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Could not launch native OpenCV window.')
      }
    } catch (err) {
      console.log('Start process error:', err)
      setProcessError(err.message)
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
    } catch (err) {
      console.log('Stop process error:', err)
    }
  }

  // ── Select Sample Video ─────────────────────────────────────
  const handleSelectSample = async (videoName) => {
    setSelectedVideo(videoName)
    setUploadError(null)
    try {
      await fetch('/api/vehicle/select-video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_name: videoName })
      })
      setActiveVideo(videoName)
    } catch (err) {
      console.log('Select video error:', err)
    }
  }

  // ── Upload Custom Video ─────────────────────────────────────
  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) handleProcessUpload(file)
  }

  const handleProcessUpload = async (file) => {
    const validExts = ['.mp4', '.avi', '.mov']
    const hasValidExt = validExts.some(ext => file.name.toLowerCase().endsWith(ext))
    if (!hasValidExt) {
      setUploadError('Invalid file format. Please upload an MP4, AVI, or MOV video.')
      return
    }

    if (file.size > 500 * 1024 * 1024) {
      setUploadError('File exceeds 500MB size limit.')
      return
    }

    setUploading(true)
    setUploadError(null)
    setUploadSuccess(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/vehicle/upload-video', {
        method: 'POST',
        body: formData
      })

      if (res.ok) {
        const data = await res.json()
        setSelectedVideo(data.filename)
        setActiveVideo(data.filename)
        setUploadSuccess(`Uploaded "${data.filename}" successfully.`)
        setTimeout(() => setUploadSuccess(null), 5000)
        fetchSampleVideos()
      } else {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Upload failed.')
      }
    } catch (err) {
      setUploadError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleProcessUpload(e.dataTransfer.files[0])
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
  }

  // ── Generate PDF Report ─────────────────────────────────────
  const handleGenerateReport = async () => {
    setGeneratingReport(true)
    try {
      const res = await fetch('/api/vehicle/report', { method: 'POST' })
      if (res.ok) {
        fetchReports()
      }
    } catch (err) {
      console.log('Report error:', err)
    } finally {
      setGeneratingReport(false)
    }
  }

  const formatSec = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }

  return (
    <div className="min-h-screen bg-[#0B0F17] text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30">

      {/* ── TOP APP BAR ─────────────────────────────────────────── */}
      <header className="h-16 border-b border-white/[0.08] bg-[#0E131F]/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-4">
          <a
            href={getDashboardUrl()}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors bg-white/[0.05] border border-white/[0.08] px-3 py-1.5 rounded-xl text-xs font-medium"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Dashboard</span>
          </a>

          <div className="h-4 w-px bg-white/[0.08]" />

          {/* Top Bar Switch Modules Dropdown */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setTopModulesOpen(!topModulesOpen)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-medium text-slate-300 hover:text-white transition-all cursor-pointer"
            >
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              <span>Switch Module</span>
              <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${topModulesOpen ? 'rotate-180' : ''}`} />
            </button>

            {topModulesOpen && (
              <div
                className="absolute top-full left-0 mt-2 w-56 rounded-2xl bg-[#0E131F] border border-white/[0.12] shadow-2xl p-2 z-50 flex flex-col gap-1 backdrop-blur-xl"
                onMouseLeave={() => setTopModulesOpen(false)}
              >
                <span className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-slate-500 font-semibold">
                  Cortexium Ecosystem
                </span>

                <a
                  href={getModuleUrl('/module/social')}
                  className="flex items-center justify-between p-2 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-white/[0.06] transition-all"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="w-6 h-6 rounded-lg bg-cyan-500/10 flex items-center justify-center text-cyan-400">
                      <Users className="w-3.5 h-3.5" />
                    </div>
                    <span>Social Intelligence</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">:3021</span>
                </a>

                <a
                  href={getModuleUrl('/module/organizer')}
                  className="flex items-center justify-between p-2 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-white/[0.06] transition-all"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="w-6 h-6 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                      <Box className="w-3.5 h-3.5" />
                    </div>
                    <span>Spatial Organizer</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">:3022</span>
                </a>

                <a
                  href={getModuleUrl('/module/vehicle')}
                  className="flex items-center justify-between p-2 rounded-xl text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 font-semibold"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="w-6 h-6 rounded-lg bg-amber-500/20 flex items-center justify-center text-amber-400">
                      <Car className="w-3.5 h-3.5" />
                    </div>
                    <span>Vehicle HUD</span>
                  </div>
                  <span className="text-[10px] font-mono text-emerald-400">Active</span>
                </a>
              </div>
            )}
          </div>

          <div className="h-4 w-px bg-white/[0.08]" />

          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
              <Car className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-slate-100 tracking-wide">Cortexium</span>
                <span className="text-xs text-slate-400">Vehicle Intelligence</span>
              </div>
            </div>
          </div>
        </div>

        {/* Backend & Running Indicator */}
        <div className="flex items-center gap-3 text-xs">
          {isProcessRunning ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Analysis Window Active {processPid ? `(PID ${processPid})` : ''}</span>
              <button
                onClick={handleStopProcess}
                className="ml-2 bg-rose-500/20 hover:bg-rose-500/40 text-rose-300 px-2.5 py-0.5 rounded-md text-[11px] font-medium transition-all"
              >
                Stop
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-slate-400">
              <span className="w-2 h-2 rounded-full bg-slate-500" />
              <span>Standby</span>
            </div>
          )}

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-slate-400 font-mono text-[11px]">
            <span>API:</span>
            <span className={backendStatus === 'ONLINE' ? 'text-emerald-400 font-semibold' : 'text-amber-400 font-semibold'}>
              {backendStatus}
            </span>
          </div>
        </div>
      </header>

      {/* ── MAIN WORKSPACE ───────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">

        {/* ── 1. LEFT SIDEBAR NAVIGATION ─────────────────────────── */}
        <aside className="w-64 border-r border-white/[0.08] bg-[#0E131F]/50 flex flex-col p-4 gap-6 shrink-0 overflow-y-auto">
          {/* Main Nav Links */}
          <div className="flex flex-col gap-1">
            <a
              href={getDashboardUrl()}
              className="flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-100 hover:bg-white/[0.04] transition-colors"
            >
              <LayoutDashboard className="w-4 h-4" />
              <span>Dashboard</span>
            </a>

            {/* Modules Accordion Toggle */}
            <button
              type="button"
              onClick={() => setModulesOpen(!modulesOpen)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium text-slate-300 hover:text-white hover:bg-white/[0.04] transition-all cursor-pointer"
            >
              <div className="flex items-center gap-3">
                <Layers className="w-4 h-4 text-cyan-400" />
                <span>Modules</span>
              </div>
              <ChevronDown
                className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${modulesOpen ? 'rotate-0' : '-rotate-90'}`}
              />
            </button>

            {/* Expanded Modules Sub-List */}
            {modulesOpen && (
              <div className="flex flex-col gap-1 pl-2.5 my-1 border-l border-white/[0.08] ml-4">
                {/* 1. Social Intelligence */}
                <a
                  href={getModuleUrl('/module/social')}
                  className="flex items-center justify-between px-2.5 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-cyan-300 hover:bg-cyan-500/10 transition-all group"
                >
                  <div className="flex items-center gap-2">
                    <Users className="w-3.5 h-3.5 text-cyan-400 group-hover:scale-110 transition-transform" />
                    <span>Social Recall</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 group-hover:text-cyan-400">
                    :3021
                  </span>
                </a>

                {/* 2. Spatial Organizer */}
                <a
                  href={getModuleUrl('/module/organizer')}
                  className="flex items-center justify-between px-2.5 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-emerald-300 hover:bg-emerald-500/10 transition-all group"
                >
                  <div className="flex items-center gap-2">
                    <Box className="w-3.5 h-3.5 text-emerald-400 group-hover:scale-110 transition-transform" />
                    <span>Spatial Memory</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 group-hover:text-emerald-400">
                    :3022
                  </span>
                </a>

                {/* 3. Vehicle Intelligence (Current Active) */}
                <button
                  type="button"
                  onClick={() => setCurrentView('workspace')}
                  className={`w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-xs transition-all cursor-pointer ${
                    currentView === 'workspace'
                      ? 'font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/20 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Car className="w-3.5 h-3.5 text-amber-400" />
                    <span>Vehicle HUD</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span className="text-[10px] font-mono text-emerald-400">Active</span>
                  </div>
                </button>
              </div>
            )}
          </div>

          {/* Grouped Section: Sample Videos */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between px-2">
              <span className="text-[11px] font-semibold text-slate-400 tracking-wider uppercase">
                Sample Videos
              </span>
              <span className="text-[10px] text-slate-500 font-mono">{videos.length}</span>
            </div>

            <div className="flex flex-col gap-1">
              {videos.map((vid) => {
                const isSelected = selectedVideo === vid.name
                const isPlayingThis = isProcessRunning && activeVideo === vid.name

                return (
                  <button
                    key={vid.name}
                    onClick={() => handleSelectSample(vid.name)}
                    className={`w-full text-left px-3 py-2.5 rounded-xl text-xs transition-all flex items-center justify-between group cursor-pointer ${
                      isSelected
                        ? 'bg-amber-100 text-slate-900 font-semibold shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <Film className={`w-3.5 h-3.5 shrink-0 ${isSelected ? 'text-slate-900' : 'text-slate-500 group-hover:text-slate-300'}`} />
                      <span className="truncate">{vid.name}</span>
                    </div>

                    {isPlayingThis ? (
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0 ml-2" />
                    ) : vid.size_mb ? (
                      <span className={`text-[10px] font-mono shrink-0 ml-2 ${isSelected ? 'text-slate-700' : 'text-slate-500'}`}>
                        {vid.size_mb}MB
                      </span>
                    ) : null}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Secondary Nav Links: Vehicle Data (Settings removed) */}
          <div className="flex flex-col gap-1 pt-2 border-t border-white/[0.06]">
            <button
              type="button"
              onClick={() => setCurrentView('data')}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-medium transition-all cursor-pointer ${
                currentView === 'data'
                  ? 'bg-amber-100 text-slate-900 font-bold shadow-md active:scale-95'
                  : 'text-slate-300 hover:text-white hover:bg-white/[0.05]'
              }`}
            >
              <div className="flex items-center gap-3">
                <Database className={`w-4 h-4 ${currentView === 'data' ? 'text-slate-900' : 'text-cyan-400'}`} />
                <span>Vehicle Data</span>
              </div>
              {currentView === 'data' ? (
                <span className="w-1.5 h-1.5 rounded-full bg-slate-900" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
              )}
            </button>
          </div>

          {/* User Profile at Bottom */}
          <div className="mt-auto pt-4 border-t border-white/[0.06] flex items-center gap-3 px-2">
            <div className="w-7 h-7 rounded-full bg-white/[0.08] flex items-center justify-center text-slate-300">
              <User className="w-3.5 h-3.5" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-medium text-slate-300">Driver Profile</span>
              <span className="text-[10px] text-slate-500">Autonomous HUD Active</span>
            </div>
          </div>
        </aside>

        {/* ── 2. CENTER WORKSPACE OR VEHICLE DATA ──── */}
        <main className={`flex-1 p-8 overflow-y-auto flex flex-col gap-6 w-full ${currentView === 'data' ? 'max-w-5xl' : 'max-w-4xl'} mx-auto`}>

          {currentView === 'data' ? (
            /* ── VEHICLE DATA TELEMETRY VIEW ── */
            <div className="flex flex-col gap-6">
              {/* Header Title & Return Button */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
                <div>
                  <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2.5">
                    <Database className="w-5 h-5 text-cyan-400" />
                    <span>Vehicle Telemetry Data</span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Telemetry inspection for footage: <span className="font-mono text-cyan-300 font-semibold">{selectedVideo}</span>
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setCurrentView('workspace')}
                  className="px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.10] text-xs font-semibold text-slate-200 transition-all flex items-center gap-2 cursor-pointer active:scale-95 w-fit"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Return to Workspace</span>
                </button>
              </div>

              {loadingTelemetry ? (
                <div className="p-16 rounded-2xl bg-white/[0.02] border border-white/[0.06] flex flex-col items-center justify-center text-center gap-3">
                  <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
                  <span className="text-xs text-slate-400 font-mono">Loading telemetry dataset…</span>
                </div>
              ) : telemetryData?.has_telemetry ? (
                /* ── Telemetry Exists: Metric Cards + Data Table ── */
                <div className="flex flex-col gap-6">
                  {/* Summary Metric Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.08] flex flex-col">
                      <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Dataset File</span>
                      <span className="text-sm font-bold text-cyan-300 font-mono mt-1 truncate">
                        {telemetryData.telemetry_file}
                      </span>
                      <span className="text-[10px] text-slate-500 mt-0.5">Matched CSV</span>
                    </div>

                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.08] flex flex-col">
                      <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Total Records</span>
                      <span className="text-xl font-bold text-slate-100 font-mono mt-1">
                        {telemetryData.total_records}
                      </span>
                      <span className="text-[10px] text-slate-500 mt-0.5">Synced frames</span>
                    </div>

                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.08] flex flex-col">
                      <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Duration</span>
                      <span className="text-xl font-bold text-emerald-300 font-mono mt-1">
                        {telemetryData.duration_sec}s
                      </span>
                      <span className="text-[10px] text-slate-500 mt-0.5">Elapsed time</span>
                    </div>

                    <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.08] flex flex-col">
                      <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Max / Avg Speed</span>
                      <span className="text-base font-bold text-amber-300 font-mono mt-1">
                        {telemetryData.max_speed} / {telemetryData.avg_speed} <span className="text-xs font-normal text-slate-400">km/h</span>
                      </span>
                      <span className="text-[10px] text-slate-500 mt-0.5">Speed dynamics</span>
                    </div>
                  </div>

                  {/* Telemetry Table Container */}
                  <div className="rounded-2xl bg-white/[0.02] border border-white/[0.08] overflow-hidden flex flex-col shadow-xl">
                    <div className="p-4 bg-white/[0.03] border-b border-white/[0.06] flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-200">
                        Recorded Telemetry Frames ({telemetryData.records?.length} entries)
                      </span>
                      <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        GPS & Dynamics Synced
                      </span>
                    </div>

                    <div className="overflow-x-auto max-h-[460px] overflow-y-auto">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-[#0E131F] sticky top-0 border-b border-white/[0.08] text-[11px] text-slate-400">
                          <tr>
                            <th className="p-3 font-semibold">Frame #</th>
                            <th className="p-3 font-semibold">Time (s)</th>
                            <th className="p-3 font-semibold">Speed (km/h)</th>
                            <th className="p-3 font-semibold">Latitude</th>
                            <th className="p-3 font-semibold">Longitude</th>
                            <th className="p-3 font-semibold">Heading (deg)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.04] text-slate-300">
                          {telemetryData.records?.map((row, idx) => (
                            <tr key={idx} className="hover:bg-white/[0.03] transition-colors">
                              <td className="p-3 text-slate-400">{row.frame_idx ?? idx}</td>
                              <td className="p-3 text-cyan-300">{typeof row.timestamp_sec === 'number' ? row.timestamp_sec.toFixed(2) : (row.timestamp_sec ?? '-')}</td>
                              <td className="p-3 text-amber-300 font-semibold">{row.speed_kmh ?? row.speed ?? '-'}</td>
                              <td className="p-3 text-slate-300">{row.latitude ? Number(row.latitude).toFixed(4) : '-'}</td>
                              <td className="p-3 text-slate-300">{row.longitude ? Number(row.longitude).toFixed(4) : '-'}</td>
                              <td className="p-3 text-slate-400">{row.heading_deg ?? row.heading ?? '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : (
                /* ── No Telemetry Exists for this Video ── */
                <div className="p-12 rounded-2xl bg-white/[0.02] border border-white/[0.08] flex flex-col items-center justify-center text-center gap-5">
                  <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shadow-md">
                    <AlertTriangle className="w-7 h-7" />
                  </div>

                  <div className="flex flex-col gap-1.5 max-w-lg">
                    <h3 className="text-lg font-bold text-slate-100">
                      No Telemetry Data Exists
                    </h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      No synchronized telemetry dataset was found for <span className="font-mono text-amber-300 font-semibold">"{selectedVideo}"</span>. This video operates in computer vision perception mode without vehicle dynamics data.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06] flex flex-col gap-2 max-w-md w-full text-left">
                    <span className="text-[11px] font-semibold text-slate-300">
                      Select driving footage with pre-recorded telemetry:
                    </span>
                    <div className="flex flex-col gap-1.5">
                      {['NavVideoForTesting.mp4', 'NavTesting_2.mp4', 'NavTesting_3.mp4'].map(name => (
                        <button
                          key={name}
                          type="button"
                          onClick={() => handleSelectSample(name)}
                          className="px-3 py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-slate-200 font-mono transition-all flex items-center justify-between group cursor-pointer"
                        >
                          <div className="flex items-center gap-2">
                            <Film className="w-3.5 h-3.5 text-cyan-400 group-hover:scale-110 transition-transform" />
                            <span>{name}</span>
                          </div>
                          <span className="text-[10px] text-emerald-400">View Telemetry →</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* ── NORMAL VIDEO WORKSPACE VIEW ── */
            <>
              {/* Header Title */}
              <div>
                <h2 className="text-xl font-bold text-slate-100">Video Workspace</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Select or upload driving footage. High-precision 3D AR HUD runs inside the native analysis window.
                </p>
              </div>

          {/* Inline Banners */}
          {uploadError && (
            <div className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                <span>{uploadError}</span>
              </div>
              <button onClick={() => setUploadError(null)} className="text-red-400 hover:text-white">✕</button>
            </div>
          )}

          {uploadSuccess && (
            <div className="px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{uploadSuccess}</span>
              </div>
              <button onClick={() => setUploadSuccess(null)} className="text-emerald-400 hover:text-white">✕</button>
            </div>
          )}

          {processError && (
            <div className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                <span>Launcher Notice: {processError}</span>
              </div>
              <button onClick={() => setProcessError(null)} className="text-red-400 hover:text-white">✕</button>
            </div>
          )}

          {/* ── STATE A: NOT RUNNING — DRAG & DROP UPLOAD ZONE & LAUNCHER ── */}
          {!isProcessRunning ? (
            <div className="flex flex-col gap-6">

              {/* Upload Drop Zone */}
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                className="relative rounded-2xl border-2 border-dashed border-white/[0.12] hover:border-cyan-500/40 bg-white/[0.02] p-12 flex flex-col items-center justify-center text-center gap-4 transition-all group"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".mp4,.mov,.avi"
                  onChange={handleFileChange}
                  className="hidden"
                />

                <div className="w-16 h-16 rounded-2xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-slate-300 group-hover:scale-105 transition-transform">
                  <Upload className="w-7 h-7 text-amber-200" />
                </div>

                <div className="flex flex-col gap-1">
                  <span className="text-base font-semibold text-slate-100">Upload a driving video</span>
                  <span className="text-xs text-slate-400">Drag and drop file here, or browse files</span>
                </div>

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="px-5 py-2.5 rounded-xl bg-white/[0.08] hover:bg-white/[0.14] border border-white/[0.12] text-xs font-semibold text-white transition-all shadow-sm"
                >
                  {uploading ? 'Uploading…' : 'Browse files'}
                </button>

                <p className="text-[11px] text-slate-500 mt-2">
                  Accepted formats: MP4, MOV, AVI (max 500MB)
                </p>
              </div>

              {/* Selected File Chip & Primary Launcher Button */}
              <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-white/[0.03] border border-white/[0.08]">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                    <FileVideo className="w-4 h-4" />
                  </div>
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-slate-100">{selectedVideo}</span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {videos.find(v => v.name === selectedVideo)?.size_mb ? `${videos.find(v => v.name === selectedVideo).size_mb} MB` : 'Ready'}
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-400">Selected driving footage for analysis</span>
                  </div>
                </div>

                <button
                  onClick={() => handleStartProcess(selectedVideo)}
                  disabled={startingProcess}
                  className="px-6 py-3 rounded-xl bg-amber-100 hover:bg-amber-200 text-slate-900 font-bold text-xs transition-all shadow-md flex items-center gap-2 active:scale-95"
                >
                  {startingProcess ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Opening window…</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5 fill-slate-900" />
                      <span>Open in Cortexium window</span>
                    </>
                  )}
                </button>
              </div>

              {/* Advisory Card */}
              <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] flex items-center justify-between text-xs text-slate-400">
                <span>Playback opens in the Cortexium analysis window for accurate overlays.</span>
                <span className="px-2.5 py-1 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Ready to launch
                </span>
              </div>

            </div>
          ) : (
            /* ── STATE B: ACTIVE ANALYSIS PLAYING STATE ───────────── */
            <div className="flex flex-col gap-6">

              {/* Main Analysis Status Card */}
              <div className="p-8 rounded-2xl bg-white/[0.03] border border-white/[0.10] flex flex-col items-center justify-center text-center gap-5 relative overflow-hidden">
                <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shadow-lg shadow-emerald-500/20">
                  <span className="w-3.5 h-3.5 rounded-full bg-emerald-400 animate-ping" />
                </div>

                <div className="flex flex-col gap-1">
                  <h3 className="text-xl font-bold text-slate-100">{activeVideo}</h3>
                  <p className="text-xs text-slate-400">
                    Currently playing in Cortexium OpenCV analysis window with live AR HUD overlay
                  </p>
                </div>

                <div className="px-4 py-1.5 rounded-full bg-white/[0.06] border border-white/[0.08] text-xs font-mono text-cyan-300">
                  Elapsed: {formatSec(playElapsedSec)}
                </div>

                <button
                  onClick={handleStopProcess}
                  className="px-6 py-2.5 rounded-xl bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 font-semibold text-xs transition-all flex items-center gap-2 shadow-lg shadow-red-950/40"
                >
                  <Square className="w-3.5 h-3.5 fill-red-300" />
                  <span>Stop Analysis Window</span>
                </button>
              </div>

              {/* Live Telemetry Glanceable Chips */}
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] flex flex-col items-center text-center">
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider">Speed</span>
                  <span className="text-xl font-bold text-slate-100 font-mono mt-1">{speed} <span className="text-xs font-normal text-slate-400">km/h</span></span>
                </div>

                <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] flex flex-col items-center text-center">
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider">Headway Gap</span>
                  <span className="text-xl font-bold text-cyan-300 font-mono mt-1">{distanceToLead} <span className="text-xs font-normal text-slate-400">m</span></span>
                  <span className={`text-[10px] mt-0.5 ${distanceToLead < 12 ? 'text-amber-400' : 'text-emerald-400'}`}>
                    {distanceToLead < 12 ? 'Close Gap' : 'Safe Gap'}
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] flex flex-col items-center text-center">
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider">Risk Assessment</span>
                  <span className={`text-base font-bold mt-1.5 ${isFCWActive ? 'text-rose-400' : 'text-emerald-400'}`}>
                    {isFCWActive ? 'Elevated' : 'Optimal Pace'}
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono mt-0.5">Score: {safetyScore}/100</span>
                </div>
              </div>

                </div>
              )}

            </>
          )}

        </main>

        {/* ── 3. RIGHT PANEL (PDF SESSION REPORTS ONLY) ─── */}
        <aside className="w-80 border-l border-white/[0.08] bg-[#0E131F]/50 p-6 flex flex-col gap-6 shrink-0 overflow-y-auto">

          {/* Session Reports Download Card */}
          <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/[0.08] flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-semibold text-slate-200">Session Reports</span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.05] text-slate-400 border border-white/[0.08]">
                PDF Logs
              </span>
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed">
              Diagnostic post-trip safety reports and telemetry logs available for download.
            </p>

            {reports.length > 0 ? (
              <div className="flex flex-col gap-2 pt-2 border-t border-white/[0.06]">
                <span className="text-[10px] text-slate-400 font-medium">Available Reports ({reports.length})</span>
                {reports.map((r, i) => (
                  <a
                    key={i}
                    href={r.download_url}
                    download
                    className="flex items-center justify-between p-2.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.06] text-xs text-slate-300 font-mono transition-all group"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <FileText className="w-3.5 h-3.5 text-slate-400 group-hover:text-cyan-400 shrink-0" />
                      <span className="truncate">{r.filename}</span>
                    </div>
                    <Download className="w-3.5 h-3.5 text-slate-400 group-hover:text-cyan-300 shrink-0 ml-2" />
                  </a>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04] text-center text-xs text-slate-500">
                No session reports available yet.
              </div>
            )}
          </div>

        </aside>

      </div>

    </div>
  )
}
