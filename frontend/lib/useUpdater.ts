import { useState, useEffect, useCallback } from "react";

export interface UpdateInfo {
  version: string;
  body: string;
  date: string;
}

export interface UpdaterState {
  checking: boolean;
  updateAvailable: boolean;
  update: UpdateInfo | null;
  downloadProgress: number; // 0-100
  downloading: boolean;
  error: string | null;
}

// 检测是否在 Tauri 环境
function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function useUpdater() {
  const [state, setState] = useState<UpdaterState>({
    checking: false,
    updateAvailable: false,
    update: null,
    downloadProgress: 0,
    downloading: false,
    error: null,
  });

  const checkForUpdates = useCallback(async () => {
    if (!isTauri()) {
      setState((s) => ({ ...s, error: "非桌面环境，无法检查更新" }));
      return;
    }

    setState((s) => ({ ...s, checking: true, error: null }));

    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check();

      if (update) {
        setState((s) => ({
          ...s,
          checking: false,
          updateAvailable: true,
          update: {
            version: update.version,
            body: update.body || "暂无更新日志",
            date: update.date || "",
          },
        }));
      } else {
        setState((s) => ({
          ...s,
          checking: false,
          updateAvailable: false,
          update: null,
        }));
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      // 网络错误或 GitHub 未配置时静默处理
      setState((s) => ({
        ...s,
        checking: false,
        error: msg,
      }));
    }
  }, []);

  const installUpdate = useCallback(async () => {
    if (!isTauri()) return;

    setState((s) => ({ ...s, downloading: true, downloadProgress: 0, error: null }));

    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check();

      if (!update) {
        setState((s) => ({ ...s, downloading: false, error: "未找到可用更新" }));
        return;
      }

      // 下载并安装
      let downloaded = 0;
      let contentLength = 0;

      await update.downloadAndInstall((event) => {
        switch (event.event) {
          case "Started":
            contentLength = event.data.contentLength || 0;
            break;
          case "Progress":
            downloaded += event.data.chunkLength || 0;
            if (contentLength > 0) {
              const pct = Math.round((downloaded / contentLength) * 100);
              setState((s) => ({ ...s, downloadProgress: pct }));
            }
            break;
          case "Finished":
            setState((s) => ({ ...s, downloadProgress: 100 }));
            break;
        }
      });

      // 安装完成，应用会自动重启
      setState((s) => ({ ...s, downloading: false }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setState((s) => ({
        ...s,
        downloading: false,
        downloadProgress: 0,
        error: msg,
      }));
    }
  }, []);

  // 启动时静默检查一次
  useEffect(() => {
    if (isTauri()) {
      // 延迟 3 秒检查，避免影响启动速度
      const timer = setTimeout(() => {
        checkForUpdates();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [checkForUpdates]);

  return {
    ...state,
    isTauri: isTauri(),
    checkForUpdates,
    installUpdate,
  };
}
