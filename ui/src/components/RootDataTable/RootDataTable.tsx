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
import type { RootDataRow } from '../../types'

interface RootDataTableProps {
  data: RootDataRow[]
  loading: boolean
  onColumnMoved?: (event: ColumnMovedEvent) => void
  onSortChanged?: (event: SortChangedEvent) => void
  onColumnVisibilityChanged?: (event: ColumnVisibleEvent) => void
}

const RootDataTable = forwardRef<AgGridReact, RootDataTableProps>(
  function RootDataTable(
    { data, loading, onColumnMoved, onSortChanged, onColumnVisibilityChanged },
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

  const columnDefs: ColDef<RootDataRow>[] = useMemo(
    () => [
      { field: 'id', headerName: 'ID', width: 80 },
      { field: 'company_title', headerName: 'Company', width: 180 },
      { field: 'job_role', headerName: 'Role', width: 200 },
      { field: 'seniority_level_normalized', headerName: 'Seniority', width: 120 },
      {
        field: 'min_salary_usd',
        headerName: 'Min Salary',
        width: 120,
        valueFormatter: formatCurrency,
      },
      {
        field: 'max_salary_usd',
        headerName: 'Max Salary',
        width: 120,
        valueFormatter: formatCurrency,
      },
      { field: 'location_city', headerName: 'City', width: 120 },
      { field: 'location_country', headerName: 'Country', width: 100 },
      {
        field: 'is_remote',
        headerName: 'Remote',
        width: 90,
        valueFormatter: formatBoolean,
      },
      { field: 'employment_type_normalized', headerName: 'Type', width: 100 },
      { field: 'company_industry', headerName: 'Industry', width: 140 },
      { field: 'company_size', headerName: 'Size', width: 100 },
      { field: 'primary_role', headerName: 'Primary Role', width: 140 },
      { field: 'role_category', headerName: 'Category', width: 120 },
      { field: 'scraper_source', headerName: 'Source', width: 100 },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 110,
        valueFormatter: formatDate,
      },
    ],
    [formatCurrency, formatBoolean, formatDate]
  )

  const defaultColDef: ColDef = useMemo(
    () => ({
      sortable: true,
      resizable: true,
      filter: true,
    }),
    []
  )

  return (
    <div className="ag-theme-alpine" style={{ height: '100%', width: '100%' }}>
      <AgGridReact<RootDataRow>
        ref={ref}
        rowData={data}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        loading={loading}
        animateRows={true}
        rowSelection="multiple"
        suppressDragLeaveHidesColumns={true}
        onColumnMoved={onColumnMoved}
        onSortChanged={onSortChanged}
        onColumnVisible={onColumnVisibilityChanged}
      />
    </div>
  )
  }
)

export default RootDataTable
