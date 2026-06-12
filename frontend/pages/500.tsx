import React from "react";
import { Result, Button } from "antd";
import { useRouter } from "next/router";

export default function ServerErrorPage() {
  const router = useRouter();
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "80vh" }}>
      <Result
        status="500"
        title="服务器错误"
        subTitle="服务器出现了问题，请稍后再试"
        extra={
          <Button type="primary" onClick={() => router.reload()}>
            刷新页面
          </Button>
        }
      />
    </div>
  );
}
