import { useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { X, Plus, Filter, Trash2 } from 'lucide-react'
import type { FilterCondition, ColumnMetadata } from '@/api/rootData'

interface FilterBuilderProps {
  columns: ColumnMetadata[]
  filters: FilterCondition[]
  onFiltersChange: (filters: FilterCondition[]) => void
  onApply: () => void
  onClear: () => void
}

// Operator labels for display
const OPERATOR_LABELS: Record<string, string> = {
  '=': 'equals',
  '!=': 'not equals',
  '<>': 'not equals',
  '>': 'greater than',
  '<': 'less than',
  '>=': 'greater or equal',
  '<=': 'less or equal',
  'LIKE': 'contains (case sensitive)',
  'ILIKE': 'contains',
  'NOT LIKE': 'not contains (case sensitive)',
  'NOT ILIKE': 'not contains',
  'IN': 'in list',
  'NOT IN': 'not in list',
  'IS NULL': 'is empty',
  'IS NOT NULL': 'is not empty',
  'BETWEEN': 'between',
}

export function FilterBuilder({
  columns,
  filters,
  onFiltersChange,
  onApply,
  onClear,
}: FilterBuilderProps) {
  const [isExpanded, setIsExpanded] = useState(filters.length > 0)

  const addFilter = useCallback(() => {
    const defaultColumn = columns[0]?.name || ''
    const defaultOperator = columns[0]?.operators[0] || '='
    const newFilter: FilterCondition = {
      column: defaultColumn,
      operator: defaultOperator,
      value: '',
      logic: filters.length > 0 ? 'AND' : null,
    }
    onFiltersChange([...filters, newFilter])
  }, [columns, filters, onFiltersChange])

  const removeFilter = useCallback((index: number) => {
    const newFilters = filters.filter((_, i) => i !== index)
    // Update logic for first filter (should be null)
    if (newFilters.length > 0 && newFilters[0].logic) {
      newFilters[0] = { ...newFilters[0], logic: null }
    }
    onFiltersChange(newFilters)
  }, [filters, onFiltersChange])

  const updateFilter = useCallback((index: number, updates: Partial<FilterCondition>) => {
    const newFilters = filters.map((f, i) => {
      if (i !== index) return f

      const updated = { ...f, ...updates }

      // If column changed, reset operator to first valid one for new column type
      if (updates.column) {
        const col = columns.find(c => c.name === updates.column)
        if (col && !col.operators.includes(updated.operator)) {
          updated.operator = col.operators[0] || '='
        }
        // Reset value when column changes
        updated.value = ''
      }

      // Clear value for IS NULL / IS NOT NULL operators
      if (updates.operator && ['IS NULL', 'IS NOT NULL'].includes(updates.operator)) {
        updated.value = null
      }

      return updated
    })
    onFiltersChange(newFilters)
  }, [filters, columns, onFiltersChange])

  const getColumnType = useCallback((columnName: string) => {
    return columns.find(c => c.name === columnName)?.type || 'text'
  }, [columns])

  const getColumnOperators = useCallback((columnName: string) => {
    return columns.find(c => c.name === columnName)?.operators || ['=']
  }, [columns])

  const renderValueInput = useCallback((filter: FilterCondition, index: number) => {
    const columnType = getColumnType(filter.column)
    const operator = filter.operator

    // No value input for IS NULL / IS NOT NULL
    if (['IS NULL', 'IS NOT NULL'].includes(operator)) {
      return <span className="text-muted-foreground text-sm italic">No value needed</span>
    }

    // Boolean type
    if (columnType === 'boolean') {
      return (
        <Select
          value={String(filter.value)}
          onValueChange={(value) => updateFilter(index, { value: value === 'true' })}
        >
          <SelectTrigger className="w-[120px]">
            <SelectValue placeholder="Select..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="true">Yes</SelectItem>
            <SelectItem value="false">No</SelectItem>
          </SelectContent>
        </Select>
      )
    }

    // BETWEEN operator needs two values
    if (operator === 'BETWEEN') {
      const values = Array.isArray(filter.value) ? filter.value : ['', '']
      return (
        <div className="flex items-center gap-2">
          <Input
            type={columnType === 'numeric' || columnType === 'integer' ? 'number' : 'text'}
            placeholder="Min"
            value={values[0] || ''}
            onChange={(e) => updateFilter(index, { value: [e.target.value, values[1]] })}
            className="w-[100px]"
          />
          <span className="text-muted-foreground">and</span>
          <Input
            type={columnType === 'numeric' || columnType === 'integer' ? 'number' : 'text'}
            placeholder="Max"
            value={values[1] || ''}
            onChange={(e) => updateFilter(index, { value: [values[0], e.target.value] })}
            className="w-[100px]"
          />
        </div>
      )
    }

    // IN / NOT IN operator needs comma-separated values
    if (['IN', 'NOT IN'].includes(operator)) {
      const displayValue = Array.isArray(filter.value) ? filter.value.join(', ') : filter.value
      return (
        <Input
          placeholder="value1, value2, value3..."
          value={displayValue || ''}
          onChange={(e) => {
            const values = e.target.value.split(',').map(v => v.trim()).filter(v => v)
            updateFilter(index, { value: values.length > 0 ? values : e.target.value })
          }}
          className="w-[200px]"
        />
      )
    }

    // Default text/number input
    return (
      <Input
        type={columnType === 'numeric' || columnType === 'integer' ? 'number' : 'text'}
        placeholder={['LIKE', 'ILIKE', 'NOT LIKE', 'NOT ILIKE'].includes(operator) ? '%value%' : 'Enter value...'}
        value={filter.value || ''}
        onChange={(e) => {
          const val = columnType === 'numeric' || columnType === 'integer'
            ? (e.target.value === '' ? '' : Number(e.target.value))
            : e.target.value
          updateFilter(index, { value: val })
        }}
        className="w-[180px]"
      />
    )
  }, [getColumnType, updateFilter])

  return (
    <Card className="border-border/50">
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4" />
            <CardTitle className="text-sm font-medium">Filters</CardTitle>
            {filters.length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {filters.length} active
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            {filters.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onClear}
                className="h-8 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-4 w-4 mr-1" />
                Clear All
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="h-8"
            >
              {isExpanded ? 'Collapse' : 'Expand'}
            </Button>
          </div>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className="pt-0 pb-4 px-4">
          <div className="space-y-3">
            {filters.map((filter, index) => (
              <div key={index} className="flex items-center gap-2 flex-wrap">
                {/* AND/OR Logic selector (not for first filter) */}
                {index > 0 && (
                  <Select
                    value={filter.logic || 'AND'}
                    onValueChange={(value) => updateFilter(index, { logic: value as 'AND' | 'OR' })}
                  >
                    <SelectTrigger className="w-[80px] h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="AND">AND</SelectItem>
                      <SelectItem value="OR">OR</SelectItem>
                    </SelectContent>
                  </Select>
                )}

                {/* Column selector */}
                <Select
                  value={filter.column}
                  onValueChange={(value) => updateFilter(index, { column: value })}
                >
                  <SelectTrigger className="w-[180px] h-8">
                    <SelectValue placeholder="Select column..." />
                  </SelectTrigger>
                  <SelectContent>
                    {columns.map((col) => (
                      <SelectItem key={col.name} value={col.name}>
                        {col.name.replace(/_/g, ' ')}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {/* Operator selector */}
                <Select
                  value={filter.operator}
                  onValueChange={(value) => updateFilter(index, { operator: value })}
                >
                  <SelectTrigger className="w-[160px] h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {getColumnOperators(filter.column).map((op) => (
                      <SelectItem key={op} value={op}>
                        {OPERATOR_LABELS[op] || op}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {/* Value input */}
                {renderValueInput(filter, index)}

                {/* Remove button */}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeFilter(index)}
                  className="h-8 w-8 text-muted-foreground hover:text-destructive"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}

            {/* Add filter and Apply buttons */}
            <div className="flex items-center gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={addFilter}
                className="h-8"
              >
                <Plus className="h-4 w-4 mr-1" />
                Add Filter
              </Button>

              {filters.length > 0 && (
                <Button
                  size="sm"
                  onClick={onApply}
                  className="h-8"
                >
                  Apply Filters
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}

export default FilterBuilder
