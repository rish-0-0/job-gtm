import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Textarea } from '../ui/textarea'
import { Badge } from '../ui/badge'
import {
  GridViewState,
  SaveViewRequest,
  COLUMN_LABELS,
  ColumnId,
} from '../../types/gridState'

interface SaveViewDialogProps {
  open: boolean
  onClose: () => void
  viewState: GridViewState
  onSave: (request: SaveViewRequest) => void
  isLoading?: boolean
}

export function SaveViewDialog({
  open,
  onClose,
  viewState,
  onSave,
  isLoading = false,
}: SaveViewDialogProps) {
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [nameError, setNameError] = useState<string | null>(null)

  const visibleColumns = viewState.columnOrder.filter(
    (col) => !viewState.hiddenColumns.includes(col)
  )

  const validateName = (value: string) => {
    const sanitized = value.toLowerCase().replace(/[^a-z0-9_]/g, '')
    setName(sanitized)

    if (sanitized.length < 3) {
      setNameError('Name must be at least 3 characters')
    } else if (sanitized.length > 50) {
      setNameError('Name must be at most 50 characters')
    } else if (!/^[a-z]/.test(sanitized)) {
      setNameError('Name must start with a letter')
    } else {
      setNameError(null)
    }
  }

  const handleSave = () => {
    if (nameError || name.length < 3 || displayName.length < 3) return

    onSave({
      name,
      display_name: displayName,
      description: description || undefined,
      columns: visibleColumns,
    })
  }

  const handleClose = () => {
    setName('')
    setDisplayName('')
    setDescription('')
    setNameError(null)
    onClose()
  }

  const canSave =
    name.length >= 3 &&
    displayName.length >= 3 &&
    !nameError &&
    visibleColumns.length > 0

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Save as View</DialogTitle>
          <DialogDescription>
            Create a custom materialized view with your current column configuration.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              placeholder="my_custom_view"
              value={name}
              onChange={(e) => validateName(e.target.value)}
            />
            {nameError && (
              <p className="text-sm text-destructive">{nameError}</p>
            )}
            <p className="text-xs text-muted-foreground">
              Lowercase letters, numbers, and underscores only. Must start with a letter.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="displayName">Display Name</Label>
            <Input
              id="displayName"
              placeholder="My Custom View"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description (optional)</Label>
            <Textarea
              id="description"
              placeholder="A brief description of this view..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </div>

          <div className="border rounded-lg p-4 space-y-3">
            <div>
              <h4 className="font-medium mb-2">
                Columns ({visibleColumns.length})
              </h4>
              <div className="flex flex-wrap gap-1">
                {visibleColumns.map((col) => (
                  <Badge key={col} variant="secondary" className="text-xs">
                    {COLUMN_LABELS[col as ColumnId]}
                  </Badge>
                ))}
              </div>
            </div>

            {viewState.sorting.length > 0 && (
              <div>
                <h4 className="font-medium mb-2">Sorting</h4>
                <div className="flex flex-wrap gap-1">
                  {viewState.sorting.map((s) => (
                    <Badge key={s.column} variant="outline" className="text-xs">
                      {COLUMN_LABELS[s.column as ColumnId]}{' '}
                      {s.direction === 'asc' ? '↑' : '↓'}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {viewState.groupBy.length > 0 && (
              <div>
                <h4 className="font-medium mb-2">Grouped By</h4>
                <div className="flex flex-wrap gap-1">
                  {viewState.groupBy.map((col) => (
                    <Badge key={col} variant="outline" className="text-xs">
                      {COLUMN_LABELS[col as ColumnId]}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {viewState.hiddenColumns.length > 0 && (
              <div className="text-sm text-muted-foreground">
                {viewState.hiddenColumns.length} column(s) hidden and excluded from view
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!canSave || isLoading}>
            {isLoading ? 'Creating...' : 'Create View'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
