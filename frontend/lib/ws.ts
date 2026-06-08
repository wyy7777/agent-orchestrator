type MessageHandler = (data: Record<string, unknown>) => void;

function getWsUrl() {
  if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
  if (typeof window === "undefined") return "ws://localhost:8000/ws";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws`;
}

let ws: WebSocket | null = null;
let handlers: MessageHandler[] = [];
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function connectWebSocket(taskId?: string) {
  if (ws && ws.readyState === WebSocket.OPEN) return;

  const WS_URL = getWsUrl();
  const url = taskId ? `${WS_URL}?task_id=${taskId}` : WS_URL;
  ws = new WebSocket(url);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handlers.forEach((h) => h(data));
    } catch {}
  };

  ws.onclose = () => {
    ws = null;
    reconnectTimer = setTimeout(() => connectWebSocket(taskId), 3000);
  };

  ws.onerror = () => {
    ws?.close();
  };
}

export function disconnectWebSocket() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  if (ws) {
    ws.close();
    ws = null;
  }
}

export function onMessage(handler: MessageHandler) {
  handlers.push(handler);
  return () => {
    handlers = handlers.filter((h) => h !== handler);
  };
}
