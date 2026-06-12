import React from "react";
import { Result, Button } from "antd";
import { useRouter } from "next/router";

export default function ForbiddenPage() {
  const router = useRouter();
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "80vh" }}>
      <Result
        status="403"
        title="访问被拒绝"
        subTitle="您没有权限访问此页面"
        extra={
          <Button type="primary" onClick={() => router.push("/")}>
            返回首页
          </Button>
        }
      />
    </div>
  );
}
