import { useState } from 'react'
import { Search, Play, Download, Clock, MapPin, AlertTriangle, Ghost } from 'lucide-react'

const API = '/api'

interface QueryResult {
  query?: string
  results?: any[]
  count?: number
  latency_ms?: number
  covered?: string[]
  missing?: string[]
  coverage_pct?: number
}

const PRESETS = [
  { id: 'flagship', label: 'Active Not Inspected', desc: 'Active businesses without inspection in N months', icon: AlertTriangle },
  { id: 'ghosts', label: 'Ghost Candidates', desc: 'Dormant businesses with no recent activity', icon: Ghost },
  { id: 'coverage', label: 'Department Coverage', desc: 'Which departments have records for a UBID', icon: Search },
]

export default function QueryConsole() {
  const [activePreset, setActivePreset] = useState('flagship')
  const [pincode, setPincode] = useState('560058')
  const [months, setMonths] = useState(18)
  const [ubidInput, setUbidInput] = useState('')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const runQuery = async () => {
    setLoading(true)
    setError('')
    try {
      let url = ''
      if (activePreset === 'flagship') {
        url = `${API}/query/active-not-inspected?pincode=${pincode}&months_threshold=${months}`
      } else if (activePreset === 'ghosts') {
        url = `${API}/query/ghost-candidates?min_months_silent=${months}`
      } else if (activePreset === 'coverage') {
        url = `${API}/query/department-coverage/${ubidInput}`
      }
      const res = await fetch(url)
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const data = await res.json()
      setResult(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const exportCSV = () => {
    if (!result?.results?.length) return
    const keys = Object.keys(result.results[0])
    const csv = [keys.join(','), ...result.results.map(r => keys.map(k => JSON.stringify(r[k] ?? '')).join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'nexusid-query-results.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="max-w-[1200px] mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Query Console</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          Run analytical queries against the identity graph
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {/* Sidebar - Presets */}
        <div className="col-span-1 space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>
            Saved Queries
          </div>
          {PRESETS.map(p => (
            <button
              key={p.id}
              onClick={() => setActivePreset(p.id)}
              className="w-full text-left p-3 rounded-md transition-all duration-150"
              style={{
                background: activePreset === p.id ? 'rgba(46,124,255,0.1)' : 'var(--bg-surface)',
                border: `1px solid ${activePreset === p.id ? 'var(--brand-500)' : 'var(--border-subtle)'}`,
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <p.icon size={12} style={{ color: activePreset === p.id ? 'var(--brand-300)' : 'var(--text-tertiary)' }} />
                <span className="text-xs font-semibold" style={{ color: activePreset === p.id ? 'var(--brand-300)' : 'var(--text-primary)' }}>
                  {p.label}
                </span>
              </div>
              <div className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{p.desc}</div>
            </button>
          ))}
        </div>

        {/* Main */}
        <div className="col-span-3 space-y-4">
          {/* Parameters */}
          <div className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
            <div className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-tertiary)' }}>
              Parameters
            </div>

            {(activePreset === 'flagship' || activePreset === 'ghosts') && (
              <div className="flex gap-4">
                {activePreset === 'flagship' && (
                  <div className="flex-1">
                    <label className="text-xs mb-1 block" style={{ color: 'var(--text-secondary)' }}>Pincode</label>
                    <div className="relative">
                      <MapPin size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }} />
                      <input value={pincode} onChange={e => setPincode(e.target.value)}
                             className="w-full pl-9 pr-3 py-2 rounded-md text-sm font-mono"
                             style={{ background: 'var(--bg-elevated)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', outline: 'none' }} />
                    </div>
                  </div>
                )}
                <div className="flex-1">
                  <label className="text-xs mb-1 block" style={{ color: 'var(--text-secondary)' }}>
                    {activePreset === 'flagship' ? 'Months Without Inspection' : 'Months Silent'}
                  </label>
                  <input type="number" value={months} onChange={e => setMonths(Number(e.target.value))}
                         className="w-full px-3 py-2 rounded-md text-sm font-mono"
                         style={{ background: 'var(--bg-elevated)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', outline: 'none' }} />
                </div>
              </div>
            )}

            {activePreset === 'coverage' && (
              <div>
                <label className="text-xs mb-1 block" style={{ color: 'var(--text-secondary)' }}>UBID</label>
                <input value={ubidInput} onChange={e => setUbidInput(e.target.value)}
                       placeholder="UBID-PAN-XXXXX..."
                       className="w-full px-3 py-2 rounded-md text-sm font-mono"
                       style={{ background: 'var(--bg-elevated)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', outline: 'none' }} />
              </div>
            )}

            <button onClick={runQuery} disabled={loading}
                    className="mt-4 flex items-center gap-2 px-5 py-2 rounded-md text-sm font-semibold transition-all"
                    style={{ background: 'var(--brand-500)', color: '#fff', opacity: loading ? 0.7 : 1 }}>
              {loading ? <Clock size={14} className="animate-spin" /> : <Play size={14} />}
              {loading ? 'Running...' : 'Execute Query'}
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 rounded-md text-sm" style={{ background: 'rgba(242,76,92,0.1)', color: 'var(--danger)', border: '1px solid rgba(242,76,92,0.2)' }}>
              {error}
            </div>
          )}

          {/* Results */}
          {result && (
            <div className="rounded-lg overflow-hidden" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
              {/* Results header */}
              <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  <span><strong style={{ color: 'var(--text-primary)' }}>{result.count ?? result.results?.length ?? 0}</strong> results</span>
                  {result.latency_ms && <span className="flex items-center gap-1"><Clock size={10} />{result.latency_ms.toFixed(0)}ms</span>}
                  {result.query && <span className="font-mono text-[10px] truncate max-w-md">{result.query}</span>}
                </div>
                {result.results && result.results.length > 0 && (
                  <button onClick={exportCSV} className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium"
                          style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)' }}>
                    <Download size={12} /> Export CSV
                  </button>
                )}
              </div>

              {/* Coverage result */}
              {activePreset === 'coverage' && result.covered && (
                <div className="p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                      Coverage: {result.coverage_pct}%
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {['SHOP_EST', 'FACTORIES', 'LABOUR', 'KSPCB', 'GST'].map(dept => {
                      const covered = (result.covered as string[]).includes(dept)
                      return (
                        <div key={dept} className="flex-1 p-3 rounded-md text-center" style={{
                          background: covered ? 'rgba(45,212,164,0.1)' : 'var(--bg-elevated)',
                          border: `1px solid ${covered ? 'rgba(45,212,164,0.3)' : 'var(--border-subtle)'}`,
                        }}>
                          <div className="text-xs font-semibold" style={{ color: covered ? 'var(--success)' : 'var(--text-disabled)' }}>{dept}</div>
                          <div className="text-[10px] mt-1" style={{ color: 'var(--text-tertiary)' }}>{covered ? 'Covered' : 'Missing'}</div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Table results */}
              {result.results && result.results.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr style={{ background: 'var(--bg-elevated)' }}>
                        {Object.keys(result.results[0]).map(key => (
                          <th key={key} className="text-left px-3 py-2 font-semibold uppercase tracking-wider"
                              style={{ color: 'var(--text-tertiary)', borderBottom: '1px solid var(--border-subtle)' }}>
                            {key.replace(/_/g, ' ')}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.results.map((row: any, i: number) => (
                        <tr key={i} className="transition-colors"
                            style={{ borderBottom: '1px solid var(--border-subtle)' }}
                            onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                          {Object.values(row).map((val: any, j: number) => (
                            <td key={j} className="px-3 py-2.5 font-mono" style={{ color: 'var(--text-primary)' }}>
                              {val === null ? <span style={{ color: 'var(--text-disabled)' }}>—</span> : String(val).slice(0, 40)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {result.results && result.results.length === 0 && (
                <div className="text-center py-10 text-sm" style={{ color: 'var(--text-tertiary)' }}>
                  No results match the query parameters.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
