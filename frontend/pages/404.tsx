import React from "react";
import { Result, Button } from "antd";
import { useRouter } from "next/router";

export default function NotFoundPage() {
  const router = useRouter();
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "80vh" }}>
      <Result
        status="404"
        title="页面未找到"
        subTitle="您访问的页面不存在或已被移除"
        extra={
          <Button type="primary" onClick={() => router.push("/")}>
            返回首页
          </Button>
        }
      />
    </div>
  );
}
