import { useMemo, useCallback, forwardRef } from 'react'
import { AgGridReact } from 'ag-grid-react'
import {
  ColDef,
  ValueFormatterParams,
  ColumnMovedEvent,
  SortChangedEvent,
  ColumnVisibleEvent,
} from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { COLUMN_LABELS, ColumnId } from '../../types/gridState'

interface RootDataTableProps {
  data: Record<string, unknown>[]
  loading: boolean
  columns?: string[]
  grouped?: boolean
  onColumnMoved?: (event: ColumnMovedEvent) => void
  onSortChanged?: (event: SortChangedEvent) => void
  onColumnVisibilityChanged?: (event: ColumnVisibleEvent) => void
}

// Default columns when not grouped
const DEFAULT_COLUMNS = [
  'id', 'company_title', 'job_role', 'seniority_level_normalized',
  'min_salary_usd', 'max_salary_usd', 'location_city', 'location_country',
  'is_remote', 'employment_type_normalized', 'company_industry', 'company_size',
  'primary_role', 'role_category', 'scraper_source', 'created_at',
]

// Column width configurations
const COLUMN_WIDTHS: Record<string, number> = {
  id: 80,
  company_title: 180,
  job_role: 200,
  seniority_level_normalized: 120,
  min_salary_usd: 120,
  max_salary_usd: 120,
  location_city: 120,
  location_country: 100,
  is_remote: 90,
  employment_type_normalized: 100,
  company_industry: 140,
  company_size: 100,
  primary_role: 140,
  role_category: 120,
  scraper_source: 100,
  created_at: 110,
}

const RootDataTable = forwardRef<AgGridReact, RootDataTableProps>(
  function RootDataTable(
    { data, loading, columns, grouped = false, onColumnMoved, onSortChanged, onColumnVisibilityChanged },
    ref
  ) {
  const formatCurrency = useCallback((params: ValueFormatterParams) => {
    if (params.value == null) return '-'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(params.value)
  }, [])

  const formatBoolean = useCallback((params: ValueFormatterParams) => {
    if (params.value == null) return '-'
    return params.value ? 'Yes' : 'No'
  }, [])

  const formatDate = useCallback((params: ValueFormatterParams) => {
    if (!params.value) return '-'
    return new Date(params.value).toLocaleDateString()
  }, [])

  const columnDefs: ColDef[] = useMemo(() => {
    const cols = columns ?? DEFAULT_COLUMNS

    return cols.map((col) => {
      const baseCol: ColDef = {
        field: col,
        headerName: COLUMN_LABELS[col as ColumnId] || col,
        width: COLUMN_WIDTHS[col] || 120,
        sortable: !grouped, // Disable sorting when grouped (server handles it)
        resizable: true,
        filter: !grouped,
      }

      // Apply formatters based on column type
      if (col === 'min_salary_usd' || col === 'max_salary_usd') {
        baseCol.valueFormatter = formatCurrency
      } else if (col === 'is_remote') {
        baseCol.valueFormatter = formatBoolean
      } else if (col === 'created_at') {
        baseCol.valueFormatter = formatDate
      }

      return baseCol
    })
  }, [columns, grouped, formatCurrency, formatBoolean, formatDate])

  const defaultColDef: ColDef = useMemo(
    () => ({
      sortable: !grouped,
      resizable: true,
      filter: !grouped,
    }),
    [grouped]
  )

  return (
    <div className="ag-theme-alpine" style={{ height: '100%', width: '100%' }}>
      <AgGridReact
        ref={ref}
        rowData={data}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        loading={loading}
        animateRows={true}
        rowSelection={grouped ? undefined : 'multiple'}
        suppressDragLeaveHidesColumns={!grouped}
        onColumnMoved={grouped ? undefined : onColumnMoved}
        onSortChanged={grouped ? undefined : onSortChanged}
        onColumnVisible={grouped ? undefined : onColumnVisibilityChanged}
      />
    </div>
  )
  }
)

export default RootDataTable
