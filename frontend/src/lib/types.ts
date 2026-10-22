/** Tipos espejo de los esquemas del backend (Fase 3). */

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type EntityType = 'symbol' | 'emotion' | 'person' | 'place'

export interface DreamCreatePayload {
  text: string
  mood_on_wake?: string | null
  dreamed_at?: string | null
}

export interface DreamRead {
  id: number
  text: string
  title: string | null
  mood_on_wake: string | null
  dreamed_at: string | null
  analysis_status: AnalysisStatus
  one_line_insight: string | null
  summary: string | null
  analysis_error: string | null
  created_at: string
  analyzed_at: string | null
}

export interface DreamList {
  total: number
  items: DreamRead[]
}

export interface ProviderStatus {
  provider: string
  ok: string
  detail: string
}

export interface GraphNode {
  id: number
  title: string | null
  preview: string
  analysis_status: AnalysisStatus
  insight: string | null
  mood_on_wake: string | null
  dreamed_at: string | null
  created_at: string
}

export interface GraphEdge {
  source: number
  target: number
  similarity: number
}

export interface GraphPayload {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface Pattern {
  name: string
  type: EntityType
  dream_count: number
  last_seen_at: string | null
  exemplar_dream_id: number | null
  interpretation: string | null
}

export interface PatternsResponse {
  dreams_analyzed: number
  total: number
  patterns: Pattern[]
}

export interface ReadingResponse {
  reading: string | null
  detail: string | null
}

export type ProviderName = 'ollama' | 'openai'

export interface RuntimeSettingsRead {
  provider: ProviderName
  ollama_base_url: string
  ollama_chat_model: string
  ollama_embed_model: string
  openai_base_url: string
  openai_chat_model: string
  openai_embed_model: string
  openai_api_key_set: boolean
  source: 'runtime' | 'env'
}

export interface RuntimeSettingsUpdate {
  provider?: ProviderName | null
  ollama_base_url?: string | null
  ollama_chat_model?: string | null
  ollama_embed_model?: string | null
  openai_base_url?: string | null
  openai_chat_model?: string | null
  openai_embed_model?: string | null
  openai_api_key?: string | null
}