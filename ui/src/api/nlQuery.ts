import { useMutation, useQuery } from '@tanstack/react-query'
import apiClient from './client'

// Request/Response types
export interface NLQueryRequest {
  query: string
  llm_provider?: string
  force_regenerate?: boolean
}

export interface NLQueryResponse {
  sql: string
  cache_hit: boolean
  llm_provider: string
  similarity_score?: number
  execution_count?: number
  metadata?: Record<string, any>
}

export interface ExecuteSQLRequest {
  sql: string
}

export interface ExecuteSQLResponse {
  columns: string[]
  rows: Record<string, any>[]
  row_count: number
  execution_time_ms: number
}

export interface LLMProvider {
  name: string
  available: boolean
  display_name: string
}

export interface ProvidersResponse {
  providers: LLMProvider[]
}

// Generate SQL from natural language
async function generateSQL(request: NLQueryRequest): Promise<NLQueryResponse> {
  const response = await apiClient.post<NLQueryResponse>('/nl-query/generate', request)
  return response.data
}

export function useGenerateSQL() {
  return useMutation({
    mutationFn: generateSQL,
  })
}

// Execute SQL and get results
async function executeSQL(request: ExecuteSQLRequest): Promise<ExecuteSQLResponse> {
  const response = await apiClient.post<ExecuteSQLResponse>('/nl-query/execute', request)
  return response.data
}

export function useExecuteSQL() {
  return useMutation({
    mutationFn: executeSQL,
  })
}

// Get available providers
async function getProviders(): Promise<LLMProvider[]> {
  const response = await apiClient.get<ProvidersResponse>('/nl-query/providers')
  return response.data.providers
}

export function useProviders() {
  return useQuery({
    queryKey: ['nl-query-providers'],
    queryFn: getProviders,
    staleTime: Infinity,  // Providers don't change often
  })
}
