'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

export function AWBNavigation() {
  const pathname = usePathname()

  const isActive = (path: string) => {
    return pathname === path
  }

  return (
    <div className="mb-6 flex gap-2 p-4 bg-slate-50 rounded-lg border border-slate-200">
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
    </div>
  )
}
