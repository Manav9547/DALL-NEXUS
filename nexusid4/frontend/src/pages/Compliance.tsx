import { useAdapterHealth, useModelStatus, useReviewerKPIs, useStats, usePipelineStats } from '../hooks/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Activity, CheckCircle, AlertTriangle, XCircle, Cpu, Users, Shield, RefreshCw } from 'lucide-react'

export default function Compliance() {
  const { data: adapters } = useAdapterHealth()
  const { data: model } = useModelStatus()
  const { data: reviewer } = useReviewerKPIs()
  const { data: stats } = useStats()
  const { data: pipeline } = usePipelineStats()

  return (
    <div className="max-w-[1400px] mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Compliance Dashboard</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
          System health, model performance, and operational metrics
        </p>
      </div>

      {/* Top KPIs */}
      <div className="grid grid-cols-4 gap-4 mb-6 animate-stagger">
        <KPI
          icon={CheckCircle}
          label="Adapters Healthy"
          value={`${adapters?.filter((a: any) => a.status === 'HEALTHY').length || 0}/${adapters?.length || 0}`}
          color="var(--success)"
          status={adapters?.every((a: any) => a.status === 'HEALTHY') ? 'good' : 'warn'}
        />
        <KPI
          icon={Activity}
          label="Review Queue"
          value={stats?.review_queue_depth || 0}
          color={stats?.review_queue_depth > 50 ? 'var(--warning)' : 'var(--success)'}
          status={stats?.review_queue_depth > 50 ? 'warn' : 'good'}
        />
        <KPI
          icon={Cpu}
          label="Model PR-AUC"
          value={model?.pr_auc?.toFixed(3) || '—'}
          color="var(--brand-300)"
          status="good"
        />
        <KPI
          icon={Shield}
          label="False Merge Rate"
          value={model ? `${(model.false_merge_rate * 100).toFixed(1)}%` : '—'}
          color={model?.false_merge_rate < 0.01 ? 'var(--success)' : 'var(--danger)'}
          status={model?.false_merge_rate < 0.01 ? 'good' : 'warn'}
        />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Adapter Health Grid */}
        <div className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
            Adapter Health
          </h3>
          <div className="space-y-2">
            {(adapters || []).map((a: any) => (
              <div key={a.source_system} className="flex items-center justify-between p-3 rounded-md"
                   style={{ background: 'var(--bg-elevated)', border: `1px solid ${a.status === 'HEALTHY' ? 'rgba(45,212,164,0.2)' : 'rgba(242,76,92,0.2)'}` }}>
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full" style={{
                    background: a.status === 'HEALTHY' ? 'var(--success)' : 'var(--danger)',
                    animation: 'pulse-dot 2s infinite',
                  }} />
                  <div>
                    <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{a.source_system}</div>
                    <div className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                      {a.total_records.toLocaleString()} records · {a.freshness_seconds.toFixed(0)}s ago
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-mono" style={{ color: a.status === 'HEALTHY' ? 'var(--success)' : 'var(--danger)' }}>
                    {a.status}
                  </div>
                  {a.last_error && (
                    <div className="text-[10px] truncate max-w-[120px]" style={{ color: 'var(--danger)' }}>{a.last_error}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Model Status */}
        <div className="space-y-4">
          <div className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
              Model Status
            </h3>
            {model && (
              <div className="space-y-3">
                <ModelRow label="Active Version" value={model.active_version} />
                <ModelRow label="PR-AUC" value={model.pr_auc?.toFixed(4)} good={model.pr_auc >= 0.97} />
                <ModelRow label="False Merge Rate" value={`${(model.false_merge_rate * 100).toFixed(2)}%`} good={model.false_merge_rate < 0.01} />
                <ModelRow label="Auto-link Threshold" value={model.auto_link_threshold?.toFixed(2)} />
                <ModelRow label="Review Threshold" value={model.review_threshold?.toFixed(2)} />
                <div className="pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Threshold Visualization</span>
                  </div>
                  <div className="mt-2 h-6 rounded-full overflow-hidden flex" style={{ background: 'var(--bg-elevated)' }}>
                    <div className="h-full flex items-center justify-center text-[9px] font-bold" style={{
                      width: `${model.review_threshold * 100}%`, background: 'rgba(107,116,136,0.3)', color: 'var(--text-tertiary)'
                    }}>HOLD</div>
                    <div className="h-full flex items-center justify-center text-[9px] font-bold" style={{
                      width: `${(model.auto_link_threshold - model.review_threshold) * 100}%`, background: 'rgba(245,165,36,0.3)', color: 'var(--warning)'
                    }}>REVIEW</div>
                    <div className="h-full flex items-center justify-center text-[9px] font-bold" style={{
                      width: `${(1 - model.auto_link_threshold) * 100}%`, background: 'rgba(45,212,164,0.3)', color: 'var(--success)'
                    }}>AUTO</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Reviewer KPIs */}
          <div className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
              Reviewer Performance
            </h3>
            {reviewer && (
              <div className="space-y-3">
                <ModelRow label="Total Reviewed" value={reviewer.total_reviewed} />
                <ModelRow label="Confirmed" value={reviewer.confirmed} />
                <ModelRow label="Rejected" value={reviewer.rejected} />
                <ModelRow label="Confirm Rate" value={`${(reviewer.confirm_rate * 100).toFixed(1)}%`} />
                <div className="mt-2">
                  <div className="text-[10px] mb-1" style={{ color: 'var(--text-tertiary)' }}>Confirm vs Reject</div>
                  <div className="h-3 rounded-full overflow-hidden flex" style={{ background: 'var(--bg-elevated)' }}>
                    <div className="h-full" style={{
                      width: `${reviewer.confirm_rate * 100}%`, background: 'var(--success)',
                    }} />
                    <div className="h-full" style={{
                      width: `${(1 - reviewer.confirm_rate) * 100}%`, background: 'var(--danger)',
                    }} />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Pipeline Throughput */}
      {pipeline?.stages && (
        <div className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-tertiary)' }}>
            Pipeline Throughput
          </h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={pipeline.stages} barSize={40}>
              <XAxis dataKey="name" tick={{ fill: '#6b7488', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#6b7488', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#181d2a', border: '1px solid #2a3142', borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {pipeline.stages.map((_: any, i: number) => {
                  const colors = ['#2e7cff', '#6ba8ff', '#2dd4a4', '#f5a524']
                  return <rect key={i} fill={colors[i % colors.length]} />
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function KPI({ icon: Icon, label, value, color, status }: any) {
  return (
    <div className="p-4 rounded-lg" style={{
      background: 'var(--bg-surface)',
      border: `1px solid ${status === 'warn' ? 'rgba(245,165,36,0.3)' : 'var(--border-subtle)'}`,
    }}>
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} style={{ color }} />
        <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
      </div>
      <div className="text-2xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
    </div>
  )
}

function ModelRow({ label, value, good }: { label: string; value: any; good?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
      <span className="text-xs font-mono font-semibold" style={{
        color: good === true ? 'var(--success)' : good === false ? 'var(--danger)' : 'var(--text-primary)',
      }}>{value}</span>
    </div>
  )
}
