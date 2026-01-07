import { useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import type { SalaryByLocationData } from '@/api/rootData'

interface SalaryByLocationChartProps {
  data: SalaryByLocationData[]
  isLoading?: boolean
  title?: string
  description?: string
}

const chartConfig = {
  avgMinSalary: {
    label: 'Avg Min Salary',
    color: 'hsl(217.2 91.2% 59.8%)',
  },
  avgMaxSalary: {
    label: 'Avg Max Salary',
    color: 'hsl(142.1 76.2% 36.3%)',
  },
} satisfies ChartConfig

type MetricKey = 'avgMinSalary' | 'avgMaxSalary'

export function SalaryByLocationChart({
  data,
  isLoading,
  title = 'Average Salary by Location',
  description = 'Top locations by average minimum salary',
}: SalaryByLocationChartProps) {
  const [activeMetric, setActiveMetric] = useState<MetricKey>('avgMinSalary')

  const chartData = useMemo(() => {
    if (!data?.length) return []
    // Reverse to show lowest to highest for better area chart visualization
    return [...data].reverse()
  }, [data])

  const total = useMemo(() => {
    if (!data?.length) return { avgMinSalary: 0, avgMaxSalary: 0, count: 0 }
    return {
      avgMinSalary: Math.round(
        data.reduce((acc, curr) => acc + curr.avgMinSalary, 0) / data.length
      ),
      avgMaxSalary: Math.round(
        data.reduce((acc, curr) => acc + curr.avgMaxSalary, 0) / data.length
      ),
      count: data.reduce((acc, curr) => acc + curr.jobCount, 0),
    }
  }, [data])

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(value)
  }

  if (isLoading) {
    return (
      <Card className="border-border/50 bg-card/50">
        <CardHeader className="flex flex-col items-stretch space-y-0 border-b border-border/50 p-0 sm:flex-row">
          <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5 sm:py-6">
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="px-2 sm:p-6">
          <div className="flex h-[250px] items-center justify-center">
            <span className="text-muted-foreground">Loading chart data...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!data?.length) {
    return (
      <Card className="border-border/50 bg-card/50">
        <CardHeader className="flex flex-col items-stretch space-y-0 border-b border-border/50 p-0 sm:flex-row">
          <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5 sm:py-6">
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="px-2 sm:p-6">
          <div className="flex h-[250px] items-center justify-center">
            <span className="text-muted-foreground">No salary data available</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-border/50 bg-card/50">
      <CardHeader className="flex flex-col items-stretch space-y-0 border-b border-border/50 p-0 sm:flex-row">
        <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5 sm:py-6">
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <div className="flex">
          {(['avgMinSalary', 'avgMaxSalary'] as const).map((key) => (
            <button
              key={key}
              data-active={activeMetric === key}
              className="relative z-30 flex flex-1 flex-col justify-center gap-1 border-t border-border/50 px-6 py-4 text-left even:border-l data-[active=true]:bg-muted/50 sm:border-l sm:border-t-0 sm:px-8 sm:py-6"
              onClick={() => setActiveMetric(key)}
            >
              <span className="text-xs text-muted-foreground">
                {chartConfig[key].label}
              </span>
              <span className="text-lg font-bold leading-none sm:text-3xl">
                {formatCurrency(total[key])}
              </span>
              <span className="text-xs text-muted-foreground">
                avg across {data.length} locations
              </span>
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="px-2 sm:p-6">
        <ChartContainer
          config={chartConfig}
          className="aspect-auto h-[250px] w-full"
        >
          <AreaChart
            accessibilityLayer
            data={chartData}
            margin={{
              left: 12,
              right: 12,
            }}
          >
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey="location"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={32}
              tickFormatter={(value) => {
                // Truncate long country names
                return value.length > 12 ? value.slice(0, 12) + '...' : value
              }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
            />
            <ChartTooltip
              cursor={false}
              content={
                <ChartTooltipContent
                  className="w-[200px]"
                  formatter={(value, name) => (
                    <div className="flex flex-col">
                      <span className="text-muted-foreground">
                        {chartConfig[name as keyof typeof chartConfig]?.label}
                      </span>
                      <span className="font-bold">
                        {formatCurrency(value as number)}
                      </span>
                    </div>
                  )}
                  labelFormatter={(value) => String(value)}
                />
              }
            />
            <defs>
              <linearGradient id="fillMinSalary" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor="hsl(217.2 91.2% 59.8%)"
                  stopOpacity={0.8}
                />
                <stop
                  offset="95%"
                  stopColor="hsl(217.2 91.2% 59.8%)"
                  stopOpacity={0.1}
                />
              </linearGradient>
              <linearGradient id="fillMaxSalary" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor="hsl(142.1 76.2% 36.3%)"
                  stopOpacity={0.8}
                />
                <stop
                  offset="95%"
                  stopColor="hsl(142.1 76.2% 36.3%)"
                  stopOpacity={0.1}
                />
              </linearGradient>
            </defs>
            <Area
              dataKey={activeMetric}
              type="natural"
              fill={activeMetric === 'avgMinSalary' ? 'url(#fillMinSalary)' : 'url(#fillMaxSalary)'}
              stroke={chartConfig[activeMetric].color}
              strokeWidth={2}
            />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
