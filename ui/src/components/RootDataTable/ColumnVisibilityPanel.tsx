import { Columns } from 'lucide-react'
import { Button } from '../ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu'
import { ALL_COLUMNS, COLUMN_LABELS, ColumnId } from '../../types/gridState'

interface ColumnVisibilityPanelProps {
  hiddenColumns: string[]
  onToggleColumn: (columnId: string) => void
}

export function ColumnVisibilityPanel({
  hiddenColumns,
  onToggleColumn,
}: ColumnVisibilityPanelProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <Columns className="h-4 w-4 mr-2" />
          Columns
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56 max-h-80 overflow-y-auto">
        <DropdownMenuLabel>Toggle Columns</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {ALL_COLUMNS.map((colId) => (
          <DropdownMenuCheckboxItem
            key={colId}
            checked={!hiddenColumns.includes(colId)}
            onCheckedChange={() => onToggleColumn(colId)}
            disabled={colId === 'id'}
          >
            {COLUMN_LABELS[colId as ColumnId]}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
