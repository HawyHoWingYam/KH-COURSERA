'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { awbApi, OneDriveSyncRecord } from '@/lib/api'

export default function OneDriveSyncPage() {
  const [syncHistory, setSyncHistory] = useState<OneDriveSyncRecord[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSyncing, setIsSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Form state for advanced options
  const [month, setMonth] = useState<string>('')
  const [force, setForce] = useState(false)
  const [reconcile, setReconcile] = useState(false)
  const [scanProcessed, setScanProcessed] = useState(true)

  // Fetch sync status from backend
  const fetchSyncStatus = async () => {
    try {
      const response = await awbApi.getSyncStatus(10)
      if (response.success && response.syncs) {
        setSyncHistory(response.syncs)
      }
      setError(null)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch sync status'
      setError(errorMessage)
      console.error('Error fetching sync status:', err)
    } finally {
      setIsLoading(false)
    }
  }

  // Load sync history on mount
  useEffect(() => {
    fetchSyncStatus()
  }, [])

  // Auto-refresh sync history every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchSyncStatus()
    }, 10000)

    return () => clearInterval(interval)
  }, [])

  // Trigger manual sync
  const handleTriggerSync = async () => {
    setIsSyncing(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await awbApi.triggerSync({
        month: month || undefined,
        force,
        reconcile,
        scan_processed: scanProcessed,
      })
      if (response.success) {
        setSuccess(`OneDrive sync triggered successfully! ${response.message}`)
        // Refresh sync status immediately
        setTimeout(() => {
          fetchSyncStatus()
        }, 2000)
      } else {
        setError(response.message || 'Failed to trigger sync')
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to trigger OneDrive sync'
      setError(errorMessage)
      console.error('Error triggering sync:', err)
    } finally {
      setIsSyncing(false)
    }
  }

  // Status badge component
  const StatusBadge = ({ status }: { status: string }) => {
    let bgColor = 'bg-gray-100'
    let textColor = 'text-gray-700'
    let icon = '⏳'

    if (status === 'success') {
      bgColor = 'bg-green-100'
      textColor = 'text-green-700'
      icon = '✅'
    } else if (status === 'failed' || status === 'error') {
      bgColor = 'bg-red-100'
      textColor = 'text-red-700'
      icon = '❌'
    } else if (status === 'in_progress') {
      bgColor = 'bg-blue-100'
      textColor = 'text-blue-700'
      icon = '🔄'
    }

    return (
      <span className={`inline-block ${bgColor} ${textColor} px-3 py-1 rounded-full text-sm font-medium`}>
        {icon} {status}
      </span>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <Card className="mb-6">
          <CardHeader className="space-y-2">
            <CardTitle className="text-3xl">OneDrive Sync Management</CardTitle>
            <CardDescription>
              Monitor and manage automatic OneDrive synchronization for Air Waybill files
            </CardDescription>
          </CardHeader>
        </Card>

        {/* Trigger Sync Section */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">OneDrive Sync Operations</CardTitle>
            <CardDescription>
              Trigger manual sync with optional reconciliation mode
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Error Alert */}
            {error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 mb-4">
                <strong>❌ Error:</strong> {error}
              </div>
            )}

            {/* Success Alert */}
            {success && (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 mb-4">
                <strong>✅ Success:</strong> {success}
              </div>
            )}

            {/* Trigger Sync Section */}
            <div className="border-t border-slate-200 pt-4">
              <h3 className="text-md font-semibold text-slate-900 mb-4">📡 Trigger OneDrive Sync</h3>
              <div className="space-y-3 mb-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Month (YYYY-MM)</label>
                    <input
                      type="text"
                      value={month}
                      onChange={(e) => setMonth(e.target.value)}
                      placeholder="e.g., 2025-10"
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={force}
                      onChange={(e) => setForce(e.target.checked)}
                      className="w-4 h-4 text-blue-600"
                    />
                    <span className="text-sm text-slate-700">Force rescan (ignore last sync time)</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={reconcile}
                      onChange={(e) => setReconcile(e.target.checked)}
                      className="w-4 h-4 text-blue-600"
                    />
                    <span className="text-sm text-slate-700">Reconciliation mode (filename-based matching)</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={scanProcessed}
                      onChange={(e) => setScanProcessed(e.target.checked)}
                      className="w-4 h-4 text-blue-600"
                    />
                    <span className="text-sm text-slate-700">Scan processed folder (during reconciliation)</span>
                  </label>
                </div>
              </div>
              <button
                onClick={handleTriggerSync}
                disabled={isSyncing}
                className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-slate-400 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
              >
                {isSyncing ? (
                  <>
                    <span className="inline-block animate-spin">⏳</span>
                    Syncing...
                  </>
                ) : (
                  <>
                    🔄 Trigger Sync
                  </>
                )}
              </button>
            </div>

          </CardContent>
        </Card>

        {/* Sync History Section */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Sync History</CardTitle>
            <CardDescription>
              Last 10 sync records from OneDrive to S3
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <span className="inline-block animate-spin text-2xl mr-2">⏳</span>
                <span className="text-slate-600">Loading sync history...</span>
              </div>
            ) : syncHistory.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-slate-600">No sync records found. Start by triggering a manual sync above.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50">
                      <th className="text-left px-4 py-3 font-semibold text-slate-700">Sync ID</th>
                      <th className="text-left px-4 py-3 font-semibold text-slate-700">Timestamp</th>
                      <th className="text-left px-4 py-3 font-semibold text-slate-700">Status</th>
                      <th className="text-center px-4 py-3 font-semibold text-slate-700">Files Processed</th>
                      <th className="text-center px-4 py-3 font-semibold text-slate-700">Files Failed</th>
                      <th className="text-left px-4 py-3 font-semibold text-slate-700">Error Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {syncHistory.map((record) => (
                      <tr key={record.sync_id} className="border-b border-slate-200 hover:bg-slate-50">
                        <td className="px-4 py-3 text-slate-900 font-medium">#{record.sync_id}</td>
                        <td className="px-4 py-3 text-slate-700">
                          {new Date(record.last_sync_time).toLocaleString()}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={record.sync_status} />
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className="inline-block bg-green-100 text-green-700 px-3 py-1 rounded font-medium">
                            {record.files_processed}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          {record.files_failed > 0 ? (
                            <span className="inline-block bg-red-100 text-red-700 px-3 py-1 rounded font-medium">
                              {record.files_failed}
                            </span>
                          ) : (
                            <span className="text-slate-500">0</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-slate-600 max-w-xs truncate">
                          {record.error_message ? (
                            <span className="text-red-600 font-medium">{record.error_message}</span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Info Section */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-lg">ℹ️ About OneDrive Sync</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-600 space-y-3">
            <div>
              <strong className="text-slate-900">Automatic Daily Sync:</strong>
              <p>Files are automatically synced from OneDrive folder "HYA-OCR" to S3 bucket daily at 2:00 AM (UTC+8).</p>
            </div>
            <div>
              <strong className="text-slate-900">Deduplication:</strong>
              <p>Files are tracked by their OneDrive source path to prevent duplicate processing. If the same file exists from a previous sync, it will be skipped.</p>
            </div>
            <div>
              <strong className="text-slate-900">File Organization:</strong>
              <p>Synced files are organized in S3 by month: <code className="bg-slate-100 px-2 py-1 rounded">s3://bucket/upload/onedrive/airway-bills/YYYY/MM/filename.pdf</code></p>
            </div>
            <div>
              <strong className="text-slate-900">Processing Workflow:</strong>
              <p>After sync, files are available for manual AWB monthly processing or can be automatically processed based on your configuration.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
