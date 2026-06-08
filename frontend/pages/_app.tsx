import type { AppProps } from "next/app";
import { ConfigProvider, App as AntApp, theme as antTheme } from "antd";
import zhCN from "antd/locale/zh_CN";
import AppLayout from "@/components/Layout";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useState, useEffect } from "react";
import "../styles/globals.css";

export default function App({ Component, pageProps }: AppProps) {
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("darkMode");
    if (saved === "true") setDarkMode(true);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    if (!saved && mq.matches) setDarkMode(true);
  }, []);

  const toggleDark = () => {
    setDarkMode((prev) => {
      localStorage.setItem("darkMode", String(!prev));
      return !prev;
    });
  };

  return (
    <ErrorBoundary>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: darkMode ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
          token: {
            colorPrimary: "#1677ff",
            borderRadius: 8,
          },
        }}
      >
        <AntApp>
          <AppLayout darkMode={darkMode} toggleDark={toggleDark}>
            <Component {...pageProps} />
          </AppLayout>
        </AntApp>
      </ConfigProvider>
    </ErrorBoundary>
  );
}
