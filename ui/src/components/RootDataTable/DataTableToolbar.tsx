import { RotateCcw, Save, ArrowUpDown } from 'lucide-react'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { ColumnVisibilityPanel } from './ColumnVisibilityPanel'
import { GroupByDropdown } from './GroupByDropdown'
import { COLUMN_LABELS, ColumnId, SortItem } from '../../types/gridState'

interface DataTableToolbarProps {
  hiddenColumns: string[]
  groupBy: string[]
  sorting: SortItem[]
  hasChanges: boolean
  onToggleColumn: (columnId: string) => void
  onToggleGroup: (columnId: string) => void
  onReset: () => void
  onSaveView: () => void
}

export function DataTableToolbar({
  hiddenColumns,
  groupBy,
  sorting,
  hasChanges,
  onToggleColumn,
  onToggleGroup,
  onReset,
  onSaveView,
}: DataTableToolbarProps) {
  return (
    <div className="flex items-center justify-between py-4">
      <div className="flex items-center gap-2">
        <ColumnVisibilityPanel
          hiddenColumns={hiddenColumns}
          onToggleColumn={onToggleColumn}
        />
        <GroupByDropdown
          selectedGroups={groupBy}
          onToggleGroup={onToggleGroup}
        />

        {sorting.length > 0 && (
          <div className="flex items-center gap-1 ml-2">
            <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Sort:</span>
            {sorting.map((s, i) => (
              <Badge key={s.column} variant="secondary" className="text-xs">
                {COLUMN_LABELS[s.column as ColumnId]} {s.direction === 'asc' ? '↑' : '↓'}
                {i < sorting.length - 1 && ','}
              </Badge>
            ))}
          </div>
        )}

        {groupBy.length > 0 && (
          <div className="flex items-center gap-1 ml-2">
            <span className="text-sm text-muted-foreground">Grouped:</span>
            {groupBy.map((col, i) => (
              <Badge key={col} variant="outline" className="text-xs">
                {COLUMN_LABELS[col as ColumnId]}
                {i < groupBy.length - 1 && ','}
              </Badge>
            ))}
          </div>
        )}

        {hasChanges && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            className="ml-2"
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Reset
          </Button>
        )}
      </div>

      {hasChanges && (
        <Button onClick={onSaveView}>
          <Save className="h-4 w-4 mr-2" />
          Save as View
        </Button>
      )}
    </div>
  )
}
