export interface RootDataRow {
  id: number
  company_title: string | null
  job_role: string | null
  job_location_normalized: string | null
  employment_type_normalized: string | null
  min_salary_usd: number | null
  max_salary_usd: number | null
  seniority_level_normalized: string | null
  is_remote: boolean | null
  location_city: string | null
  location_country: string | null
  company_industry: string | null
  company_size: string | null
  primary_role: string | null
  role_category: string | null
  scraper_source: string | null
  enrichment_status: string | null
  created_at: string | null
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type RootDataResponse = PaginatedResponse<RootDataRow>
