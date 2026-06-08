import type { AppProps } from "next/app";
import { ConfigProvider, App as AntApp } from "antd";
import zhCN from "antd/locale/zh_CN";
import AppLayout from "@/components/Layout";
import "../styles/globals.css";

const theme = {
  token: {
    colorPrimary: "#1677ff",
    borderRadius: 8,
  },
};

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <AntApp>
        <AppLayout>
          <Component {...pageProps} />
        </AppLayout>
      </AntApp>
    </ConfigProvider>
  );
}
