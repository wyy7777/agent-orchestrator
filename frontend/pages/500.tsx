import React from "react";
import { Result, Button } from "antd";
import { useRouter } from "next/router";
import { useI18n } from "@/lib/i18n";

export default function ServerErrorPage() {
  const router = useRouter();
  const { locale } = useI18n();
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "80vh" }}>
      <Result
        status="500"
        title={locale === "zh" ? "服务器错误" : "Server Error"}
        subTitle={locale === "zh" ? "服务器出现了问题，请稍后再试" : "Something went wrong on the server. Please try again later."}
        extra={
          <Button type="primary" onClick={() => router.reload()}>
            {locale === "zh" ? "刷新页面" : "Reload Page"}
          </Button>
        }
      />
    </div>
  );
}
