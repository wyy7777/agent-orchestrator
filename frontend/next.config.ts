import type { NextConfig } from "next";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  transpilePackages: ["antd", "@ant-design/icons", "@ant-design/charts"],
  reactStrictMode: true,
  // 生产构建使用静态导出（后端托管），开发模式用 rewrites 代理到后端
  ...(isDev ? {} : { output: "export" }),
  images: { unoptimized: true },
  ...(isDev
    ? {
        async rewrites() {
          return [
            { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
            { source: "/ws/:path*", destination: `${BACKEND_URL}/ws/:path*` },
          ];
        },
      }
    : {}),
};

export default nextConfig;
