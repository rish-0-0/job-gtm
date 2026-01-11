import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  CheckCircle2,
  AlertTriangle,
  Loader,
  RefreshCw,
  BarChart3,
  DollarSign,
} from 'lucide-react';
import axios from 'axios';
import { useToast } from '@/hooks/use-toast';

interface DataQualityStatus {
  total_rows: number;
  rows_with_null_locations: number;
  rows_with_pipe_separated_values: number;
  rows_with_none_values: number;
  null_location_percentage: number;
  pipe_separated_percentage: number;
  data_quality_score: number;
}

interface CleanupResponse {
  success: boolean;
  message: string;
  workflow_id: string;
  status: string;
  steps: string[];
  instructions: string;
  timestamp: string;
}

interface CleanupHistoryEntry {
  hour: string;
  rows_updated: number;
  last_update: string;
}

interface SalaryStats {
  total_with_salary: number;
  already_normalized: number;
  needs_normalization: number;
  normalization_percentage: number;
  currency_breakdown: Array<{
    currency: string;
    total_count: number;
    normalized_count: number;
    needs_normalization: number;
  }>;
  average_salaries_usd: Array<{
    currency: string;
    avg_min_usd: number;
    avg_max_usd: number;
    count: number;
  }>;
  timestamp: string;
}

interface SalaryNormalizationResponse {
  success: boolean;
  message: string;
  workflow_id: string;
  status: string;
  description: string;
  timestamp: string;
}

// Use relative path which goes through vite proxy
const API_BASE = '/api/data-cleanup';

export const DataCleanup: React.FC = () => {
  const { toast } = useToast();
  const [status, setStatus] = useState<DataQualityStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [isDryRun, setIsDryRun] = useState<boolean | null>(null);
  const [cleanupResult, setCleanupResult] = useState<CleanupResponse | null>(null);
  const [history, setHistory] = useState<CleanupHistoryEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Salary normalization state
  const [salaryStats, setSalaryStats] = useState<SalaryStats | null>(null);
  const [normalizingSalaries, setNormalizingSalaries] = useState(false);
  const [salaryNormalizationResult, setSalaryNormalizationResult] = useState<SalaryNormalizationResponse | null>(null);

  useEffect(() => {
    fetchDataQualityStatus();
    fetchCleanupHistory();
    fetchSalaryStats();
  }, []);

  const fetchDataQualityStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get<DataQualityStatus>(`${API_BASE}/status`, {
        timeout: 5000,
      });
      setStatus(response.data);
    } catch (err) {
      const errorMsg = axios.isAxiosError(err) ? err.message : String(err);
      const message = `Could not connect to API: ${errorMsg}. Make sure the API server is running (command: cd api && python -m uvicorn app.main:app --reload)`;
      setError(message);
      console.error('Error fetching status:', err);
      // Set a dummy status so the UI still renders
      setStatus({
        total_rows: 0,
        rows_with_null_locations: 0,
        rows_with_pipe_separated_values: 0,
        rows_with_none_values: 0,
        null_location_percentage: 0,
        pipe_separated_percentage: 0,
        data_quality_score: 0,
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchCleanupHistory = async () => {
    try {
      const response = await axios.get(`${API_BASE}/cleanup-history`, {
        timeout: 5000,
      });
      setHistory(response.data.cleanup_history || []);
    } catch (err) {
      console.error('Error fetching history:', err);
      setHistory([]);
    }
  };

  const fetchSalaryStats = async () => {
    try {
      const response = await axios.get<SalaryStats>(`${API_BASE}/salary-stats`, {
        timeout: 5000,
      });
      setSalaryStats(response.data);
    } catch (err) {
      console.error('Error fetching salary stats:', err);
    }
  };

  const normalizeSalaries = async () => {
    setNormalizingSalaries(true);
    setSalaryNormalizationResult(null);

    try {
      const response = await axios.post<SalaryNormalizationResponse>(`${API_BASE}/normalize-salaries`);

      setSalaryNormalizationResult(response.data);

      // Show success toast
      toast({
        title: 'Salary Normalization Started',
        description: response.data.message,
        variant: 'default',
      });

      // Refresh stats after normalization
      await fetchSalaryStats();
      await fetchDataQualityStatus();
    } catch (err) {
      const message = axios.isAxiosError(err)
        ? err.response?.data?.detail || err.message
        : 'Salary normalization failed';

      // Show error toast
      toast({
        title: 'Error',
        description: message,
        variant: 'destructive',
      });

      console.error('Error normalizing salaries:', err);
    } finally {
      setNormalizingSalaries(false);
    }
  };

  const runCleanup = async (dryRun: boolean = false) => {
    setRunning(true);
    setIsDryRun(dryRun);
    setError(null);
    setCleanupResult(null);

    try {
      const response = await axios.post<CleanupResponse>(`${API_BASE}/cleanup-and-refresh`, {
        include_whitespace_trim: true,
        include_pipe_separation: true,
        include_null_standardization: true,
        dry_run: dryRun,
      });

      setCleanupResult(response.data);

      // Show success toast
      toast({
        title: dryRun ? 'Dry Run Started' : 'Cleanup Workflow Started',
        description: response.data.message,
        variant: 'default',
      });

      // Refresh status after cleanup
      await fetchDataQualityStatus();
      await fetchCleanupHistory();
    } catch (err) {
      const message = axios.isAxiosError(err)
        ? err.response?.data?.detail || err.message
        : 'Cleanup failed';
      setError(message);

      // Show error toast
      toast({
        title: 'Error',
        description: message,
        variant: 'destructive',
      });

      console.error('Error running cleanup:', err);
    } finally {
      setRunning(false);
      setIsDryRun(null);
    }
  };

  const getQualityBadge = () => {
    if (!status) return null;
    const score = status.data_quality_score;

    if (score >= 95) {
      return <span className="px-3 py-1 rounded-full text-sm font-semibold text-white bg-green-500">Excellent</span>;
    } else if (score >= 80) {
      return <span className="px-3 py-1 rounded-full text-sm font-semibold text-white bg-blue-500">Good</span>;
    } else if (score >= 60) {
      return <span className="px-3 py-1 rounded-full text-sm font-semibold text-white bg-yellow-500">Fair</span>;
    } else {
      return <span className="px-3 py-1 rounded-full text-sm font-semibold text-white bg-red-500">Poor</span>;
    }
  };

  const formatNumber = (num: number) => {
    return num.toLocaleString();
  };

  return (
    <>
      <div className="page-header">
        <h2>Data Quality & Cleanup</h2>
      </div>

      <div className="w-full max-w-6xl space-y-6">

        {/* API Connection Error */}
        {error && (
          <div className="p-4 border border-red-300 bg-red-50 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="font-semibold text-red-900">Connection Error</div>
                <div className="text-red-700 text-sm mt-1">{error}</div>
                <button
                  onClick={fetchDataQualityStatus}
                  className="mt-2 px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Data Quality Status */}
        <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Data Quality Status</CardTitle>
              <CardDescription>Current state of data in golden job listings</CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchDataQualityStatus}
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 p-4 border border-red-500 bg-red-50 rounded-lg flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-red-900">Error</div>
                <div className="text-red-700 text-sm">{error}</div>
              </div>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader className="w-8 h-8 animate-spin text-blue-500" />
            </div>
          ) : status ? (
            <div className="space-y-6">
              {/* Quality Score */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold">Data Quality Score</span>
                  {getQualityBadge()}
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div
                    className={`h-3 rounded-full transition-all ${
                      status.data_quality_score >= 95
                        ? 'bg-green-500'
                        : status.data_quality_score >= 80
                        ? 'bg-blue-500'
                        : status.data_quality_score >= 60
                        ? 'bg-yellow-500'
                        : 'bg-red-500'
                    }`}
                    style={{ width: `${status.data_quality_score}%` }}
                  />
                </div>
                <div className="text-sm text-gray-600">
                  {status.data_quality_score.toFixed(1)}% quality
                </div>
              </div>

              {/* Statistics */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm font-medium text-gray-600">Total Rows</div>
                  <div className="text-2xl font-bold mt-1">{formatNumber(status.total_rows)}</div>
                </div>

                <div className="bg-red-50 p-4 rounded-lg border border-red-200">
                  <div className="text-sm font-medium text-red-600">Null Locations</div>
                  <div className="text-2xl font-bold mt-1 text-red-700">
                    {formatNumber(status.rows_with_null_locations)}
                  </div>
                  <div className="text-xs text-red-600 mt-1">
                    {status.null_location_percentage.toFixed(1)}%
                  </div>
                </div>

                <div className="bg-yellow-50 p-4 rounded-lg border border-yellow-200">
                  <div className="text-sm font-medium text-yellow-600">Pipe-Separated Values</div>
                  <div className="text-2xl font-bold mt-1 text-yellow-700">
                    {formatNumber(status.rows_with_pipe_separated_values)}
                  </div>
                  <div className="text-xs text-yellow-600 mt-1">
                    {status.pipe_separated_percentage.toFixed(1)}%
                  </div>
                </div>

                <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
                  <div className="text-sm font-medium text-orange-600">'None' Values</div>
                  <div className="text-2xl font-bold mt-1 text-orange-700">
                    {formatNumber(status.rows_with_none_values)}
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Cleanup Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Run Cleanup</CardTitle>
          <CardDescription>
            Execute data cleanup operations and refresh materialized views
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {cleanupResult && (
            <div className="p-4 border border-green-500 bg-green-50 rounded-lg">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="font-semibold text-green-900">Cleanup Workflow Started</div>
                  <div className="text-green-800 text-sm mt-2">
                    <p>{cleanupResult.message}</p>
                    <div className="mt-2">
                      <div className="mb-2">
                        <span className="font-semibold">Workflow ID:</span>{' '}
                        <code className="text-xs bg-green-100 px-2 py-1 rounded">{cleanupResult.workflow_id}</code>
                      </div>
                      <div>
                        <span className="font-semibold">Steps:</span>
                        <ul className="list-disc list-inside mt-1 space-y-1">
                          {cleanupResult.steps.map((step, idx) => (
                            <li key={idx}>{step}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="font-semibold text-blue-900 mb-2">Cleanup Operations</h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>✓ Standardize NULL values (None, NONE, N/A, etc.)</li>
              <li>✓ Fix pipe-separated values (a|b|c → a)</li>
              <li>✓ Trim excess whitespace from all fields</li>
              <li>✓ Refresh materialized views automatically</li>
            </ul>
          </div>

          <div className="flex gap-3">
            <Button
              onClick={() => runCleanup(true)}
              variant="outline"
              disabled={running}
              className="flex-1"
            >
              {running && isDryRun === true ? (
                <>
                  <Loader className="w-4 h-4 mr-2 animate-spin" />
                  Running Dry Run...
                </>
              ) : (
                <>
                  <BarChart3 className="w-4 h-4 mr-2" />
                  Dry Run
                </>
              )}
            </Button>
            <Button
              onClick={() => runCleanup(false)}
              disabled={running}
              className="flex-1"
              variant="destructive"
            >
              {running && isDryRun === false ? (
                <>
                  <Loader className="w-4 h-4 mr-2 animate-spin" />
                  Running Cleanup...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Run Cleanup
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Salary Normalization */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="w-5 h-5" />
            Salary Normalization
          </CardTitle>
          <CardDescription>
            Convert salaries from various currencies (INR, EUR, GBP, etc.) to USD
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {salaryNormalizationResult && (
            <div className="p-4 border border-green-500 bg-green-50 rounded-lg">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="font-semibold text-green-900">{salaryNormalizationResult.message}</div>
                  <div className="text-green-800 text-sm mt-2">
                    <p>{salaryNormalizationResult.description}</p>
                    <div className="mt-2">
                      <span className="font-semibold">Workflow ID:</span>{' '}
                      <code className="text-xs bg-green-100 px-2 py-1 rounded">{salaryNormalizationResult.workflow_id}</code>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {salaryStats && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                <div className="text-sm font-medium text-blue-600">Total with Salary</div>
                <div className="text-2xl font-bold mt-1 text-blue-700">
                  {formatNumber(salaryStats.total_with_salary)}
                </div>
              </div>

              <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                <div className="text-sm font-medium text-green-600">Already Normalized</div>
                <div className="text-2xl font-bold mt-1 text-green-700">
                  {formatNumber(salaryStats.already_normalized)}
                </div>
                <div className="text-xs text-green-600 mt-1">
                  {salaryStats.normalization_percentage.toFixed(1)}%
                </div>
              </div>

              <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
                <div className="text-sm font-medium text-orange-600">Needs Normalization</div>
                <div className="text-2xl font-bold mt-1 text-orange-700">
                  {formatNumber(salaryStats.needs_normalization)}
                </div>
              </div>
            </div>
          )}

          {salaryStats && salaryStats.currency_breakdown.length > 0 && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold text-gray-900 mb-3">Currency Breakdown</h3>
              <div className="space-y-2">
                {salaryStats.currency_breakdown.map((curr, idx) => (
                  <div key={idx} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-700">{curr.currency}</span>
                      <span className="text-gray-500">({curr.total_count} total)</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-green-600">
                        {curr.normalized_count} normalized
                      </span>
                      {curr.needs_normalization > 0 && (
                        <span className="text-orange-600">
                          {curr.needs_normalization} pending
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {salaryStats && salaryStats.average_salaries_usd.length > 0 && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold text-gray-900 mb-3">Average Salaries (USD)</h3>
              <div className="space-y-2">
                {salaryStats.average_salaries_usd.map((curr, idx) => (
                  <div key={idx} className="flex items-center justify-between text-sm">
                    <span className="font-medium text-gray-700">{curr.currency}</span>
                    <div className="text-gray-600">
                      ${formatNumber(Math.round(curr.avg_min_usd))} - ${formatNumber(Math.round(curr.avg_max_usd))}
                      <span className="text-xs text-gray-500 ml-2">({curr.count} jobs)</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="font-semibold text-blue-900 mb-2">What This Does</h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>✓ Detects currency from salary data or job location</li>
              <li>✓ <strong>Indian salaries:</strong> Updates both raw (monthly×12) and USD fields (÷80)</li>
              <li>✓ Converts other currencies (EUR, GBP, CAD, AUD, SGD) to USD</li>
              <li>✓ Idempotent - won't re-convert already normalized salaries</li>
              <li>✓ Refreshes materialized views automatically</li>
            </ul>
          </div>

          <Button
            onClick={normalizeSalaries}
            disabled={normalizingSalaries || (salaryStats?.needs_normalization === 0)}
            className="w-full"
            variant="default"
          >
            {normalizingSalaries ? (
              <>
                <Loader className="w-4 h-4 mr-2 animate-spin" />
                Normalizing Salaries...
              </>
            ) : (
              <>
                <DollarSign className="w-4 h-4 mr-2" />
                Normalize Salaries to USD
                {salaryStats && salaryStats.needs_normalization > 0 &&
                  ` (${salaryStats.needs_normalization} pending)`}
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      {history.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Cleanup Activity</CardTitle>
            <CardDescription>Last 24 hours of cleanup operations</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {history.map((entry, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                  <div>
                    <div className="font-medium">
                      {new Date(entry.hour).toLocaleString()}
                    </div>
                    <div className="text-sm text-gray-600">
                      {formatNumber(entry.rows_updated)} rows updated
                    </div>
                  </div>
                  <CheckCircle2 className="w-5 h-5 text-green-500" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* API Reference */}
      <Card>
        <CardHeader>
          <CardTitle>API Reference</CardTitle>
          <CardDescription>Available endpoints for data cleanup operations</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4 text-sm">
            <div>
              <div className="font-mono text-blue-600 font-semibold">
                GET /api/data-cleanup/status
              </div>
              <div className="text-gray-600 ml-4 mt-1">
                Get current data quality status
              </div>
            </div>

            <div>
              <div className="font-mono text-green-600 font-semibold">
                POST /api/data-cleanup/cleanup-and-refresh
              </div>
              <div className="text-gray-600 ml-4 mt-1">
                Start Temporal workflow: verify indexes → repair if needed → cleanup data → refresh views
              </div>
            </div>

            <div>
              <div className="font-mono text-blue-600 font-semibold">
                GET /api/data-cleanup/workflow-status/{'{workflow_id}'}
              </div>
              <div className="text-gray-600 ml-4 mt-1">
                Get status of a cleanup workflow (returns workflow status and step results)
              </div>
            </div>

            <div>
              <div className="font-mono text-blue-600 font-semibold">
                GET /api/data-cleanup/status
              </div>
              <div className="text-gray-600 ml-4 mt-1">
                Get current data quality metrics
              </div>
            </div>

            <div>
              <div className="font-mono text-blue-600 font-semibold">
                GET /api/data-cleanup/cleanup-history
              </div>
              <div className="text-gray-600 ml-4 mt-1">
                Get history of recent cleanup operations (last 24 hours)
              </div>
            </div>

            <div>
              <div className="font-mono text-blue-600 font-semibold">
                POST /api/data-cleanup/check-index-health
              </div>
              <div className="text-gray-600 ml-4 mt-1">
                Check database index health status
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      </div>
    </>
  );
};
