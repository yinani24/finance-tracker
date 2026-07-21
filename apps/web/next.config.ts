import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow Next dev to serve assets/HMR to a tunnel origin (ngrok/Cloudflare) used
  // for testing Plaid OAuth banks locally over HTTPS. Without this, Next dev rejects
  // the tunnel host as "Unauthorized" and the client never hydrates. Comma-separated.
  // Inactive unless DEV_TUNNEL_HOSTS is set.
  allowedDevOrigins: (process.env.DEV_TUNNEL_HOSTS || "")
    .split(",")
    .map((h) => h.trim())
    .filter(Boolean),
  // When the app is served over HTTPS through a tunnel, the browser can't call the
  // http://localhost API directly (mixed content). Set NEXT_PUBLIC_API_URL=/_api to
  // route API calls same-origin; Next proxies them to the backend server-side.
  // Inactive unless the app requests /_api paths.
  async rewrites() {
    const backend = process.env.API_PROXY_TARGET || "http://localhost:8000";
    return [{ source: "/_api/:path*", destination: `${backend}/:path*` }];
  },
  // The card-related surfaces (Explore, Recommendations) were consolidated under
  // the /cards section. Redirect the old top-level routes so bookmarks and any
  // stale links keep working. Temporary (307) to keep the move reversible.
  async redirects() {
    return [
      { source: "/explore", destination: "/cards/explore", permanent: false },
      {
        source: "/explore/:cardId",
        destination: "/cards/explore/:cardId",
        permanent: false,
      },
      {
        source: "/recommendations",
        destination: "/cards/recommendations",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
