import { RefreshCw, Database } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'
import { useRefreshMaterializedView, useRefreshStatus } from '@/api/workflows'
import { useState } from 'react'

const MATERIALIZED_VIEWS = [
  {
    name: 'mv_root_data',
    label: 'Root Data',
    description: 'Main view containing all completed job listings for the dashboard table',
  },
]

function SettingsPage() {
  const { toast } = useToast()
  const refreshMutation = useRefreshMaterializedView()
  const [refreshingView, setRefreshingView] = useState<string | null>(null)

  const { data: statusData } = useRefreshStatus(
    refreshingView || 'mv_root_data',
    !!refreshingView
  )

  const handleRefresh = async (viewName: string) => {
    setRefreshingView(viewName)

    try {
      const result = await refreshMutation.mutateAsync(viewName)

      if (result.status === 'already_running') {
        toast({
          title: 'Refresh Already Running',
          description: result.message,
          variant: 'default',
        })
      } else {
        toast({
          title: 'Refresh Started',
          description: result.message,
          variant: 'success',
        })
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to start refresh',
        variant: 'destructive',
      })
      setRefreshingView(null)
    }
  }

  // Clear refreshingView when workflow completes
  if (statusData?.status === 'completed' && refreshingView) {
    toast({
      title: 'Refresh Complete',
      description: `Successfully refreshed ${refreshingView}`,
      variant: 'success',
    })
    setRefreshingView(null)
  }

  const isRefreshing = (viewName: string) => {
    return refreshingView === viewName && statusData?.status === 'running'
  }

  return (
    <>
      <div className="page-header">
        <h2>Settings</h2>
      </div>

      <div className="space-y-6">
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-card-foreground">
              <Database className="h-5 w-5" />
              Materialized Views
            </CardTitle>
            <CardDescription>
              Refresh materialized views to update the dashboard with latest data.
              Views are automatically refreshed periodically, but you can trigger a manual refresh here.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {MATERIALIZED_VIEWS.map((view) => (
                <div
                  key={view.name}
                  className="flex items-center justify-between p-4 rounded-lg bg-muted/50 border border-border"
                >
                  <div>
                    <h4 className="font-medium text-foreground">{view.label}</h4>
                    <p className="text-sm text-muted-foreground">{view.description}</p>
                    <code className="text-xs text-muted-foreground mt-1 block">
                      {view.name}
                    </code>
                  </div>
                  <Button
                    onClick={() => handleRefresh(view.name)}
                    disabled={refreshMutation.isPending || isRefreshing(view.name)}
                    variant="outline"
                    size="sm"
                  >
                    <RefreshCw
                      className={`h-4 w-4 mr-2 ${isRefreshing(view.name) ? 'animate-spin' : ''}`}
                    />
                    {isRefreshing(view.name) ? 'Refreshing...' : 'Refresh'}
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-card-foreground">Workflows</CardTitle>
            <CardDescription>
              Coming soon: View and manage running Temporal workflows.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              This section will show active workflows, their status, and allow you to monitor
              long-running processes like enrichment and scraping jobs.
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  )
}

export default SettingsPage
