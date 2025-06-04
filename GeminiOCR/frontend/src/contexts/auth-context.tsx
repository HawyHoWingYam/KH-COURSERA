'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchApi } from '@/lib/api';

type User = {
  id: number;
  name: string;
  email: string;
  role: string;
  department_id: number | null;
};

type AuthContextType = {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (userData: any) => Promise<void>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    // Check if user is already logged in
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem('accessToken');
        if (token) {
          // Get user info using token
          const userData = await fetchApi<User>('/auth/user', {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          });
          setUser(userData);
        }
      } catch (error) {
        // Token invalid or expired, clear storage
        localStorage.removeItem('accessToken');
        localStorage.removeItem('user');
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      // Create form data for OAuth2 format
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/auth/token`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();
      
      localStorage.setItem('accessToken', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      
      setUser(data.user);
      
      // Set cookies for middleware
      document.cookie = `accessToken=${data.access_token}; path=/;`;
      document.cookie = `userRole=${data.user.role}; path=/;`;
      
      // Redirect based on role
      if (data.user.role === 'admin') {
        router.push('/admin');
      } else {
        router.push('/');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('user');
    setUser(null);
    
    // Clear cookies
    document.cookie = 'accessToken=; path=/; max-age=0';
    document.cookie = 'userRole=; path=/; max-age=0';
    
    router.push('/auth/login');
  };

  const register = async (userData: any) => {
    setIsLoading(true);
    try {
      const response = await fetchApi('/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData),
      });

      localStorage.setItem('accessToken', response.access_token);
      localStorage.setItem('user', JSON.stringify(response.user));
      
      setUser(response.user);
      
      // Set cookies for middleware
      document.cookie = `accessToken=${response.access_token}; path=/;`;
      document.cookie = `userRole=${response.user.role}; path=/;`;
      
      router.push('/');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}; 