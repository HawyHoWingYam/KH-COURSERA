import React from 'react';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-100">
      {/* Add your admin layout structure here */}
      <main className="flex-1">{children}</main>
    </div>
  );
} 