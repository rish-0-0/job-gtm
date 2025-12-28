import { Layers } from 'lucide-react'
import { Button } from '../ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu'
import {
  GROUPABLE_COLUMNS,
  COLUMN_LABELS,
  ColumnId,
} from '../../types/gridState'

interface GroupByDropdownProps {
  selectedGroups: string[]
  onToggleGroup: (columnId: string) => void
}

export function GroupByDropdown({
  selectedGroups,
  onToggleGroup,
}: GroupByDropdownProps) {
  const hasGroups = selectedGroups.length > 0

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant={hasGroups ? 'default' : 'outline'}
          size="sm"
        >
          <Layers className="h-4 w-4 mr-2" />
          Group By
          {hasGroups && (
            <span className="ml-1 rounded-full bg-primary-foreground px-1.5 text-xs text-primary">
              {selectedGroups.length}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuLabel>Group By Column</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {GROUPABLE_COLUMNS.map((colId) => (
          <DropdownMenuCheckboxItem
            key={colId}
            checked={selectedGroups.includes(colId)}
            onCheckedChange={() => onToggleGroup(colId)}
          >
            {COLUMN_LABELS[colId as ColumnId]}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
