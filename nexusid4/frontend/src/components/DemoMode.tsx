import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ChevronRight, ChevronLeft, X, Sparkles } from 'lucide-react'

interface Step {
  path: string
  title: string
  description: string
  highlight?: string // CSS selector hint (not used for actual highlighting, just context)
}

const STEPS: Step[] = [
  {
    path: '/',
    title: 'Welcome to NexusID',
    description: 'This is the system overview. The four KPI cards show live metrics from the identity resolution engine. Click "Run Full Pipeline" to process all records through blocking → scoring → resolution → activity inference.',
  },
  {
    path: '/',
    title: 'Pipeline Status',
    description: 'The pipeline strip shows data flowing through 4 stages: Ingestion (records pulled from departments), Resolution (candidate pairs scored and merged), Activity (events joined and status computed), and Review (pairs awaiting human adjudication).',
  },
  {
    path: '/review',
    title: 'Review Queue',
    description: 'These are candidate pairs the system isn\'t confident enough to auto-merge (score 55%–88%). Each row shows the pair score, source names, and a mini feature breakdown. Click any row to review it.',
  },
  {
    path: '/review',
    title: 'Reviewer Workflow',
    description: 'In the detail screen, you\'ll see records side-by-side with diff highlighting (green = match, amber = differ). The centre column shows the 5-feature score breakdown. Use keyboard shortcuts: 1 = Confirm, 2 = Reject, 3 = Escalate.',
  },
  {
    path: '/identity',
    title: 'Identity Explorer',
    description: 'Search for any business by UBID, PAN, GSTIN, name, or pincode. Each card shows the resolved identity with its activity status. Try searching "560058" to see businesses in the Peenya industrial area.',
  },
  {
    path: '/identity',
    title: 'Identity Graph',
    description: 'Click any business to see its full identity profile. The Overview tab shows a force-directed graph of all source records linked to this UBID, colored by department. The Activity tab shows the event timeline with tipping-point detection.',
  },
  {
    path: '/query',
    title: 'Analytical Queries',
    description: 'The flagship query finds "active businesses not inspected in 18 months" — a question no single department can answer today. Try pincode 560058. Results include latency metrics and CSV export.',
  },
  {
    path: '/compliance',
    title: 'Compliance Dashboard',
    description: 'Monitor adapter health (5 department connections), model performance (PR-AUC, false merge rate), and reviewer throughput. The threshold bar shows how scores map to AUTO / REVIEW / HOLD decisions.',
  },
  {
    path: '/ledger',
    title: 'Immutable Audit Trail',
    description: 'Every action — every merge, reversal, status change, and review decision — is recorded in a hash-chained event ledger. Click "Verify Chain Integrity" to cryptographically prove nothing has been tampered with.',
  },
  {
    path: '/ledger',
    title: 'Demo Complete',
    description: 'You\'ve seen the full NexusID pipeline: from fragmented department records to unified business identities, with real-time activity inference, human-in-the-loop review, and an immutable audit trail. The system resolves ~800 businesses from ~3,000 records with 99.9% PR-AUC.',
  },
]

export default function DemoMode() {
  const [active, setActive] = useState(false)
  const [step, setStep] = useState(0)
  const navigate = useNavigate()
  const location = useLocation()

  // Activate via ?demo=1
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('demo') === '1') {
      setActive(true)
      setStep(0)
    }
  }, [])

  useEffect(() => {
    if (active && STEPS[step]) {
      const targetPath = STEPS[step].path
      if (location.pathname !== targetPath) {
        navigate(targetPath)
      }
    }
  }, [step, active])

  const next = () => {
    if (step < STEPS.length - 1) setStep(s => s + 1)
    else setActive(false)
  }

  const prev = () => {
    if (step > 0) setStep(s => s - 1)
  }

  if (!active) return null

  const current = STEPS[step]

  return (
    <>
      {/* Subtle overlay */}
      <div className="fixed inset-0 z-40 pointer-events-none" style={{ background: 'rgba(0,0,0,0.15)' }} />

      {/* Tour card */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-[520px] animate-fade-in"
           style={{
             background: 'var(--bg-elevated)',
             border: '1px solid var(--brand-500)',
             borderRadius: 14,
             boxShadow: '0 16px 50px rgba(46,124,255,0.2)',
           }}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <div className="flex items-center gap-2">
            <Sparkles size={14} style={{ color: 'var(--brand-300)' }} />
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--brand-300)' }}>
              Guided Tour — Step {step + 1} of {STEPS.length}
            </span>
          </div>
          <button onClick={() => setActive(false)} className="p-1 rounded-md" style={{ color: 'var(--text-tertiary)' }}>
            <X size={14} />
          </button>
        </div>

        {/* Progress */}
        <div className="px-5 mb-3">
          <div className="h-1 rounded-full flex gap-0.5" style={{ background: 'var(--bg-hover)' }}>
            {STEPS.map((_, i) => (
              <div key={i} className="flex-1 rounded-full transition-all duration-300" style={{
                background: i <= step ? 'var(--brand-500)' : 'var(--bg-hover)',
              }} />
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="px-5 pb-2">
          <h3 className="text-base font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            {current.title}
          </h3>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {current.description}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between px-5 py-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
          <button
            onClick={prev}
            disabled={step === 0}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            style={{
              color: step === 0 ? 'var(--text-disabled)' : 'var(--text-secondary)',
              background: 'var(--bg-hover)',
            }}
          >
            <ChevronLeft size={12} /> Back
          </button>

          <span className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
            Press → or click Next
          </span>

          <button
            onClick={next}
            className="flex items-center gap-1 px-4 py-1.5 rounded-md text-xs font-semibold"
            style={{ background: 'var(--brand-500)', color: '#fff' }}
          >
            {step === STEPS.length - 1 ? 'Finish' : 'Next'} <ChevronRight size={12} />
          </button>
        </div>
      </div>
    </>
  )
}
