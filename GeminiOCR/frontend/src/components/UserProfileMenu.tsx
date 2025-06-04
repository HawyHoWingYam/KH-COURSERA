'use client';

import { useState, useEffect } from 'react';
import { fetchApi } from '@/lib/api';
import Link from 'next/link';

type User = {
  id: number;
  name: string;
  email: string;
  role: string;
  department_id: number | null;
};

type Department = {
  department_id: number;
  department_name: string;
};

export default function UserProfileMenu() {
  const [user, setUser] = useState<User | null>(null);
  const [department, setDepartment] = useState<string | null>(null);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  useEffect(() => {
    // Get user from localStorage
    const userStr = localStorage.getItem('user');
    if (userStr) {
      try {
        const userData = JSON.parse(userStr);
        setUser(userData);
        
        // If user has a department, fetch its name
        if (userData.department_id) {
          fetchDepartmentName(userData.department_id);
        }
      } catch (e) {
        console.error('Error parsing user data:', e);
      }
    }
  }, []);

  const fetchDepartmentName = async (departmentId: number) => {
    try {
      const departments = await fetchApi<Department[]>('/auth/departments');
      const userDept = departments.find(d => d.department_id === departmentId);
      if (userDept) {
        setDepartment(userDept.department_name);
      }
    } catch (err) {
      console.error('Error fetching department:', err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('user');
    window.location.href = '/auth/login';
  };

  const isLoggedIn = !!user;

  if (!user) return null;

  return (
    <div className="relative">
      {isLoggedIn ? (
        <button
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          className="flex items-center space-x-2 text-sm font-medium bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded-full transition-colors"
        >
          <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white font-medium">
            {user.name.charAt(0).toUpperCase()}
          </div>
          <div className="flex flex-col items-start">
            <span className="font-medium">{user.name}</span>
            <span className="text-xs text-gray-500">{department || 'No Department'}</span>
          </div>
        </button>
      ) : (
        <Link 
          href="/auth/login" 
          className="text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 px-4 py-2 rounded transition-colors"
        >
          Sign In
        </Link>
      )}

      {isMenuOpen && (
        <div className="absolute right-0 mt-2 w-48 py-2 bg-white rounded-md shadow-xl z-20">
          <div className="px-4 py-2 text-xs text-gray-500">
            Logged in as <span className="font-medium">{user.role}</span>
          </div>
          <div className="border-t border-gray-100"></div>
          
          {user.role === 'admin' && (
            <Link 
              href="/admin" 
              className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
              onClick={() => setIsMenuOpen(false)}
            >
              Admin Dashboard
            </Link>
          )}
          
          <Link 
            href="/profile" 
            className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            onClick={() => setIsMenuOpen(false)}
          >
            Profile Settings
          </Link>
          
          <button
            onClick={handleLogout}
            className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-100"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
} 