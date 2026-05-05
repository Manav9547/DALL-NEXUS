import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, GitMerge, Search, ShieldCheck, FileText,
  Users, Zap, Play, Terminal, X
} from 'lucide-react'

interface CommandItem {
  id: string
  label: string
  description: string
  icon: any
  action: () => void
  category: string
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const commands: CommandItem[] = [
    { id: 'nav-dashboard', label: 'Go to Dashboard', description: 'System overview and KPIs', icon: LayoutDashboard, action: () => navigate('/'), category: 'Navigation' },
    { id: 'nav-review', label: 'Go to Review Queue', description: 'Pending pairs for adjudication', icon: Users, action: () => navigate('/review'), category: 'Navigation' },
    { id: 'nav-identity', label: 'Go to Identity Explorer', description: 'Search and browse UBIDs', icon: GitMerge, action: () => navigate('/identity'), category: 'Navigation' },
    { id: 'nav-query', label: 'Go to Query Console', description: 'Run analytical queries', icon: Search, action: () => navigate('/query'), category: 'Navigation' },
    { id: 'nav-compliance', label: 'Go to Compliance Dashboard', description: 'System health and model metrics', icon: ShieldCheck, action: () => navigate('/compliance'), category: 'Navigation' },
    { id: 'nav-ledger', label: 'Go to Event Ledger', description: 'Immutable audit trail', icon: FileText, action: () => navigate('/ledger'), category: 'Navigation' },
    { id: 'act-pipeline', label: 'Run Full Pipeline', description: 'Blocking → Scoring → Resolution → Activity', icon: Play, action: () => { fetch('/api/pipeline/run-all', { method: 'POST' }); navigate('/') }, category: 'Actions' },
    { id: 'act-verify', label: 'Verify Ledger Integrity', description: 'Check hash chain for tampering', icon: ShieldCheck, action: () => { navigate('/ledger') }, category: 'Actions' },
    { id: 'act-train', label: 'Train Model', description: 'Retrain LR model on labelled data', icon: Zap, action: () => { fetch('/api/model/train', { method: 'POST' }) }, category: 'Actions' },
    { id: 'act-flagship', label: 'Run Flagship Query', description: 'Active businesses not inspected', icon: Terminal, action: () => navigate('/query'), category: 'Actions' },
    { id: 'search-560058', label: 'Search pincode 560058', description: 'Businesses in Peenya area', icon: Search, action: () => navigate('/identity?q=560058'), category: 'Quick Search' },
    { id: 'search-active', label: 'Show Active businesses', description: 'Filter by ACTIVE status', icon: Search, action: () => navigate('/identity?status=ACTIVE'), category: 'Quick Search' },
    { id: 'search-dormant', label: 'Show Dormant businesses', description: 'Ghost candidates', icon: Search, action: () => navigate('/identity?status=DORMANT'), category: 'Quick Search' },
  ]

  const filtered = query
    ? commands.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.description.toLowerCase().includes(query.toLowerCase())
      )
    : commands

  // Keyboard: open/close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(o => !o)
        setQuery('')
        setSelectedIndex(0)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Focus input when opened
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50)
  }, [open])

  // Arrow keys + enter
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(i => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      filtered[selectedIndex].action()
      setOpen(false)
    }
  }, [filtered, selectedIndex])

  if (!open) return null

  // Group by category
  const grouped: Record<string, CommandItem[]> = {}
  for (const cmd of filtered) {
    if (!grouped[cmd.category]) grouped[cmd.category] = []
    grouped[cmd.category].push(cmd)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
         onClick={() => setOpen(false)}>
      {/* Backdrop */}
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }} />

      {/* Palette */}
      <div
        className="relative w-[560px] max-h-[420px] rounded-xl overflow-hidden animate-fade-in"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', boxShadow: 'var(--shadow-lg, 0 16px 40px rgba(0,0,0,0.55))' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 h-12 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
          <Search size={16} style={{ color: 'var(--text-tertiary)' }} />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => { setQuery(e.target.value); setSelectedIndex(0) }}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--text-primary)' }}
          />
          <div className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded text-[10px]"
                 style={{ background: 'var(--bg-hover)', color: 'var(--text-tertiary)', border: '1px solid var(--border-subtle)' }}>
              ESC
            </kbd>
          </div>
        </div>

        {/* Results */}
        <div className="overflow-y-auto max-h-[360px] py-2">
          {Object.entries(grouped).map(([category, items]) => (
            <div key={category}>
              <div className="px-4 py-1.5 text-[10px] font-semibold uppercase tracking-wider"
                   style={{ color: 'var(--text-tertiary)' }}>
                {category}
              </div>
              {items.map((cmd, i) => {
                const globalIndex = filtered.indexOf(cmd)
                const isSelected = globalIndex === selectedIndex
                return (
                  <div
                    key={cmd.id}
                    onClick={() => { cmd.action(); setOpen(false) }}
                    onMouseEnter={() => setSelectedIndex(globalIndex)}
                    className="flex items-center gap-3 px-4 py-2.5 mx-2 rounded-md cursor-pointer transition-colors"
                    style={{
                      background: isSelected ? 'var(--bg-hover)' : 'transparent',
                    }}
                  >
                    <cmd.icon size={16} style={{ color: isSelected ? 'var(--brand-300)' : 'var(--text-tertiary)' }} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium" style={{ color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                        {cmd.label}
                      </div>
                      <div className="text-[11px] truncate" style={{ color: 'var(--text-tertiary)' }}>
                        {cmd.description}
                      </div>
                    </div>
                    {isSelected && (
                      <kbd className="px-1.5 py-0.5 rounded text-[9px]"
                           style={{ background: 'var(--bg-surface)', color: 'var(--text-tertiary)' }}>
                        ↵
                      </kbd>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-8 text-sm" style={{ color: 'var(--text-tertiary)' }}>
              No commands match "{query}"
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
