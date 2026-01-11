import { useQuery } from '@tanstack/react-query'
import apiClient from './client'
import type { RootDataResponse } from '../types'

// ==================== FILTER TYPES ====================

export interface FilterCondition {
  column: string
  operator: string
  value: any
  logic?: 'AND' | 'OR' | null
}

export interface ColumnMetadata {
  name: string
  type: 'integer' | 'numeric' | 'text' | 'boolean' | 'timestamp'
  operators: string[]
  sortable: boolean
  groupable: boolean
}

export interface ColumnsResponse {
  columns: ColumnMetadata[]
  view_name: string
  valid_logic: string[]
}

interface FetchRootDataParams {
  page: number
  pageSize: number
  sort?: string
  groupBy?: string
  filters?: FilterCondition[]
}

export interface SalaryByLocationData {
  location: string
  avgMinSalary: number
  avgMaxSalary: number
  jobCount: number
}

export interface SalaryChartResponse {
  data: SalaryByLocationData[]
  metric: string
  groupBy: string
  error?: string
}

// ==================== COLUMN METADATA ====================

async function fetchColumns(): Promise<ColumnsResponse> {
  const response = await apiClient.get<ColumnsResponse>('/root-data/columns')
  return response.data
}

export function useColumns() {
  return useQuery({
    queryKey: ['root-data-columns'],
    queryFn: fetchColumns,
    staleTime: 1000 * 60 * 60, // Cache for 1 hour - columns don't change often
  })
}

// ==================== ROOT DATA ====================

async function fetchRootData({
  page,
  pageSize,
  sort,
  groupBy,
  filters,
}: FetchRootDataParams): Promise<RootDataResponse> {
  const params: Record<string, string | number> = {
    page,
    page_size: pageSize,
  }

  if (sort) {
    params.sort = sort
  }

  if (groupBy) {
    params.group_by = groupBy
  }

  if (filters && filters.length > 0) {
    params.filters = JSON.stringify(filters)
  }

  const response = await apiClient.get<RootDataResponse>('/root-data', {
    params,
  })
  return response.data
}

export function useRootData(
  page: number,
  pageSize: number = 50,
  sort?: string,
  groupBy?: string,
  filters?: FilterCondition[]
) {
  // Create a stable key for filters
  const filtersKey = filters && filters.length > 0 ? JSON.stringify(filters) : null

  return useQuery({
    queryKey: ['root-data', page, pageSize, sort, groupBy, filtersKey],
    queryFn: () => fetchRootData({ page, pageSize, sort, groupBy, filters }),
    placeholderData: (previousData) => previousData,
  })
}

async function fetchSalaryByLocation(limit: number = 15): Promise<SalaryChartResponse> {
  const response = await apiClient.get<SalaryChartResponse>('/root-data/charts/salary-by-location', {
    params: { limit },
  })
  return response.data
}

export function useSalaryByLocation(limit: number = 15) {
  return useQuery({
    queryKey: ['salary-by-location', limit],
    queryFn: () => fetchSalaryByLocation(limit),
  })
}
