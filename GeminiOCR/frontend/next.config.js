/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    // This will allow the build to continue even with TypeScript errors
    ignoreBuildErrors: true,
  },
  
  // Configure allowed dev origins for cross-origin requests
  allowedDevOrigins: [
    'http://52.220.245.213:3000',
    'https://52.220.245.213:3000',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://10.0.0.10:3000'
  ],
  
  // Allow cross-origin requests to our API
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `http://localhost:8000/:path*`,
      },
      {
        source: '/files/:fileId/preview',
        destination: `http://localhost:8000/files/:fileId`,
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