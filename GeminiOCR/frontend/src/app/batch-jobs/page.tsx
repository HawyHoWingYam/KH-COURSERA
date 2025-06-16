'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function BatchJobsIndex() {
  const router = useRouter();
  
  useEffect(() => {
    // Redirect to jobs page with batch jobs filter
    router.push('/jobs?view=batch');
  }, [router]);

  return (
    <div className="flex justify-center items-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
    </div>
  );
} 