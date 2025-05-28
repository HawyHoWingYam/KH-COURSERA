import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  
  // Allow cross-origin requests to our API
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `http://${process.env.API_BASE_URL || 'localhost'}:${process.env.PORT || 8000}/:path*`,
      },
    ];
  }
};

export default nextConfig;