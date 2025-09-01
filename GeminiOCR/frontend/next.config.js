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

  // Note: allowedDevOrigins will be needed in future Next.js versions
  // experimental: {
  //   allowedDevOrigins: ['52.220.245.213']
  // },

  // Allow cross-origin requests to our API
  async rewrites() {
    // Use environment variable or fallback to localhost for development
    const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000';

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