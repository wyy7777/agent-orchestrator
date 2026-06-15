import React from "react";
import { Result, Button } from "antd";
import { useRouter } from "next/router";
import { useI18n } from "@/lib/i18n";

export default function NotFoundPage() {
  const router = useRouter();
  const { locale } = useI18n();
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "80vh" }}>
      <Result
        status="404"
        title={locale === "zh" ? "页面未找到" : "Page Not Found"}
        subTitle={locale === "zh" ? "您访问的页面不存在或已被移除" : "The page you visited does not exist or has been removed"}
        extra={
          <Button type="primary" onClick={() => router.push("/")}>
            {locale === "zh" ? "返回首页" : "Back to Home"}
          </Button>
        }
      />
    </div>
  );
}
