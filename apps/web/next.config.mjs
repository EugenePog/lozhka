/** The browser only talks to this origin; /api and /media are proxied to the public API so the session and CSRF
 *  cookies are same-site (docs 06). Set API_URL when the API is not on localhost:8010. */
const API_URL = process.env.API_URL ?? "http://localhost:8010";

/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  transpilePackages: ["@lozhka/api-client"],
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/media/:path*", destination: `${API_URL}/media/:path*` },
    ];
  },
  // the trailing-slash redirect would break POSTs through the proxy
  skipTrailingSlashRedirect: true,
};
