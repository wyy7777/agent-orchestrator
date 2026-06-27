type MessageHandler = (data: Record<string, unknown>) => void;

function getWsUrl() {
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/ws`;
  }
  return "ws://127.0.0.1:8000/ws";
}

let ws: WebSocket | null = null;
let handlers: MessageHandler[] = [];
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectDelay = 1000;
let currentTaskId: string | undefined;
let _connected = false;

export function isConnected() {
  return _connected;
}

export function connectWebSocket(taskId?: string) {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  currentTaskId = taskId;

  const WS_URL = getWsUrl();
  const params = new URLSearchParams();
  if (taskId) params.set("task_id", taskId);

  // 附加 JWT token 用于 WebSocket 认证
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  if (token) params.set("token", token);

  const qs = params.toString();
  const url = qs ? `${WS_URL}?${qs}` : WS_URL;
  ws = new WebSocket(url);

  ws.onopen = () => {
    _connected = true;
    reconnectDelay = 1000; // 重置退避
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handlers.forEach((h) => h(data));
    } catch {}
  };

  ws.onclose = () => {
    _connected = false;
    ws = null;
    // 指数退避重连，最大 30 秒
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
      connectWebSocket(currentTaskId);
    }, reconnectDelay);
  };

  ws.onerror = () => {
    ws?.close();
  };
}

export function disconnectWebSocket() {
  currentTaskId = undefined;
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = null;
  if (ws) {
    ws.close();
    ws = null;
  }
  _connected = false;
}

export function onMessage(handler: MessageHandler) {
  handlers.push(handler);
  return () => {
    handlers = handlers.filter((h) => h !== handler);
  };
}
