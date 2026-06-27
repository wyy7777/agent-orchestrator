// Type declarations for Tauri plugins (only available at runtime in desktop app)
declare module "@tauri-apps/plugin-updater" {
  interface DownloadEvent {
    event: "Started" | "Progress" | "Finished";
    data: {
      contentLength?: number;
      chunkLength?: number;
    };
  }

  interface Update {
    version: string;
    body?: string;
    date?: string;
    downloadAndInstall(onEvent?: (event: DownloadEvent) => void): Promise<void>;
  }

  export function check(): Promise<Update | null>;
}
