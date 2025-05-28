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
      {
        // Add this new rewrite rule to handle file previews
        source: '/files/:fileId/preview',
        destination: '/api/files/:fileId/preview',
      }
    ];
  }
};

export default nextConfig;