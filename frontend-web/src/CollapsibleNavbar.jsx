import React, { useState, useEffect } from 'react'
import {
  LayoutDashboard,
  Layers,
  Users,
  Box,
  Car,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  BrainCircuit
} from 'lucide-react'

export default function CollapsibleNavbar({ currentModule = 'social' }) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      if (typeof window !== 'undefined' && window.location.search.includes('collapsed=true')) {
        return true
      }
      return localStorage.getItem('cortexium_sidebar_collapsed') === 'true'
    } catch (e) {
      return false
    }
  })

  const [modulesOpen, setModulesOpen] = useState(true)

  const toggleCollapsed = () => {
    setCollapsed(prev => {
      const next = !prev
      try {
        localStorage.setItem('cortexium_sidebar_collapsed', String(next))
      } catch (e) {}
      return next
    })
  }

  const getModuleUrl = (path) => {
    if (typeof window !== 'undefined' && ['3021', '3022', '3023'].includes(window.location.port)) {
      return `http://${window.location.hostname}:3020${path}`
    }
    return path
  }

  const getDashboardUrl = () => {
    if (typeof window !== 'undefined' && ['3021', '3022', '3023'].includes(window.location.port)) {
      return `http://${window.location.hostname}:3020/`
    }
    return '/'
  }

  const modules = [
    {
      id: 'social',
      name: 'Social Recall',
      path: '/module/social',
      port: ':3021',
      icon: Users,
      colorText: 'text-cyan-300',
      colorBg: 'bg-cyan-500/10 border-cyan-500/20',
      iconColor: 'text-cyan-400',
    },
    {
      id: 'organizer',
      name: 'Spatial Memory',
      path: '/module/organizer',
      port: ':3022',
      icon: Box,
      colorText: 'text-emerald-300',
      colorBg: 'bg-emerald-500/10 border-emerald-500/20',
      iconColor: 'text-emerald-400',
    },
    {
      id: 'vehicle',
      name: 'Vehicle HUD',
      path: '/module/vehicle',
      port: ':3023',
      icon: Car,
      colorText: 'text-amber-300',
      colorBg: 'bg-amber-500/10 border-amber-500/20',
      iconColor: 'text-amber-400',
    },
  ]

  return (
    <aside
      className={`relative z-40 border-r border-white/[0.08] bg-[#0E131F]/90 backdrop-blur-xl flex flex-col shrink-0 transition-all duration-300 select-none ${
        collapsed ? 'w-16 p-3 items-center' : 'w-64 p-4'
      }`}
      style={{ minHeight: '100vh' }}
    >
      {/* ── Header / Brand ── */}
      <div className={`flex items-center mb-6 ${collapsed ? 'justify-center flex-col gap-3' : 'justify-between'}`}>
        {!collapsed ? (
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-md">
              <BrainCircuit className="text-white w-4 h-4" />
            </div>
            <div>
              <span className="text-sm font-semibold text-white tracking-tight leading-none block">
                Cortexium XR
              </span>
              <span className="text-[10px] text-slate-400 font-mono leading-none mt-0.5 block">
                Platform 2.0
              </span>
            </div>
          </div>
        ) : (
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-md">
            <BrainCircuit className="text-white w-4 h-4" />
          </div>
        )}

        {/* Toggle Collapse Button */}
        <button
          type="button"
          onClick={toggleCollapsed}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-slate-400 hover:text-white transition-colors cursor-pointer"
        >
          {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* ── Navigation Links ── */}
      <div className="flex flex-col gap-1 w-full">
        {/* Dashboard Link */}
        <div className="relative group w-full">
          <a
            href={getDashboardUrl()}
            className={`flex items-center rounded-xl text-xs font-medium text-slate-400 hover:text-slate-100 hover:bg-white/[0.04] transition-colors ${
              collapsed ? 'justify-center p-2.5' : 'gap-3 px-3 py-2'
            }`}
          >
            <LayoutDashboard className="w-4 h-4 shrink-0" />
            {!collapsed && <span>Dashboard</span>}
          </a>

          {/* Minimized Tooltip */}
          {collapsed && (
            <div className="hidden group-hover:flex absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-[#0e131f] border border-white/10 text-xs text-slate-100 font-medium whitespace-nowrap shadow-2xl z-50 pointer-events-none items-center gap-1.5">
              <span>Dashboard</span>
            </div>
          )}
        </div>

        {/* Modules Section */}
        {!collapsed ? (
          <div className="flex flex-col gap-1 mt-2">
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
                className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${
                  modulesOpen ? 'rotate-0' : '-rotate-90'
                }`}
              />
            </button>

            {modulesOpen && (
              <div className="flex flex-col gap-1 pl-2.5 my-1 border-l border-white/[0.08] ml-4">
                {modules.map((m) => {
                  const isActive = currentModule === m.id
                  const Icon = m.icon
                  return (
                    <a
                      key={m.id}
                      href={getModuleUrl(m.path)}
                      className={`flex items-center justify-between px-2.5 py-2 rounded-xl text-xs transition-all ${
                        isActive
                          ? `font-semibold ${m.colorText} ${m.colorBg} border shadow-sm`
                          : 'font-medium text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <Icon className={`w-3.5 h-3.5 ${m.iconColor}`} />
                        <span>{m.name}</span>
                      </div>
                      {isActive ? (
                        <div className="flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                          <span className="text-[10px] font-mono text-emerald-400">Active</span>
                        </div>
                      ) : (
                        <span className="text-[10px] font-mono text-slate-500">{m.port}</span>
                      )}
                    </a>
                  )
                })}
              </div>
            )}
          </div>
        ) : (
          /* Minimized Modules Icons Rail */
          <div className="flex flex-col gap-2 mt-3 pt-3 border-t border-white/[0.08] w-full items-center">
            {modules.map((m) => {
              const isActive = currentModule === m.id
              const Icon = m.icon
              return (
                <div key={m.id} className="relative group">
                  <a
                    href={getModuleUrl(m.path)}
                    className={`p-2.5 rounded-xl flex items-center justify-center transition-all ${
                      isActive
                        ? `${m.colorBg} border ${m.colorText} shadow-sm`
                        : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
                    }`}
                  >
                    <Icon className={`w-4 h-4 ${isActive ? m.iconColor : 'text-slate-400'}`} />
                  </a>

                  {/* Tooltip */}
                  <div className="hidden group-hover:flex absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-[#0e131f] border border-white/10 text-xs text-slate-100 font-medium whitespace-nowrap shadow-2xl z-50 pointer-events-none items-center gap-1.5">
                    <span>{m.name}</span>
                    <span className="text-[10px] font-mono text-slate-400">{m.port}</span>
                    {isActive && <span className="text-[10px] font-mono text-emerald-400 font-semibold">· Active</span>}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Footer / Gateway Status ── */}
      <div className="mt-auto pt-4 border-t border-white/[0.08] w-full">
        {!collapsed ? (
          <div className="flex items-center justify-between px-2 text-[10px] font-mono text-slate-500">
            <span>Gateway :3020</span>
            <span className="text-emerald-400">ONLINE</span>
          </div>
        ) : (
          <div className="flex justify-center">
            <span className="w-2 h-2 rounded-full bg-emerald-400" title="Gateway :3020 ONLINE" />
          </div>
        )}
      </div>
    </aside>
  )
}
