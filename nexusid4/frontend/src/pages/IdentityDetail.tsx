import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useIdentityDetail, useReverseMerge } from '../hooks/api'
import { ArrowLeft, GitMerge, Activity, FileText, Database, RotateCcw, Shield, MapPin, Calendar } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, ReferenceLine } from 'recharts'
import ForceGraph from '../components/ForceGraph'

const TABS = [
  { id: 'overview', label: 'Overview', icon: GitMerge },
  { id: 'activity', label: 'Activity Timeline', icon: Activity },
  { id: 'provenance', label: 'Merge History', icon: FileText },
  { id: 'records', label: 'Source Records', icon: Database },
]

export default function IdentityDetail() {
  const { ubid } = useParams<{ ubid: string }>()
  const navigate = useNavigate()
  const { data, isLoading } = useIdentityDetail(ubid || '')
  const reverseMerge = useReverseMerge()
  const [tab, setTab] = useState('overview')

  if (isLoading) return <div className="skeleton h-96 rounded-lg" />
  if (!data) return <div>Not found</div>

  const statusColor = data.activity?.status === 'ACTIVE' ? 'var(--status-active)'
    : data.activity?.status === 'DORMANT' ? 'var(--status-dormant)' : 'var(--status-closed)'

  return (
    <div className="max-w-[1200px] mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <button onClick={() => navigate('/identity')} className="p-2 rounded-md mt-1" style={{ color: 'var(--text-secondary)' }}>
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{data.primary_name}</h1>
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full" style={{ background: `${statusColor}15` }}>
              <div className="w-2 h-2 rounded-full" style={{ background: statusColor, animation: data.activity?.status === 'ACTIVE' ? 'pulse-dot 2s infinite' : 'none' }} />
              <span className="text-[10px] font-semibold uppercase" style={{ color: statusColor }}>{data.activity?.status}</span>
            </div>
          </div>
          <div className="flex items-center gap-4 mt-2 text-xs" style={{ color: 'var(--text-tertiary)' }}>
            <span className="font-mono" style={{ color: 'var(--brand-300)' }}>{data.ubid}</span>
            <span className="flex items-center gap-1"><Shield size={10} />{data.anchor_type}: {data.anchor_value || 'Internal'}</span>
            <span className="flex items-center gap-1"><MapPin size={10} />{data.primary_address}</span>
            <span className="flex items-center gap-1"><Database size={10} />{data.source_records?.length || 0} source records</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 mb-6 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors -mb-px"
            style={{
              color: tab === t.id ? 'var(--brand-300)' : 'var(--text-tertiary)',
              borderBottom: tab === t.id ? '2px solid var(--brand-500)' : '2px solid transparent',
            }}
          >
            <t.icon size={14} />{t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'overview' && <OverviewTab data={data} />}
      {tab === 'activity' && <ActivityTab data={data} />}
      {tab === 'provenance' && <ProvenanceTab data={data} onReverse={(mergeId: string) => {
        if (confirm('Reverse this merge? This will restore the loser UBID and reassign its records.')) {
          reverseMerge.mutate({ ubid: ubid!, mergeId })
        }
      }} />}
      {tab === 'records' && <SourceRecordsTab data={data} />}
    </div>
  )
}

function OverviewTab({ data }: { data: any }) {
  const graphData = data.activity?.timeline?.slice(0, 30).reverse().map((e: any, i: number) => ({
    date: e.event_date,
    weight: e.decayed_weight,
    type: e.signal_class,
  })) || []

  return (
    <div className="grid grid-cols-3 gap-4">
      {/* Identity Graph Visualization */}
      <div className="col-span-2 p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
        <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
          Identity Cluster Graph
        </h3>
        <ForceGraph
          nodes={data.graph?.nodes || []}
          edges={data.graph?.edges || []}
          width={520}
          height={300}
        />
      </div>

      {/* Quick stats */}
      <div className="space-y-4">
        <div className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <div className="text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--text-tertiary)' }}>Rolling Score</div>
          <div className="text-2xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
            {data.activity?.score?.toFixed(2)}
          </div>
        </div>
        <div className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <div className="text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--text-tertiary)' }}>Events Tracked</div>
          <div className="text-2xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
            {data.activity?.event_count || 0}
          </div>
        </div>
        <div className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <div className="text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--text-tertiary)' }}>Source Records</div>
          <div className="text-2xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
            {data.source_records?.length || 0}
          </div>
          <div className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
            across {new Set(data.source_records?.map((r: any) => r.source_system)).size} departments
          </div>
        </div>
      </div>

      {/* Activity Score Chart */}
      {graphData.length > 0 && (
        <div className="col-span-3 p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
            Activity Score Contributions (Recent)
          </h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={graphData}>
              <XAxis dataKey="date" tick={{ fill: '#6b7488', fontSize: 9 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#6b7488', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#181d2a', border: '1px solid #2a3142', borderRadius: 8, fontSize: 11 }} />
              <ReferenceLine y={0} stroke="#2a3142" />
              <Bar dataKey="weight" fill="#2e7cff" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function ActivityTab({ data }: { data: any }) {
  const timeline = data.activity?.timeline || []
  const signalColors: Record<string, string> = {
    STRONG_ACTIVE: 'var(--success)', WEAK_ACTIVE: 'var(--brand-300)',
    NEUTRAL: 'var(--text-tertiary)', DORMANCY: 'var(--warning)', CLOSURE: 'var(--danger)',
  }

  return (
    <div className="space-y-1">
      {timeline.length === 0 && (
        <div className="text-center py-12 text-sm" style={{ color: 'var(--text-tertiary)' }}>No events recorded</div>
      )}
      {timeline.map((evt: any, i: number) => (
        <div key={i} className="flex items-start gap-4 p-3 rounded-md"
             style={{
               background: evt.is_tipping_point ? 'rgba(46,124,255,0.06)' : 'var(--bg-surface)',
               border: evt.is_tipping_point ? '1px solid var(--brand-500)' : '1px solid var(--border-subtle)',
             }}>
          {/* Timeline dot */}
          <div className="flex flex-col items-center mt-1.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: signalColors[evt.signal_class] || '#6b7488' }} />
            {i < timeline.length - 1 && <div className="w-px flex-1 mt-1" style={{ background: 'var(--border-subtle)' }} />}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {evt.event_type.replace(/_/g, ' ')}
                </span>
                {evt.is_tipping_point && (
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full" style={{ background: 'var(--brand-500)', color: '#fff' }}>
                    TIPPING POINT
                  </span>
                )}
              </div>
              <span className="text-xs font-mono" style={{ color: 'var(--text-tertiary)' }}>{evt.event_date}</span>
            </div>
            <div className="flex items-center gap-4 mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
              <span>{evt.source_system}</span>
              <span className="font-mono" style={{ color: signalColors[evt.signal_class] }}>
                {evt.signal_class} (base: {evt.base_weight > 0 ? '+' : ''}{evt.base_weight})
              </span>
              <span>decay: {evt.decay_factor} → contribution: {evt.decayed_weight > 0 ? '+' : ''}{evt.decayed_weight}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function ProvenanceTab({ data, onReverse }: { data: any; onReverse: (id: string) => void }) {
  const merges = data.merge_history || []

  return (
    <div className="space-y-3">
      {merges.length === 0 && (
        <div className="text-center py-12 text-sm" style={{ color: 'var(--text-tertiary)' }}>No merge history</div>
      )}
      {merges.map((m: any) => (
        <div key={m.merge_id} className="p-4 rounded-lg" style={{
          background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
          opacity: m.reversed ? 0.5 : 1,
        }}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <GitMerge size={14} style={{ color: m.reversed ? 'var(--danger)' : 'var(--success)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {m.reversed ? 'Reversed Merge' : 'Merge'}
              </span>
              <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--text-tertiary)' }}>
                Score: {(m.score * 100).toFixed(1)}%
              </span>
            </div>
            {!m.reversed && (
              <button onClick={() => onReverse(m.merge_id)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
                      style={{ background: 'var(--bg-elevated)', color: 'var(--danger)', border: '1px solid var(--border-default)' }}>
                <RotateCcw size={12} /> Reverse
              </button>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Winner:</span> <span className="font-mono">{m.winner}</span></div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Loser:</span> <span className="font-mono">{m.loser}</span></div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Model:</span> {m.model_version}</div>
            <div><span style={{ color: 'var(--text-tertiary)' }}>Decided by:</span> {m.decided_by} at {m.decided_at?.slice(0, 19)}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function SourceRecordsTab({ data }: { data: any }) {
  const records = data.source_records || []
  const deptColors: Record<string, string> = {
    SHOP_EST: '#6ba8ff', FACTORIES: '#f5a524', LABOUR: '#2dd4a4', KSPCB: '#f24c5c', GST: '#a78bfa',
  }

  return (
    <div className="space-y-3">
      {records.map((r: any) => (
        <div key={r.id} className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                  style={{ background: `${deptColors[r.source_system] || '#6b7488'}20`, color: deptColors[r.source_system] }}>
              {r.source_system}
            </span>
            <span className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>{r.source_record_id}</span>
          </div>
          <div className="grid grid-cols-3 gap-3 text-xs">
            <Field label="Business Name" value={r.business_name} />
            <Field label="Normalized" value={r.normalized_name} />
            <Field label="Locality" value={r.address_locality} />
            <Field label="Pincode" value={r.address_pincode} />
            <Field label="PAN" value={r.pan} mono />
            <Field label="GSTIN" value={r.gstin} mono />
            <Field label="Phone" value={r.phone} />
            <Field label="Email" value={r.email} />
            <Field label="Reg Date" value={r.registration_date} />
          </div>
        </div>
      ))}
    </div>
  )
}

function Field({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{label}</div>
      <div className={`text-sm mt-0.5 ${mono ? 'font-mono' : ''}`} style={{ color: value ? 'var(--text-primary)' : 'var(--text-disabled)' }}>
        {value || '—'}
      </div>
    </div>
  )
}
