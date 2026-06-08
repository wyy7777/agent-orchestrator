import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["antd", "@ant-design/icons", "@ant-design/charts"],
  reactStrictMode: true,
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
