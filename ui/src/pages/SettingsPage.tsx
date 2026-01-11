import { RefreshCw, Database, Sparkles, Play, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'
import { useRefreshMaterializedView, useRefreshStatus, useTriggerEnrichment, useTriggerScrape } from '@/api/workflows'
import { useState, useRef, useCallback } from 'react'

const MATERIALIZED_VIEWS = [
  {
    name: 'mv_root_data',
    label: 'Root Data',
    description: 'Main view containing all completed job listings for the dashboard table',
  },
]

const DEBOUNCE_MS = 2000

function SettingsPage() {
  const { toast } = useToast()
  const refreshMutation = useRefreshMaterializedView()
  const enrichmentMutation = useTriggerEnrichment()
  const scrapeMutation = useTriggerScrape()
  const [refreshingView, setRefreshingView] = useState<string | null>(null)
  const [isEnrichmentDebounced, setIsEnrichmentDebounced] = useState(false)
  const [isScrapeDebounced, setIsScrapeDebounced] = useState(false)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const scrapeDebounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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

  const handleTriggerEnrichment = useCallback(async () => {
    if (isEnrichmentDebounced || enrichmentMutation.isPending) {
      return
    }

    // Set debounce state
    setIsEnrichmentDebounced(true)

    // Clear any existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    // Set timer to reset debounce
    debounceTimerRef.current = setTimeout(() => {
      setIsEnrichmentDebounced(false)
    }, DEBOUNCE_MS)

    try {
      const result = await enrichmentMutation.mutateAsync()

      if (result.status === 'already_running') {
        toast({
          title: 'Enrichment Already Running',
          description: result.message,
          variant: 'default',
        })
      } else {
        toast({
          title: 'Enrichment Pipeline Triggered',
          description: result.message || 'AI enrichment workflow has been started.',
          variant: 'success',
        })
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to trigger enrichment',
        variant: 'destructive',
      })
    }
  }, [isEnrichmentDebounced, enrichmentMutation, toast])

  const handleTriggerScrape = useCallback(async () => {
    if (isScrapeDebounced || scrapeMutation.isPending) {
      return
    }

    // Set debounce state
    setIsScrapeDebounced(true)

    // Clear any existing timer
    if (scrapeDebounceTimerRef.current) {
      clearTimeout(scrapeDebounceTimerRef.current)
    }

    // Set timer to reset debounce
    scrapeDebounceTimerRef.current = setTimeout(() => {
      setIsScrapeDebounced(false)
    }, DEBOUNCE_MS)

    try {
      const result = await scrapeMutation.mutateAsync()

      toast({
        title: 'Scraping Pipeline Triggered',
        description: `Workflow started with ID: ${result.workflow_id}`,
        variant: 'success',
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to trigger scraping pipeline',
        variant: 'destructive',
      })
    }
  }, [isScrapeDebounced, scrapeMutation, toast])

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
            <CardTitle className="flex items-center gap-2 text-card-foreground">
              <Search className="h-5 w-5" />
              Scraping Pipeline
            </CardTitle>
            <CardDescription>
              Trigger the scraping pipeline to collect new job listings from all configured sources.
              This runs all scrapers (Dice, SimplyHired, ZipRecruiter, etc.) to find new jobs.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50 border border-border">
              <div>
                <h4 className="font-medium text-foreground">Scrape All Sources</h4>
                <p className="text-sm text-muted-foreground">
                  Run all configured scrapers to collect new job listings from job boards.
                </p>
              </div>
              <Button
                onClick={handleTriggerScrape}
                disabled={scrapeMutation.isPending || isScrapeDebounced}
                variant="default"
                size="sm"
              >
                <Play className="h-4 w-4 mr-2" />
                {scrapeMutation.isPending ? 'Triggering...' : 'Trigger Scraping'}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-card-foreground">
              <Sparkles className="h-5 w-5" />
              AI Enrichment Pipeline
            </CardTitle>
            <CardDescription>
              Trigger the AI enrichment pipeline to process pending job listings.
              The pipeline uses Ollama to extract and normalize job data.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50 border border-border">
              <div>
                <h4 className="font-medium text-foreground">Enrichment Workflow</h4>
                <p className="text-sm text-muted-foreground">
                  Process scraped jobs through AI to extract skills, normalize locations, detect scams, and more.
                </p>
              </div>
              <Button
                onClick={handleTriggerEnrichment}
                disabled={enrichmentMutation.isPending || isEnrichmentDebounced}
                variant="default"
                size="sm"
              >
                <Play className="h-4 w-4 mr-2" />
                {enrichmentMutation.isPending ? 'Triggering...' : 'Trigger Enrichment'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}

export default SettingsPage
