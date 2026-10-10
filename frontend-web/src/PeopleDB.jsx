/**
 * Cortexium 2.0 — People Database Panel
 * Mid-Sci-Fi aesthetic — matches the new App.jsx design system.
 * Deep navy (#080c12), cyan accent, JetBrains Mono, minimal borders.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Users, UserPlus, Upload, Trash2, Edit3, Save, X,
  MessageSquare, Image, ChevronDown, ChevronUp, Plus,
  CheckCircle, AlertCircle, Camera, RefreshCw, Eye,
  ScanFace, Clock, Mic, FileText
} from 'lucide-react'

const API = import.meta.env.VITE_API_URL || ''
const faceUrl = (url) => url ? `${API}${url}` : null

// ── Avatar ─────────────────────────────────────────────────────────────────────
function Avatar({ url, name, size = 52 }) {
  const [err, setErr] = useState(false)
  if (url && !err) {
    return (
      <img
        src={faceUrl(url)} alt={name}
        onError={() => setErr(true)}
        className="object-cover rounded-xl"
        style={{ width: size, height: size }}
      />
    )
  }
  const initials = (name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
  return (
    <div
      className="rounded-xl flex items-center justify-center font-bold text-slate-400
                 bg-cyan-500/[0.08] border border-cyan-500/20"
      style={{ width: size, height: size, fontSize: size * 0.34 }}
    >
      {initials}
    </div>
  )
}

// ── Source badge ───────────────────────────────────────────────────────────────
function SourceBadge({ source }) {
  const map = {
    voice: { label: 'voice', icon: Mic, color: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20' },
    'ui-manual': { label: 'note', icon: FileText, color: 'text-slate-400 bg-white/[0.04] border-white/[0.08]' },
    'ui-upload': { label: 'upload', icon: Upload, color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
  }
  const cfg = map[source] || map['ui-manual']
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[7px] font-mono border ${cfg.color}`}>
      <Icon size={7} /> {cfg.label}
    </span>
  )
}

// ── Person Card (grid item) ────────────────────────────────────────────────────
function PersonCard({ person, onSelect, onDelete, deleteConfirm, onDeleteConfirm }) {
  const isConfirming = deleteConfirm === person.name
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96 }}
      className="relative group bg-[#080c12] border border-white/[0.07] hover:border-cyan-500/25
                 rounded-2xl p-3 cursor-pointer transition-all hover:bg-white/[0.02]"
      onClick={() => !isConfirming && onSelect(person)}
    >
      <div className="flex items-center gap-3">
        <Avatar url={person.thumbnail} name={person.name} size={48} />
        <div className="flex-1 min-w-0">
          <p className="text-white font-semibold text-[12px] truncate">{person.name}</p>
          {person.role && (
            <p className="text-[9px] font-mono text-cyan-400/70 truncate">{person.role}</p>
          )}
          <div className="flex gap-2 mt-1">
            <span className="text-[8px] font-mono text-slate-700">
              {person.image_count} img{person.image_count !== 1 ? 's' : ''}
            </span>
            <span className="text-[8px] font-mono text-slate-700">·</span>
            <span className="text-[8px] font-mono text-slate-700">{person.last_seen_str}</span>
            {person.conversation_count > 0 && (
              <>
                <span className="text-[8px] font-mono text-slate-700">·</span>
                <span className="text-[8px] font-mono text-cyan-500/60">
                  {person.conversation_count} notes
                </span>
              </>
            )}
          </div>
        </div>

        {/* Delete button */}
        {!isConfirming ? (
          <button
            onClick={e => { e.stopPropagation(); onDeleteConfirm(person.name) }}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg
                       hover:bg-red-500/15 text-slate-700 hover:text-red-400"
          >
            <Trash2 size={12} />
          </button>
        ) : (
          <div className="flex gap-1" onClick={e => e.stopPropagation()}>
            <button
              onClick={() => onDeleteConfirm(null)}
              className="px-2 py-1 text-[8px] font-mono rounded-lg border border-white/[0.08] text-slate-500 hover:text-slate-300"
            >
              cancel
            </button>
            <button
              onClick={() => onDelete(person.name)}
              className="px-2 py-1 text-[8px] font-mono rounded-lg bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-600/30"
            >
              confirm
            </button>
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ── Image Gallery ──────────────────────────────────────────────────────────────
function ImageGallery({ person, onDelete, onUpload, uploading }) {
  return (
    <div>
      <p className="text-[8px] font-mono text-slate-600 uppercase tracking-widest mb-2">
        Face Images ({person.image_count})
      </p>
      <div className="flex flex-wrap gap-2">
        {person.images.map((img, i) => (
          <div key={img.filename} className="relative group/img">
            <img
              src={faceUrl(img.url)}
              alt={`${person.name} ${i}`}
              className="w-14 h-14 object-cover rounded-xl border border-white/[0.08]"
              onError={e => { e.target.style.display = 'none' }}
            />
            {i === 0 && (
              <span className="absolute top-0.5 left-0.5 text-[6px] bg-cyan-600/80 text-white
                               px-1 py-0.5 rounded font-mono">PRIMARY</span>
            )}
            <button
              onClick={() => onDelete(img.filename)}
              className="absolute top-0.5 right-0.5 opacity-0 group-hover/img:opacity-100
                         bg-red-600/80 text-white rounded p-0.5 transition-opacity"
            >
              <X size={8} />
            </button>
          </div>
        ))}

        {/* Upload slot */}
        <label className="w-14 h-14 flex flex-col items-center justify-center
                          border border-dashed border-white/[0.10] hover:border-cyan-500/40
                          rounded-xl cursor-pointer transition-all group/up bg-black/20 hover:bg-cyan-500/[0.04]">
          <input
            type="file" accept="image/*" className="hidden"
            onChange={e => { if (e.target.files[0]) onUpload(e.target.files[0]); e.target.value = '' }}
          />
          {uploading
            ? <RefreshCw size={14} className="text-cyan-400 animate-spin" />
            : <Plus size={14} className="text-slate-700 group-hover/up:text-cyan-400 transition-colors" />}
          <span className="text-[6px] font-mono text-slate-700 group-hover/up:text-cyan-400 mt-0.5">
            {uploading ? '…' : 'add'}
          </span>
        </label>
      </div>
      <p className="text-[7px] font-mono text-slate-700 mt-2">
        3–5 images per person = best ArcFace accuracy
      </p>
    </div>
  )
}

// ── Person Detail Modal ────────────────────────────────────────────────────────
function PersonModal({ person, onClose, onRefresh, apiBase }) {
  const [name, setName]         = useState(person.name)
  const [role, setRole]         = useState(person.role || '')
  const [notes, setNotes]       = useState(person.notes || '')
  const [note, setNote]         = useState('')
  const [saving, setSaving]     = useState(false)
  const [uploading, setUploading] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const [conversations, setConversations] = useState([])
  const [convLoaded, setConvLoaded] = useState(false)

  const flash = (msg, type = 'success') => {
    setFeedback({ msg, type })
    setTimeout(() => setFeedback(null), 3000)
  }

  useEffect(() => {
    fetch(`${apiBase}/api/persons/${person.name}/conversations`)
      .then(r => r.json())
      .then(d => { setConversations(d.entries || []); setConvLoaded(true) })
      .catch(() => setConvLoaded(true))
  }, [person.name])

  const saveDetails = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${apiBase}/api/persons/${person.name}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, role, notes }),
      })
      if (res.ok) { flash('Saved!'); onRefresh() }
      else flash('Save failed', 'error')
    } finally { setSaving(false) }
  }

  const uploadImage = async (file) => {
    setUploading(true)
    const form = new FormData()
    form.append('image', file)
    try {
      const res = await fetch(`${apiBase}/api/persons/${person.name}/images`, {
        method: 'POST', body: form,
      })
      if (res.ok) { flash('Image added!'); onRefresh() }
      else flash('Upload failed', 'error')
    } finally { setUploading(false) }
  }

  const deleteImage = async (filename) => {
    await fetch(`${apiBase}/api/persons/${person.name}/images/${filename}`, { method: 'DELETE' })
    flash('Image deleted')
    onRefresh()
  }

  const addNote = async () => {
    if (!note.trim()) return
    const form = new FormData()
    form.append('note', note.trim())
    const res = await fetch(`${apiBase}/api/persons/${person.name}/conversations`, {
      method: 'POST', body: form,
    })
    if (res.ok) {
      const d = await res.json()
      setConversations(d.entries || [])
      setNote('')
      flash('Note added!')
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.80)', backdropFilter: 'blur(12px)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.94, y: 16 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.94, y: 16 }}
        onClick={e => e.stopPropagation()}
        className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl
                   border border-white/[0.09] shadow-2xl"
        style={{ background: '#080c12' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/[0.07]">
          <div className="flex items-center gap-3">
            <Avatar url={person.thumbnail} name={person.name} size={44} />
            <div>
              <h2 className="text-white font-semibold text-base">{person.name}</h2>
              <p className="text-[9px] font-mono text-slate-600">
                {person.last_seen_str} · {person.image_count} image{person.image_count !== 1 ? 's' : ''}
                {person.conversation_count > 0 && ` · ${person.conversation_count} notes`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-white/[0.05] text-slate-600 hover:text-slate-300 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <div className="p-4 space-y-5">

          {/* Feedback toast */}
          <AnimatePresence>
            {feedback && (
              <motion.div
                initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-[11px] font-mono border
                  ${feedback.type === 'error'
                    ? 'bg-red-500/10 border-red-500/25 text-red-400'
                    : 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'}`}
              >
                {feedback.type === 'error' ? <AlertCircle size={12} /> : <CheckCircle size={12} />}
                {feedback.msg}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Identity section */}
          <div className="space-y-3">
            <p className="text-[8px] font-mono text-slate-600 uppercase tracking-widest">Identity</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[8px] font-mono text-slate-600 mb-1">Full Name</label>
                <input value={name} onChange={e => setName(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2
                             text-white text-sm font-mono focus:outline-none focus:border-cyan-500/40
                             focus:bg-cyan-500/[0.03]" />
              </div>
              <div>
                <label className="block text-[8px] font-mono text-slate-600 mb-1">Role</label>
                <input value={role} onChange={e => setRole(e.target.value)}
                  placeholder="e.g. Colleague, Friend"
                  className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2
                             text-white text-sm font-mono focus:outline-none focus:border-cyan-500/40
                             focus:bg-cyan-500/[0.03] placeholder:text-slate-700" />
              </div>
            </div>
            <div>
              <label className="block text-[8px] font-mono text-slate-600 mb-1">Notes</label>
              <textarea value={notes} onChange={e => setNotes(e.target.value)}
                rows={2} placeholder="Relationship context, reminders..."
                className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2
                           text-white text-sm font-mono focus:outline-none focus:border-cyan-500/40
                           focus:bg-cyan-500/[0.03] resize-none placeholder:text-slate-700" />
            </div>
            <button onClick={saveDetails} disabled={saving}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-600/15 hover:bg-cyan-600/25
                         border border-cyan-500/25 hover:border-cyan-500/40 text-cyan-400 text-[10px]
                         font-mono font-bold transition-all disabled:opacity-30">
              <Save size={11} />
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </div>

          {/* Face images */}
          <div className="border-t border-white/[0.06] pt-4">
            <ImageGallery
              person={person}
              onDelete={deleteImage}
              onUpload={uploadImage}
              uploading={uploading}
            />
          </div>

          {/* Conversation log */}
          <div className="border-t border-white/[0.06] pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[8px] font-mono text-slate-600 uppercase tracking-widest">
                Conversation Log
              </p>
              <span className="text-[8px] font-mono text-slate-700">
                {conversations.length} entries
              </span>
            </div>

            {/* Manual note input */}
            <div className="flex gap-2">
              <input
                value={note} onChange={e => setNote(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addNote()}
                placeholder="Add a note (or speak with camera active)…"
                className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2
                           text-white text-[11px] font-mono focus:outline-none focus:border-cyan-500/40
                           focus:bg-cyan-500/[0.03] placeholder:text-slate-700"
              />
              <button onClick={addNote}
                className="px-3 py-2 rounded-xl bg-cyan-600/15 hover:bg-cyan-600/25
                           border border-cyan-500/25 text-cyan-400 transition-all">
                <Plus size={13} />
              </button>
            </div>

            {/* Entries list */}
            <div className="space-y-1.5 max-h-44 overflow-y-auto pr-0.5">
              {convLoaded && conversations.length === 0 && (
                <div className="flex flex-col items-center justify-center py-6 text-slate-700 gap-2">
                  <MessageSquare size={18} strokeWidth={1.5} />
                  <p className="text-[9px] font-mono">
                    No entries yet — voice transcripts will appear here automatically
                  </p>
                </div>
              )}
              {[...conversations].reverse().map((entry, i) => (
                <div key={i} className="px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                  <p className="text-[10px] text-slate-300 leading-relaxed">{entry.note}</p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-[7px] font-mono text-slate-700">
                      {new Date(entry.timestamp).toLocaleString([], {
                        month: 'short', day: 'numeric',
                        hour: '2-digit', minute: '2-digit'
                      })}
                    </span>
                    <SourceBadge source={entry.source} />
                    {entry.emotion && (
                      <span className="text-[7px] font-mono text-amber-500/60">{entry.emotion}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ── Add Person Modal ───────────────────────────────────────────────────────────
function AddPersonModal({ onClose, onAdded, apiBase }) {
  const [name, setName]     = useState('')
  const [role, setRole]     = useState('')
  const [notes, setNotes]   = useState('')
  const [file, setFile]     = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState(null)

  const handleFile = (f) => {
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }

  const submit = async () => {
    if (!name.trim()) { setError('Name is required'); return }
    setLoading(true); setError(null)
    const form = new FormData()
    form.append('name', name.trim())
    form.append('role', role.trim())
    form.append('notes', notes.trim())
    if (file) form.append('image', file)
    try {
      const res = await fetch(`${apiBase}/api/persons`, { method: 'POST', body: form })
      if (res.ok) { onAdded(); onClose() }
      else { const d = await res.json(); setError(d.detail || 'Failed to create person') }
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.80)', backdropFilter: 'blur(12px)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.94, y: 16 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.94 }}
        onClick={e => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl border border-white/[0.09] shadow-2xl"
        style={{ background: '#080c12' }}
      >
        <div className="flex items-center justify-between p-4 border-b border-white/[0.07]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/20
                            flex items-center justify-center">
              <UserPlus size={14} className="text-cyan-400" />
            </div>
            <h2 className="text-white font-semibold text-[14px]">Add New Person</h2>
          </div>
          <button onClick={onClose}
            className="p-1.5 rounded-xl hover:bg-white/[0.05] text-slate-600 hover:text-slate-300 transition-colors">
            <X size={15} />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Face image upload */}
          <label className="block cursor-pointer">
            <input type="file" accept="image/*" className="hidden"
              onChange={e => { if (e.target.files[0]) handleFile(e.target.files[0]) }} />
            <div className={`flex items-center justify-center h-28 rounded-xl border border-dashed
                             transition-all ${preview ? 'border-cyan-500/40' : 'border-white/[0.08] hover:border-cyan-500/25'}`}>
              {preview ? (
                <img src={preview} className="h-full w-full object-cover rounded-xl" />
              ) : (
                <div className="text-center">
                  <ScanFace size={22} className="mx-auto text-slate-700 mb-1.5" />
                  <p className="text-[9px] font-mono text-slate-700">Upload face image (optional)</p>
                  <p className="text-[7px] font-mono text-slate-800 mt-0.5">Add more later for better accuracy</p>
                </div>
              )}
            </div>
          </label>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[8px] font-mono text-slate-600 mb-1">Name *</label>
              <input value={name} onChange={e => setName(e.target.value)}
                placeholder="Full name"
                className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2
                           text-white text-sm font-mono focus:outline-none focus:border-cyan-500/40
                           placeholder:text-slate-700" />
            </div>
            <div>
              <label className="block text-[8px] font-mono text-slate-600 mb-1">Role</label>
              <input value={role} onChange={e => setRole(e.target.value)}
                placeholder="e.g. Colleague"
                className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2
                           text-white text-sm font-mono focus:outline-none focus:border-cyan-500/40
                           placeholder:text-slate-700" />
            </div>
          </div>

          <div>
            <label className="block text-[8px] font-mono text-slate-600 mb-1">Notes</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)}
              rows={2} placeholder="Any context about this person..."
              className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2
                         text-white text-sm font-mono focus:outline-none focus:border-cyan-500/40
                         resize-none placeholder:text-slate-700" />
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-[11px] font-mono
                            bg-red-500/10 border border-red-500/20 px-3 py-2 rounded-xl">
              <AlertCircle size={11} /> {error}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button onClick={onClose}
              className="flex-1 py-2.5 rounded-xl border border-white/[0.08] text-slate-500
                         hover:text-slate-300 hover:bg-white/[0.03] text-[11px] font-mono transition-all">
              Cancel
            </button>
            <button onClick={submit} disabled={loading}
              className="flex-1 py-2.5 rounded-xl bg-cyan-600/20 hover:bg-cyan-600/30
                         border border-cyan-500/30 hover:border-cyan-500/45 text-cyan-300 font-bold
                         text-[11px] font-mono transition-all disabled:opacity-30
                         flex items-center justify-center gap-2">
              {loading ? <RefreshCw size={13} className="animate-spin" /> : <UserPlus size={13} />}
              {loading ? 'Adding…' : 'Add Person'}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Main PeopleDB component
// ══════════════════════════════════════════════════════════════════════════════
export default function PeopleDB({ apiBase = '' }) {
  const [persons, setPersons]   = useState([])
  const [loading, setLoading]   = useState(false)
  const [selected, setSelected] = useState(null)
  const [showAdd, setShowAdd]   = useState(false)
  const [search, setSearch]     = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/api/persons`)
      const d   = await res.json()
      setPersons(d.persons || [])
      if (selected) {
        const updated = (d.persons || []).find(p => p.name === selected.name)
        if (updated) setSelected(updated)
      }
    } catch (e) {
      console.error('PeopleDB load error:', e)
    } finally {
      setLoading(false)
    }
  }, [apiBase, selected?.name])

  useEffect(() => { load() }, [])

  const handleDelete = async (name) => {
    await fetch(`${apiBase}/api/persons/${name}`, { method: 'DELETE' })
    setDeleteConfirm(null)
    if (selected?.name === name) setSelected(null)
    load()
  }

  const filtered = persons.filter(p =>
    !search ||
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.role || '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="h-full flex flex-col gap-3 min-h-0">

      {/* Header */}
      <div className="flex items-center justify-between gap-2 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Users size={13} className="text-cyan-500" />
          <span className="text-[11px] font-mono font-bold text-slate-300">People</span>
          <span className="text-[8px] font-mono text-slate-700 bg-white/[0.04] px-1.5 py-0.5 rounded-full">
            {persons.length}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={load} disabled={loading}
            className="p-1.5 rounded-lg hover:bg-white/[0.05] text-slate-700 hover:text-slate-400 transition-colors">
            <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-cyan-600/15 hover:bg-cyan-600/25
                       border border-cyan-500/25 hover:border-cyan-500/40 text-cyan-400 text-[9px] font-mono
                       font-bold transition-all">
            <UserPlus size={11} /> Add
          </button>
        </div>
      </div>

      {/* Search */}
      <input
        value={search} onChange={e => setSearch(e.target.value)}
        placeholder="Search name or role…"
        className="w-full bg-white/[0.03] border border-white/[0.07] rounded-xl px-3 py-2
                   text-slate-300 text-[11px] font-mono placeholder:text-slate-700
                   focus:outline-none focus:border-cyan-500/35 focus:bg-cyan-500/[0.02] flex-shrink-0"
      />

      {/* Cards */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-0.5 space-y-1.5">
        {loading && persons.length === 0 && (
          <div className="flex items-center justify-center h-24 text-slate-700">
            <RefreshCw size={16} className="animate-spin" />
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center h-28 text-slate-700 gap-2">
            <Users size={24} strokeWidth={1.2} />
            <p className="text-[10px] font-mono">{search ? 'No results' : 'No persons registered yet'}</p>
            {!search && (
              <button onClick={() => setShowAdd(true)}
                className="text-[9px] font-mono text-cyan-500 hover:text-cyan-300 transition-colors">
                Add your first person →
              </button>
            )}
          </div>
        )}

        <AnimatePresence>
          {filtered.map(p => (
            <PersonCard
              key={p.name}
              person={p}
              onSelect={setSelected}
              onDelete={handleDelete}
              deleteConfirm={deleteConfirm}
              onDeleteConfirm={setDeleteConfirm}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* Modals */}
      <AnimatePresence>
        {selected && (
          <PersonModal
            person={selected}
            onClose={() => setSelected(null)}
            onRefresh={load}
            apiBase={apiBase}
          />
        )}
        {showAdd && (
          <AddPersonModal
            onClose={() => setShowAdd(false)}
            onAdded={load}
            apiBase={apiBase}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
