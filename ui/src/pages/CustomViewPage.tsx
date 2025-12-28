import { useState, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AgGridReact } from 'ag-grid-react'
import { ColDef, ValueFormatterParams } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { useCustomViewData, useViewSalaryByLocation } from '../api/customViews'
import { COLUMN_LABELS, ColumnId } from '../types/gridState'
import { SalaryByLocationChart } from '../components/charts/SalaryByLocationChart'

const PAGE_SIZE = 50

function CustomViewPage() {
  const { name } = useParams<{ name: string }>()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)

  const { data, isLoading, isError, error } = useCustomViewData(
    name ?? '',
    page,
    PAGE_SIZE
  )

  const { data: chartData, isLoading: chartLoading } = useViewSalaryByLocation(name ?? '', 15)

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
    if (!data?.columns) return []

    return data.columns.map((col) => {
      const baseCol: ColDef = {
        field: col,
        headerName: COLUMN_LABELS[col as ColumnId] || col,
        sortable: true,
        resizable: true,
        filter: true,
      }

      // Apply formatters based on column type
      if (col === 'min_salary_usd' || col === 'max_salary_usd') {
        baseCol.valueFormatter = formatCurrency
        baseCol.width = 120
      } else if (col === 'is_remote') {
        baseCol.valueFormatter = formatBoolean
        baseCol.width = 90
      } else if (col === 'created_at') {
        baseCol.valueFormatter = formatDate
        baseCol.width = 110
      } else if (col === 'id') {
        baseCol.width = 80
      } else if (col === 'company_title' || col === 'job_role') {
        baseCol.width = 180
      } else {
        baseCol.width = 120
      }

      return baseCol
    })
  }, [data?.columns, formatCurrency, formatBoolean, formatDate])

  if (!name) {
    navigate('/')
    return null
  }

  if (isError) {
    return (
      <div className="error">
        Error loading view: {error instanceof Error ? error.message : 'Unknown error'}
      </div>
    )
  }

  const totalPages = data?.total_pages ?? 0
  const total = data?.total ?? 0
  const startRecord = (page - 1) * PAGE_SIZE + 1
  const endRecord = Math.min(page * PAGE_SIZE, total)

  // Check if view has salary and location columns for chart
  const hasChartData = data?.columns?.includes('min_salary_usd') && data?.columns?.includes('location_country')

  return (
    <>
      <div className="page-header">
        <h2>{data?.view_name?.replace('mv_custom_', '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) || 'Custom View'}</h2>
      </div>

      {hasChartData && (
        <div className="chart-container">
          <SalaryByLocationChart
            data={chartData?.data ?? []}
            isLoading={chartLoading}
          />
        </div>
      )}

      <div className="table-container">
        <div className="ag-theme-alpine" style={{ height: '100%', width: '100%' }}>
          <AgGridReact
            rowData={data?.data ?? []}
            columnDefs={columnDefs}
            loading={isLoading}
            animateRows={true}
            rowSelection="multiple"
          />
        </div>
      </div>

      <div className="pagination">
        <div className="pagination-info">
          {total > 0 ? (
            <>
              Showing {startRecord.toLocaleString()} - {endRecord.toLocaleString()} of{' '}
              {total.toLocaleString()} records
            </>
          ) : (
            'No records'
          )}
        </div>
        <div className="pagination-controls">
          <button
            className="pagination-btn"
            onClick={() => setPage(1)}
            disabled={page === 1 || isLoading}
          >
            First
          </button>
          <button
            className="pagination-btn"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1 || isLoading}
          >
            Previous
          </button>
          <span style={{ padding: '8px 12px' }}>
            Page {page} of {totalPages}
          </span>
          <button
            className="pagination-btn"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages || isLoading}
          >
            Next
          </button>
          <button
            className="pagination-btn"
            onClick={() => setPage(totalPages)}
            disabled={page >= totalPages || isLoading}
          >
            Last
          </button>
        </div>
      </div>
    </>
  )
}

export default CustomViewPage
