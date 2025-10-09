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


  // Allow cross-origin requests to our API
  async rewrites() {
    // Use Docker service name for environment-independent deployment
    const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000';

    console.log("=== next.config.js Debug ===");
    console.log("NEXT_PUBLIC_API_URL:", process.env.NEXT_PUBLIC_API_URL);
    console.log("Resolved apiHost:", apiHost);
    console.log("===========================");

    return [
      {
        source: '/api/:path*',
        destination: `${apiHost}/:path*`,
      },
      {
        source: '/files/:fileId/preview',
        destination: `${apiHost}/files/:fileId`,
      }
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