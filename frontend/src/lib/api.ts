import type {
  DreamCreatePayload,
  DreamList,
  DreamRead,
  GraphPayload,
  PatternsResponse,
  ProviderStatus,
  ReadingResponse,
  RuntimeSettingsRead,
  RuntimeSettingsUpdate,
} from '@/lib/types'

const BASE_URL = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body && typeof body.detail === 'string' ? body.detail : response.statusText
    throw new Error(detail)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export const api = {
  listDreams: (limit = 100) => request<DreamList>(`/dreams?limit=${limit}`),
  createDream: (payload: DreamCreatePayload) =>
    request<DreamRead>('/dreams', { method: 'POST', body: JSON.stringify(payload) }),
  getDream: (id: number) => request<DreamRead>(`/dreams/${id}`),
  deleteDream: (id: number) => request<void>(`/dreams/${id}`, { method: 'DELETE' }),
  deleteAllDreams: () => request<void>('/dreams', { method: 'DELETE' }),
  reanalyze: (id: number) =>
    request<{ status: string; dream_id: string }>(`/analysis/reanalyze/${id}`, { method: 'POST' }),
  providerStatus: () => request<ProviderStatus>('/analysis/provider-status'),
  graph: (limit = 200) => request<GraphPayload>(`/analysis/graph?limit=${limit}`),
  patterns: (minCount = 2, limit = 100) =>
    request<PatternsResponse>(`/analysis/patterns?min_count=${minCount}&limit=${limit}`),
  patternsReading: (minCount = 2) =>
    request<ReadingResponse>(`/analysis/patterns/reading?min_count=${minCount}`, { method: 'POST' }),
  getSettings: () => request<RuntimeSettingsRead>('/settings'),
  updateSettings: (payload: RuntimeSettingsUpdate) =>
    request<RuntimeSettingsRead>('/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  resetSettings: () => request<RuntimeSettingsRead>('/settings', { method: 'DELETE' }),
  detectSettings: () =>
    request<RuntimeSettingsRead>('/settings/detect', { method: 'POST' }),
  listModels: () => request<{ chat: string[]; embed: string[] }>('/settings/models'),
}