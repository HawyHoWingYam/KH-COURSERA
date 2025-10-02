import type { NextConfig } from "next";

// Resolve backend base URL once, avoiding accidental use of the Next.js PORT (3000)
// Use Docker service name for environment-independent deployment
const apiBase = (process.env.NEXT_PUBLIC_API_URL || "http://backend:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        // Proxy API calls to the FastAPI backend
        source: "/api/:path*",
        destination: `${apiBase}/:path*`,
      },
      {
        // File previews route (kept for clarity; proxies through /api rule above)
        source: "/files/:fileId/preview",
        destination: "/api/files/:fileId/preview",
      },
    ];
  },
};

export default nextConfig;
