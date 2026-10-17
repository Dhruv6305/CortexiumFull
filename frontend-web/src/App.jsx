/**
 * Cortexium 2.0 — Main Application
 * Mid-Sci-Fi Ambient Intelligence HUD
 *  - Multi-person detection overlay (ArcFace)
 *  - Per-person voice transcript auto-save
 *  - Clean, breathable sci-fi aesthetic
 *  - All processing local — no cloud
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Points, PointMaterial } from '@react-three/drei'
import * as THREE from 'three'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Camera, Activity, Users, Navigation, Zap, Shield, Cpu, Radar,
  Eye, BrainCircuit, Mic, MicOff, UserPlus, Upload, CheckCircle,
  AlertCircle, Settings, Bell, Waves, User, Clock, Globe, Database,
  MessageSquare, TrendingUp, AlertTriangle, Wifi, WifiOff, RefreshCw,
  Terminal, ChevronRight, Sparkles, BarChart3, Play, StopCircle,
  History, ChevronDown, ChevronUp, Scan, ScanFace, Signal, FileText, X,
  FlipHorizontal
} from 'lucide-react'
import PeopleDB from './PeopleDB.jsx'
import CollapsibleNavbar from './CollapsibleNavbar.jsx'

// ─────────────────────────────────────────────
//  Three.js Background — subtle neural field
// ─────────────────────────────────────────────

function NeuralField() {
  const count = 800
  const points = useRef()
  const positions = React.useMemo(() => {
    const pos = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 16
      pos[i * 3 + 1] = (Math.random() - 0.5) * 16
      pos[i * 3 + 2] = (Math.random() - 0.5) * 16
    }
    return pos
  }, [])

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (points.current) {
      points.current.rotation.y = t * 0.025
      points.current.rotation.x = t * 0.01
    }
  })

  return (
    <Points ref={points} positions={positions} stride={3} frustumCulled={false}>
      <PointMaterial
        transparent color="#06b6d4" size={0.018}
        sizeAttenuation depthWrite={false}
        blending={THREE.AdditiveBlending} opacity={0.5}
      />
    </Points>
  )
}

// ─────────────────────────────────────────────
//  Constants
// ─────────────────────────────────────────────

// API calls use relative paths — Vite proxy routes to backend (see vite.config.ts)
// This means port changes in change_ports.py only need to update vite.config.ts — not this file.
const API    = import.meta.env.VITE_API_URL || ''
const _wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws'
const WS_URL = import.meta.env.VITE_WS_URL  || `${_wsProto}://${window.location.host}/ws/events`

const AGENTS = [
  { id: 'navigation', description: 'GPS, routes, spatial awareness' },
  { id: 'social', description: 'Face recognition, relationship context' },
  { id: 'environment', description: 'Object detection, hazard scoring' },
  { id: 'orchestrator', description: 'Master AI coordinator' },
]

const EMOTION_COLORS = {
  happy: '#fbbf24', sad: '#60a5fa', angry: '#f87171',
  surprised: '#fb923c', neutral: '#94a3b8', fear: '#c084fc',
  disgust: '#4ade80', contempt: '#f472b6',
}

// ─────────────────────────────────────────────
//  Reusable UI Components
// ─────────────────────────────────────────────

const Panel = ({ children, title, icon: Icon, className = '', accent = 'cyan' }) => {
  const accents = {
    cyan: 'text-cyan-400',
    green: 'text-emerald-400',
    amber: 'text-amber-400',
    blue: 'text-blue-400',
    rose: 'text-rose-400',
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`hud-panel pointer-events-auto ${className}`}
    >
      {title && (
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-white/[0.06]">
          {Icon && <Icon size={13} className={accents[accent]} />}
          <span className="text-[9px] font-mono font-bold tracking-[0.2em] text-slate-500 uppercase">
            {title}
          </span>
        </div>
      )}
      {children}
    </motion.div>
  )
}

const StatusDot = ({ online, pulse = true }) => (
  <span className={`inline-block w-1.5 h-1.5 rounded-full ${
    online ? 'bg-emerald-400' : 'bg-red-500'
  } ${online && pulse ? 'animate-pulse' : ''}`} />
)

// Person ring — shown in left panel for each detected face
const PersonRing = ({ person, emotion }) => {
  const color = EMOTION_COLORS[emotion] || '#94a3b8'
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      className="flex items-center gap-3 p-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08]
                 hover:border-cyan-500/30 transition-all"
    >
      <div className="relative flex-shrink-0">
        <div
          className="w-9 h-9 rounded-full flex items-center justify-center"
          style={{
            background: `radial-gradient(circle, ${color}20 0%, transparent 70%)`,
            border: `1.5px solid ${color}60`,
            boxShadow: `0 0 12px ${color}30`,
          }}
        >
          <ScanFace size={16} style={{ color }} />
        </div>
        <span
          className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-slate-950"
          style={{ background: color }}
        />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold text-white truncate">{person}</p>
        <p className="text-[9px] font-mono capitalize" style={{ color }}>{emotion || 'neutral'}</p>
      </div>
      <div className="flex flex-col items-end">
        <Signal size={10} className="text-emerald-400" />
        <span className="text-[7px] font-mono text-slate-600 mt-0.5">LIVE</span>
      </div>
    </motion.div>
  )
}

const ObjectBadge = ({ obj }) => {
  const conf = Math.round(obj.confidence * 100)
  return (
    <div className="flex items-center justify-between px-2.5 py-1.5 rounded-lg
                    bg-white/[0.03] border border-white/[0.06] text-[9px]">
      <span className="font-mono text-slate-300 capitalize">{obj.class}</span>
      <span className={`font-mono font-bold ${conf > 80 ? 'text-emerald-400' : conf > 60 ? 'text-cyan-400' : 'text-slate-500'}`}>
        {conf}%
      </span>
    </div>
  )
}

const EncounterRow = ({ encounter }) => {
  const time = new Date(encounter.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const color = EMOTION_COLORS[encounter.emotion] || '#94a3b8'
  return (
    <motion.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex items-center gap-2.5 py-2 px-2.5 rounded-lg bg-white/[0.03]
                 border border-white/[0.06] hover:border-white/[0.1] transition-colors"
    >
      <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ background: `${color}20`, border: `1px solid ${color}50` }}>
        <User size={12} style={{ color }} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-semibold text-slate-200 truncate">{encounter.person_name}</p>
        <p className="text-[8px] font-mono text-slate-600 capitalize">{encounter.emotion || '—'}</p>
      </div>
      <span className="text-[8px] font-mono text-slate-600 flex-shrink-0">{time}</span>
    </motion.div>
  )
}

const AgentBtn = ({ agent, onClick }) => {
  const icons = { navigation: Navigation, social: Users, environment: Globe, memory: Database, adaptive: TrendingUp, orchestrator: BrainCircuit }
  const Icon = icons[agent.id] || Cpu
  return (
    <button
      onClick={() => onClick(agent)}
      className="w-full flex items-center gap-3 p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]
                 hover:border-cyan-500/30 hover:bg-cyan-500/[0.04] transition-all text-left group"
    >
      <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center
                      group-hover:border-cyan-400/40 transition-colors flex-shrink-0">
        <Icon size={14} className="text-cyan-400" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-semibold text-slate-200 capitalize">{agent.id}</p>
        <p className="text-[8px] font-mono text-slate-600 truncate">{agent.description}</p>
      </div>
      <ChevronRight size={11} className="text-slate-700 group-hover:text-cyan-400 transition-colors flex-shrink-0" />
    </button>
  )
}

// ─────────────────────────────────────────────
//  Live Subtitles
// ─────────────────────────────────────────────
const LiveSubtitles = ({ text, isFinal }) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: 8 }}
    className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 w-[78%] max-w-2xl
               px-6 py-3 rounded-2xl text-center
               bg-black/75 backdrop-blur-xl border-t border-cyan-500/30
               shadow-[0_-16px_48px_rgba(6,182,212,0.12)]"
  >
    <div className="flex items-center justify-center gap-2 mb-1">
      <Waves className="text-cyan-500" size={10} />
      <span className="text-[7px] font-mono font-bold tracking-[0.35em] text-cyan-500 uppercase">
        Voice Capture
      </span>
    </div>
    <p className={`text-sm font-medium leading-snug ${isFinal ? 'text-white' : 'text-slate-400'}`}>
      {text || 'Listening…'}
    </p>
  </motion.div>
)

// ─────────────────────────────────────────────
//  Notification Toast
// ─────────────────────────────────────────────
const Toast = ({ notification }) => {
  const styles = {
    success: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300',
    error:   'bg-red-500/15 border-red-500/40 text-red-300',
    info:    'bg-cyan-500/15 border-cyan-500/40 text-cyan-300',
  }
  const icons = { success: CheckCircle, error: AlertCircle, info: Zap }
  const Icon = icons[notification.type] || Zap
  return (
    <motion.div
      key={notification.id}
      initial={{ opacity: 0, y: -16, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -16, scale: 0.95 }}
      className={`absolute top-5 left-1/2 -translate-x-1/2 px-5 py-2.5 rounded-full border
                  backdrop-blur-xl flex items-center gap-2 text-[9px] font-semibold
                  uppercase tracking-widest shadow-2xl pointer-events-none z-30
                  ${styles[notification.type] || styles.info}`}
    >
      <Icon size={11} />
      {notification.message}
    </motion.div>
  )
}

// ─────────────────────────────────────────────
//  Conversation Overlay
//  Triggered by voice: "show past conversations" / "what did we talk about"
// ─────────────────────────────────────────────
const ConversationOverlay = ({ data, onClose }) => {
  const { personName, entries } = data
  const SOURCE_ICONS = { voice: Mic, 'ui-manual': FileText, 'ui-upload': Upload }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] flex items-end justify-center p-6"
      style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(14px)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 60, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 60, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 280, damping: 26 }}
        onClick={e => e.stopPropagation()}
        className="w-full max-w-2xl rounded-2xl border border-white/[0.10] overflow-hidden"
        style={{ background: '#080c12' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.07]"
          style={{ background: 'rgba(6,182,212,0.04)' }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/25
                            flex items-center justify-center">
              <MessageSquare size={14} className="text-cyan-400" />
            </div>
            <div>
              <h2 className="text-white font-semibold text-[14px]">{personName}</h2>
              <p className="text-[8px] font-mono text-slate-600 uppercase tracking-widest">
                {entries.length} conversation{entries.length !== 1 ? 's' : ''} · voice-triggered
              </p>
            </div>
          </div>
          <button onClick={onClose}
            className="p-2 rounded-xl hover:bg-white/[0.06] text-slate-600 hover:text-slate-300 transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Entry list */}
        <div className="max-h-[55vh] overflow-y-auto p-5 space-y-2">
          {entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-slate-700 gap-3">
              <MessageSquare size={28} strokeWidth={1.2} />
              <p className="text-[11px] font-mono text-center">
                No conversations recorded yet.<br />
                Voice transcripts will appear here automatically.
              </p>
            </div>
          ) : (
            [...entries].reverse().map((entry, i) => {
              const Icon = SOURCE_ICONS[entry.source] || FileText
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.025 }}
                  className="flex gap-3 p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06]
                             hover:border-white/[0.10] transition-colors"
                >
                  {/* Source icon */}
                  <div className={`flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center mt-0.5
                    ${entry.source === 'voice'
                      ? 'bg-cyan-500/10 border border-cyan-500/20'
                      : 'bg-white/[0.04] border border-white/[0.07]'}`}>
                    <Icon size={11} className={entry.source === 'voice' ? 'text-cyan-400' : 'text-slate-600'} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] text-slate-200 leading-relaxed">{entry.note}</p>
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className="text-[8px] font-mono text-slate-700">
                        {new Date(entry.timestamp).toLocaleString([], {
                          weekday: 'short', month: 'short', day: 'numeric',
                          hour: '2-digit', minute: '2-digit'
                        })}
                      </span>
                      {entry.emotion && (
                        <span className="text-[8px] font-mono text-amber-500/60 capitalize">
                          · {entry.emotion}
                        </span>
                      )}
                    </div>
                  </div>
                </motion.div>
              )
            })
          )}
        </div>

        {/* Footer hint */}
        <div className="px-5 py-3 border-t border-white/[0.06] flex items-center justify-between">
          <p className="text-[8px] font-mono text-slate-700">
            Say <span className="text-cyan-500/70">"show past conversations"</span> anytime to re-open this
          </p>
          <button onClick={onClose}
            className="text-[9px] font-mono text-slate-600 hover:text-slate-300 transition-colors px-3 py-1.5
                       rounded-lg border border-white/[0.06] hover:border-white/[0.1]">
            Close
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ─────────────────────────────────────────────
//  Main Application
// ─────────────────────────────────────────────

export default function App() {
  // ── System State ──
  const [backendOnline, setBackendOnline] = useState(false)
  const [wsConnected, setWsConnected] = useState(false)
  const [visionOnline, setVisionOnline] = useState(false)
  const [activeTab, setActiveTab] = useState('vision')

  // ── Session State ──
  const [sessionStarted, setSessionStarted] = useState(false)
  const [sessionHistory, setSessionHistory] = useState([])
  const [expandedSession, setExpandedSession] = useState(null)

  // ── CV / Detection State — Multi-Person ──
  const [detectedObjects, setDetectedObjects] = useState([])
  const [detectedPersons, setDetectedPersons] = useState([])   // [{name, confidence, region, emotion}]
  const [faceAnalysis, setFaceAnalysis] = useState([])
  const [frameRate, setFrameRate] = useState(0)

  // ── Voice/STT State ──
  const [isRecording, setIsRecording] = useState(false)
  const [isAlwaysOn, setIsAlwaysOn] = useState(false)
  const [transcription, setTranscription] = useState('')
  const [interimText, setInterimText] = useState('')
  const [pendingName, setPendingName] = useState(null)
  const [introDetected, setIntroDetected] = useState(false)

  // ── Encounter Log State ──
  const [encounters, setEncounters] = useState([])

  // ── Agent State ──
  const [agentResponse, setAgentResponse] = useState(null)
  const [agentQuery, setAgentQuery] = useState('')
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [agentLoading, setAgentLoading] = useState(false)

  // ── Adaptive State ──
  const [insights, setInsights] = useState(null)
  const [predictions, setPredictions] = useState([])

  // ── UI State ──
  const [notification, setNotification] = useState(null)
  const [videoProcessing, setVideoProcessing] = useState(false)
  const [vlmScene, setVlmScene] = useState(null)
  const [vlmScanning, setVlmScanning] = useState(false)
  // Conversation overlay — triggered by voice command (face-anchored)
  // { personName, summary, lastSeen, role, sessionCount, loading } | null
  const [faceCard, setFaceCard] = useState(null)
  const [isMirrored, setIsMirrored] = useState(true)
  const isMirroredRef = useRef(true)
  useEffect(() => { isMirroredRef.current = isMirrored }, [isMirrored])
  const inFlightRef = useRef(false)

  // ── Refs ──
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const overlayCanvasRef = useRef(null)
  const recognitionRef = useRef(null)
  const wsRef = useRef(null)
  const frameTimerRef = useRef(null)
  const frameCountRef = useRef(0)
  const lastFpsUpdate = useRef(Date.now())
  const sessionId = useRef(`session_${Date.now()}`)
  const [sessionIdDisplay, setSessionIdDisplay] = useState(sessionId.current)
  const detectedPersonsRef = useRef([])  // track current frame persons for voice save
  const seenPersonsThisSession = useRef(new Set())  // all persons recognized this session (never empty at end)
  const ambientActiveRef = useRef(false)  // true flag for ambient restart (avoids stale closure)

  // Keep refs in sync with state
  useEffect(() => { detectedPersonsRef.current = detectedPersons }, [detectedPersons])
  useEffect(() => { ambientActiveRef.current = isAlwaysOn }, [isAlwaysOn])

  // ─────────────────────────────────────────────
  //  Backend Health Check (Resilient against CPU load spikes)
  // ─────────────────────────────────────────────
  useEffect(() => {
    let failCount = 0
    const checkBackend = async () => {
      // If WebSocket is connected, backend is definitely online
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        failCount = 0
        setBackendOnline(true)
        return
      }
      try {
        const res = await fetch(`${API}/api/health`, { signal: AbortSignal.timeout(10000) })
        if (res.ok) {
          failCount = 0
          setBackendOnline(true)
        } else {
          failCount++
          if (failCount >= 5) setBackendOnline(false)
        }
      } catch {
        failCount++
        if (failCount >= 5) setBackendOnline(false)
      }
    }
    checkBackend()
    const interval = setInterval(checkBackend, 5000)
    return () => clearInterval(interval)
  }, [])

  // ─────────────────────────────────────────────
  //  WebSocket Connection
  // ─────────────────────────────────────────────
  useEffect(() => {
    let reconnectTimer
    const connect = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) return
      try {
        const ws = new WebSocket(WS_URL)
        ws.onopen = () => { setWsConnected(true); console.log('[WS] Connected') }
        ws.onmessage = (msg) => {
          try { handleWSEvent(JSON.parse(msg.data)) } catch { /* ignore */ }
        }
        ws.onclose = () => { setWsConnected(false); reconnectTimer = setTimeout(connect, 3000) }
        ws.onerror = () => { setWsConnected(false) }
        wsRef.current = ws
      } catch {
        reconnectTimer = setTimeout(connect, 5000)
      }
    }
    connect()
    return () => { clearTimeout(reconnectTimer); wsRef.current?.close() }
  }, [])

  const handleRecognizedPersons = useCallback((persons) => {
    (persons || []).forEach(p => {
      if (p.name && !seenPersonsThisSession.current.has(p.name)) {
        seenPersonsThisSession.current.add(p.name)
        // Show face card in neutral idle state (NO auto-fetch of last-session)
        setFaceCard(prev => {
          if (prev && prev.personName === p.name) return prev
          return {
            personName: p.name,
            summary: null,
            loading: false,
            mode: 'idle',
            autoShown: true,
          }
        })
      }
    })
  }, [])

  const handleWSEvent = useCallback((event) => {
    switch (event.event_type) {
      case 'frame_processed': {
        const d = event.data || {}
        if (d.detected_objects) setDetectedObjects(d.detected_objects)
        if (d.face_analysis) setFaceAnalysis(d.face_analysis)
        // Multi-person: merge emotion into persons list
        if (d.persons !== undefined) {
          const enriched = (d.persons || []).map(p => {
            const matched = (d.face_analysis || []).find(f => {
              if (!f.region || !p.region) return false
              const dx = Math.abs((f.region.x + f.region.w / 2) - (p.region.x + p.region.w / 2))
              const dy = Math.abs((f.region.y + f.region.h / 2) - (p.region.y + p.region.h / 2))
              return dx < 80 && dy < 80
            })
            return { ...p, emotion: matched?.dominant_emotion || null }
          })
          setDetectedPersons(enriched)
          handleRecognizedPersons(enriched)
        } else if (d.identity) {
          // Legacy fallback: single identity
          const name = d.identity
          const emo = d.face_analysis?.[0]?.dominant_emotion || null
          setDetectedPersons(name ? [{ name, confidence: 0.9, region: null, emotion: emo }] : [])
          if (name && !seenPersonsThisSession.current.has(name)) {
            seenPersonsThisSession.current.add(name)
            setFaceCard(prev => prev ? prev : {
              personName: name,
              summary: null,
              loading: false,
              mode: 'idle',
              autoShown: true,
            })
          }
        }
        break
      }
      case 'scene_analyzed':
        if (event.data) setVlmScene(event.data)
        break
      case 'intro_detected':
        if (event.data?.name) {
          setPendingName(event.data.name)
          setIntroDetected(true)
          showNotification('info', `Introduction detected: ${event.data.name}`)
        }
        break
      case 'person_registered':
        showNotification('success', `Registered: ${event.data?.name}`)
        setPendingName(null)
        setIntroDetected(false)
        loadEncounters()
        break
      case 'agent_response':
        setAgentResponse(event.data)
        break
      case 'conversation_saved':
        loadEncounters()
        break
      case 'show_conversations': {
        const pName = event.data?.person_name
        if (pName) fetchFaceSummary(pName)
        break
      }
      case 'video_analysis_complete':
        showNotification('success', `Video scan: ${event.data?.processed_frames} frames`)
        break
      default:
        break
    }
  }, [])

  // ─────────────────────────────────────────────
  //  Camera + Frame Capture Pipeline
  // ─────────────────────────────────────────────
  const setupCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        setVisionOnline(true)
      }
    } catch (err) {
      setVisionOnline(false)
      showNotification('error', 'Camera access denied — check browser permissions')
    }
  }, [])

  const stopCamera = useCallback(async () => {
    await finalizeSessionForAll()  // persist session summaries before stopping
    const stream = videoRef.current?.srcObject
    if (stream) stream.getTracks().forEach(t => t.stop())
    if (videoRef.current) videoRef.current.srcObject = null
    setVisionOnline(false)
    setFaceAnalysis([])
    setDetectedObjects([])
    setDetectedPersons([])
    setFrameRate(0)
    if (overlayCanvasRef.current) {
      const ctx = overlayCanvasRef.current.getContext('2d')
      ctx.clearRect(0, 0, overlayCanvasRef.current.width, overlayCanvasRef.current.height)
    }
  }, [])

  const startSession = useCallback(async () => {
    sessionId.current = `session_${Date.now()}`
    setSessionIdDisplay(sessionId.current)
    seenPersonsThisSession.current = new Set()  // reset accumulated persons for this new session
    setSessionStarted(true)
    await setupCamera()
    showNotification('success', 'Session started')
  }, [setupCamera])

  const endSession = useCallback(async () => {
    setIsAlwaysOn(false)
    ambientActiveRef.current = false
    try { recognitionRef.current?.abort() } catch { /* ok */ }
    try {
      await fetch(`${API}/api/memory/sessions/${sessionId.current}/end`, { method: 'POST' })
    } catch { /* ok */ }
    stopCamera()
    setSessionStarted(false)
    showNotification('info', 'Session saved')
    try {
      const res = await fetch(`${API}/api/memory/sessions/history?limit=20`)
      const data = await res.json()
      setSessionHistory(data.sessions || [])
    } catch { /* silent */ }
  }, [stopCamera])

  const captureFrame = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || !backendOnline || !sessionStarted) return
    if (inFlightRef.current) return  // Drop tick if previous frame is still processing!

    const video = videoRef.current
    const canvas = canvasRef.current
    if (video.readyState < video.HAVE_ENOUGH_DATA) return

    inFlightRef.current = true
    try {
      const ctx = canvas.getContext('2d')
      // ── Downscale to max 480×270 for fast encode + lower backend load ──
      // Full resolution (1280×720) creates a ~50KB JPEG and takes ~300ms round-trip.
      // At 480×270 the JPEG is ~10KB, backend sees the same face at adequate detail,
      // and effective FPS roughly doubles (backend is the bottleneck, not capture speed).
      const srcW = video.videoWidth  || 640
      const srcH = video.videoHeight || 480
      const MAX_DIM = 480
      const scale = Math.min(1.0, MAX_DIM / Math.max(srcW, srcH))
      canvas.width  = Math.round(srcW * scale)
      canvas.height = Math.round(srcH * scale)
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      const frame_b64 = canvas.toDataURL('image/jpeg', 0.65)

      frameCountRef.current++
      const now = Date.now()
      if (now - lastFpsUpdate.current > 1000) {
        setFrameRate(Math.round(frameCountRef.current * 1000 / (now - lastFpsUpdate.current)))
        frameCountRef.current = 0
        lastFpsUpdate.current = now
      }

      const res = await fetch(`${API}/api/vision/frame`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          frame_b64,
          session_id: sessionId.current,
          timestamp: Date.now() / 1000,
          name: pendingName || undefined,
        }),
        signal: AbortSignal.timeout(3500),
      })
      if (res.ok) {
        const d = await res.json()
        if (d.detected_objects) setDetectedObjects(d.detected_objects)
        if (d.face_analysis) setFaceAnalysis(d.face_analysis)
        if (d.persons !== undefined) {
          const enriched = (d.persons || []).map(p => {
            const matched = (d.face_analysis || []).find(f => {
              if (!f.region || !p.region) return false
              // Scale coordinates back to video dimensions for overlay rendering
              const px = p.region.x / scale
              const py = p.region.y / scale
              const fx = f.region.x / scale
              const fy = f.region.y / scale
              const dx = Math.abs((fx + f.region.w / scale / 2) - (px + p.region.w / scale / 2))
              const dy = Math.abs((fy + f.region.h / scale / 2) - (py + p.region.h / scale / 2))
              return dx < 80 && dy < 80
            })
            // Scale regions back up to original video resolution for correct overlay positioning
            const scaleRegion = (r) => r ? { x: Math.round(r.x / scale), y: Math.round(r.y / scale), w: Math.round(r.w / scale), h: Math.round(r.h / scale) } : r
            return { ...p, region: scaleRegion(p.region), emotion: matched?.dominant_emotion || null }
          })
          setDetectedPersons(enriched)
          handleRecognizedPersons(enriched)
        }
        // Also scale face_analysis regions back for overlay
        if (d.face_analysis && scale < 1.0) {
          setFaceAnalysis(d.face_analysis.map(f => ({
            ...f,
            region: f.region ? { x: Math.round(f.region.x / scale), y: Math.round(f.region.y / scale), w: Math.round(f.region.w / scale), h: Math.round(f.region.h / scale) } : f.region,
          })))
        }
      }
    } catch (err) {
      if (err.name !== 'TimeoutError') console.error('[Frame] Error:', err)
    } finally {
      inFlightRef.current = false
    }
  }, [backendOnline, pendingName, sessionStarted, handleRecognizedPersons])

  useEffect(() => {
    clearInterval(frameTimerRef.current)
    // Poll at 120ms intervals — fast enough for smooth overlay, backend will drop frames it can't keep up with
    frameTimerRef.current = setInterval(captureFrame, 120)
    return () => clearInterval(frameTimerRef.current)
  }, [captureFrame])

  // ─────────────────────────────────────────────
  //  Multi-Person Face Overlay (Canvas with 60FPS LERP Smoothing)
  // ─────────────────────────────────────────────
  const smoothBoxesRef = useRef([])

  useEffect(() => {
    const targets = []
    detectedPersons.forEach(person => {
      if (person.region?.w && person.region?.h) {
        targets.push({
          id: person.name || 'known',
          name: person.name,
          emotion: person.emotion,
          isKnown: true,
          targetX: person.region.x,
          targetY: person.region.y,
          targetW: person.region.w,
          targetH: person.region.h,
        })
      }
    })
    faceAnalysis.forEach(face => {
      const region = face.region
      if (!region?.w || !region?.h) return
      const isKnown = targets.some(t => {
        const dx = Math.abs((region.x + region.w / 2) - (t.targetX + t.targetW / 2))
        const dy = Math.abs((region.y + region.h / 2) - (t.targetY + t.targetH / 2))
        return dx < 60 && dy < 60
      })
      if (!isKnown) {
        targets.push({
          id: `unknown_${region.x}_${region.y}`,
          name: null,
          emotion: face.dominant_emotion,
          isKnown: false,
          targetX: region.x,
          targetY: region.y,
          targetW: region.w,
          targetH: region.h,
        })
      }
    })

    const newSmooth = targets.map(t => {
      const existing = smoothBoxesRef.current.find(b => b.id === t.id || (Math.abs(b.curX - t.targetX) < 100 && Math.abs(b.curY - t.targetY) < 100))
      if (existing) {
        return { ...t, curX: existing.curX, curY: existing.curY, curW: existing.curW, curH: existing.curH }
      }
      return { ...t, curX: t.targetX, curY: t.targetY, curW: t.targetW, curH: t.targetH }
    })
    smoothBoxesRef.current = newSmooth
  }, [detectedPersons, faceAnalysis])

  useEffect(() => {
    let animId
    const renderOverlay = () => {
      const overlay = overlayCanvasRef.current
      const video = videoRef.current
      if (overlay && video && video.readyState >= video.HAVE_CURRENT_DATA) {
        const vw = video.videoWidth || 640
        const vh = video.videoHeight || 480
        if (overlay.width !== vw || overlay.height !== vh) {
          overlay.width = vw
          overlay.height = vh
        }
        const ctx = overlay.getContext('2d')
        ctx.clearRect(0, 0, vw, vh)

        smoothBoxesRef.current.forEach(box => {
          box.curX += (box.targetX - box.curX) * 0.65
          box.curY += (box.targetY - box.curY) * 0.65
          box.curW += (box.targetW - box.curW) * 0.65
          box.curH += (box.targetH - box.curH) * 0.65

          const rawX = box.curX
          const rawY = box.curY
          const w = box.curW
          const h = box.curH
          const mirrored = isMirroredRef.current
          const x = mirrored ? (vw - rawX - w) : rawX
          const y = rawY

          if (box.isKnown) {
            const emotion = box.emotion || ''
            const label = (box.name || 'UNKNOWN').toUpperCase()
            const emotionColor = EMOTION_COLORS[emotion] || '#22d3ee'
            const faceColor = '#22d3ee'

            ctx.save()
            ctx.shadowColor = faceColor
            ctx.shadowBlur = 18
            ctx.strokeStyle = faceColor + '90'
            ctx.lineWidth = 1
            ctx.strokeRect(x, y, w, h)
            ctx.restore()

            const cs = Math.min(20, w * 0.28)
            ctx.save()
            ctx.strokeStyle = faceColor
            ctx.lineWidth = 2
            ctx.shadowColor = faceColor
            ctx.shadowBlur = 10
            ctx.beginPath(); ctx.moveTo(x, y + cs); ctx.lineTo(x, y); ctx.lineTo(x + cs, y); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(x + w - cs, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + cs); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(x, y + h - cs); ctx.lineTo(x, y + h); ctx.lineTo(x + cs, y + h); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(x + w - cs, y + h); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w, y + h - cs); ctx.stroke()
            ctx.restore()

            const tagH = 20
            const tagPad = 10
            ctx.save()
            ctx.fillStyle = 'rgba(0, 20, 30, 0.85)'
            ctx.beginPath()
            ctx.roundRect(x - 1, y - tagH - 4, Math.max(w + 2, label.length * 7.5 + tagPad * 2), tagH, 4)
            ctx.fill()
            ctx.fillStyle = faceColor
            ctx.font = 'bold 9.5px "JetBrains Mono", monospace'
            ctx.fillText(label, x + tagPad - 2, y - 8)
            ctx.restore()

            if (emotion) {
              const emLabel = emotion.toUpperCase()
              const emW = emLabel.length * 6.5 + 12
              ctx.save()
              ctx.fillStyle = emotionColor + '25'
              ctx.beginPath()
              ctx.roundRect(x, y + h + 4, emW, 15, 3)
              ctx.fill()
              ctx.fillStyle = emotionColor
              ctx.font = '7.5px "JetBrains Mono", monospace'
              ctx.fillText(emLabel, x + 5, y + h + 14)
              ctx.restore()
            }
          } else {
            const cs = Math.min(16, w * 0.25)
            ctx.save()
            ctx.strokeStyle = '#475569'
            ctx.lineWidth = 1.5
            ctx.beginPath(); ctx.moveTo(x, y + cs); ctx.lineTo(x, y); ctx.lineTo(x + cs, y); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(x + w - cs, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + cs); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(x, y + h - cs); ctx.lineTo(x, y + h); ctx.lineTo(x + cs, y + h); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(x + w - cs, y + h); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w, y + h - cs); ctx.stroke()
            ctx.fillStyle = '#475569'
            ctx.font = '8px monospace'
            ctx.fillText('UNKNOWN', x + 3, y - 5)
            ctx.restore()
          }
        })
      }
      animId = requestAnimationFrame(renderOverlay)
    }
    renderOverlay()
    return () => cancelAnimationFrame(animId)
  }, [])

  // ─────────────────────────────────────────────
  //  Session History
  // ─────────────────────────────────────────────
  const loadSessions = useCallback(async () => {
    if (!backendOnline) return
    try {
      const res = await fetch(`${API}/api/memory/sessions/history?limit=20`)
      const data = await res.json()
      setSessionHistory(data.sessions || [])
    } catch { /* silent */ }
  }, [backendOnline])

  useEffect(() => { loadSessions() }, [loadSessions])

  // ─────────────────────────────────────────────
  //  VLM Scene Scan
  // ─────────────────────────────────────────────
  const vlmScan = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || !backendOnline || vlmScanning) return
    const video = videoRef.current
    const canvas = canvasRef.current
    if (video.readyState < video.HAVE_ENOUGH_DATA) return
    const ctx = canvas.getContext('2d')
    canvas.width = video.videoWidth || 320
    canvas.height = video.videoHeight || 240
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    const frame_b64 = canvas.toDataURL('image/jpeg', 0.85)
    setVlmScanning(true)
    try {
      const res = await fetch(`${API}/api/vision/scene`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ frame_b64, session_id: sessionId.current, timestamp: Date.now() / 1000 }),
        signal: AbortSignal.timeout(30000),
      })
      const data = await res.json()
      if (data.vlm_available) { setVlmScene(data); showNotification('success', 'Scene analysis complete') }
      else showNotification('error', 'qwen2.5vl offline — start Ollama with VLM model')
    } catch (err) {
      showNotification('error', `VLM scan failed: ${err.message}`)
    } finally {
      setVlmScanning(false)
    }
  }, [backendOnline, vlmScanning])

  // ─────────────────────────────────────────────
  //  Voice / STT Pipeline
  // ─────────────────────────────────────────────
  const toggleAlwaysOnVoice = () => {
    if (isAlwaysOn) {
      setIsAlwaysOn(false)
      ambientActiveRef.current = false
      clearTimeout(interimTimerRef.current)
      lastInterimRef.current = ''
      try { recognitionRef.current?.abort() } catch { /* ok */ }
    } else {
      setIsAlwaysOn(true)
      startVoiceCapture()
    }
  }

  // ── Robust ambient voice capture ──────────────────────────────────────────
  // continuous = true:  mic stays held open — Chrome's tab indicator stays solid
  //                     (no flicker between utterances). This is what we want.
  // continuous = false: Chrome releases + re-acquires the mic between utterances,
  //                     causing the tab mic icon to flicker and audio to drop.
  //
  // Latency strategy: Chrome's continuous VAD waits ~1-2s of silence before
  // firing isFinal. We solve this with a 750ms interim-stability timer:
  // if the interim transcript hasn't changed for 750ms we treat it as final
  // ourselves and call recognition.stop() to flush it cleanly.
  // recognition.stop() (NOT abort) triggers isFinal on the current utterance,
  // fires onend, and we restart — mic stays warm, no flicker.
  const interimTimerRef = useRef(null)
  const lastInterimRef  = useRef('')
  const lastInterimSnapRef = useRef('')  // snapshot used by the timer closure

  const startVoiceCapture = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      showNotification('error', 'Browser does not support Speech Recognition')
      setIsAlwaysOn(false)
      ambientActiveRef.current = false
      return
    }

    // Abort any in-flight recognition before creating a new one
    try { recognitionRef.current?.abort() } catch { /* ok */ }
    clearTimeout(interimTimerRef.current)

    const recognition = new SR()
    // CONTINUOUS = TRUE — mic stays open, no flicker
    recognition.continuous     = true
    recognition.interimResults = true
    recognition.lang           = 'en-US'
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setIsRecording(true)
      setInterimText('')
      lastInterimRef.current = ''
      lastInterimSnapRef.current = ''
    }

    recognition.onend = () => {
      setIsRecording(false)
      clearTimeout(interimTimerRef.current)
      // Drain any remaining interim text that never got a isFinal
      const pending = lastInterimRef.current.trim()
      if (pending) {
        setTranscription(pending)
        setInterimText('')
        lastInterimRef.current = ''
        lastInterimSnapRef.current = ''
        processFinalVoice(pending)
      }
      // Restart to keep listening — the recognition object is spent after onend
      if (ambientActiveRef.current) {
        // Small delay only to let Chrome's audio stack settle (avoids AbortError on fast restart)
        setTimeout(() => {
          if (ambientActiveRef.current) startVoiceCapture()
        }, 80)
      }
    }

    // Recoverable errors: restart. Fatal errors: stop ambient mode.
    recognition.onerror = (e) => {
      setIsRecording(false)
      clearTimeout(interimTimerRef.current)
      const RECOVERABLE = ['no-speech', 'aborted', 'audio-capture']
      if (RECOVERABLE.includes(e.error)) {
        if (ambientActiveRef.current) {
          setTimeout(() => { if (ambientActiveRef.current) startVoiceCapture() }, 150)
        }
      } else {
        console.error('[Voice] Fatal STT error:', e.error)
        setIsAlwaysOn(false)
        ambientActiveRef.current = false
        if (e.error === 'not-allowed') {
          showNotification('error', 'Microphone access denied — check browser permissions')
        }
      }
    }

    recognition.onresult = (event) => {
      clearTimeout(interimTimerRef.current)
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          const final = result[0].transcript.trim()
          clearTimeout(interimTimerRef.current)
          lastInterimRef.current = ''
          lastInterimSnapRef.current = ''
          if (final) {
            setTranscription(final)
            setInterimText('')
            processFinalVoice(final)
          }
        } else {
          interim += result[0].transcript
          setInterimText(interim)
          lastInterimRef.current = interim
          // Interim early-fire: if interim text is stable for 750ms, treat as final.
          // We call recognition.stop() — this flushes the current utterance as isFinal
          // and fires onend, which then restarts recognition cleanly.
          // The mic stays warm in Chrome (no release + re-acquire) because stop()
          // is a graceful flush, not an emergency abort.
          const snapshot = interim
          lastInterimSnapRef.current = snapshot
          interimTimerRef.current = setTimeout(() => {
            // Only fire if the interim text hasn't changed since we set the timer
            if (lastInterimSnapRef.current === snapshot && lastInterimRef.current.trim()) {
              // stop() causes Chrome to finalize the utterance → triggers isFinal + onend
              try { recognition.stop() } catch { /* ok */ }
            }
          }, 750)
        }
      }
    }

    try {
      recognition.start()
      recognitionRef.current = recognition
    } catch (err) {
      console.error('[Voice] start() failed:', err)
      if (ambientActiveRef.current) {
        setTimeout(() => { if (ambientActiveRef.current) startVoiceCapture() }, 500)
      }
    }
  }

  // ── Fetch summary and show inline face card ──────────────────────────────
  // ── Show current session summary (finalize first, then display) ───────────
  const fetchFaceSummary = useCallback(async (personName, wantPrevious = false) => {
    setFaceCard({ personName, summary: null, loading: true, mode: wantPrevious ? 'previous' : 'current' })
    const sid = sessionId.current
    try {
      // Step 1: finalize the current session so it gets a summary file
      await fetch(`${API}/api/persons/${encodeURIComponent(personName)}/finalize-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid }),
      })
      // Step 2: fetch the requested session
      // If wantPrevious is true, pass session_id to exclude the current live session
      const url = wantPrevious 
        ? `${API}/api/persons/${encodeURIComponent(personName)}/last-session?session_id=${sid}`
        : `${API}/api/persons/${encodeURIComponent(personName)}/last-session`
        
      const res = await fetch(url)
      const data = await res.json()
      if (data.found) {
        setFaceCard({
          personName,
          summary: data.summary || 'No summary available.',
          sessionCode: data.session_code,
          date: data.date,
          startedAt: data.started_at,
          loading: false,
          mode: 'current',
        })
      } else {
        setFaceCard({
          personName,
          summary: wantPrevious ? 'No previous session found.' : 'Nothing spoken yet this session. Speak while your face is recognized to build a conversation log.',
          sessionCode: null,
          loading: false,
          mode: wantPrevious ? 'previous' : 'current',
        })
      }
    } catch {
      setFaceCard({ personName, summary: 'Could not load session summary.', loading: false, mode: wantPrevious ? 'previous' : 'current' })
    }
  }, [])

  // ── Fetch sessions for a specific date ────────────────────────────────────
  const fetchSessionByDate = useCallback(async (personName, dateStr) => {
    setFaceCard({ personName, summary: null, loading: true, mode: 'date', dateQuery: dateStr })
    try {
      const res = await fetch(
        `${API}/api/persons/${encodeURIComponent(personName)}/sessions-by-date?date=${encodeURIComponent(dateStr)}`
      )
      const data = await res.json()
      if (data.found && data.sessions.length > 0) {
        // Show the most recent session from that date
        const s = data.sessions[0]
        setFaceCard({
          personName,
          summary: s.summary || 'No summary available.',
          sessionCode: s.session_code,
          date: s.date,
          startedAt: s.started_at,
          totalOnDate: data.sessions.length,
          loading: false,
          mode: 'date',
          dateQuery: dateStr,
        })
      } else {
        setFaceCard({
          personName,
          summary: `No sessions found for "${dateStr}".`,
          sessionCode: null,
          loading: false,
          mode: 'date',
          dateQuery: dateStr,
        })
      }
    } catch {
      setFaceCard({ personName, summary: 'Could not load sessions.', loading: false, mode: 'date' })
    }
  }, [])

  // ── Finalize session summaries for all persons seen this session ─────────────
  const finalizeSessionForAll = useCallback(async () => {
    // Use seenPersonsThisSession (accumulates across whole session, never empty at End)
    // instead of detectedPersonsRef.current (only current frame — may be empty)
    const allSeen = [...seenPersonsThisSession.current]
    const sid = sessionId.current
    if (!allSeen.length || !sid) return
    try {
      await Promise.all(allSeen.map(name =>
        fetch(`${API}/api/persons/${encodeURIComponent(name)}/finalize-session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sid }),
        })
      ))
      console.log('[Session] Finalized summaries for:', allSeen)
    } catch (e) {
      console.warn('[Session] Finalize error:', e)
    }
  }, [])

  const processFinalVoice = async (text) => {
    if (!backendOnline) return
    const currentPersons = detectedPersonsRef.current
    const primaryPerson = currentPersons.length > 0 ? currentPersons[0].name : null
    const primaryEmotion = currentPersons.length > 0 ? currentPersons[0].emotion : null

    // ── Send to NLP backend (handles intent classification, recall & storage) ──
    try {
      let persons = currentPersons
      if (!persons.length && seenPersonsThisSession.current.size > 0) {
        persons = [...seenPersonsThisSession.current].map(name => ({ name, emotion: 'neutral' }))
      }
      const effectivePrimary = persons.length > 0 ? persons[0].name : primaryPerson
      const effectiveEmotion = persons.length > 0 ? persons[0].emotion : primaryEmotion

      const res = await fetch(`${API}/api/audio/process-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          session_id: sessionId.current,
          // Multi-person: send ALL detected or recent people so each gets the transcript saved
          detected_persons: persons.map(p => p.name),
          detected_emotions: Object.fromEntries(persons.map(p => [p.name, p.emotion || 'neutral'])),
          // Legacy single-person fields for backward compat
          detected_person: effectivePrimary,
          detected_emotion: effectiveEmotion,
        }),
      })
      const data = await res.json()
      if (data.extracted_name) {
        setPendingName(data.extracted_name)
        setIntroDetected(true)
        showNotification('info', `Name detected: "${data.extracted_name}"`)
      }
      // If user asked a recall question, backend returns recall_summary
      if (data.recall_summary) {
        setFaceCard({
          personName: data.recall_person || effectivePrimary || 'Conversation',
          summary: data.recall_summary,
          sessionCode: data.session_code || null,
          date: data.session_date || null,
          loading: false,
          mode: 'previous',
        })
        showNotification('info', `Recalled session for ${data.recall_person || 'person'}`)
      } else if (data.show_conversations_for) {
        await fetchFaceSummary(data.show_conversations_for)
      }
    } catch (err) {
      console.error('[Voice] NLP error:', err)
    }
  }

  // ─────────────────────────────────────────────
  //  Encounter Log
  // ─────────────────────────────────────────────
  const loadEncounters = useCallback(async () => {
    if (!backendOnline) return
    try {
      const res = await fetch(`${API}/api/memory/encounters?limit=20`)
      const data = await res.json()
      setEncounters(data.encounters || [])
    } catch { /* silent */ }
  }, [backendOnline])

  useEffect(() => {
    loadEncounters()
    const interval = setInterval(loadEncounters, 15000)
    return () => clearInterval(interval)
  }, [loadEncounters])

  // ─────────────────────────────────────────────
  //  Adaptive Insights
  // ─────────────────────────────────────────────
  const loadInsights = useCallback(async () => {
    if (!backendOnline) return
    try {
      const [insRes, predRes] = await Promise.all([
        fetch(`${API}/api/adaptive/insights`),
        fetch(`${API}/api/adaptive/predictions?session_id=${sessionId.current}`),
      ])
      setInsights(await insRes.json())
      const predData = await predRes.json()
      setPredictions(predData.predictions || [])
    } catch { /* silent */ }
  }, [backendOnline])

  useEffect(() => {
    loadInsights()
    const interval = setInterval(loadInsights, 20000)
    return () => clearInterval(interval)
  }, [loadInsights])

  // ─────────────────────────────────────────────
  //  Agent Query
  // ─────────────────────────────────────────────
  const askAgent = async (query, agentId = 'orchestrator') => {
    if (!backendOnline || !query.trim()) return
    setAgentLoading(true)
    setAgentResponse(null)
    try {
      const res = await fetch(`${API}/api/agents/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          agent: agentId,
          session_id: sessionId.current,
          context: {
            objects: detectedObjects.slice(0, 5).map(o => o.class),
            persons: detectedPersons.map(p => p.name),
            emotion: faceAnalysis[0]?.dominant_emotion,
          },
        }),
      })
      setAgentResponse(await res.json())
    } catch {
      showNotification('error', 'Agent query failed')
    } finally {
      setAgentLoading(false)
    }
  }

  // ─────────────────────────────────────────────
  //  Notifications
  // ─────────────────────────────────────────────
  const showNotification = (type, message, duration = 4000) => {
    setNotification({ type, message, id: Date.now() })
    setTimeout(() => setNotification(null), duration)
  }

  // ─────────────────────────────────────────────
  //  Right Panel Tab Content
  // ─────────────────────────────────────────────
  const renderRightPanel = () => {
    switch (activeTab) {

      case 'vision':
        return (
          <>
            <Panel title="Detected Objects" icon={Cpu} accent="cyan">
              <div className="space-y-1">
                {detectedObjects.length > 0 ? (
                  detectedObjects.slice(0, 7).map((obj, i) => <ObjectBadge key={i} obj={obj} />)
                ) : (
                  <div className="h-16 flex items-center justify-center border border-dashed border-white/[0.06] rounded-xl">
                    <span className="text-[9px] font-mono text-slate-700">No objects detected</span>
                  </div>
                )}
                {detectedObjects.length > 7 && (
                  <p className="text-[8px] text-slate-700 text-center font-mono pt-1">
                    +{detectedObjects.length - 7} more
                  </p>
                )}
              </div>
            </Panel>

            <Panel title="Face Analysis" icon={Eye} accent="cyan">
              <div className="space-y-2">
                {faceAnalysis.length > 0 ? (
                  faceAnalysis.slice(0, 2).map((face, i) => (
                    <div key={i} className="space-y-1.5 p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <User size={9} className="text-cyan-500" />
                        <span className="text-[8px] font-mono text-slate-500">Face {i + 1}</span>
                      </div>
                      {[
                        { k: 'Emotion', v: face.dominant_emotion, c: EMOTION_COLORS[face.dominant_emotion] || '#94a3b8' },
                        { k: 'Age', v: face.age ? `~${face.age} yrs` : '—', c: '#60a5fa' },
                        { k: 'Gender', v: face.dominant_gender, c: '#f472b6' },
                      ].map(({ k, v, c }) => (
                        <div key={k} className="flex justify-between text-[9px]">
                          <span className="font-mono text-slate-600 uppercase tracking-wider">{k}</span>
                          <span className="font-semibold font-mono capitalize" style={{ color: c }}>{v || '—'}</span>
                        </div>
                      ))}
                    </div>
                  ))
                ) : (
                  <div className="h-14 flex items-center justify-center border border-dashed border-white/[0.06] rounded-xl">
                    <span className="text-[9px] font-mono text-slate-700">No faces in frame</span>
                  </div>
                )}
              </div>
            </Panel>

            <Panel title="VLM Scene AI" icon={Sparkles} accent="cyan">
              <div className="space-y-3">
                <button
                  onClick={vlmScan}
                  disabled={vlmScanning || !backendOnline}
                  className={`w-full py-2.5 rounded-xl text-[9px] font-mono font-bold tracking-widest
                              transition-all flex items-center justify-center gap-2 border
                              ${vlmScanning
                                ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 animate-pulse'
                                : 'bg-white/[0.04] hover:bg-cyan-500/10 text-slate-400 hover:text-cyan-300 border-white/[0.08] hover:border-cyan-500/30'
                              } disabled:opacity-30`}
                >
                  <BrainCircuit size={12} className={vlmScanning ? 'animate-spin' : ''} />
                  {vlmScanning ? 'Analysing Scene…' : 'Scan with qwen2.5vl'}
                </button>

                {vlmScene?.description && (
                  <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
                    <div className="p-2.5 rounded-xl bg-cyan-500/[0.05] border border-cyan-500/20">
                      <span className="block text-[7px] text-cyan-500 font-mono font-bold tracking-widest uppercase mb-1">
                        Scene
                      </span>
                      <p className="text-[9px] text-slate-300 leading-relaxed">{vlmScene.description}</p>
                    </div>
                    {vlmScene.hazards?.length > 0 && (
                      <div className="p-2.5 rounded-xl bg-red-500/[0.08] border border-red-500/25">
                        <span className="block text-[7px] text-red-400 font-mono font-bold tracking-widest uppercase mb-1">
                          Hazards
                        </span>
                        {vlmScene.hazards.map((h, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-[9px] text-red-300 font-mono">
                            <AlertTriangle size={8} className="flex-shrink-0" /> {h}
                          </div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                )}

                <div className="pt-1 border-t border-white/[0.06]">
                  <p className="text-[7px] text-slate-700 font-mono uppercase tracking-widest mb-2">POV Clip Analysis</p>
                  <div className="relative p-3 border border-dashed border-white/[0.08] hover:border-cyan-500/25 rounded-xl
                                  bg-black/20 transition-all cursor-pointer group text-center">
                    <input type="file" accept="video/*" onChange={async (e) => {
                      const file = e.target.files[0]
                      if (!file) return
                      setVideoProcessing(true)
                      const form = new FormData()
                      form.append('file', file)
                      try {
                        const res = await fetch(`${API}/api/vision/video/process`, { method: 'POST', body: form })
                        const d = await res.json()
                        showNotification('success', `Scan done: ${d.processed_frames} frames`)
                      } catch {
                        showNotification('error', 'Video analysis failed')
                      } finally { setVideoProcessing(false); e.target.value = '' }
                    }} className="absolute inset-0 opacity-0 cursor-pointer" />
                    <Upload className="mx-auto mb-1 text-slate-700 group-hover:text-cyan-500 transition-colors" size={14} />
                    <span className="text-[8px] font-mono text-slate-700 group-hover:text-cyan-400 transition-colors">
                      {videoProcessing ? 'Scanning…' : 'Upload Clip'}
                    </span>
                  </div>
                </div>
              </div>
            </Panel>
          </>
        )

      case 'bio-logs':
        return (
          <>
            <Panel title="Encounter Log" icon={Users} accent="green">
              <div className="space-y-1 max-h-[280px] overflow-y-auto pr-0.5">
                {encounters.length > 0 ? (
                  encounters.map((enc, i) => <EncounterRow key={enc.encounter_id || i} encounter={enc} />)
                ) : (
                  <div className="h-20 flex flex-col items-center justify-center text-slate-700 gap-2">
                    <Users size={20} />
                    <span className="text-[9px] font-mono">No encounters yet</span>
                  </div>
                )}
              </div>
              <button onClick={loadEncounters}
                className="mt-3 w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg
                           text-[8px] font-mono text-slate-600 hover:text-slate-300 transition-colors
                           border border-white/[0.06] hover:border-white/[0.1]">
                <RefreshCw size={9} /> Refresh
              </button>
            </Panel>

            <Panel title="Persons Seen" icon={User} accent="green">
              <div className="space-y-1">
                {[...new Set(encounters.map(e => e.person_name))].map((name, i) => (
                  <div key={i} className="flex items-center gap-2.5 p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                    <div className="w-6 h-6 rounded-full bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center">
                      <User size={10} className="text-emerald-400" />
                    </div>
                    <span className="text-[10px] font-semibold text-slate-200 flex-1">{name}</span>
                    <span className="text-[8px] font-mono text-slate-600">
                      {encounters.filter(e => e.person_name === name).length}×
                    </span>
                  </div>
                ))}
                {encounters.length === 0 && (
                  <p className="text-[9px] font-mono text-slate-700 text-center py-3">No persons registered</p>
                )}
              </div>
            </Panel>
          </>
        )

      case 'agents':
        return (
          <>
            <Panel title="AI Agents" icon={BrainCircuit} accent="blue">
              <div className="space-y-1.5">
                {AGENTS.map(agent => (
                  <AgentBtn key={agent.id} agent={agent} onClick={(a) => {
                    setSelectedAgent(a); setAgentQuery(''); setAgentResponse(null)
                  }} />
                ))}
              </div>
            </Panel>

            {selectedAgent && (
              <Panel title={`${selectedAgent.id} Agent`} icon={Terminal} accent="cyan">
                <div className="space-y-3">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={agentQuery}
                      onChange={e => setAgentQuery(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && askAgent(agentQuery, selectedAgent.id)}
                      placeholder={`Ask ${selectedAgent.id}…`}
                      className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2
                                 text-[10px] font-mono text-slate-200 placeholder-slate-700
                                 focus:outline-none focus:border-cyan-500/40"
                    />
                    <button
                      onClick={() => askAgent(agentQuery, selectedAgent.id)}
                      disabled={agentLoading || !agentQuery.trim()}
                      className="px-3 rounded-lg bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-500/30
                                 disabled:opacity-30 transition-colors flex items-center justify-center"
                    >
                      {agentLoading
                        ? <RefreshCw size={12} className="text-cyan-400 animate-spin" />
                        : <Zap size={12} className="text-cyan-400" />}
                    </button>
                  </div>
                  {agentResponse && (
                    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                      className="p-3 rounded-xl bg-cyan-500/[0.05] border border-cyan-500/20">
                      <span className="block text-[7px] text-cyan-500 font-mono font-bold tracking-widest mb-1.5 uppercase">
                        {agentResponse.agent} Response
                      </span>
                      <p className="text-[10px] text-slate-200 leading-relaxed font-mono">
                        {agentResponse.response}
                      </p>
                    </motion.div>
                  )}
                </div>
              </Panel>
            )}
          </>
        )

      case 'people':
        return (
          <Panel title="People Database" icon={Users} accent="cyan" className="flex-1">
            <div className="h-[calc(100vh-260px)] flex flex-col">
              <PeopleDB apiBase={API} />
            </div>
          </Panel>
        )

      case 'systems':
        return (
          <>
            <Panel title="System Status" icon={Activity} accent="green">
              <div className="space-y-2">
                {[
                  { label: 'Backend API', value: backendOnline ? 'ONLINE' : 'OFFLINE', ok: backendOnline },
                  { label: 'WebSocket', value: wsConnected ? 'CONNECTED' : 'DISCONNECTED', ok: wsConnected },
                  { label: 'Vision', value: visionOnline ? 'ACTIVE' : 'INACTIVE', ok: visionOnline },
                  { label: 'Frame Rate', value: `${frameRate} fps`, ok: frameRate > 0 },
                  { label: 'Session', value: sessionId.current.split('_')[1] || '—', ok: true },
                ].map(({ label, value, ok }) => (
                  <div key={label} className="flex justify-between items-center text-[9px] py-1.5 border-b border-white/[0.04]">
                    <span className="font-mono text-slate-600 uppercase tracking-wider">{label}</span>
                    <div className="flex items-center gap-1.5">
                      <StatusDot online={ok} pulse={ok} />
                      <span className={`font-bold font-mono ${ok ? 'text-slate-300' : 'text-slate-600'}`}>{value}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Adaptive Insights" icon={Sparkles} accent="amber">
              {insights ? (
                <div className="space-y-2">
                  {[
                    { label: 'Encounters', value: insights.total_encounters },
                    { label: 'Persons Seen', value: insights.unique_persons_seen },
                    { label: 'Objects', value: insights.unique_objects_detected },
                    { label: 'Events', value: insights.system_uptime_events },
                  ].map(({ label, value }) => (
                    <div key={label} className="flex justify-between text-[9px]">
                      <span className="font-mono text-slate-600 uppercase tracking-wider">{label}</span>
                      <span className="text-amber-400 font-bold font-mono">{value ?? '—'}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-14 flex items-center justify-center opacity-20"><BarChart3 size={20} /></div>
              )}
              <button onClick={loadInsights} className="mt-3 w-full flex items-center justify-center gap-1.5 py-1.5
                rounded-lg text-[8px] font-mono text-slate-600 hover:text-slate-300 border border-white/[0.06]
                hover:border-white/[0.1] transition-colors">
                <RefreshCw size={9} /> Refresh
              </button>
            </Panel>
          </>
        )

      case 'history':
        return (
          <Panel title="Session History" icon={History} accent="blue">
            <div className="space-y-1.5 max-h-[calc(100vh-260px)] overflow-y-auto pr-0.5">
              <button onClick={loadSessions} className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg
                text-[8px] font-mono text-slate-600 hover:text-slate-300 border border-white/[0.06] hover:border-white/[0.1]
                transition-colors mb-2">
                <RefreshCw size={9} /> Refresh History
              </button>

              {sessionHistory.length === 0 ? (
                <div className="h-20 flex flex-col items-center justify-center text-slate-700 gap-2">
                  <History size={20} />
                  <span className="text-[9px] font-mono">No sessions saved yet</span>
                </div>
              ) : (
                sessionHistory.map((sess) => {
                  const sid = sess.session_id
                  const start = new Date(sess.started_at * 1000)
                  const end = sess.ended_at ? new Date(sess.ended_at * 1000) : null
                  const isExpanded = expandedSession === sid
                  const duration = end ? Math.round((sess.ended_at - sess.started_at) / 60) : null
                  return (
                    <div key={sid} className="rounded-xl border border-white/[0.07] bg-white/[0.02] overflow-hidden">
                      <button
                        onClick={() => setExpandedSession(isExpanded ? null : sid)}
                        className="w-full flex items-center justify-between p-2.5 text-left hover:bg-white/[0.04] transition-colors"
                      >
                        <div className="min-w-0 flex-1">
                          <span className="block text-[9px] font-semibold text-blue-400 truncate">
                            {sid.split('_')[1] || sid.slice(-8)}
                          </span>
                          <span className="text-[7px] font-mono text-slate-600">
                            {start.toLocaleDateString()} {start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            {duration !== null && ` · ${duration}m`}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                          {sess.persons_seen?.length > 0 && (
                            <span className="text-[7px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-mono">
                              {sess.persons_seen.length} people
                            </span>
                          )}
                          {isExpanded ? <ChevronUp size={10} className="text-slate-600" /> : <ChevronDown size={10} className="text-slate-600" />}
                        </div>
                      </button>
                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="px-2.5 pb-2.5 space-y-2 border-t border-white/[0.06]"
                          >
                            {sess.persons_seen?.length > 0 && (
                              <div className="pt-2">
                                <span className="text-[7px] font-mono text-slate-600 uppercase tracking-widest">Persons</span>
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {sess.persons_seen.map((p, j) => (
                                    <span key={j} className="text-[8px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-300 font-mono border border-blue-500/20">{p}</span>
                                  ))}
                                </div>
                              </div>
                            )}
                            {sess.conversation_lines?.length > 0 && (
                              <div>
                                <span className="text-[7px] font-mono text-slate-600 uppercase tracking-widest">Transcript</span>
                                <div className="mt-1 max-h-24 overflow-y-auto space-y-0.5">
                                  {sess.conversation_lines.map((line, j) => (
                                    <p key={j} className="text-[8px] font-mono text-slate-500 leading-snug">{line}</p>
                                  ))}
                                </div>
                              </div>
                            )}
                            {sess.encounters?.length > 0 && (
                              <p className="text-[7px] font-mono text-slate-700">{sess.encounters.length} encounters recorded</p>
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )
                })
              )}
            </div>
          </Panel>
        )

      default:
        return null
    }
  }

  // ─────────────────────────────────────────────
  //  Render
  // ─────────────────────────────────────────────
  const primaryPerson = detectedPersons[0]

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[#0b0f17] text-white selection:bg-cyan-500/20">
      {/* ── Shared Collapsible Left Navbar ── */}
      <CollapsibleNavbar currentModule="social" />

      {/* ── Main App Content ── */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-y-auto lg:overflow-hidden bg-[#0b0f17] relative">

      {/* ─── HEADER ─── */}
      <motion.header
        initial={{ y: -40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.4 }}
        className="relative z-10 px-4 md:px-6 py-2.5 md:h-14 flex flex-wrap md:flex-nowrap justify-between items-center gap-2
                   bg-[#0E131F]/90 backdrop-blur-2xl border-b border-white/[0.08]"
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
              <BrainCircuit className="text-white" size={16} />
            </div>
            {backendOnline && <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-[#0b0f17] animate-pulse" />}
          </div>
          <div>
            <h1 className="text-[13px] font-bold tracking-[0.12em] font-mono text-slate-100">
              CORTEXIUM 2.0
            </h1>
            <span className="text-[7px] font-mono text-slate-400 uppercase tracking-[0.25em]">
              Social Intelligence
            </span>
          </div>
        </div>

        {/* Status indicators */}
        <div className="flex items-center gap-3 md:gap-5 flex-wrap">
          {[
            { label: 'Voice', value: isAlwaysOn ? 'AMBIENT' : isRecording ? 'LIVE' : 'STANDBY', online: isAlwaysOn || isRecording },
            { label: 'Vision', value: visionOnline ? 'ACTIVE' : 'IDLE', online: visionOnline },
            { label: 'WS', value: wsConnected ? 'LIVE' : 'RECONNECTING', online: wsConnected },
          ].map(({ label, value, online }) => (
            <div key={label} className="flex flex-col items-end gap-0.5">
              <span className="text-[7px] text-slate-700 font-mono uppercase tracking-widest">{label}</span>
              <div className="flex items-center gap-1.5">
                <StatusDot online={online} />
                <span className={`text-[9px] font-mono font-bold ${online ? 'text-slate-300' : 'text-slate-600'}`}>{value}</span>
              </div>
            </div>
          ))}

          {!backendOnline && (
            <span className="text-[8px] font-mono text-red-400 animate-pulse tracking-widest">
              BACKEND OFFLINE
            </span>
          )}
        </div>
      </motion.header>

      {/* ─── MAIN ─── */}
      <main className="flex-1 relative z-10 grid grid-cols-1 lg:grid-cols-12 overflow-y-auto lg:overflow-hidden min-h-0">

        {/* LEFT PANEL */}
        <div className="col-span-1 lg:col-span-3 p-3 flex flex-col gap-3 bg-gradient-to-r from-black/60 to-transparent overflow-y-auto">

          {/* Session Control */}
          <Panel title="Session" icon={Camera} accent="cyan">
            {!sessionStarted ? (
              <motion.button
                whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                onClick={startSession}
                disabled={!backendOnline}
                className="w-full py-5 rounded-2xl flex flex-col items-center justify-center gap-2.5
                           bg-gradient-to-br from-cyan-600 to-blue-700 text-white
                           shadow-[0_0_32px_rgba(6,182,212,0.3)] border border-cyan-500/30
                           hover:shadow-[0_0_48px_rgba(6,182,212,0.45)] transition-all disabled:opacity-30
                           pointer-events-auto"
              >
                <Play size={20} className="drop-shadow-lg" />
                <span className="text-[9px] font-mono font-bold tracking-[0.3em] uppercase">Start Session</span>
                <span className="text-[7px] font-mono text-cyan-200/60">Camera will activate</span>
              </motion.button>
            ) : (
              <div className="space-y-2.5">
                {/* Session live badge */}
                <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-500/[0.08] border border-emerald-500/20">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-[9px] font-mono text-emerald-400 flex-1">Session Active</span>
                  {frameRate > 0 && (
                    <span className="text-[8px] font-mono text-slate-600">{frameRate}fps</span>
                  )}
                </div>

                {faceAnalysis.length > 0 && (
                  <div className="text-[8px] font-mono text-cyan-500 px-1">
                    {faceAnalysis.length} face{faceAnalysis.length !== 1 ? 's' : ''} in frame
                  </div>
                )}

                <button
                  onClick={endSession}
                  className="w-full py-2 rounded-xl flex items-center justify-center gap-2
                             bg-red-600/10 border border-red-500/25 text-red-400 text-[8px]
                             font-mono font-bold tracking-widest hover:bg-red-600/20
                             transition-all pointer-events-auto"
                >
                  <StopCircle size={11} /> END SESSION
                </button>
              </div>
            )}
          </Panel>

          {/* Detected Persons */}
          <Panel title="Live Detection" icon={ScanFace} accent="cyan">
            <div className="space-y-2">
              <AnimatePresence mode="popLayout">
                {detectedPersons.length > 0 ? (
                  detectedPersons.map((person) => (
                    <PersonRing
                      key={person.name}
                      person={person.name}
                      emotion={person.emotion}
                    />
                  ))
                ) : introDetected ? (
                  <motion.div
                    key="intro"
                    initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                    className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center gap-3"
                  >
                    <div className="w-8 h-8 rounded-full bg-amber-500/15 border border-amber-400/30
                                    flex items-center justify-center flex-shrink-0 animate-pulse">
                      <UserPlus className="text-amber-400" size={15} />
                    </div>
                    <div>
                      <span className="block text-[8px] text-amber-400 font-mono font-bold uppercase tracking-widest">Intro Detected</span>
                      <p className="text-[11px] font-semibold text-amber-200 mt-0.5">{pendingName}</p>
                      <span className="text-[7px] text-amber-500/60 font-mono">Align face for registration…</span>
                    </div>
                  </motion.div>
                ) : (
                  <div className="py-4 flex flex-col items-center justify-center text-slate-700 gap-2">
                    <Scan size={22} />
                    <span className="text-[9px] font-mono">
                      {sessionStarted ? 'Awaiting detection…' : 'Start session to begin'}
                    </span>
                  </div>
                )}
              </AnimatePresence>
            </div>

            {/* Voice Toggle */}
            <button
              onClick={toggleAlwaysOnVoice}
              disabled={!sessionStarted}
              className={`mt-3 w-full py-2.5 rounded-xl text-[9px] font-mono font-bold tracking-widest
                          transition-all pointer-events-auto flex items-center justify-center gap-2
                          ${isAlwaysOn
                            ? 'bg-emerald-600/15 text-emerald-400 border border-emerald-500/30'
                            : 'bg-cyan-600/15 hover:bg-cyan-600/20 text-cyan-400 border border-cyan-500/25 hover:border-cyan-500/40'
                          } disabled:opacity-25`}
            >
              {isAlwaysOn
                ? <><Waves className="animate-pulse" size={13} /> Listening Active</>
                : <><Mic size={13} /> Enable Voice</>
              }
            </button>
          </Panel>

          {/* Conversations hint when recognized */}
          {primaryPerson && (
            <Panel title="Active Person" icon={MessageSquare} accent="green">
              <div className="text-center py-2">
                <p className="text-sm font-semibold text-white">{primaryPerson.name}</p>
                <p className="text-[8px] font-mono text-slate-600 mt-1">
                  Voice transcripts auto-saving to profile
                </p>
                <button
                  onClick={() => setActiveTab('people')}
                  className="mt-2 text-[8px] font-mono text-cyan-500 hover:text-cyan-300 transition-colors"
                >
                  View conversation log →
                </button>
              </div>
            </Panel>
          )}
        </div>

        {/* CENTER — Camera Viewport */}
        <div className="col-span-1 lg:col-span-6 relative overflow-hidden bg-black min-h-[340px] lg:min-h-0 aspect-video lg:aspect-auto">

          {!sessionStarted ? (
            /* Pre-session splash */
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-6 pointer-events-auto">
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-80 h-80 relative">
                  <div className="absolute inset-0 border border-white/[0.04] rounded-full" />
                  <div className="absolute inset-6 border border-dashed border-cyan-500/10 rounded-full animate-spin" style={{ animationDuration: '25s' }} />
                  <div className="absolute inset-14 border border-dashed border-blue-500/08 rounded-full animate-spin" style={{ animationDuration: '18s', animationDirection: 'reverse' }} />
                </div>
              </div>
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                className="relative z-10 flex flex-col items-center gap-5"
              >
                <Radar size={40} className="text-cyan-500/30 animate-pulse" />
                <div className="text-center">
                  <p className="text-[10px] font-mono text-slate-600 tracking-widest uppercase mb-1">Cortexium Vision</p>
                  <p className="text-slate-700 text-[9px] font-mono">Start a session to activate camera</p>
                </div>
                <motion.button
                  whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                  onClick={startSession}
                  disabled={!backendOnline}
                  className="px-10 py-4 rounded-2xl flex items-center gap-3
                             bg-gradient-to-r from-cyan-600 to-blue-600
                             shadow-[0_0_48px_rgba(6,182,212,0.4)] border border-cyan-500/40
                             text-white text-[11px] font-mono font-bold tracking-[0.25em]
                             hover:shadow-[0_0_64px_rgba(6,182,212,0.6)] transition-all
                             disabled:opacity-30 pointer-events-auto"
                >
                  <Play size={18} />
                  START SESSION
                </motion.button>
                {!backendOnline && (
                  <p className="text-[8px] text-red-400 font-mono animate-pulse">Backend offline — run launch.bat first</p>
                )}
              </motion.div>
            </div>
          ) : (
            /* Live Camera Feed */
            <>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="absolute inset-0 w-full h-full object-cover transition-transform duration-200"
                style={{ transform: isMirrored ? 'scaleX(-1)' : 'none' }}
              />
              <canvas ref={canvasRef} className="hidden" />
              {/* Face Overlay */}
              <canvas
                ref={overlayCanvasRef}
                className="absolute inset-0 w-full h-full pointer-events-none"
                style={{ objectFit: 'cover' }}
              />
              {/* Scan line */}
              <div className="absolute inset-0 scan-line opacity-[0.07] pointer-events-none" />
              {/* HUD corners */}
              <div className="absolute top-4 left-4 w-6 h-6 border-l border-t border-cyan-500/40" />
              <div className="absolute top-4 right-4 w-6 h-6 border-r border-t border-cyan-500/40" />
              <div className="absolute bottom-4 left-4 w-6 h-6 border-l border-b border-cyan-500/30" />
              <div className="absolute bottom-4 right-4 w-6 h-6 border-r border-b border-cyan-500/30" />
              {/* Status badges */}
              <div className="absolute top-5 left-5 flex items-center gap-2 pointer-events-auto">
                {frameRate > 0 && (
                  <div className="px-2 py-1 bg-black/50 rounded text-[8px] font-mono text-cyan-500 backdrop-blur-sm border border-cyan-500/20">
                    {frameRate} fps
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => setIsMirrored(prev => !prev)}
                  className={`px-2.5 py-1 rounded text-[8px] font-mono border backdrop-blur-sm transition-all flex items-center gap-1.5 cursor-pointer ${
                    isMirrored
                      ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300 shadow-[0_0_12px_rgba(6,182,212,0.15)]'
                      : 'bg-black/60 border-white/10 text-slate-400 hover:text-white'
                  }`}
                  title="Toggle Mirror Mode for camera orientation"
                >
                  <FlipHorizontal size={10} />
                  <span>{isMirrored ? 'MIRROR: ON' : 'MIRROR: OFF'}</span>
                </button>
              </div>
              <div className="absolute top-5 right-5 flex items-center gap-1.5 px-2.5 py-1
                              bg-black/50 rounded-full border border-emerald-500/20 backdrop-blur-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[7px] font-mono text-emerald-400 uppercase tracking-wider">Live</span>
              </div>
              {/* Person name badges + face-anchored summary cards */}
              {detectedPersons.length > 0 && (
                <div className="absolute bottom-16 left-1/2 -translate-x-1/2 flex gap-2 flex-wrap justify-center">
                  {detectedPersons.map((p) => (
                    <motion.div
                      key={p.name}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="px-3 py-1 bg-black/60 border border-cyan-500/40 rounded-full backdrop-blur-sm
                                 flex items-center gap-1.5 cursor-pointer"
                      onClick={() => fetchFaceSummary(p.name)}
                    >
                      <CheckCircle size={10} className="text-emerald-400" />
                      <span className="text-[9px] font-mono text-white">{p.name}</span>
                      <span className="text-[8px] font-mono text-slate-500">{Math.round((p.confidence || 0) * 100)}%</span>
                      <span className="text-[7px] font-mono text-cyan-500/50 ml-0.5">tap</span>
                    </motion.div>
                  ))}
                </div>
              )}
              {/* Face-anchored conversation summary card */}
              <AnimatePresence>
                {faceCard && (
                  <motion.div
                    initial={{ opacity: 0, x: 16, y: -8 }}
                    animate={{ opacity: 1, x: 0, y: 0 }}
                    exit={{ opacity: 0, x: 16 }}
                    transition={{ type: 'spring', stiffness: 260, damping: 22 }}
                    className="absolute top-16 right-4 w-60 rounded-2xl overflow-hidden z-10
                               border border-cyan-500/25 shadow-[0_0_40px_rgba(6,182,212,0.10)]"
                    style={{ background: 'rgba(8,12,18,0.92)', backdropFilter: 'blur(20px)' }}
                  >
                    {/* Card header */}
                    <div className="flex items-center justify-between px-3.5 py-2.5
                                    border-b border-white/[0.06]"
                      style={{ background: 'rgba(6,182,212,0.05)' }}>
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-lg bg-cyan-500/15 border border-cyan-500/25
                                        flex items-center justify-center">
                          <MessageSquare size={10} className="text-cyan-400" />
                        </div>
                        <div>
                          <p className="text-white font-semibold text-[11px] leading-none">{faceCard.personName}</p>
                          {faceCard.role && (
                            <p className="text-[7px] font-mono text-cyan-400/60 mt-0.5">{faceCard.role}</p>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() => setFaceCard(null)}
                        className="text-slate-700 hover:text-slate-400 transition-colors p-0.5 rounded"
                      >
                        <X size={12} />
                      </button>
                    </div>
                    {/* Summary body */}
                    <div className="px-3.5 py-3">
                      {faceCard.loading ? (
                        <div className="flex items-center gap-2 text-slate-600">
                          <RefreshCw size={11} className="animate-spin" />
                          <span className="text-[9px] font-mono">Loading…</span>
                        </div>
                      ) : faceCard.summary ? (
                        <p className="text-[10px] text-slate-300 leading-relaxed">
                          {faceCard.summary}
                        </p>
                      ) : (
                        <div className="space-y-1 py-0.5">
                          <p className="text-[9px] text-slate-400 font-mono italic">No summary requested yet.</p>
                          <p className="text-[8px] text-cyan-400/80 font-mono leading-relaxed">
                            Ask &ldquo;what did we talk about last time?&rdquo; to recall.
                          </p>
                        </div>
                      )}
                    </div>
                    {/* Card footer */}
                    {!faceCard.loading && (
                      <div className="px-3.5 pb-3 flex items-center gap-3">
                        {faceCard.lastSeen && (
                          <span className="text-[7px] font-mono text-slate-700">{faceCard.lastSeen}</span>
                        )}
                        {faceCard.sessionCount > 0 && (
                          <span className="text-[7px] font-mono text-slate-700">
                            {faceCard.sessionCount} session{faceCard.sessionCount !== 1 ? 's' : ''}
                          </span>
                        )}
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </>
          )}

          {/* Live Subtitles */}
          <AnimatePresence>
            {(isRecording || transcription) && (
              <LiveSubtitles
                text={interimText || transcription}
                isFinal={!!transcription && !interimText}
              />
            )}
          </AnimatePresence>

          {/* Notification Toast */}
          <AnimatePresence>
            {notification && <Toast notification={notification} />}
          </AnimatePresence>
        </div>

        {/* RIGHT PANEL */}
        <div className="col-span-1 lg:col-span-3 p-3 flex flex-col gap-3 bg-gradient-to-l from-black/60 to-transparent overflow-y-auto">
          {renderRightPanel()}
        </div>
      </main>

      {/* ─── FOOTER / Tab Nav ─── */}
      <footer className="relative z-10 px-5 h-12 flex justify-between items-center
                         bg-black/50 backdrop-blur-2xl border-t border-white/[0.06]">
        {/* Tab Navigation */}
        <div className="flex gap-1">
          {[
            { id: 'vision',   label: 'Vision',   icon: Camera },
            { id: 'bio-logs', label: 'Bio-Logs', icon: Users },
            { id: 'people',   label: 'People',   icon: UserPlus },
            { id: 'agents',   label: 'Agents',   icon: BrainCircuit },
            { id: 'systems',  label: 'Systems',  icon: Activity },
            { id: 'history',  label: 'History',  icon: History },
          ].map(({ id, label, icon: Icon }) => (
            <button key={id}
              onClick={() => setActiveTab(id)}
              className={`px-4 py-1.5 rounded-lg text-[8px] font-mono font-bold tracking-widest
                          transition-all flex items-center gap-1.5
                          ${activeTab === id
                            ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                            : 'text-slate-600 hover:text-slate-400 hover:bg-white/[0.04] border border-transparent'
                          }`}
            >
              <Icon size={10} />
              {label}
            </button>
          ))}
        </div>

        {/* Footer Stats */}
        <div className="flex items-center gap-4 text-slate-700 font-mono text-[7px]">
          <span className={wsConnected ? 'text-emerald-500' : 'text-amber-600 animate-pulse'}>
            {wsConnected ? '● WS LIVE' : '◌ RECONNECTING'}
          </span>
          <span>SESSION: {sessionIdDisplay.split('_')[1] || '—'}</span>
          <span>LOCAL · AES-256</span>
        </div>
      </footer>

      {/* No popup — conversation card is inline on the camera view */}
      </div>
    </div>
  )
}
