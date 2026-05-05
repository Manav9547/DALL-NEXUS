import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const BASE = '/api'

async function fetchJSON(path: string) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function postJSON(path: string, body?: unknown) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

// ─── Stats ────────────────────────────────────────────────────────────────
export function useStats() {
  return useQuery({ queryKey: ['stats'], queryFn: () => fetchJSON('/stats') })
}

export function usePipelineStats() {
  return useQuery({ queryKey: ['pipeline-stats'], queryFn: () => fetchJSON('/stats/pipeline') })
}

export function useRecentActivity() {
  return useQuery({ queryKey: ['recent-activity'], queryFn: () => fetchJSON('/stats/recent-activity'), refetchInterval: 10_000 })
}

export function useDepartmentStats() {
  return useQuery({ queryKey: ['dept-stats'], queryFn: () => fetchJSON('/stats/departments') })
}

// ─── Pipeline ─────────────────────────────────────────────────────────────
export function useRunPipeline() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => postJSON('/pipeline/run-all'),
    onSuccess: () => { qc.invalidateQueries() },
  })
}

// ─── Review Queue ─────────────────────────────────────────────────────────
export function useReviewQueue(cursor = 0, limit = 20) {
  return useQuery({ queryKey: ['review-queue', cursor, limit], queryFn: () => fetchJSON(`/reviews/queue?cursor=${cursor}&limit=${limit}`) })
}

export function useReviewDetail(id: string) {
  return useQuery({ queryKey: ['review', id], queryFn: () => fetchJSON(`/reviews/${id}`), enabled: !!id })
}

export function useReviewExplanation(id: string) {
  return useQuery({
    queryKey: ['review-explanation', id],
    queryFn: () => fetchJSON(`/reviews/explanation/${id}`),
    enabled: false, // lazy-loaded on demand
  })
}

export function useSubmitReview() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, decision, reviewer_id, notes }: { id: string; decision: string; reviewer_id: string; notes?: string }) =>
      postJSON(`/reviews/${id}/decide`, { decision, reviewer_id, notes }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['review-queue'] }) },
  })
}

// ─── Identity ─────────────────────────────────────────────────────────────
export function useIdentitySearch(q: string, status?: string) {
  return useQuery({
    queryKey: ['identity-search', q, status],
    queryFn: () => fetchJSON(`/identity/search?q=${encodeURIComponent(q)}&limit=30${status ? `&status=${status}` : ''}`),
    enabled: q.length > 0,
  })
}

export function useIdentityDetail(ubid: string) {
  return useQuery({ queryKey: ['identity', ubid], queryFn: () => fetchJSON(`/identity/${ubid}`), enabled: !!ubid })
}

export function useReverseMerge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ ubid, mergeId }: { ubid: string; mergeId: string }) =>
      postJSON(`/identity/${ubid}/reverse-merge/${mergeId}?reason=Admin+reversal`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['identity'] }) },
  })
}

// ─── Query ────────────────────────────────────────────────────────────────
export function useFlagshipQuery(pincode: string, months: number) {
  return useQuery({
    queryKey: ['flagship', pincode, months],
    queryFn: () => fetchJSON(`/query/active-not-inspected?pincode=${pincode}&months_threshold=${months}`),
    enabled: false,
  })
}

export function useGhostCandidates(district?: string) {
  return useQuery({
    queryKey: ['ghosts', district],
    queryFn: () => fetchJSON(`/query/ghost-candidates?min_months_silent=12${district ? `&district=${district}` : ''}`),
    enabled: false,
  })
}

// ─── Compliance ───────────────────────────────────────────────────────────
export function useAdapterHealth() {
  return useQuery({ queryKey: ['adapter-health'], queryFn: () => fetchJSON('/health/adapters'), refetchInterval: 30_000 })
}

export function useModelStatus() {
  return useQuery({ queryKey: ['model-status'], queryFn: () => fetchJSON('/compliance/model') })
}

export function useReviewerKPIs() {
  return useQuery({ queryKey: ['reviewer-kpis'], queryFn: () => fetchJSON('/compliance/reviewer-kpis') })
}

// ─── Ledger ───────────────────────────────────────────────────────────────
export function useLedger(aggregateType?: string, cursor = 0) {
  return useQuery({
    queryKey: ['ledger', aggregateType, cursor],
    queryFn: () => fetchJSON(`/ledger?limit=50&cursor=${cursor}${aggregateType ? `&aggregate_type=${aggregateType}` : ''}`),
  })
}

export function useVerifyLedger() {
  return useMutation({ mutationFn: () => postJSON('/ledger/verify') })
}
