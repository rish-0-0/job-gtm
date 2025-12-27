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

async function fetchCustomViews(): Promise<ListViewsResponse> {
  const response = await apiClient.get<ListViewsResponse>('/views')
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
