/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    const publicApiBase = process.env.NEXT_PUBLIC_API_URL || "/api";
    const apiBase =
      process.env.INTERNAL_API_URL ||
      (publicApiBase.startsWith("http") ? publicApiBase : "http://localhost:8000/api");
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase.replace(/\/$/, "")}/:path*`
      }
    ];
  }
};

export default nextConfig;
