import { useStats, usePipelineStats, useRecentActivity, useDepartmentStats, useRunPipeline } from '../hooks/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { Activity, Database, GitMerge, Users, Zap, Play, CheckCircle, AlertTriangle, Clock } from 'lucide-react'

const STATUS_COLORS = { active: '#2dd4a4', dormant: '#f5a524', closed: '#6b7488' }

export default function Dashboard() {
  const { data: stats, isLoading } = useStats()
  const { data: pipeline } = usePipelineStats()
  const { data: recent } = useRecentActivity()
  const { data: depts } = useDepartmentStats()
  const runPipeline = useRunPipeline()

  if (isLoading) return <LoadingSkeleton />

  const s = stats || {}
  const pieData = [
    { name: 'Active', value: s.active_businesses || 0, color: STATUS_COLORS.active },
    { name: 'Dormant', value: s.dormant_businesses || 0, color: STATUS_COLORS.dormant },
    { name: 'Closed', value: s.closed_businesses || 0, color: STATUS_COLORS.closed },
  ]

  return (
    <div className="max-w-[1400px] mx-auto animate-stagger">
      {/* Hero */}
      <div className="mb-8">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              NexusID
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
              Real-time business identity resolution for Karnataka's regulatory ecosystem
            </p>
          </div>
          <button
            onClick={() => runPipeline.mutate()}
            disabled={runPipeline.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all duration-150"
            style={{
              background: runPipeline.isPending ? 'var(--bg-elevated)' : 'var(--brand-500)',
              color: '#fff',
              opacity: runPipeline.isPending ? 0.7 : 1,
            }}
          >
            {runPipeline.isPending ? <Clock size={14} className="animate-spin" /> : <Play size={14} />}
            {runPipeline.isPending ? 'Running Pipeline...' : 'Run Full Pipeline'}
          </button>
        </div>

        {runPipeline.isSuccess && (
          <div className="mt-3 p-3 rounded-md text-sm flex items-center gap-2 animate-fade-in"
               style={{ background: 'rgba(45,212,164,0.1)', color: 'var(--success)', border: '1px solid rgba(45,212,164,0.2)' }}>
            <CheckCircle size={14} />
            Pipeline completed in {runPipeline.data?.elapsed_seconds}s —
            {' '}{runPipeline.data?.resolution?.merges_performed} merges,
            {' '}{runPipeline.data?.resolution?.active_ubids} UBIDs
          </div>
        )}
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KPICard icon={Database} label="Departments" value={s.departments_connected} sub="Connected" color="var(--brand-500)" />
        <KPICard icon={GitMerge} label="UBIDs Resolved" value={s.total_ubids} sub={`${s.total_merges} merges`} color="var(--success)" />
        <KPICard icon={Activity} label="Active Businesses" value={s.active_businesses} sub={`of ${s.total_ubids} total`} color="var(--status-active)" />
        <KPICard icon={Zap} label="Auto-link Rate" value={`${(s.auto_link_rate * 100).toFixed(1)}%`} sub={`${s.review_queue_depth} pending reviews`} color="var(--warning)" />
      </div>

      {/* Pipeline Status */}
      {pipeline?.stages && (
        <div className="mb-6 p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
            Pipeline Status
          </h3>
          <div className="flex items-center gap-0">
            {pipeline.stages.map((stage: any, i: number) => (
              <div key={stage.name} className="flex items-center flex-1">
                <div className="flex-1 p-3 rounded-md" style={{ background: 'var(--bg-elevated)' }}>
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-2 h-2 rounded-full" style={{
                      background: stage.status === 'healthy' ? 'var(--success)' : 'var(--warning)',
                      animation: 'pulse-dot 2s infinite',
                    }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{stage.name}</span>
                  </div>
                  <div className="text-lg font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                    {stage.count.toLocaleString()}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{stage.label}</div>
                </div>
                {i < pipeline.stages.length - 1 && (
                  <div className="w-8 flex justify-center" style={{ color: 'var(--text-tertiary)' }}>→</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Two-column: Charts + Activity */}
      <div className="grid grid-cols-5 gap-4">
        {/* Left: Charts */}
        <div className="col-span-3 space-y-4">
          {/* Department Records */}
          {depts && depts.length > 0 && (
            <div className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
              <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
                Records by Department
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={depts} barSize={32}>
                  <XAxis dataKey="department" tick={{ fill: '#6b7488', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#6b7488', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#181d2a', border: '1px solid #2a3142', borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: '#e6ebf5' }}
                  />
                  <Bar dataKey="record_count" fill="#2e7cff" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Status Distribution */}
          <div className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
              Business Status Distribution
            </h3>
            <div className="flex items-center gap-6">
              <div className="w-40 h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={65} dataKey="value" strokeWidth={0}>
                      {pieData.map((e, i) => <Cell key={i} fill={e.color} />)}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex-1 space-y-3">
                {pieData.map(d => (
                  <div key={d.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ background: d.color }} />
                      <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{d.name}</span>
                    </div>
                    <span className="text-sm font-mono font-semibold" style={{ color: 'var(--text-primary)' }}>{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right: Activity Feed */}
        <div className="col-span-2 p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
            Recent Activity
          </h3>
          <div className="space-y-2 max-h-[420px] overflow-y-auto">
            {(recent || []).map((entry: any) => (
              <div key={entry.ledger_id} className="flex items-start gap-3 p-2.5 rounded-md transition-colors"
                   style={{ background: 'var(--bg-elevated)' }}>
                <EventIcon type={entry.event_type} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                    {formatEventType(entry.event_type)}
                  </div>
                  <div className="text-[10px] font-mono truncate" style={{ color: 'var(--text-tertiary)' }}>
                    {entry.aggregate_id?.slice(0, 24)}
                  </div>
                </div>
                <div className="text-[10px] shrink-0" style={{ color: 'var(--text-tertiary)' }}>
                  {entry.hash}
                </div>
              </div>
            ))}
            {(!recent || recent.length === 0) && (
              <div className="text-center py-8 text-sm" style={{ color: 'var(--text-tertiary)' }}>
                No activity yet. Run the pipeline to generate events.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function KPICard({ icon: Icon, label, value, sub, color }: any) {
  return (
    <div className="p-4 rounded-lg transition-all duration-150 hover:translate-y-[-1px]"
         style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
      <div className="flex items-center gap-2 mb-3">
        <Icon size={14} style={{ color }} />
        <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
      </div>
      <div className="text-2xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      <div className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{sub}</div>
    </div>
  )
}

function EventIcon({ type }: { type: string }) {
  const color = type.includes('MERGE') ? 'var(--brand-500)'
    : type.includes('STATUS') ? 'var(--warning)'
    : type.includes('REVIEW') ? 'var(--success)'
    : 'var(--text-tertiary)'
  return (
    <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5"
         style={{ background: `${color}20`, color }}>
      {type.includes('MERGE') ? <GitMerge size={12} /> : type.includes('REVIEW') ? <Users size={12} /> : <Activity size={12} />}
    </div>
  )
}

function formatEventType(t: string) {
  return t.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase())
}

function LoadingSkeleton() {
  return (
    <div className="max-w-[1400px] mx-auto space-y-6">
      <div className="skeleton h-12 w-60" />
      <div className="grid grid-cols-4 gap-4">
        {[1,2,3,4].map(i => <div key={i} className="skeleton h-28 rounded-lg" />)}
      </div>
      <div className="skeleton h-16 rounded-lg" />
      <div className="grid grid-cols-5 gap-4">
        <div className="col-span-3 skeleton h-80 rounded-lg" />
        <div className="col-span-2 skeleton h-80 rounded-lg" />
      </div>
    </div>
  )
}
