import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  
  // Allow cross-origin requests to our API
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ];
  }
};

export default nextConfig;