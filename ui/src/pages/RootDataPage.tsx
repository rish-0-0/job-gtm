import { useState, useRef, useCallback } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { useRootData, useSalaryByLocation, useColumns } from '../api/rootData'
import type { FilterCondition } from '../api/rootData'
import { useCreateView } from '../api/customViews'
import RootDataTable from '../components/RootDataTable'
import { DataTableToolbar } from '../components/RootDataTable/DataTableToolbar'
import { SaveViewDialog } from '../components/RootDataTable/SaveViewDialog'
import { FilterBuilder } from '../components/FilterBuilder'
import { SalaryByLocationChart } from '../components/charts/SalaryByLocationChart'
import { useGridState } from '../hooks/useGridState'
import { useToast } from '../hooks/use-toast'
import type { SaveViewRequest } from '../types/gridState'

const PAGE_SIZE = 50

function RootDataPage() {
  const [page, setPage] = useState(1)
  const [saveDialogOpen, setSaveDialogOpen] = useState(false)
  const [filters, setFilters] = useState<FilterCondition[]>([])
  const [appliedFilters, setAppliedFilters] = useState<FilterCondition[]>([])
  const gridRef = useRef<AgGridReact>(null)
  const { toast } = useToast()

  const {
    currentState,
    hasChanges,
    toggleColumnVisibility,
    toggleGroupBy,
    syncFromGrid,
    resetToDefault,
    getSortParam,
    getGroupByParam,
  } = useGridState(gridRef)

  const sortParam = getSortParam()
  const groupByParam = getGroupByParam()

  // Fetch column metadata for filter builder
  const { data: columnsData } = useColumns()

  const { data, isLoading, isError, error } = useRootData(
    page,
    PAGE_SIZE,
    sortParam,
    groupByParam,
    appliedFilters.length > 0 ? appliedFilters : undefined
  )

  const { data: chartData, isLoading: chartLoading } = useSalaryByLocation(15)

  const createViewMutation = useCreateView()

  const handleColumnMoved = useCallback(() => {
    syncFromGrid()
  }, [syncFromGrid])

  const handleSortChanged = useCallback(() => {
    syncFromGrid()
    setPage(1)
  }, [syncFromGrid])

  const handleColumnVisibilityChanged = useCallback(() => {
    syncFromGrid()
  }, [syncFromGrid])

  const handleToggleColumn = useCallback(
    (columnId: string) => {
      toggleColumnVisibility(columnId)
      if (gridRef.current?.api) {
        gridRef.current.api.setColumnsVisible([columnId], currentState.hiddenColumns.includes(columnId))
      }
    },
    [toggleColumnVisibility, currentState.hiddenColumns]
  )

  const handleToggleGroup = useCallback(
    (columnId: string) => {
      toggleGroupBy(columnId)
      setPage(1)
    },
    [toggleGroupBy]
  )

  const handleReset = useCallback(() => {
    resetToDefault()
    setFilters([])
    setAppliedFilters([])
    setPage(1)
  }, [resetToDefault])

  const handleFiltersChange = useCallback((newFilters: FilterCondition[]) => {
    setFilters(newFilters)
  }, [])

  const handleApplyFilters = useCallback(() => {
    setAppliedFilters(filters)
    setPage(1)
    if (filters.length > 0) {
      toast({
        title: 'Filters applied',
        description: `${filters.length} filter${filters.length > 1 ? 's' : ''} applied to the data.`,
      })
    }
  }, [filters, toast])

  const handleClearFilters = useCallback(() => {
    setFilters([])
    setAppliedFilters([])
    setPage(1)
    toast({
      title: 'Filters cleared',
      description: 'All filters have been removed.',
    })
  }, [toast])

  const handleSaveView = useCallback(
    async (request: SaveViewRequest) => {
      try {
        await createViewMutation.mutateAsync(request)
        setSaveDialogOpen(false)
        toast({
          title: 'View created',
          description: `"${request.display_name}" is being created. This may take a moment.`,
        })
      } catch (err) {
        toast({
          title: 'Error',
          description: err instanceof Error ? err.message : 'Failed to create view',
          variant: 'destructive',
        })
      }
    },
    [createViewMutation, toast]
  )

  if (isError) {
    return (
      <div className="error">
        Error loading data: {error instanceof Error ? error.message : 'Unknown error'}
      </div>
    )
  }

  const totalPages = data?.total_pages ?? 0
  const total = data?.total ?? 0
  const startRecord = (page - 1) * PAGE_SIZE + 1
  const endRecord = Math.min(page * PAGE_SIZE, total)

  return (
    <>
      <div className="page-header">
        <h2>Root Data</h2>
      </div>

      <div className="chart-container">
        <SalaryByLocationChart
          data={chartData?.data ?? []}
          isLoading={chartLoading}
        />
      </div>

      {columnsData?.columns && (
        <div className="filter-container" style={{ marginBottom: '1rem' }}>
          <FilterBuilder
            columns={columnsData.columns}
            filters={filters}
            onFiltersChange={handleFiltersChange}
            onApply={handleApplyFilters}
            onClear={handleClearFilters}
          />
        </div>
      )}

      <DataTableToolbar
        hiddenColumns={currentState.hiddenColumns}
        groupBy={currentState.groupBy}
        sorting={currentState.sorting}
        hasChanges={hasChanges}
        onToggleColumn={handleToggleColumn}
        onToggleGroup={handleToggleGroup}
        onReset={handleReset}
        onSaveView={() => setSaveDialogOpen(true)}
      />

      <div className="table-container">
        <RootDataTable
          ref={gridRef}
          data={data?.data ?? []}
          loading={isLoading}
          columns={data?.columns}
          grouped={data?.grouped ?? false}
          onColumnMoved={handleColumnMoved}
          onSortChanged={handleSortChanged}
          onColumnVisibilityChanged={handleColumnVisibilityChanged}
        />
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

      <SaveViewDialog
        open={saveDialogOpen}
        onClose={() => setSaveDialogOpen(false)}
        viewState={currentState}
        onSave={handleSaveView}
        isLoading={createViewMutation.isPending}
      />
    </>
  )
}

export default RootDataPage
