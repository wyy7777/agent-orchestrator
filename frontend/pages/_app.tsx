import type { AppProps } from "next/app";
import { ConfigProvider, App as AntApp, theme as antTheme } from "antd";
import zhCN from "antd/locale/zh_CN";
import enUS from "antd/locale/en_US";
import AppLayout from "@/components/Layout";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useState, useEffect, useCallback } from "react";
import { I18nContext, t, type Locale } from "@/lib/i18n";
import "../styles/globals.css";

export default function App({ Component, pageProps }: AppProps) {
  const [darkMode, setDarkMode] = useState(false);
  const [locale, setLocale] = useState<Locale>("zh");

  useEffect(() => {
    const savedDark = localStorage.getItem("darkMode");
    if (savedDark === "true") setDarkMode(true);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    if (!savedDark && mq.matches) setDarkMode(true);

    const savedLocale = localStorage.getItem("locale") as Locale;
    if (savedLocale === "en" || savedLocale === "zh") setLocale(savedLocale);
  }, []);

  const toggleDark = () => {
    setDarkMode((prev) => {
      localStorage.setItem("darkMode", String(!prev));
      return !prev;
    });
  };

  const handleSetLocale = useCallback((newLocale: Locale) => {
    setLocale(newLocale);
    localStorage.setItem("locale", newLocale);
  }, []);

  const translate = useCallback((key: string) => t(locale, key), [locale]);

  const antLocale = locale === "en" ? enUS : zhCN;

  return (
    <ErrorBoundary>
      <I18nContext.Provider value={{ locale, t: translate, setLocale: handleSetLocale }}>
        <ConfigProvider
          locale={antLocale}
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
      </I18nContext.Provider>
    </ErrorBoundary>
  );
}
