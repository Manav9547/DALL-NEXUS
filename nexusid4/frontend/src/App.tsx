import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import {
  LayoutDashboard, GitMerge, Search, ShieldCheck, FileText,
  Users, ChevronLeft, ChevronRight, Zap, Moon, Sun, Sparkles,
} from 'lucide-react'
import Dashboard from './pages/Dashboard'
import ReviewQueue from './pages/ReviewQueue'
import ReviewDetail from './pages/ReviewDetail'
import IdentityExplorer from './pages/IdentityExplorer'
import IdentityDetail from './pages/IdentityDetail'
import QueryConsole from './pages/QueryConsole'
import Compliance from './pages/Compliance'
import LedgerExplorer from './pages/LedgerExplorer'
import CommandPalette from './components/CommandPalette'
import DemoMode from './components/DemoMode'

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/review', icon: Users, label: 'Reviewer' },
  { to: '/identity', icon: GitMerge, label: 'Identity' },
  { to: '/query', icon: Search, label: 'Query' },
  { to: '/compliance', icon: ShieldCheck, label: 'Compliance' },
  { to: '/ledger', icon: FileText, label: 'Ledger' },
]

export default function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const location = useLocation()

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const crumb = NAV_ITEMS.find(n => n.to === '/' ? location.pathname === '/' : location.pathname.startsWith(n.to))

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>
      <CommandPalette />
      <DemoMode />

      {/* Sidebar */}
      <aside className="flex flex-col border-r transition-all duration-200 shrink-0"
        style={{ width: collapsed ? 60 : 220, borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
        <div className="flex items-center gap-2 px-4 h-14 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="w-8 h-8 rounded-md flex items-center justify-center shrink-0" style={{ background: 'var(--brand-500)' }}>
            <Zap size={18} color="#fff" />
          </div>
          {!collapsed && <span className="font-bold text-sm tracking-tight" style={{ color: 'var(--text-primary)' }}>NexusID</span>}
        </div>

        <nav className="flex-1 py-3 flex flex-col gap-0.5 px-2">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => {
            const active = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)
            return (
              <NavLink key={to} to={to}
                className="flex items-center gap-3 px-3 py-2 rounded-md text-[13px] font-medium transition-colors duration-150"
                style={{ color: active ? 'var(--brand-300)' : 'var(--text-secondary)', background: active ? 'rgba(46,124,255,0.1)' : 'transparent' }}>
                <Icon size={18} />{!collapsed && label}
              </NavLink>
            )
          })}
        </nav>

        <div className="border-t flex flex-col" style={{ borderColor: 'var(--border-subtle)' }}>
          {!collapsed && (
            <a href="/?demo=1" className="flex items-center gap-2 px-3 py-2 mx-2 mt-2 rounded-md text-[11px] font-medium"
               style={{ color: 'var(--brand-300)', background: 'rgba(46,124,255,0.08)' }}>
              <Sparkles size={14} /> Start Guided Tour
            </a>
          )}
          <button onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            className="flex items-center justify-center gap-2 h-10 transition-colors" style={{ color: 'var(--text-tertiary)' }}>
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            {!collapsed && <span className="text-[11px]">{theme === 'dark' ? 'Light' : 'Dark'}</span>}
          </button>
          <button onClick={() => setCollapsed(!collapsed)}
            className="flex items-center justify-center h-10 border-t transition-colors"
            style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}>
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="flex items-center justify-between h-14 px-6 border-b shrink-0"
          style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}>
          <div className="flex items-center gap-2 text-sm">
            <span style={{ color: 'var(--text-tertiary)' }}>NexusID</span>
            <span style={{ color: 'var(--text-tertiary)' }}>/</span>
            <span style={{ color: 'var(--text-primary)' }} className="font-medium">{crumb?.label || 'Page'}</span>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
              className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs cursor-pointer"
              style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)', border: '1px solid var(--border-default)' }}>
              <Search size={12} /><span>Search... ⌘K</span>
            </button>
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold"
                 style={{ background: 'var(--brand-600)', color: '#fff' }}>KA</div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/review" element={<ReviewQueue />} />
            <Route path="/review/:id" element={<ReviewDetail />} />
            <Route path="/identity" element={<IdentityExplorer />} />
            <Route path="/identity/:ubid" element={<IdentityDetail />} />
            <Route path="/query" element={<QueryConsole />} />
            <Route path="/compliance" element={<Compliance />} />
            <Route path="/ledger" element={<LedgerExplorer />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
