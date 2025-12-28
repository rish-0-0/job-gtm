export interface SortItem {
  column: string
  direction: 'asc' | 'desc'
}

export interface GridViewState {
  columnOrder: string[]
  hiddenColumns: string[]
  sorting: SortItem[]
  groupBy: string[]
}

export interface SaveViewRequest {
  name: string
  display_name: string
  description?: string
  columns: string[]
}

export interface CustomView {
  id: number
  name: string
  display_name: string
  view_name: string
  columns: string[]
  status: 'pending' | 'creating' | 'completed' | 'failed' | 'deleting'
  error_message?: string
  workflow_id?: string
  row_count?: number
  last_refreshed_at?: string
}

export interface CreateViewResponse {
  id: number
  name: string
  display_name: string
  view_name: string
  columns: string[]
  status: string
  workflow_id?: string
  message: string
}

// These must match the columns defined in RootDataTable.tsx
export const ALL_COLUMNS = [
  'id',
  'company_title',
  'job_role',
  'seniority_level_normalized',
  'min_salary_usd',
  'max_salary_usd',
  'location_city',
  'location_country',
  'is_remote',
  'employment_type_normalized',
  'company_industry',
  'company_size',
  'primary_role',
  'role_category',
  'scraper_source',
  'created_at',
] as const

export type ColumnId = (typeof ALL_COLUMNS)[number]

export const GROUPABLE_COLUMNS = [
  'company_industry',
  'seniority_level_normalized',
  'location_country',
  'is_remote',
  'employment_type_normalized',
  'primary_role',
  'role_category',
  'scraper_source',
] as const

export type GroupableColumnId = (typeof GROUPABLE_COLUMNS)[number]

export const COLUMN_LABELS: Record<ColumnId, string> = {
  id: 'ID',
  company_title: 'Company',
  job_role: 'Role',
  seniority_level_normalized: 'Seniority',
  min_salary_usd: 'Min Salary',
  max_salary_usd: 'Max Salary',
  location_city: 'City',
  location_country: 'Country',
  is_remote: 'Remote',
  employment_type_normalized: 'Type',
  company_industry: 'Industry',
  company_size: 'Size',
  primary_role: 'Primary Role',
  role_category: 'Category',
  scraper_source: 'Source',
  created_at: 'Created',
}

export const DEFAULT_VIEW_STATE: GridViewState = {
  columnOrder: [...ALL_COLUMNS],
  hiddenColumns: [],
  sorting: [],
  groupBy: [],
}
