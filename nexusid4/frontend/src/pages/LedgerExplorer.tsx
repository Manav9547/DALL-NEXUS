import { useState } from 'react'
import { useLedger, useVerifyLedger } from '../hooks/api'
import { Shield, CheckCircle, XCircle, ChevronDown, ChevronRight, Filter, RefreshCw } from 'lucide-react'

const AGGREGATE_TYPES = ['', 'UBID', 'MERGE', 'REVERSAL', 'STATUS', 'REVIEW', 'DECISION']

export default function LedgerExplorer() {
  const [aggregateFilter, setAggregateFilter] = useState('')
  const [cursor, setCursor] = useState(0)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const { data, isLoading } = useLedger(aggregateFilter || undefined, cursor)
  const verifyLedger = useVerifyLedger()

  const entries = data?.entries || []
  const total = data?.total || 0

  const toggleExpand = (id: number) => {
    const next = new Set(expanded)
    next.has(id) ? next.delete(id) : next.add(id)
    setExpanded(next)
  }

  return (
    <div className="max-w-[1200px] mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Event Ledger</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
            Immutable, hash-chained audit trail — {total} entries
          </p>
        </div>

        {/* Verify Button */}
        <button
          onClick={() => verifyLedger.mutate()}
          disabled={verifyLedger.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-semibold transition-all"
          style={{
            background: verifyLedger.isPending ? 'var(--bg-elevated)' : 'var(--brand-500)',
            color: '#fff',
          }}
        >
          {verifyLedger.isPending ? <RefreshCw size={14} className="animate-spin" /> : <Shield size={14} />}
          Verify Chain Integrity
        </button>
      </div>

      {/* Verification Result */}
      {verifyLedger.data && (
        <div className="mb-6 p-4 rounded-lg animate-fade-in" style={{
          background: verifyLedger.data.verified ? 'rgba(45,212,164,0.08)' : 'rgba(242,76,92,0.08)',
          border: `1px solid ${verifyLedger.data.verified ? 'rgba(45,212,164,0.3)' : 'rgba(242,76,92,0.3)'}`,
        }}>
          <div className="flex items-center gap-3">
            {verifyLedger.data.verified ? (
              <>
                <CheckCircle size={24} style={{ color: 'var(--success)' }} />
                <div>
                  <div className="text-sm font-semibold" style={{ color: 'var(--success)' }}>Chain Integrity Verified</div>
                  <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    All {verifyLedger.data.entries} entries have valid hash chains. No tampering detected.
                  </div>
                </div>
              </>
            ) : (
              <>
                <XCircle size={24} style={{ color: 'var(--danger)' }} />
                <div>
                  <div className="text-sm font-semibold" style={{ color: 'var(--danger)' }}>Integrity Violation Detected</div>
                  <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    {verifyLedger.data.errors?.length} error(s) found in the hash chain.
                  </div>
                  {verifyLedger.data.errors?.map((err: any, i: number) => (
                    <div key={i} className="text-xs font-mono mt-1" style={{ color: 'var(--danger)' }}>
                      Ledger #{err.ledger_id}: {err.error}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="flex items-center gap-3 mb-4">
        <Filter size={14} style={{ color: 'var(--text-tertiary)' }} />
        <div className="flex gap-1">
          {AGGREGATE_TYPES.map(t => (
            <button
              key={t || 'all'}
              onClick={() => { setAggregateFilter(t); setCursor(0) }}
              className="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
              style={{
                background: aggregateFilter === t ? 'rgba(46,124,255,0.15)' : 'var(--bg-surface)',
                color: aggregateFilter === t ? 'var(--brand-300)' : 'var(--text-secondary)',
                border: `1px solid ${aggregateFilter === t ? 'var(--brand-500)' : 'var(--border-subtle)'}`,
              }}
            >
              {t || 'All'}
            </button>
          ))}
        </div>
      </div>

      {/* Entries */}
      {isLoading ? (
        <div className="space-y-2">
          {[1,2,3,4,5].map(i => <div key={i} className="skeleton h-14 rounded-md" />)}
        </div>
      ) : entries.length === 0 ? (
        <div className="text-center py-16 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <Shield size={40} style={{ color: 'var(--text-tertiary)' }} className="mx-auto" />
          <h3 className="text-base font-semibold mt-4" style={{ color: 'var(--text-primary)' }}>No ledger entries</h3>
          <p className="text-sm mt-1" style={{ color: 'var(--text-tertiary)' }}>Run the pipeline to generate audit events</p>
        </div>
      ) : (
        <div className="space-y-1 animate-stagger">
          {entries.map((entry: any) => {
            const isOpen = expanded.has(entry.ledger_id)
            return (
              <div key={entry.ledger_id} className="rounded-md overflow-hidden"
                   style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
                {/* Row */}
                <div
                  onClick={() => toggleExpand(entry.ledger_id)}
                  className="flex items-center gap-4 px-4 py-3 cursor-pointer transition-colors"
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  {isOpen ? <ChevronDown size={12} style={{ color: 'var(--text-tertiary)' }} /> : <ChevronRight size={12} style={{ color: 'var(--text-tertiary)' }} />}

                  <span className="text-xs font-mono w-12 text-right" style={{ color: 'var(--text-tertiary)' }}>#{entry.ledger_id}</span>

                  <TypeBadge type={entry.aggregate_type} />

                  <span className="text-sm font-medium flex-1" style={{ color: 'var(--text-primary)' }}>
                    {entry.event_type.replace(/_/g, ' ')}
                  </span>

                  <span className="text-[10px] font-mono truncate max-w-[180px]" style={{ color: 'var(--brand-300)' }}>
                    {entry.aggregate_id?.slice(0, 24)}
                  </span>

                  <div className="flex items-center gap-2 text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>
                    <span title="Hash">{entry.hash}</span>
                    <span style={{ color: 'var(--border-default)' }}>←</span>
                    <span title="Previous hash">{entry.prev_hash}</span>
                  </div>

                  <span className="text-[10px] shrink-0" style={{ color: 'var(--text-tertiary)' }}>
                    {entry.created_at?.slice(11, 19)}
                  </span>
                </div>

                {/* Expanded payload */}
                {isOpen && (
                  <div className="px-4 pb-4 pt-0">
                    <div className="p-3 rounded-md text-xs font-mono overflow-x-auto" style={{
                      background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
                      border: '1px solid var(--border-subtle)',
                    }}>
                      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {JSON.stringify(entry.payload, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {total > 50 && (
        <div className="flex items-center justify-between mt-4 text-sm" style={{ color: 'var(--text-tertiary)' }}>
          <span>{cursor + 1}–{Math.min(cursor + 50, total)} of {total}</span>
          <div className="flex gap-2">
            <button onClick={() => setCursor(Math.max(0, cursor - 50))} disabled={cursor === 0}
                    className="px-3 py-1.5 rounded-md text-xs"
                    style={{ background: 'var(--bg-elevated)', color: cursor === 0 ? 'var(--text-disabled)' : 'var(--text-secondary)' }}>
              Previous
            </button>
            <button onClick={() => setCursor(cursor + 50)} disabled={cursor + 50 >= total}
                    className="px-3 py-1.5 rounded-md text-xs"
                    style={{ background: 'var(--bg-elevated)', color: cursor + 50 >= total ? 'var(--text-disabled)' : 'var(--text-secondary)' }}>
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    UBID: 'var(--brand-300)', MERGE: 'var(--success)', REVERSAL: 'var(--danger)',
    STATUS: 'var(--warning)', REVIEW: 'var(--info)', DECISION: 'var(--text-secondary)',
  }
  const color = colors[type] || 'var(--text-tertiary)'
  return (
    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full w-20 text-center"
          style={{ background: `${color}15`, color }}>
      {type}
    </span>
  )
}
