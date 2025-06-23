/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    // This will allow the build to continue even with TypeScript errors
    ignoreBuildErrors: true,
  },
  
  // Allow cross-origin requests to our API
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `http://52.220.245.213:8000/:path*`,
      },
      {
        source: '/files/:fileId/preview',
        destination: `http://52.220.245.213:8000/files/:fileId`,
      }
    ];
  }
};

module.exports = nextConfig;