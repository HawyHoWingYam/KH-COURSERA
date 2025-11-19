/** @type {import('next').NextConfig} */
const nextConfig = {
  // 启用standalone输出模式，用于Docker部署
  output: 'standalone',

  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    // This will allow the build to continue even with TypeScript errors
    ignoreBuildErrors: true,
  },


  // Proxy frontend '/api/*' calls to the backend.
  // Note: The backend mixes routes: most are mounted at '/', but some are under '/api' (e.g. awb, admin/usage).
  // We special‑case those first, then fall back to '/' for the rest to avoid widespread 404s.
  async rewrites() {
    // Use Docker service name for container envs or explicit public URL when provided
    const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://175.41.133.177:8000';

    console.log("=== next.config.js Debug ===");
    console.log("NEXT_PUBLIC_API_URL:", process.env.NEXT_PUBLIC_API_URL);
    console.log("Resolved apiHost:", apiHost);
    console.log("===========================");

    return [
      // Keep backend endpoints that are already under /api working
      { source: '/api/awb/:path*', destination: `${apiHost}/api/awb/:path*` },
      { source: '/api/admin/:path*', destination: `${apiHost}/api/admin/:path*` },

      // Map remaining '/api/*' calls to backend root-mounted routes (e.g., /orders, /document-types, /jobs, ...)
      { source: '/api/:path*', destination: `${apiHost}/:path*` },

      // File preview passthrough (non-API)
      { source: '/files/:fileId/preview', destination: `${apiHost}/files/:fileId` },
    ];
  },

  // Additional CORS configuration
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'Access-Control-Allow-Origin',
            value: '*',
          },
          {
            key: 'Access-Control-Allow-Methods',
            value: 'GET, POST, PUT, DELETE, OPTIONS',
          },
          {
            key: 'Access-Control-Allow-Headers',
            value: 'Content-Type, Authorization',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
