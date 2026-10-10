/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false, // strict mode double-mounts effects, which opens the sim websocket twice in dev
  devIndicators: false,
  eslint: { ignoreDuringBuilds: true },
  outputFileTracingRoot: import.meta.dirname,
};
export default nextConfig;
