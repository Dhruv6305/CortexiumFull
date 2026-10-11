/**
 * Cortexium XR 2.0 — Central Gateway Dashboard
 * 
 * Calm, editorial, ambient computing hardware launch aesthetic.
 * Desktop-first, responsive, visual-led walkthrough for evaluation panels.
 */
import React, { useState, useEffect } from 'react'
import {
  Users,
  Box,
  Car,
  ChevronRight,
  ExternalLink,
  Shield,
  Eye,
  CheckCircle2,
  Clock,
  Layers,
  Sparkles,
  ArrowRight,
  Compass,
  Monitor,
  Glasses,
  Headset,
  Smartphone
} from 'lucide-react'

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
        // Fallback check to vehicle status
        try {
          const res2 = await fetch('/api/vehicle/status', { signal: AbortSignal.timeout(3000) })
          setStatus(res2.ok ? 'online' : 'offline')
        } catch {
          setStatus('offline')
        }
      }
    }
    check()
    const id = setInterval(check, 10000)
    return () => clearInterval(id)
  }, [])

  return status
}

export default function App() {
  const backendStatus = useBackendHealth()
  const [activeTab, setActiveTab] = useState('walkthrough')

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen bg-[#0B0F17] text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30">

      {/* ── 1. CLEAN EDITORIAL NAVBAR ──────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 h-16 bg-[#0B0F17]/85 backdrop-blur-xl border-b border-white/[0.08] px-6 lg:px-12 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-white/[0.06] border border-white/[0.12] flex items-center justify-center font-bold text-sm tracking-tight text-slate-100">
            C
          </div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm tracking-wide text-white">Cortexium XR</span>
            <span className="text-[11px] font-mono text-slate-400 px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08]">
              v2.0
            </span>
          </div>
        </div>

        {/* Navigation Anchors */}
        <div className="hidden md:flex items-center gap-8 text-xs font-medium text-slate-400">
          <button onClick={() => scrollTo('hero')} className="hover:text-white transition-colors">Overview</button>
          <button onClick={() => scrollTo('why-glasses')} className="hover:text-white transition-colors">Why Glasses</button>
          <button onClick={() => scrollTo('walkthrough-social')} className="hover:text-white transition-colors">Social Recall</button>
          <button onClick={() => scrollTo('walkthrough-organizer')} className="hover:text-white transition-colors">Spatial Memory</button>
          <button onClick={() => scrollTo('walkthrough-vehicle')} className="hover:text-white transition-colors">Driver Clarity</button>
          <button onClick={() => scrollTo('roadmap')} className="hover:text-white transition-colors">Roadmap</button>
        </div>

        {/* Status & CTA */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-slate-400">
            <span className={`w-2 h-2 rounded-full ${backendStatus === 'online' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            <span>{backendStatus === 'online' ? 'System Online' : 'Local Fallback'}</span>
          </div>

          <button
            onClick={() => scrollTo('modules')}
            className="px-4 py-2 rounded-xl bg-white/[0.08] hover:bg-white/[0.14] border border-white/[0.12] text-xs font-semibold text-white transition-all shadow-sm"
          >
            Launch Modules
          </button>
        </div>
      </nav>

      {/* ── 2. HERO / LANDING SECTION (SCREEN A) ───────────────── */}
      <section id="hero" className="pt-32 pb-20 px-6 lg:px-12 max-w-7xl mx-auto w-full min-h-[92vh] flex items-center">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center w-full">
          
          {/* Left Text Column */}
          <div className="lg:col-span-5 flex flex-col gap-6 text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.08] w-fit text-xs text-slate-400 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              <span>Cortexium XR 2.0 / Ambient Intelligence</span>
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white leading-[1.08]">
              Computing belongs in your line of sight.
            </h1>

            <p className="text-base text-slate-400 leading-relaxed font-normal max-w-lg">
              Real-time social recall, spatial organization, and driver clarity — without looking down at a screen.
            </p>

            <div className="flex flex-wrap items-center gap-4 pt-2">
              <button
                onClick={() => scrollTo('why-glasses')}
                className="px-6 py-3 rounded-xl bg-amber-100 hover:bg-amber-200 text-slate-900 font-semibold text-xs transition-all shadow-md active:scale-95 flex items-center gap-2"
              >
                <span>Explore Walkthrough</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>

              <button
                onClick={() => scrollTo('modules')}
                className="px-6 py-3 rounded-xl bg-white/[0.05] hover:bg-white/[0.10] border border-white/[0.10] text-slate-200 font-medium text-xs transition-all"
              >
                Launch Platform
              </button>
            </div>
          </div>

          {/* Right Hero Visual Column */}
          <div className="lg:col-span-7 flex justify-center">
            <div className="relative rounded-3xl overflow-hidden border border-white/[0.10] shadow-2xl bg-black/30 max-h-[620px] w-full">
              <img
                src="/media/hero-smart-glasses.jpg"
                alt="Person wearing smart spectacles with ambient AR display"
                className="w-full h-full object-cover rounded-3xl"
              />
            </div>
          </div>

        </div>
      </section>

      {/* ── 3. WHY GLASSES SECTION (SCREEN B) ──────────────────── */}
      <section id="why-glasses" className="py-24 px-6 lg:px-12 max-w-7xl mx-auto w-full border-t border-white/[0.06]">
        <div className="flex flex-col gap-10">
          <div className="flex flex-col gap-2 max-w-2xl">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">The Paradigm Shift</span>
            <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
              Shift your attention back to the world.
            </h2>
            <p className="text-sm text-slate-400">
              Smart spectacles deliver ambient assistance without demanding physical head-down absorption.
            </p>
          </div>

          <div className="rounded-3xl overflow-hidden border border-white/[0.10] shadow-2xl bg-black/30">
            <img
              src="/media/why-glasses-comparison.jpg"
              alt="Visual comparison: Heads Down phone paradigm vs. Eyes Forward ambient glasses"
              className="w-full h-auto object-cover"
            />
          </div>
        </div>
      </section>

      {/* ── 4. MODULE WALKTHROUGHS ──────────────────────────────── */}
      
      {/* ── 4A. SOCIAL INTELLIGENCE (SCREEN C) ─────────────────── */}
      <section id="walkthrough-social" className="py-24 px-6 lg:px-12 max-w-7xl mx-auto w-full border-t border-white/[0.06]">
        <div className="flex flex-col gap-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div className="flex flex-col gap-2">
              <span className="text-xs font-mono uppercase tracking-wider text-cyan-400">01 / Ambient Perception</span>
              <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
                Social Intelligence — Instant Context, Seamless Recall
              </h2>
              <p className="text-sm text-slate-400 max-w-2xl">
                For continuous meetings and identifying specific colleagues in crowded conference venues.
              </p>
            </div>

            <a
              href="/module/social"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-xs font-semibold w-fit transition-all"
            >
              <span>Live Social App</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>

          <div className="rounded-3xl overflow-hidden border border-white/[0.10] shadow-2xl bg-black/30">
            <img
              src="/media/social-walkthrough.jpg"
              alt="Social Walkthrough: Meeting memory floating card & crowd locator highlight"
              className="w-full h-auto object-cover"
            />
          </div>
        </div>
      </section>

      {/* ── 4B. SPATIAL ORGANIZER (SCREEN D) ───────────────────── */}
      <section id="walkthrough-organizer" className="py-24 px-6 lg:px-12 max-w-7xl mx-auto w-full border-t border-white/[0.06]">
        <div className="flex flex-col gap-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div className="flex flex-col gap-2">
              <span className="text-xs font-mono uppercase tracking-wider text-emerald-400">02 / Spatial Memory</span>
              <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
                Spatial Organizer — Effortless Inventory & Placement Clarity
              </h2>
              <p className="text-sm text-slate-400 max-w-2xl">
                For shopkeepers and warehouse staff. Automatically detects misplaced stock and highlights the target shelf slot.
              </p>
            </div>

            <a
              href="/module/organizer"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs font-semibold w-fit transition-all"
            >
              <span>Live Organizer App</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>

          <div className="rounded-3xl overflow-hidden border border-white/[0.10] shadow-2xl bg-black/30">
            <img
              src="/media/organizer-walkthrough.jpg"
              alt="Spatial Organizer Walkthrough: Inventory detection brackets and green target placement slot"
              className="w-full h-auto object-cover"
            />
          </div>
        </div>
      </section>

      {/* ── 4C. VEHICLE INTELLIGENCE (SCREEN E - REVISED) ──────── */}
      <section id="walkthrough-vehicle" className="py-24 px-6 lg:px-12 max-w-7xl mx-auto w-full border-t border-white/[0.06]">
        <div className="flex flex-col gap-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div className="flex flex-col gap-2">
              <span className="text-xs font-mono uppercase tracking-wider text-amber-400">03 / Driver Safety & Clarity</span>
              <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
                Driver Clarity — Active Safety & Complex Highway Decision HUD
              </h2>
              <p className="text-sm text-slate-400 max-w-2xl">
                Drowsiness alert safety mode, and instant highway split clarity guiding you into the underpass instead of confusing bridge ramps.
              </p>
            </div>

            <a
              href="/module/vehicle"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-semibold w-fit transition-all"
            >
              <span>Live Vehicle App</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>

          {/* Revised Screen E Visual: View 1 (Safety Mode) + View 2 (Underpass Route) */}
          <div className="rounded-3xl overflow-hidden border border-white/[0.10] shadow-2xl bg-black/30">
            <img
              src="/media/vehicle-walkthrough.jpg"
              alt="Vehicle Walkthrough: Drowsiness Safety Mode & Underpass Decision HUD"
              className="w-full h-auto object-cover"
            />
          </div>
        </div>
      </section>

      {/* ── 5. FORM FACTOR ROADMAP (SCREEN F) ──────────────────── */}
      <section id="roadmap" className="py-24 px-6 lg:px-12 max-w-7xl mx-auto w-full border-t border-white/[0.06]">
        <div className="flex flex-col gap-10">
          <div className="flex flex-col gap-2 max-w-2xl">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Hardware Evolution</span>
            <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
              The Form Factor Evolution — Ambient Intelligence Roadmap
            </h2>
            <p className="text-sm text-slate-400">
              Cortexium XR spans from desktop monitor validation to daily smart spectacles and immersive XR hardware.
            </p>
          </div>

          <div className="rounded-3xl overflow-hidden border border-white/[0.10] shadow-2xl bg-black/30">
            <img
              src="/media/roadmap-evolution.jpg"
              alt="Hardware Roadmap progression: Monitor to Mobile AR to Smart Spectacles to XR Headset"
              className="w-full h-auto object-cover"
            />
          </div>
        </div>
      </section>

      {/* ── 6. LIVE MODULE LAUNCHER (SCREEN G) ─────────────────── */}
      <section id="modules" className="py-24 px-6 lg:px-12 max-w-7xl mx-auto w-full border-t border-white/[0.06]">
        <div className="flex flex-col gap-10">
          <div className="flex flex-col gap-2">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Live Ecosystem</span>
            <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
              Experience the Ecosystem — Live Modules
            </h2>
            <p className="text-sm text-slate-400">
              All modules run concurrently through the centralized port 3020 reverse proxy.
            </p>
          </div>

          {/* Three Clean Launcher Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

            {/* Card 1: Social Intelligence */}
            <div className="rounded-2xl p-6 bg-white/[0.03] border border-white/[0.08] hover:border-cyan-500/30 transition-all flex flex-col justify-between gap-6 group hover:bg-white/[0.04]">
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                      <Users className="w-4 h-4" />
                    </div>
                    <span className="text-base font-semibold text-white">Social Intelligence</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.05] text-slate-400 border border-white/[0.08]">
                    Port 3021
                  </span>
                </div>

                {/* Editorial Feature Highlights */}
                <div className="p-4 rounded-xl bg-black/30 border border-white/[0.06] flex flex-col gap-3">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Perception Engine:</span>
                    <span className="font-mono text-cyan-300">ArcFace + DeepFace</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Context Memory:</span>
                    <span className="font-mono text-slate-200">Local Knowledge Graph</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">HUD Overlay:</span>
                    <span className="font-mono text-emerald-400">Glanceable Name & Tags</span>
                  </div>
                </div>

                <p className="text-xs text-slate-400 leading-relaxed">
                  Real-time facial context, relationship graphs, and automated meeting memory cards.
                </p>
              </div>

              <a
                href="/module/social"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-2.5 rounded-xl bg-amber-100 hover:bg-amber-200 text-slate-900 font-semibold text-xs transition-all flex items-center justify-center gap-1.5 shadow-sm active:scale-95"
              >
                <span>Launch Social</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>

            {/* Card 2: Spatial Organizer */}
            <div className="rounded-2xl p-6 bg-white/[0.03] border border-white/[0.08] hover:border-emerald-500/30 transition-all flex flex-col justify-between gap-6 group hover:bg-white/[0.04]">
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                      <Box className="w-4 h-4" />
                    </div>
                    <span className="text-base font-semibold text-white">Spatial Organizer</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.05] text-slate-400 border border-white/[0.08]">
                    Port 3022
                  </span>
                </div>

                {/* Editorial Feature Highlights */}
                <div className="p-4 rounded-xl bg-black/30 border border-white/[0.06] flex flex-col gap-3">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Spatial Vision:</span>
                    <span className="font-mono text-emerald-300">YOLOv8 Detection</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Shelf Placement:</span>
                    <span className="font-mono text-slate-200">Dynamic Green AR Slot</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Inventory Sync:</span>
                    <span className="font-mono text-emerald-400">Misplacement Warning</span>
                  </div>
                </div>

                <p className="text-xs text-slate-400 leading-relaxed">
                  Adaptive spatial memory and shelf placement recommendation engine for retail and warehousing.
                </p>
              </div>

              <a
                href="/module/organizer"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-2.5 rounded-xl bg-amber-100 hover:bg-amber-200 text-slate-900 font-semibold text-xs transition-all flex items-center justify-center gap-1.5 shadow-sm active:scale-95"
              >
                <span>Launch Organizer</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>

            {/* Card 3: Vehicle HUD */}
            <div className="rounded-2xl p-6 bg-white/[0.03] border border-white/[0.08] hover:border-amber-500/30 transition-all flex flex-col justify-between gap-6 group hover:bg-white/[0.04]">
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                      <Car className="w-4 h-4" />
                    </div>
                    <span className="text-base font-semibold text-white">Vehicle HUD</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.05] text-slate-400 border border-white/[0.08]">
                    Port 3023
                  </span>
                </div>

                {/* Editorial Feature Highlights */}
                <div className="p-4 rounded-xl bg-black/30 border border-white/[0.06] flex flex-col gap-3">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Analysis Engine:</span>
                    <span className="font-mono text-amber-300">30 FPS Native OpenCV</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Safety Features:</span>
                    <span className="font-mono text-slate-200">Drowsiness & Collision</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Highway Split:</span>
                    <span className="font-mono text-emerald-400">Ground Underpass Route</span>
                  </div>
                </div>

                <p className="text-xs text-slate-400 leading-relaxed">
                  Driver safety cues, active telemetry cockpit, and highway underpass decision clarity.
                </p>
              </div>

              <a
                href="/module/vehicle"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-2.5 rounded-xl bg-amber-100 hover:bg-amber-200 text-slate-900 font-semibold text-xs transition-all flex items-center justify-center gap-1.5 shadow-sm active:scale-95"
              >
                <span>Launch Vehicle</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>

          </div>
        </div>
      </section>

      {/* ── 7. FOOTER ──────────────────────────────────────────── */}
      <footer className="border-t border-white/[0.06] py-12 px-6 lg:px-12 bg-[#090D14] text-xs text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-slate-300">Cortexium XR 2.0</span>
          <span>•</span>
          <span>Ambient Computing for Smart Spectacles</span>
        </div>

        <div className="flex items-center gap-6 font-mono text-[11px]">
          <span>Gateway: :3020</span>
          <span>Backend: :4040</span>
          <span>Social: :3021</span>
          <span>Organizer: :3022</span>
          <span>Vehicle: :3023</span>
        </div>
      </footer>

    </div>
  )
}
