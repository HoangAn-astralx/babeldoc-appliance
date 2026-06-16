/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    // Required for react-pdf / pdfjs-dist (avoids canvas node module error)
    config.resolve.alias.canvas = false;
    return config;
  },
  async rewrites() {
    const gateway = process.env.GATEWAY_URL || "http://127.0.0.1:8088";
    return [
      { source: "/api/:path*", destination: `${gateway}/api/:path*` },
    ];
  },
};

module.exports = nextConfig;
