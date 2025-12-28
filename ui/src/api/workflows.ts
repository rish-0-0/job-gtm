import { useMutation, useQuery } from '@tanstack/react-query'
import apiClient from './client'

interface RefreshViewResponse {
  workflow_id: string
  view_name: string
  status: 'started' | 'already_running'
  message: string
}

interface WorkflowStatusResponse {
  workflow_id: string
  status: string
  result: Record<string, unknown> | null
}

interface AvailableViewsResponse {
  views: string[]
}

export async function refreshMaterializedView(viewName: string): Promise<RefreshViewResponse> {
  const response = await apiClient.post<RefreshViewResponse>('/workflows/views/refresh', {
    view_name: viewName,
  })
  return response.data
}

export async function getRefreshStatus(viewName: string): Promise<WorkflowStatusResponse> {
  const response = await apiClient.get<WorkflowStatusResponse>(
    `/workflows/views/refresh/${viewName}/status`
  )
  return response.data
}

export async function getAvailableViews(): Promise<AvailableViewsResponse> {
  const response = await apiClient.get<AvailableViewsResponse>('/workflows/views/available')
  return response.data
}

export function useAvailableViews() {
  return useQuery({
    queryKey: ['available-views'],
    queryFn: getAvailableViews,
  })
}

export function useRefreshStatus(viewName: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ['refresh-status', viewName],
    queryFn: () => getRefreshStatus(viewName),
    enabled,
    refetchInterval: (query) => {
      // Poll every 2 seconds if workflow is running
      const status = query.state.data?.status
      if (status === 'running') {
        return 2000
      }
      return false
    },
  })
}

export function useRefreshMaterializedView() {
  return useMutation({
    mutationFn: refreshMaterializedView,
  })
}
