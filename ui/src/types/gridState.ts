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

export const ALL_COLUMNS = [
  'id',
  'company_title',
  'job_role',
  'job_location_normalized',
  'employment_type_normalized',
  'min_salary_usd',
  'max_salary_usd',
  'seniority_level_normalized',
  'is_remote',
  'location_city',
  'location_country',
  'company_industry',
  'company_size',
  'primary_role',
  'role_category',
  'scraper_source',
  'enrichment_status',
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
  job_location_normalized: 'Location',
  employment_type_normalized: 'Employment Type',
  min_salary_usd: 'Min Salary',
  max_salary_usd: 'Max Salary',
  seniority_level_normalized: 'Seniority',
  is_remote: 'Remote',
  location_city: 'City',
  location_country: 'Country',
  company_industry: 'Industry',
  company_size: 'Company Size',
  primary_role: 'Primary Role',
  role_category: 'Role Category',
  scraper_source: 'Source',
  enrichment_status: 'Enrichment',
  created_at: 'Created At',
}

export const DEFAULT_VIEW_STATE: GridViewState = {
  columnOrder: [...ALL_COLUMNS],
  hiddenColumns: [],
  sorting: [],
  groupBy: [],
}
