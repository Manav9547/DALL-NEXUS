import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useIdentitySearch } from '../hooks/api'
import { Search, GitMerge, MapPin, Shield } from 'lucide-react'

export default function IdentityExplorer() {
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const { data, isLoading } = useIdentitySearch(query, statusFilter || undefined)
  const navigate = useNavigate()

  const items = data?.items || []

  return (
    <div className="max-w-[1200px] mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Identity Explorer</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          Search by UBID, PAN, GSTIN, business name, or pincode
        </p>
      </div>

      {/* Search bar */}
      <div className="flex gap-3 mb-6">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }} />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search UBID, PAN, GSTIN, name, or pincode..."
            className="w-full pl-10 pr-4 py-2.5 rounded-md text-sm"
            style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', outline: 'none' }}
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="px-3 py-2.5 rounded-md text-sm"
          style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', outline: 'none' }}
        >
          <option value="">All Status</option>
          <option value="ACTIVE">Active</option>
          <option value="DORMANT">Dormant</option>
          <option value="CLOSED">Closed</option>
        </select>
      </div>

      {/* Results */}
      {query && isLoading && (
        <div className="grid grid-cols-3 gap-4">
          {[1,2,3].map(i => <div key={i} className="skeleton h-44 rounded-lg" />)}
        </div>
      )}

      {query && !isLoading && items.length === 0 && (
        <div className="flex flex-col items-center py-16 rounded-lg"
             style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <Search size={40} style={{ color: 'var(--text-tertiary)' }} />
          <h3 className="text-base font-semibold mt-4" style={{ color: 'var(--text-primary)' }}>No results found</h3>
          <p className="text-sm mt-1" style={{ color: 'var(--text-tertiary)' }}>Try a different search term</p>
        </div>
      )}

      {items.length > 0 && (
        <>
          <div className="text-xs mb-3" style={{ color: 'var(--text-tertiary)' }}>
            {items.length} results · {data?.latency_ms?.toFixed(0)}ms
          </div>
          <div className="grid grid-cols-3 gap-4 animate-stagger">
            {items.map((item: any) => (
              <div
                key={item.ubid}
                onClick={() => navigate(`/identity/${item.ubid}`)}
                className="p-4 rounded-lg cursor-pointer transition-all duration-150"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--brand-500)'; e.currentTarget.style.transform = 'translateY(-1px)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-subtle)'; e.currentTarget.style.transform = 'none' }}
              >
                {/* Status + Anchor */}
                <div className="flex items-center justify-between mb-3">
                  <StatusPill status={item.activity_status} />
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded"
                        style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)' }}>
                    {item.anchor_type}
                  </span>
                </div>

                {/* Name */}
                <div className="text-sm font-semibold mb-1 truncate" style={{ color: 'var(--text-primary)' }}>
                  {item.primary_name}
                </div>

                {/* Address */}
                <div className="flex items-center gap-1 text-xs mb-3" style={{ color: 'var(--text-tertiary)' }}>
                  <MapPin size={10} />
                  <span className="truncate">{item.primary_address} — {item.primary_pincode}</span>
                </div>

                {/* UBID */}
                <div className="text-[10px] font-mono truncate mb-3" style={{ color: 'var(--brand-300)' }}>
                  {item.ubid}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                  <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    <GitMerge size={10} />
                    <span>{item.source_record_count} records</span>
                  </div>
                  {item.anchor_value && (
                    <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                      <Shield size={10} />
                      <span className="font-mono">{item.anchor_value?.slice(0, 10)}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {!query && (
        <div className="flex flex-col items-center py-20 rounded-lg"
             style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <GitMerge size={48} style={{ color: 'var(--text-tertiary)' }} />
          <h3 className="text-base font-semibold mt-4" style={{ color: 'var(--text-primary)' }}>Search for a business identity</h3>
          <p className="text-sm mt-1" style={{ color: 'var(--text-tertiary)' }}>
            Enter a UBID, PAN, GSTIN, business name, or pincode to explore
          </p>
        </div>
      )}
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const colors: Record<string, string> = {
    ACTIVE: 'var(--status-active)', DORMANT: 'var(--status-dormant)', CLOSED: 'var(--status-closed)',
  }
  const color = colors[status] || 'var(--text-tertiary)'
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-2 h-2 rounded-full" style={{ background: color }} />
      <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color }}>{status}</span>
    </div>
  )
}
