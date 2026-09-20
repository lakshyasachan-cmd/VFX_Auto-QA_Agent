/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Required for Docker multi-stage build: generates a self-contained
  // Node.js server in .next/standalone without needing node_modules at runtime.
  output: 'standalone',
};

module.exports = nextConfig;
