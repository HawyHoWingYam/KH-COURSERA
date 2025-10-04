import type { NextConfig } from "next";

// Resolve backend base URL once, avoiding accidental use of the Next.js PORT (3000)
// Use Docker service name for environment-independent deployment
// Force rebuild: 2025-10-04 to clear Docker build cache
const apiBase = (process.env.NEXT_PUBLIC_API_URL || "http://backend:8000").replace(/\/$/, "");

// Debug logging for build diagnostics
console.log("=== Next.js Config Debug ===");
console.log("NEXT_PUBLIC_API_URL:", process.env.NEXT_PUBLIC_API_URL);
console.log("API_BASE_URL:", process.env.API_BASE_URL);
console.log("Resolved apiBase:", apiBase);
console.log("==========================");

const nextConfig: NextConfig = {
  async rewrites() {
    const rules = [
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

    console.log("=== Rewrites Configuration ===");
    console.log(JSON.stringify(rules, null, 2));
    console.log("=============================");

    return rules;
  },
};

export default nextConfig;
