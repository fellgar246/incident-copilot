import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static hosting is the production build. Dev keeps dynamic incident ids.
  ...(process.env.NODE_ENV === "production" ? { output: "export" as const } : {}),
  trailingSlash: true,
  reactStrictMode: true,
};

export default nextConfig;
