import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useReviewQueue } from '../hooks/api'
import { Users, ChevronRight, AlertTriangle, Search } from 'lucide-react'

export default function ReviewQueue() {
  const [cursor, setCursor] = useState(0)
  const { data, isLoading } = useReviewQueue(cursor, 20)
  const navigate = useNavigate()

  const items = data?.items || []
  const total = data?.total || 0

  return (
    <div className="max-w-[1200px] mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Review Queue</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
            {total} pairs awaiting human adjudication
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-md"
             style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)', border: '1px solid var(--border-default)' }}>
          <span>Shortcuts:</span>
          <kbd className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>J/K</kbd>
          <span>navigate</span>
          <kbd className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>Enter</kbd>
          <span>open</span>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1,2,3,4,5].map(i => <div key={i} className="skeleton h-16 rounded-md" />)}
        </div>
      ) : items.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          {/* Table Header */}
          <div className="grid grid-cols-12 gap-4 px-4 py-2 text-xs font-semibold uppercase tracking-wider"
               style={{ color: 'var(--text-tertiary)' }}>
            <div className="col-span-1">Score</div>
            <div className="col-span-3">Source A</div>
            <div className="col-span-3">Source B</div>
            <div className="col-span-2">Match Preview</div>
            <div className="col-span-2">Blocking</div>
            <div className="col-span-1"></div>
          </div>

          {/* Rows */}
          <div className="space-y-1 animate-stagger">
            {items.map((item: any) => (
              <div
                key={item.id}
                onClick={() => navigate(`/review/${item.id}`)}
                className="grid grid-cols-12 gap-4 items-center px-4 py-3 rounded-md cursor-pointer transition-all duration-150"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'var(--bg-surface)')}
              >
                <div className="col-span-1">
                  <ScoreBadge score={item.score} />
                </div>
                <div className="col-span-3 min-w-0">
                  <div className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{item.record_a_name}</div>
                  <div className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>{item.record_a_source}</div>
                </div>
                <div className="col-span-3 min-w-0">
                  <div className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{item.record_b_name}</div>
                  <div className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>{item.record_b_source}</div>
                </div>
                <div className="col-span-2">
                  <FeaturePreview features={item.feature_breakdown} />
                </div>
                <div className="col-span-2">
                  <div className="flex flex-wrap gap-1">
                    {(item.blocking_keys || []).map((k: string, i: number) => (
                      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)' }}>{k}</span>
                    ))}
                  </div>
                </div>
                <div className="col-span-1 flex justify-end">
                  <ChevronRight size={14} style={{ color: 'var(--text-tertiary)' }} />
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4 text-sm" style={{ color: 'var(--text-tertiary)' }}>
            <span>Showing {cursor + 1}–{Math.min(cursor + 20, total)} of {total}</span>
            <div className="flex gap-2">
              <button
                onClick={() => setCursor(Math.max(0, cursor - 20))}
                disabled={cursor === 0}
                className="px-3 py-1.5 rounded-md text-xs font-medium"
                style={{ background: 'var(--bg-elevated)', color: cursor === 0 ? 'var(--text-disabled)' : 'var(--text-secondary)' }}
              >Previous</button>
              <button
                onClick={() => setCursor(cursor + 20)}
                disabled={cursor + 20 >= total}
                className="px-3 py-1.5 rounded-md text-xs font-medium"
                style={{ background: 'var(--bg-elevated)', color: cursor + 20 >= total ? 'var(--text-disabled)' : 'var(--text-secondary)' }}
              >Next</button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round((score || 0) * 100)
  const color = pct >= 80 ? 'var(--success)' : pct >= 55 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div className="flex flex-col items-center">
      <span className="text-sm font-bold font-mono" style={{ color }}>{pct}%</span>
      <div className="w-full h-1 rounded-full mt-1" style={{ background: 'var(--bg-elevated)' }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}

function FeaturePreview({ features }: { features: any }) {
  if (!features) return null
  const bars = [
    { key: 'anchor', label: 'ANC', value: features.anchor_score },
    { key: 'name', label: 'NAM', value: features.name_score },
    { key: 'addr', label: 'ADR', value: features.address_score },
  ]
  return (
    <div className="flex items-end gap-1 h-5">
      {bars.map(b => (
        <div key={b.key} className="flex flex-col items-center" title={`${b.label}: ${((b.value || 0) * 100).toFixed(0)}%`}>
          <div className="w-3 rounded-sm" style={{
            height: `${Math.max(2, (b.value || 0) * 20)}px`,
            background: (b.value || 0) > 0.7 ? 'var(--success)' : (b.value || 0) > 0.4 ? 'var(--warning)' : 'var(--danger)',
          }} />
        </div>
      ))}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 rounded-lg"
         style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
      <Users size={40} style={{ color: 'var(--text-tertiary)' }} />
      <h3 className="text-base font-semibold mt-4" style={{ color: 'var(--text-primary)' }}>Queue is empty</h3>
      <p className="text-sm mt-1" style={{ color: 'var(--text-tertiary)' }}>
        Run the pipeline to generate candidate pairs for review.
      </p>
    </div>
  )
}
