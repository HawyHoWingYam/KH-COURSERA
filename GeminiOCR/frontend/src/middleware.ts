import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get('accessToken')?.value;
  
  console.log("Middleware checking path:", pathname);
  console.log("Token exists:", !!token);
  
  // Allow public routes
  if (
    pathname.startsWith('/auth') || 
    pathname.startsWith('/_next') || 
    pathname.startsWith('/favicon.ico')
  ) {
    return NextResponse.next();
  }
  
  // Check if the user is logged in
  if (!token) {
    const url = new URL('/auth/login', request.url);
    url.searchParams.set('from', pathname);
    return NextResponse.redirect(url);
  }
  
  // Admin route protection
  if (pathname.startsWith('/admin')) {
    // In a real app, you'd verify the token and check if the user has admin role
    // For simplicity, we're just checking if there's a role cookie
    const userRole = request.cookies.get('userRole')?.value;
    if (userRole !== 'admin') {
      return NextResponse.redirect(new URL('/', request.url));
    }
  }
  
  return NextResponse.next();
}

export const config = {
  // Temporarily disable middleware to debug
  matcher: ['/disabled-for-now'],
}; 