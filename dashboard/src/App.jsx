/**
 * Cortexium XR — Central Dashboard
 *
 * Design system: Stitch MCP (Cortexium XR project 4242614913711395722)
 * Layout: Hero → Story → Module Launchers (3 cards) → XR Roadmap → Footer
 * Modules open in new tab at their respective frontend ports.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, useInView, AnimatePresence } from 'framer-motion'
import {
  Users, Box, Plus, Activity, Wifi, WifiOff,
  ExternalLink, ChevronRight, Lock, Zap, Eye,
  Brain, Globe, Cpu, Shield, Radio, Layers, Car
} from 'lucide-react'

// ─────────────────────────────────────────────
// Animated Background — neural mesh particles
// ─────────────────────────────────────────────
function NeuralBackground() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let animId

    const resize = () => {
      canvas.width  = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    const NODES = 55
    const nodes = Array.from({ length: NODES }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
      r: Math.random() * 1.5 + 0.5,
    }))

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Draw connections
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x
          const dy = nodes[i].y - nodes[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 140) {
            const alpha = (1 - dist / 140) * 0.12
            ctx.beginPath()
            ctx.strokeStyle = `rgba(0, 242, 255, ${alpha})`
            ctx.lineWidth = 0.5
            ctx.moveTo(nodes[i].x, nodes[i].y)
            ctx.lineTo(nodes[j].x, nodes[j].y)
            ctx.stroke()
          }
        }
      }

      // Draw nodes
      nodes.forEach(n => {
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2)
        ctx.fillStyle = 'rgba(0, 242, 255, 0.4)'
        ctx.fill()
        n.x += n.vx
        n.y += n.vy
        if (n.x < 0 || n.x > canvas.width)  n.vx *= -1
        if (n.y < 0 || n.y > canvas.height) n.vy *= -1
      })

      animId = requestAnimationFrame(draw)
    }

    draw()
    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(animId)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed', inset: 0, zIndex: 0,
        pointerEvents: 'none', opacity: 0.7,
      }}
    />
  )
}

// ─────────────────────────────────────────────
// Floating Orbs — ambient glow
// ─────────────────────────────────────────────
function AmbientOrbs() {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', top: '-10%', left: '15%',
        width: 600, height: 600, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,242,255,0.06) 0%, transparent 70%)',
        filter: 'blur(60px)',
        animation: 'float 10s ease-in-out infinite',
      }} />
      <div style={{
        position: 'absolute', bottom: '10%', right: '10%',
        width: 500, height: 500, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(78,222,163,0.05) 0%, transparent 70%)',
        filter: 'blur(80px)',
        animation: 'float-2 14s ease-in-out infinite',
      }} />
      <div style={{
        position: 'absolute', top: '40%', right: '25%',
        width: 300, height: 300, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(124,58,237,0.04) 0%, transparent 70%)',
        filter: 'blur(60px)',
        animation: 'float 18s ease-in-out infinite reverse',
      }} />
    </div>
  )
}

// ─────────────────────────────────────────────
// Scan Line overlay
// ─────────────────────────────────────────────
function ScanLine() {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1, pointerEvents: 'none',
      background: 'repeating-linear-gradient(to bottom, transparent 0px, transparent 3px, rgba(0,242,255,0.012) 3px, rgba(0,242,255,0.012) 4px)',
    }} />
  )
}

// ─────────────────────────────────────────────
// Backend Health Hook
// ─────────────────────────────────────────────
function useBackendHealth() {
  const [status, setStatus] = useState('checking')

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('/api/health', { signal: AbortSignal.timeout(3000) })
        setStatus(res.ok ? 'online' : 'offline')
      } catch {
        setStatus('offline')
      }
    }
    check()
    const id = setInterval(check, 10000)
    return () => clearInterval(id)
  }, [])

  return status
}

// ─────────────────────────────────────────────
// Fade-up animation wrapper
// ─────────────────────────────────────────────
function FadeUp({ children, delay = 0, className = '', style = {} }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 24 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
      style={style}
    >
      {children}
    </motion.div>
  )
}

// ─────────────────────────────────────────────
// Navigation
// ─────────────────────────────────────────────
function Navbar({ backendStatus }) {
  const statusColor = backendStatus === 'online' ? '#00f2ff'
    : backendStatus === 'offline' ? '#f43f5e' : '#f59e0b'
  const statusLabel = backendStatus === 'online' ? 'System Active'
    : backendStatus === 'offline' ? 'Backend Offline' : 'Connecting...'

  const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })

  return (
    <nav style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 40px', height: 68,
      background: 'rgba(8, 12, 18, 0.7)',
      backdropFilter: 'blur(24px)',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
    }}>
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8,
          background: 'linear-gradient(135deg, rgba(0,242,255,0.2), rgba(0,242,255,0.05))',
          border: '1px solid rgba(0,242,255,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 12px rgba(0,242,255,0.2)',
        }}>
          <Cpu size={18} color="#00f2ff" />
        </div>
        <span style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 16, fontWeight: 700,
          color: '#e1fdff', letterSpacing: '0.08em',
        }}>
          CORTEXIUM
        </span>
        <div style={{
          marginLeft: 8, padding: '3px 10px',
          borderRadius: 4,
          background: `rgba(${backendStatus === 'online' ? '0,242,255' : backendStatus === 'offline' ? '244,63,94' : '245,158,11'},0.1)`,
          border: `1px solid ${statusColor}`,
          boxShadow: `0 0 4px ${statusColor}80`,
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: statusColor,
            animation: backendStatus === 'online' ? 'pulse-dot 2s infinite' : 'none',
          }} />
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10, color: statusColor, letterSpacing: '0.1em', textTransform: 'uppercase',
          }}>{statusLabel}</span>
        </div>
      </div>

      {/* Nav links */}
      <div style={{ display: 'flex', gap: 32 }}>
        {[['Dashboard', 'hero'], ['Modules', 'modules'], ['Story', 'story'], ['Roadmap', 'roadmap']].map(([label, id]) => (
          <button key={id} onClick={() => scrollTo(id)} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase',
            color: '#b9cacb', transition: 'color 0.2s',
            padding: '4px 0',
          }}
          onMouseEnter={e => e.target.style.color = '#00f2ff'}
          onMouseLeave={e => e.target.style.color = '#b9cacb'}
          >{label}</button>
        ))}
      </div>

      {/* CTA */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 10, color: '#849495', letterSpacing: '0.08em',
        }}>v2.0.0</span>
        <button
          onClick={() => document.getElementById('modules')}
          className="btn-primary"
        >
          <Zap size={12} />
          Launch Module
        </button>
      </div>
    </nav>
  )
}

// ─────────────────────────────────────────────
// Hero Section
// ─────────────────────────────────────────────
function HeroSection() {
  return (
    <section id="hero" style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      textAlign: 'center', padding: '120px 40px 80px',
      position: 'relative', zIndex: 2,
    }}>
      {/* System label */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        style={{ marginBottom: 24 }}
      >
        <span style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11, letterSpacing: '0.25em', textTransform: 'uppercase',
          color: '#00f2ff',
          padding: '6px 16px', borderRadius: 4,
          background: 'rgba(0,242,255,0.06)',
          border: '1px solid rgba(0,242,255,0.2)',
        }}>
          XR Intelligence Platform — v2.0
        </span>
      </motion.div>

      {/* Main headline */}
      <motion.h1
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
        style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 'clamp(48px, 8vw, 84px)',
          fontWeight: 700, lineHeight: 1.05,
          letterSpacing: '-0.02em',
          color: '#00f2ff',
          textShadow: '0 0 60px rgba(0,242,255,0.4), 0 0 120px rgba(0,242,255,0.15)',
          marginBottom: 24, maxWidth: 900,
        }}
      >
        ADAPTIVE REALITY<br />
        <span style={{ color: '#e1fdff', textShadow: 'none' }}>ENGINE</span>
      </motion.h1>

      {/* Subtitle */}
      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.4 }}
        style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: 18, fontWeight: 400, lineHeight: 1.6,
          color: '#b9cacb', maxWidth: 580, marginBottom: 48,
        }}
      >
        Seamlessly weaving neural intelligence overlays into physical environments via XR HUD — designed for Meta glasses, Apple Vision Pro, and beyond.
      </motion.p>

      {/* CTA row */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.55 }}
        style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'center' }}
      >
        <button
          onClick={() => document.getElementById('modules')?.scrollIntoView({ behavior: 'smooth' })}
          style={{
            background: 'rgba(0,242,255,0.15)',
            border: '1px solid rgba(0,242,255,0.6)',
            color: '#00f2ff',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 12, letterSpacing: '0.1em', textTransform: 'uppercase',
            padding: '12px 32px', borderRadius: 6,
            cursor: 'pointer', transition: 'all 0.2s',
            display: 'flex', alignItems: 'center', gap: 8,
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0,242,255,0.25)'; e.currentTarget.style.boxShadow = '0 0 20px rgba(0,242,255,0.3)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(0,242,255,0.15)'; e.currentTarget.style.boxShadow = 'none' }}
        >
          <Layers size={14} />
          Explore Modules
        </button>
        <button
          onClick={() => document.getElementById('story')?.scrollIntoView({ behavior: 'smooth' })}
          style={{
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.12)',
            color: '#b9cacb',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 12, letterSpacing: '0.1em', textTransform: 'uppercase',
            padding: '12px 32px', borderRadius: 6,
            cursor: 'pointer', transition: 'all 0.2s',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.25)'; e.currentTarget.style.color = '#e1fdff' }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)'; e.currentTarget.style.color = '#b9cacb' }}
        >
          The Vision
        </button>
      </motion.div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.2, duration: 0.5 }}
        style={{
          position: 'absolute', bottom: 40, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
        }}
      >
        <span style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: '#849495', letterSpacing: '0.15em' }}>SCROLL</span>
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          style={{ width: 1, height: 30, background: 'linear-gradient(to bottom, #00f2ff, transparent)' }}
        />
      </motion.div>
    </section>
  )
}

// ─────────────────────────────────────────────
// Story Section
// ─────────────────────────────────────────────
function StorySection() {
  const steps = [
    { icon: <Eye size={20} color="#00f2ff" />, label: 'Perceive', desc: 'Real-time camera feeds, spatial sensors, and environmental data are continuously ingested.' },
    { icon: <Brain size={20} color="#4edea3" />, label: 'Process', desc: 'AI agents analyze, recognize, and contextualize every element in the scene simultaneously.' },
    { icon: <Globe size={20} color="#d2bbff" />, label: 'Project', desc: 'Structured intelligence overlays are anchored to the real world at sub-millisecond latency.' },
  ]

  return (
    <section id="story" style={{ padding: '120px 40px', position: 'relative', zIndex: 2 }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>

        <FadeUp style={{ marginBottom: 64, textAlign: 'center' }}>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: 11, color: '#849495', letterSpacing: '0.2em', textTransform: 'uppercase' }}>
            Platform Overview
          </span>
        </FadeUp>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 64 }}>
          {/* The Vision */}
          <FadeUp delay={0.1}>
            <div className="glass-panel glass-panel-hover" style={{ padding: 40, height: '100%', position: 'relative', overflow: 'hidden' }}>
              <div className="accent-line-cyan" style={{ position: 'absolute', top: 0, left: 0, width: 2, height: '100%' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                <Eye size={24} color="#00f2ff" />
                <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 600, color: '#e1fdff' }}>
                  The Vision
                </h2>
              </div>
              <p style={{ fontFamily: 'Inter, sans-serif', fontSize: 15, lineHeight: 1.75, color: '#b9cacb' }}>
                The future of human-computer interaction transcends screens. Cortexium XR integrates high-dimensional intelligence directly into your spatial awareness — creating an intuitive head-up display that reacts to context in real time.
              </p>
              <p style={{ fontFamily: 'Inter, sans-serif', fontSize: 15, lineHeight: 1.75, color: '#b9cacb', marginTop: 16 }}>
                We are building the foundational infrastructure for the next paradigm of digital existence — where information is ambient, adaptive, and felt rather than merely seen. Designed from the ground up for Meta glasses, Apple Vision Pro, and future XR hardware.
              </p>
            </div>
          </FadeUp>

          {/* How It Works */}
          <FadeUp delay={0.2}>
            <div className="glass-panel glass-panel-hover" style={{ padding: 40, height: '100%', position: 'relative', overflow: 'hidden' }}>
              <div className="accent-line-green" style={{ position: 'absolute', top: 0, left: 0, width: 2, height: '100%' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
                <Activity size={24} color="#4edea3" />
                <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 22, fontWeight: 600, color: '#e1fdff' }}>
                  How It Works
                </h2>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {steps.map((s, i) => (
                  <div key={i} style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
                    <div style={{
                      width: 36, height: 36, flexShrink: 0, borderRadius: 8,
                      background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {s.icon}
                    </div>
                    <div>
                      <span style={{ fontFamily: 'JetBrains Mono', fontSize: 11, color: '#849495', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                        Step 1 — {s.label}
                      </span>
                      <p style={{ fontFamily: 'Inter', fontSize: 14, color: '#b9cacb', lineHeight: 1.6, marginTop: 4 }}>{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </FadeUp>
        </div>

        {/* Stats bar */}
        <FadeUp delay={0.3}>
          <div className="glass-panel" style={{
            padding: '24px 40px',
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 24, textAlign: 'center',
          }}>
            {[
              { val: '3', label: 'Active Modules', color: '#00f2ff' },
              { val: 'XR', label: 'Display Mode', color: '#4edea3' },
              { val: '∞', label: 'Context Threads', color: '#d2bbff' },
              { val: '< 1ms', label: 'Overlay Latency', color: '#f59e0b' },
            ].map((s, i) => (
              <div key={i}>
                <div style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 28, fontWeight: 700, color: s.color,
                  textShadow: `0 0 20px ${s.color}60`,
                }}>{s.val}</div>
                <div style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#849495', letterSpacing: '0.12em', textTransform: 'uppercase', marginTop: 4 }}>{s.label}</div>
              </div>
            ))}
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

// ─────────────────────────────────────────────
// Module Card Component
// ─────────────────────────────────────────────
function ModuleCard({ module, index }) {
  const [hovered, setHovered] = useState(false)

  const accentClass = module.accent === 'cyan' ? 'module-card-cyan'
    : module.accent === 'green' ? 'module-card-green'
    : 'module-card-locked'

  const launch = () => {
    if (module.url) window.open(module.url, '_blank')
  }

  return (
    <FadeUp delay={0.1 * index}>
      <div
        className={`glass-panel glass-panel-hover ${accentClass}`}
        style={{
          padding: 32, cursor: module.url ? 'pointer' : 'default',
          border: `1px solid ${module.borderColor}`,
          position: 'relative', overflow: 'hidden', height: '100%',
          display: 'flex', flexDirection: 'column',
        }}
        onMouseEnter={() => setHovered(false)}
        onMouseLeave={() => setHovered(false)}
        onClick={launch}
      >
        {/* Locked overlay */}
        {module.locked && (
          <div style={{
            position: 'absolute', inset: 0, zIndex: 10,
            background: 'rgba(16,20,26,0.25)',
            backdropFilter: 'blur(2px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Lock size={36} color="rgba(228,212,255,0.5)" />
          </div>
        )}

        {/* Top row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32 }}>
          <div style={{
            width: 48, height: 48, borderRadius: 10,
            background: `rgba(${module.rgbAccent}, 0.08)`,
            border: `1px solid rgba(${module.rgbAccent}, 0.2)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'transform 0.2s',
            transform: hovered && !module.locked ? 'scale(1.1)' : 'scale(1)',
          }}>
            <module.Icon size={22} color={module.accentColor} />
          </div>

          <span style={{
            padding: '4px 10px', borderRadius: 4,
            fontFamily: 'JetBrains Mono', fontSize: 9,
            letterSpacing: '0.12em', textTransform: 'uppercase',
            background: `rgba(${module.rgbAccent}, 0.1)`,
            border: `1px solid ${module.accentColor}`,
            color: module.accentColor,
            boxShadow: `0 0 6px ${module.accentColor}60`,
          }}>
            {module.status}
          </span>
        </div>

        {/* Content */}
        <div style={{ flex: 1 }}>
          <h3 style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 20, fontWeight: 600,
            color: '#e1fdff', marginBottom: 10,
          }}>{module.name}</h3>
          <p style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: 14, lineHeight: 1.65, color: '#b9cacb',
          }}>{module.description}</p>
        </div>

        {/* Divider */}
        <div style={{
          margin: '24px 0',
          height: 1,
          background: `linear-gradient(to right, rgba(${module.rgbAccent}, 0.4), transparent)`,
        }} />

        {/* Launch button or coming soon */}
        {module.url ? (
          <button
            style={{
              background: 'transparent', border: 'none',
              display: 'flex', alignItems: 'center', gap: 8,
              fontFamily: 'JetBrains Mono', fontSize: 11,
              color: module.accentColor, cursor: 'pointer',
              letterSpacing: '0.1em', textTransform: 'uppercase',
              padding: 0, transition: 'gap 0.2s',
            }}
          >
            <ExternalLink size={13} />
            Launch Module
            <ChevronRight size={13} style={{ marginLeft: 'auto' }} />
          </button>
        ) : (
          <span style={{
            fontFamily: 'JetBrains Mono', fontSize: 10,
            color: '#849495', letterSpacing: '0.12em', textTransform: 'uppercase',
          }}>
            Coming Soon
          </span>
        )}
      </div>
    </FadeUp>
  )
}

// ─────────────────────────────────────────────
// Modules Section
// ─────────────────────────────────────────────
function ModulesSection() {
  const modules = [
    {
      name: 'Social Intelligence',
      description: 'Real-time face recognition, person memory, voice integration, and social context overlays. Understand who is around you and build persistent relationship graphs.',
      Icon: Users,
      accent: 'cyan',
      accentColor: '#00f2ff',
      rgbAccent: '0,242,255',
      borderColor: 'rgba(0,242,255,0.2)',
      status: 'Online',
      url: '/module/social',
      locked: false,
    },
    {
      name: 'Spatial Organizer',
      description: 'AI-powered spatial object detection and adaptive placement intelligence. Teaches your space to organize itself using YOLO and a personalized CatBoost ML model.',
      Icon: Box,
      accent: 'green',
      accentColor: '#4edea3',
      rgbAccent: '78,222,163',
      borderColor: 'rgba(78,222,163,0.2)',
      status: 'Online',
      url: '/module/organizer',
      locked: false,
    },
    {
      name: 'Vehicle Telemetry & 3D AR HUD',
      description: 'Context-aware ADAS driving assistant with monocular headway ranging, 3D perspective AR chevrons, lane drift analysis, turn-by-turn navigation, and automated PDF safety audits.',
      Icon: Car,
      accent: 'cyan',
      accentColor: '#00f2ff',
      rgbAccent: '0,242,255',
      borderColor: 'rgba(0,242,255,0.2)',
      status: 'Online',
      url: '/module/vehicle',
      locked: false,
    },
  ]

  return (
    <section id="modules" style={{ padding: '80px 40px 120px', position: 'relative', zIndex: 2 }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>

        <FadeUp style={{ marginBottom: 48 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, paddingBottom: 20, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: 11, color: '#849495', letterSpacing: '0.2em', textTransform: 'uppercase' }}>
              Active Modules
            </span>
            <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.04)' }} />
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#849495', letterSpacing: '0.1em' }}>
              3 / 3 deployed
            </span>
          </div>
        </FadeUp>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24 }}>
          {modules.map((m, i) => <ModuleCard key={m.name} module={m} index={i} />)}
        </div>
      </div>
    </section>
  )
}

// ─────────────────────────────────────────────
// XR Roadmap Section
// ─────────────────────────────────────────────
function RoadmapSection() {
  const phases = [
    { phase: 'Phase 1', label: 'Monitor Display', desc: 'Running now — full AI pipeline on desktop screen.', active: true, icon: <Cpu size={18} color="#00f2ff" /> },
    { phase: 'Phase 2', label: 'Mobile AR', desc: 'Camera overlay via iOS/Android WebXR session.', active: false, icon: <Radio size={18} color="#849495" /> },
    { phase: 'Phase 3', label: 'Smart Glasses', desc: 'Meta Ray-Ban, Snap Spectacles passthrough mode.', active: false, icon: <Eye size={18} color="#849495" /> },
    { phase: 'Phase 4', label: 'Full XR Headset', desc: 'Apple Vision Pro / Meta Quest immersive deployment.', active: false, icon: <Globe size={18} color="#849495" /> },
  ]

  return (
    <section id="roadmap" style={{ padding: '80px 40px 120px', position: 'relative', zIndex: 2 }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>

        <FadeUp style={{ marginBottom: 48 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, paddingBottom: 20, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: 11, color: '#849495', letterSpacing: '0.2em', textTransform: 'uppercase' }}>
              XR Deployment Roadmap
            </span>
          </div>
        </FadeUp>

        {/* Timeline */}
        <div style={{ position: 'relative' }}>
          {/* Connector line */}
          <div style={{
            position: 'absolute', top: 20, left: '10%', right: '10%', height: 1,
            background: 'rgba(255,255,255,0.08)',
          }} />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24, position: 'relative', zIndex: 1 }}>
            {phases.map((p, i) => (
              <FadeUp key={i} delay={0.1 * i}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: '50%', marginBottom: 16,
                    background: p.active ? 'rgba(0,242,255,0.1)' : 'rgba(16,20,26,0.8)',
                    border: `2px solid ${p.active ? '#00f2ff' : '#3a494b'}`,
                    boxShadow: p.active ? '0 0 16px rgba(0,242,255,0.5)' : 'none',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 0.3s',
                  }}>
                    {p.icon}
                  </div>
                  <span style={{
                    fontFamily: 'JetBrains Mono', fontSize: 9,
                    color: p.active ? '#00f2ff' : '#849495',
                    letterSpacing: '0.12em', textTransform: 'uppercase',
                    marginBottom: 8,
                  }}>{p.phase}</span>
                  <h4 style={{
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: 16, fontWeight: 600,
                    color: p.active ? '#e1fdff' : '#849495',
                    marginBottom: 8,
                  }}>{p.label}</h4>
                  <p style={{
                    fontFamily: 'Inter', fontSize: 13,
                    color: p.active ? '#b9cacb' : '#849495',
                    lineHeight: 1.5,
                  }}>{p.desc}</p>
                  {p.active && (
                    <div style={{
                      marginTop: 12, padding: '3px 10px', borderRadius: 4,
                      background: 'rgba(0,242,255,0.1)', border: '1px solid rgba(0,242,255,0.4)',
                      fontFamily: 'JetBrains Mono', fontSize: 9, color: '#00f2ff',
                      letterSpacing: '0.1em', textTransform: 'uppercase',
                    }}>
                      Current
                    </div>
                  )}
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

// ─────────────────────────────────────────────
// Footer
// ─────────────────────────────────────────────
function Footer() {
  return (
    <footer style={{
      borderTop: '1px solid rgba(255,255,255,0.05)',
      background: 'rgba(10,14,20,0.8)',
      padding: '32px 40px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      position: 'relative', zIndex: 2,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Cpu size={16} color="#00f2ff" />
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 15, fontWeight: 600, color: '#e1fdff' }}>
          Cortexium XR
        </span>
        <span style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#849495' }}>v2.0</span>
      </div>

      <div style={{ display: 'flex', gap: 24 }}>
        {['API Backend :4040', 'Gateway :3020', 'Social :3021', 'Organizer :3022', 'Vehicle :3023'].map(s => (
          <span key={s} style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#849495', letterSpacing: '0.08em' }}>
            {s}
          </span>
        ))}
      </div>

      <span style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#849495' }}>
        © 2026 Cortexium XR — Neural Interface Active
      </span>
    </footer>
  )
}

// ─────────────────────────────────────────────
// Root App
// ─────────────────────────────────────────────
export default function App() {
  const backendStatus = useBackendHealth()

  return (
    <div style={{ position: 'relative', minHeight: '100vh' }}>
      <NeuralBackground />
      <AmbientOrbs />
      <ScanLine />
      <Navbar backendStatus={backendStatus} />
      <main>
        <HeroSection />
        <ModulesSection />
        <StorySection />
        <RoadmapSection />
      </main>
      <Footer />
    </div>
  )
}
