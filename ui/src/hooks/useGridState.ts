import { useState, useCallback, useMemo, RefObject } from 'react'
import { AgGridReact } from 'ag-grid-react'
import isEqual from 'lodash/isEqual'
import {
  GridViewState,
  DEFAULT_VIEW_STATE,
  SortItem,
  ALL_COLUMNS,
} from '../types/gridState'

export function useGridState(gridRef: RefObject<AgGridReact | null>) {
  const [currentState, setCurrentState] = useState<GridViewState>(DEFAULT_VIEW_STATE)

  const hasChanges = useMemo(() => {
    return !isEqual(DEFAULT_VIEW_STATE, currentState)
  }, [currentState])

  const updateColumnOrder = useCallback((newOrder: string[]) => {
    setCurrentState((prev) => ({
      ...prev,
      columnOrder: newOrder,
    }))
  }, [])

  const updateHiddenColumns = useCallback((hiddenColumns: string[]) => {
    setCurrentState((prev) => ({
      ...prev,
      hiddenColumns,
    }))
  }, [])

  const toggleColumnVisibility = useCallback((columnId: string) => {
    setCurrentState((prev) => {
      const isHidden = prev.hiddenColumns.includes(columnId)
      return {
        ...prev,
        hiddenColumns: isHidden
          ? prev.hiddenColumns.filter((c) => c !== columnId)
          : [...prev.hiddenColumns, columnId],
      }
    })
  }, [])

  const updateSorting = useCallback((sorting: SortItem[]) => {
    setCurrentState((prev) => ({
      ...prev,
      sorting,
    }))
  }, [])

  const updateGroupBy = useCallback((groupBy: string[]) => {
    setCurrentState((prev) => ({
      ...prev,
      groupBy,
    }))
  }, [])

  const toggleGroupBy = useCallback((columnId: string) => {
    setCurrentState((prev) => {
      const isGrouped = prev.groupBy.includes(columnId)
      return {
        ...prev,
        groupBy: isGrouped
          ? prev.groupBy.filter((c) => c !== columnId)
          : [...prev.groupBy, columnId],
      }
    })
  }, [])

  const getVisibleOrderedColumns = useCallback(() => {
    return currentState.columnOrder.filter(
      (col) => !currentState.hiddenColumns.includes(col)
    )
  }, [currentState.columnOrder, currentState.hiddenColumns])

  const syncFromGrid = useCallback(() => {
    if (!gridRef.current?.api) return

    const columnState = gridRef.current.api.getColumnState()
    if (!columnState) return

    const newOrder: string[] = []
    const newHidden: string[] = []
    const newSorting: SortItem[] = []

    columnState.forEach((col) => {
      if (col.colId && ALL_COLUMNS.includes(col.colId as typeof ALL_COLUMNS[number])) {
        newOrder.push(col.colId)
        if (col.hide) {
          newHidden.push(col.colId)
        }
        if (col.sort) {
          newSorting.push({
            column: col.colId,
            direction: col.sort as 'asc' | 'desc',
          })
        }
      }
    })

    // Sort by sortIndex for multi-sort order
    newSorting.sort((a, b) => {
      const aState = columnState.find((c) => c.colId === a.column)
      const bState = columnState.find((c) => c.colId === b.column)
      return (aState?.sortIndex ?? 0) - (bState?.sortIndex ?? 0)
    })

    setCurrentState((prev) => ({
      ...prev,
      columnOrder: newOrder,
      hiddenColumns: newHidden,
      sorting: newSorting,
    }))
  }, [gridRef])

  const resetToDefault = useCallback(() => {
    setCurrentState(DEFAULT_VIEW_STATE)

    if (gridRef.current?.api) {
      // Reset column order and visibility
      const defaultColumnState = ALL_COLUMNS.map((colId) => ({
        colId,
        hide: false,
        sort: null as 'asc' | 'desc' | null,
        sortIndex: null,
      }))
      gridRef.current.api.applyColumnState({
        state: defaultColumnState,
        applyOrder: true,
      })
    }
  }, [gridRef])

  const getSortParam = useCallback(() => {
    if (currentState.sorting.length === 0) return undefined
    return currentState.sorting
      .map((s) => `${s.column}:${s.direction}`)
      .join(',')
  }, [currentState.sorting])

  const getGroupByParam = useCallback(() => {
    if (currentState.groupBy.length === 0) return undefined
    return currentState.groupBy.join(',')
  }, [currentState.groupBy])

  return {
    currentState,
    hasChanges,
    updateColumnOrder,
    updateHiddenColumns,
    toggleColumnVisibility,
    updateSorting,
    updateGroupBy,
    toggleGroupBy,
    getVisibleOrderedColumns,
    syncFromGrid,
    resetToDefault,
    getSortParam,
    getGroupByParam,
  }
}
