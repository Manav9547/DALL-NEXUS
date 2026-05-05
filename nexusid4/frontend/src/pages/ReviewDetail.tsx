import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useReviewDetail, useSubmitReview, useReviewExplanation } from '../hooks/api'
import { Check, X, AlertTriangle, ArrowLeft, Keyboard, Brain, ShieldCheck } from 'lucide-react'

const FEATURES = [
  { key: 'anchor_score', label: 'Anchor Match', weight: 0.40, desc: 'PAN / GSTIN exact match' },
  { key: 'name_score', label: 'Name Similarity', weight: 0.25, desc: 'Jaro-Winkler + Token Sort' },
  { key: 'address_score', label: 'Address Match', weight: 0.20, desc: 'Pincode + Locality + District' },
  { key: 'contact_score', label: 'Contact Match', weight: 0.10, desc: 'Phone / Email' },
  { key: 'date_proximity_score', label: 'Date Proximity', weight: 0.05, desc: 'Registration date proximity' },
]

export default function ReviewDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data, isLoading } = useReviewDetail(id || '')
  const submitReview = useSubmitReview()
  const [holdProgress, setHoldProgress] = useState<string | null>(null)
  const [holdTimer, setHoldTimer] = useState<ReturnType<typeof setTimeout> | null>(null)
  const [notes, setNotes] = useState('')
  const [showExplanation, setShowExplanation] = useState(false)
  const [explanation, setExplanation] = useState<any>(null)
  const [loadingExplanation, setLoadingExplanation] = useState(false)

  const loadExplanation = async () => {
    if (explanation || !id) return
    setLoadingExplanation(true)
    try {
      const res = await fetch(`/api/reviews/explanation/${id}`)
      const data = await res.json()
      setExplanation(data)
    } catch {} finally { setLoadingExplanation(false) }
  }

  const handleDecision = useCallback((decision: string) => {
    if (!id) return
    submitReview.mutate(
      { id, decision, reviewer_id: 'reviewer-1', notes: notes || undefined },
      { onSuccess: () => navigate('/review') }
    )
  }, [id, notes, submitReview, navigate])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === '1') handleDecision('CONFIRM')
      else if (e.key === '2') handleDecision('REJECT')
      else if (e.key === '3') handleDecision('ESCALATE')
      else if (e.key === 'e' || e.key === 'E') { setShowExplanation(s => !s); if (!explanation) loadExplanation() }
      else if (e.key === 'Escape') navigate('/review')
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [handleDecision, navigate])

  if (isLoading) return <div className="skeleton h-96 rounded-lg" />
  if (!data) return <div>Not found</div>

  const features = data.feature_breakdown || {}

  return (
    <div className="max-w-[1400px] mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/review')} className="p-2 rounded-md transition-colors"
                  style={{ color: 'var(--text-secondary)' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>Review Pair</h1>
            <span className="text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{id?.slice(0, 12)}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          <Keyboard size={12} />
          <kbd className="px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-elevated)' }}>1</kbd> Confirm
          <kbd className="px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-elevated)' }}>2</kbd> Reject
          <kbd className="px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-elevated)' }}>3</kbd> Escalate
        </div>
      </div>

      {/* Three-column layout */}
      <div className="grid grid-cols-7 gap-4 mb-4">
        {/* Record A */}
        <div className="col-span-3">
          <RecordCard record={data.record_a} label="Record A" otherRecord={data.record_b} />
        </div>

        {/* Score Breakdown (centre) */}
        <div className="col-span-1">
          <div className="p-4 rounded-lg sticky top-0" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
            <div className="text-center mb-4">
              <div className="text-3xl font-bold font-mono" style={{
                color: (data.score || 0) >= 0.8 ? 'var(--success)' : (data.score || 0) >= 0.55 ? 'var(--warning)' : 'var(--danger)'
              }}>
                {Math.round((data.score || 0) * 100)}%
              </div>
              <div className="text-[10px] uppercase tracking-wider mt-1" style={{ color: 'var(--text-tertiary)' }}>
                Composite Score
              </div>
            </div>

            <div className="space-y-3">
              {FEATURES.map(f => {
                const val = features[f.key] || 0
                const contribution = val * f.weight
                return (
                  <div key={f.key}>
                    <div className="flex items-center justify-between text-[10px] mb-1">
                      <span style={{ color: 'var(--text-secondary)' }}>{f.label}</span>
                      <span className="font-mono font-semibold" style={{ color: 'var(--text-primary)' }}>
                        {(val * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full" style={{ background: 'var(--bg-elevated)' }}>
                      <div className="h-full rounded-full transition-all duration-300" style={{
                        width: `${Math.max(0, Math.min(100, val * 100))}%`,
                        background: val > 0.7 ? 'var(--success)' : val > 0.4 ? 'var(--warning)' : val >= 0 ? 'var(--danger)' : 'var(--danger)',
                      }} />
                    </div>
                    <div className="text-[9px] mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                      w={f.weight} → +{(contribution * 100).toFixed(1)}%
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Blocking keys */}
            <div className="mt-4 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
              <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: 'var(--text-tertiary)' }}>Blocked By</div>
              <div className="flex flex-wrap gap-1">
                {(data.blocking_keys || []).map((k: string, i: number) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 rounded-full"
                        style={{ background: 'rgba(46,124,255,0.1)', color: 'var(--brand-300)' }}>{k}</span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Record B */}
        <div className="col-span-3">
          <RecordCard record={data.record_b} label="Record B" otherRecord={data.record_a} />
        </div>
      </div>

      {/* AI Explanation Panel */}
      <div className="mb-4">
        <button
          onClick={() => { setShowExplanation(!showExplanation); if (!explanation) loadExplanation() }}
          className="flex items-center gap-2 px-4 py-2 rounded-md text-xs font-medium transition-all w-full"
          style={{
            background: showExplanation ? 'rgba(46,124,255,0.08)' : 'var(--bg-surface)',
            border: `1px solid ${showExplanation ? 'var(--brand-500)' : 'var(--border-subtle)'}`,
            color: showExplanation ? 'var(--brand-300)' : 'var(--text-secondary)',
          }}
        >
          <Brain size={14} />
          AI Explanation
          {explanation?.pii_verification?.verified && (
            <span className="flex items-center gap-1 ml-auto text-[10px]" style={{ color: 'var(--success)' }}>
              <ShieldCheck size={10} /> PII-safe
            </span>
          )}
        </button>

        {showExplanation && (
          <div className="mt-2 p-4 rounded-lg animate-fade-in" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
            {loadingExplanation ? (
              <div className="skeleton h-20 rounded-md" />
            ) : explanation ? (
              <>
                <div className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
                  {explanation.explanation}
                </div>
                <div className="flex items-center gap-2 pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                  <ShieldCheck size={12} style={{ color: explanation.pii_verification?.verified ? 'var(--success)' : 'var(--danger)' }} />
                  <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                    Generated from scrambled data — no PII transmitted. {explanation.pii_verification?.violations?.length || 0} violations detected.
                  </span>
                </div>
              </>
            ) : (
              <div className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Failed to load explanation.</div>
            )}
          </div>
        )}
      </div>

      {/* Action Bar */}
      <div className="sticky bottom-0 p-4 rounded-lg flex items-center gap-4"
           style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', backdropFilter: 'blur(8px)' }}>
        <input
          type="text"
          placeholder="Add review notes (optional)..."
          value={notes}
          onChange={e => setNotes(e.target.value)}
          className="flex-1 px-3 py-2 rounded-md text-sm"
          style={{ background: 'var(--bg-elevated)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', outline: 'none' }}
        />

        <button
          onClick={() => handleDecision('CONFIRM')}
          disabled={submitReview.isPending}
          className="flex items-center gap-2 px-6 py-2.5 rounded-md text-sm font-semibold transition-all duration-150"
          style={{ background: 'var(--success)', color: '#0a0d14' }}
        >
          <Check size={16} /> Confirm Match
        </button>

        <button
          onClick={() => handleDecision('REJECT')}
          disabled={submitReview.isPending}
          className="flex items-center gap-2 px-6 py-2.5 rounded-md text-sm font-semibold transition-all duration-150"
          style={{ background: 'var(--danger)', color: '#fff' }}
        >
          <X size={16} /> Reject
        </button>

        <button
          onClick={() => handleDecision('ESCALATE')}
          disabled={submitReview.isPending}
          className="flex items-center gap-2 px-6 py-2.5 rounded-md text-sm font-semibold transition-all duration-150"
          style={{ background: 'var(--warning)', color: '#0a0d14' }}
        >
          <AlertTriangle size={16} /> Escalate
        </button>
      </div>
    </div>
  )
}

function RecordCard({ record, label, otherRecord }: { record: any; label: string; otherRecord: any }) {
  if (!record) return null

  const deptColors: Record<string, string> = {
    SHOP_EST: '#6ba8ff', FACTORIES: '#f5a524', LABOUR: '#2dd4a4', KSPCB: '#f24c5c', GST: '#a78bfa',
  }

  const fields = [
    { key: 'business_name', label: 'Business Name' },
    { key: 'normalized_name', label: 'Normalized' },
    { key: 'address_locality', label: 'Locality' },
    { key: 'address_pincode', label: 'Pincode' },
    { key: 'address_city', label: 'City' },
    { key: 'address_district', label: 'District' },
    { key: 'pan', label: 'PAN' },
    { key: 'gstin', label: 'GSTIN' },
    { key: 'phone', label: 'Phone' },
    { key: 'email', label: 'Email' },
    { key: 'registration_date', label: 'Reg. Date' },
  ]

  return (
    <div className="rounded-lg overflow-hidden" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
              style={{ background: `${deptColors[record.source_system] || '#6b7488'}20`, color: deptColors[record.source_system] || '#6b7488' }}>
          {record.source_system}
        </span>
      </div>

      {/* Fields */}
      <div className="p-4 space-y-2.5">
        {fields.map(f => {
          const val = record[f.key]
          const otherVal = otherRecord?.[f.key]
          const matches = val && otherVal && String(val).toLowerCase() === String(otherVal).toLowerCase()
          const differs = val && otherVal && !matches

          return (
            <div key={f.key}>
              <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--text-tertiary)' }}>{f.label}</div>
              <div className="text-sm font-mono px-2 py-1 rounded"
                   style={{
                     color: 'var(--text-primary)',
                     background: matches ? 'rgba(45,212,164,0.08)' : differs ? 'rgba(245,165,36,0.08)' : 'transparent',
                     borderLeft: matches ? '2px solid var(--success)' : differs ? '2px solid var(--warning)' : '2px solid transparent',
                   }}>
                {val || <span style={{ color: 'var(--text-disabled)' }}>—</span>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
