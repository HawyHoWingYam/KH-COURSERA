import type { NextConfig } from "next";

// Resolve backend base URL once, avoiding accidental use of the Next.js PORT (3000)
// Use Docker service name for environment-independent deployment
// Force rebuild: 2025-10-04 to clear Docker build cache
const apiBase = (process.env.NEXT_PUBLIC_API_URL || "http://175.41.133.177:8000").replace(/\/$/, "");

// Debug logging for build diagnostics
console.log("=== Next.js Config Debug ===");
console.log("NEXT_PUBLIC_API_URL:", process.env.NEXT_PUBLIC_API_URL);
console.log("API_BASE_URL:", process.env.API_BASE_URL);
console.log("Resolved apiBase:", apiBase);
console.log("==========================");

const nextConfig: NextConfig = {
  // 启用standalone输出模式，用于Docker部署
  output: 'standalone',

  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },

  // Proxy frontend '/api/*' calls to the backend, preserving existing '/api' namespaces used by the backend.
  async rewrites() {
    const rules = [
      // Keep backend endpoints that are already under /api working
      { source: "/api/awb/:path*", destination: `${apiBase}/api/awb/:path*` },
      { source: "/api/admin/:path*", destination: `${apiBase}/api/admin/:path*` },

      // Map remaining '/api/*' calls to backend root-mounted routes
      { source: "/api/:path*", destination: `${apiBase}/:path*` },

      // File preview passthrough (non-API)
      { source: "/files/:fileId/preview", destination: `${apiBase}/files/:fileId` },
    ];

    console.log("=== Rewrites Configuration ===");
    console.log(JSON.stringify(rules, null, 2));
    console.log("=============================");

    return rules;
  },

  // Add redirects for reorganized routes
  async redirects() {
    return [
      // Move OneDrive Sync under Admin
      {
        source: "/awb/sync",
        destination: "/admin/awb/sync",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
