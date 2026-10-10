/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false, // strict mode double-mounts effects, which opens the sim websocket twice in dev
  devIndicators: false,
  eslint: { ignoreDuringBuilds: true },
  outputFileTracingRoot: import.meta.dirname,
  // Static snapshot for GitHub Pages: `STATIC_EXPORT=1 NEXT_PUBLIC_BASE_PATH=/healthhacks26 NEXT_PUBLIC_STATIC_SNAPSHOT=1 pnpm build`
  ...(process.env.STATIC_EXPORT
    ? { output: "export", basePath: process.env.NEXT_PUBLIC_BASE_PATH || "", trailingSlash: true, images: { unoptimized: true } }
    : {}),
};
export default nextConfig;
