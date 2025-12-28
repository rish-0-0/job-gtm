import { useQuery } from '@tanstack/react-query'
import apiClient from './client'
import type { RootDataResponse } from '../types'

interface FetchRootDataParams {
  page: number
  pageSize: number
  sort?: string
  groupBy?: string
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

async function fetchRootData({
  page,
  pageSize,
  sort,
  groupBy,
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

  const response = await apiClient.get<RootDataResponse>('/root-data', {
    params,
  })
  return response.data
}

export function useRootData(
  page: number,
  pageSize: number = 50,
  sort?: string,
  groupBy?: string
) {
  return useQuery({
    queryKey: ['root-data', page, pageSize, sort, groupBy],
    queryFn: () => fetchRootData({ page, pageSize, sort, groupBy }),
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
