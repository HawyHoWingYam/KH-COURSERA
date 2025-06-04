'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export function useAuthCheck() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    // Check if token exists
    const token = localStorage.getItem('accessToken');
    const user = localStorage.getItem('user');
    
    if (!token || !user) {
      // No token or user, redirect to login
      router.push('/auth/login');
      setIsAuthenticated(false);
    } else {
      // Token exists, validate it (optional)
      setIsAuthenticated(true);
    }
    
    setIsLoading(false);
  }, [router]);

  return { isAuthenticated, isLoading };
} 