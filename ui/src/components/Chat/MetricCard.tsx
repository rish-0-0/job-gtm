import { Card, CardContent } from '@/components/ui/card'
import { ChatMessageData } from './ChatMessage'

interface MetricCardProps {
  data: ChatMessageData
}

function formatMetricValue(value: any): string {
  if (typeof value === 'number') {
    // Format large numbers with commas
    return new Intl.NumberFormat('en-US').format(value)
  }
  return String(value)
}

function formatColumnLabel(column: string): string {
  // Convert snake_case to Title Case
  return column
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function MetricCard({ data }: MetricCardProps) {
  const column = data.columns[0]
  const value = data.rows[0][column]

  // Format value based on type
  const formattedValue = formatMetricValue(value)
  const label = formatColumnLabel(column)

  return (
    <Card className="metric-card">
      <CardContent className="flex flex-col items-center justify-center p-6">
        <span className="text-sm text-muted-foreground mb-2">{label}</span>
        <span className="text-4xl font-bold">{formattedValue}</span>
      </CardContent>
    </Card>
  )
}
