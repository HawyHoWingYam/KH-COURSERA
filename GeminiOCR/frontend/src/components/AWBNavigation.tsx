'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

export function AWBNavigation() {
  const pathname = usePathname()

  const isActive = (path: string) => {
    if (path === '/awb/sync') return pathname === '/awb/sync'
    if (path === '/awb/monthly') return pathname === '/awb/monthly'
    if (path === '/batch-jobs') return pathname.startsWith('/batch-jobs')
    return false
  }

  return (
    <div className="mb-6 flex gap-2 p-4 bg-slate-50 rounded-lg border border-slate-200">
      <Link
        href="/awb/sync"
        className={`px-4 py-2 rounded-lg transition-all font-medium ${
          isActive('/awb/sync')
            ? 'bg-green-600 text-white shadow-md'
            : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
        }`}
      >
        📁 同步管理
      </Link>

      <Link
        href="/awb/monthly"
        className={`px-4 py-2 rounded-lg transition-all font-medium ${
          isActive('/awb/monthly')
            ? 'bg-purple-600 text-white shadow-md'
            : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
        }`}
      >
        📄 月度處理
      </Link>

      <Link
        href="/batch-jobs"
        className={`px-4 py-2 rounded-lg transition-all font-medium ${
          isActive('/batch-jobs')
            ? 'bg-slate-600 text-white shadow-md'
            : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
        }`}
      >
        📋 批次任務
      </Link>
    </div>
  )
}
