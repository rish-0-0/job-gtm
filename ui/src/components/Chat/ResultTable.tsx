import { useRef, useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatMessageData } from './ChatMessage'

interface ResultTableProps {
  data: ChatMessageData
}

function formatColumnHeader(column: string): string {
  // Convert snake_case to Title Case
  return column
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function getValueFormatter(column: string) {
  // Currency formatting
  if (column.includes('salary') || column.includes('usd')) {
    return (params: any) => {
      if (params.value == null) return ''
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
      }).format(params.value)
    }
  }

  // Boolean formatting
  if (column.startsWith('is_') || column.startsWith('has_')) {
    return (params: any) => {
      if (params.value == null) return ''
      return params.value ? 'Yes' : 'No'
    }
  }

  // Date formatting
  if (column.includes('_at') || column.includes('date')) {
    return (params: any) => {
      if (!params.value) return ''
      return new Date(params.value).toLocaleString()
    }
  }

  return undefined
}

export function ResultTable({ data }: ResultTableProps) {
  const gridRef = useRef<AgGridReact>(null)

  // Generate column definitions dynamically
  const columnDefs = useMemo(() => {
    return data.columns.map(col => ({
      field: col,
      headerName: formatColumnHeader(col),
      sortable: true,
      resizable: true,
      valueFormatter: getValueFormatter(col),
    }))
  }, [data.columns])

  const handleExport = () => {
    if (gridRef.current?.api) {
      gridRef.current.api.exportDataAsCsv({
        fileName: `query-results-${Date.now()}.csv`,
      })
    }
  }

  return (
    <div className="result-table-container">
      <div className="result-table-header">
        <span className="text-sm text-muted-foreground">
          {data.rowCount} {data.rowCount === 1 ? 'row' : 'rows'}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={handleExport}
          className="ml-auto"
        >
          <Download className="w-4 h-4 mr-2" />
          Export CSV
        </Button>
      </div>

      <div className="ag-theme-alpine" style={{ height: 400, width: '100%' }}>
        <AgGridReact
          ref={gridRef}
          columnDefs={columnDefs}
          rowData={data.rows}
          pagination={data.rowCount > 50}
          paginationPageSize={50}
          domLayout="normal"
        />
      </div>
    </div>
  )
}
