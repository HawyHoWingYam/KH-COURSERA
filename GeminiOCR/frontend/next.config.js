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
  
  // For Next.js 15+, use experimental config for dev origins
  experimental: {
    allowedDevOrigins: [
      'http://52.220.245.213:3000',
      'https://52.220.245.213:3000',
      'http://localhost:3000',
      'http://127.0.0.1:3000',
      'http://10.0.0.10:3000'
    ],
  },
  
  // Allow cross-origin requests to our API
  async rewrites() {
    // 在Docker环境中，使用内部服务名称
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