import React from "react";
import { Result, Button } from "antd";
import { useRouter } from "next/router";
import { useI18n } from "@/lib/i18n";

export default function ForbiddenPage() {
  const router = useRouter();
  const { locale } = useI18n();
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "80vh" }}>
      <Result
        status="403"
        title={locale === "zh" ? "访问被拒绝" : "Access Denied"}
        subTitle={locale === "zh" ? "您没有权限访问此页面" : "You do not have permission to access this page"}
        extra={
          <Button type="primary" onClick={() => router.push("/")}>
            {locale === "zh" ? "返回首页" : "Back to Home"}
          </Button>
        }
      />
    </div>
  );
}
