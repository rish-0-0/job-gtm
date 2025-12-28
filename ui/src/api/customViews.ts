import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from './client'
import type {
  CustomView,
  SaveViewRequest,
  CreateViewResponse,
} from '../types/gridState'

interface ListViewsResponse {
  views: CustomView[]
}

interface AvailableColumnsResponse {
  columns: string[]
}

export interface ViewDataResponse {
  data: Record<string, unknown>[]
  total: number
  page: number
  page_size: number
  total_pages: number
  view_name: string
  columns: string[]
}

async function fetchCustomViews(): Promise<ListViewsResponse> {
  const response = await apiClient.get<ListViewsResponse>('/views')
  return response.data
}

async function fetchCustomViewData(
  name: string,
  page: number,
  pageSize: number
): Promise<ViewDataResponse> {
  const response = await apiClient.get<ViewDataResponse>(`/views/${name}/data`, {
    params: { page, page_size: pageSize },
  })
  return response.data
}

async function fetchAvailableColumns(): Promise<AvailableColumnsResponse> {
  const response = await apiClient.get<AvailableColumnsResponse>('/views/columns')
  return response.data
}

async function createCustomView(
  request: SaveViewRequest
): Promise<CreateViewResponse> {
  const response = await apiClient.post<CreateViewResponse>('/views', request)
  return response.data
}

async function deleteCustomView(name: string): Promise<void> {
  await apiClient.delete(`/views/${name}`)
}

export function useCustomViews() {
  return useQuery({
    queryKey: ['custom-views'],
    queryFn: fetchCustomViews,
  })
}

export function useAvailableColumns() {
  return useQuery({
    queryKey: ['available-columns'],
    queryFn: fetchAvailableColumns,
  })
}

export function useCreateView() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createCustomView,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-views'] })
    },
  })
}

export function useDeleteView() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteCustomView,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-views'] })
    },
  })
}

export function useCustomViewData(name: string, page: number, pageSize: number = 50) {
  return useQuery({
    queryKey: ['custom-view-data', name, page, pageSize],
    queryFn: () => fetchCustomViewData(name, page, pageSize),
    enabled: !!name,
  })
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

async function fetchViewSalaryByLocation(
  name: string,
  limit: number = 15
): Promise<SalaryChartResponse> {
  const response = await apiClient.get<SalaryChartResponse>(`/views/${name}/charts/salary-by-location`, {
    params: { limit },
  })
  return response.data
}

export function useViewSalaryByLocation(name: string, limit: number = 15) {
  return useQuery({
    queryKey: ['view-salary-by-location', name, limit],
    queryFn: () => fetchViewSalaryByLocation(name, limit),
    enabled: !!name,
  })
}
