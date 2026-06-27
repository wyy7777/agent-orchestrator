// Agent Orchestrator — PWA Service Worker
// 提供离线缓存支持，优先使用 Cache API 缓存静态资源

const CACHE_NAME = "agent-orch-v1";

// 需要预缓存的资源（首次访问时缓存）
const PRECACHE_URLS = [
  "/",
  "/favicon.ico",
  "/favicon.png",
  "/manifest.json",
];

// 安装阶段：预缓存关键资源
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS);
    })
  );
  self.skipWaiting();
});

// 激活阶段：清理旧缓存
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// 拦截请求：网络优先，缓存兜底
self.addEventListener("fetch", (event) => {
  // 只处理 GET 请求
  if (event.request.method !== "GET") return;

  // API 请求不使用缓存
  if (event.request.url.includes("/api/")) return;

  // WebSocket 不缓存
  if (event.request.url.includes("/ws")) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // 缓存成功的响应
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return response;
      })
      .catch(() => {
        // 网络不可用时从缓存返回
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          // 对于导航请求，返回首页（SPA 支持）
          if (event.request.mode === "navigate") {
            return caches.match("/");
          }
          return new Response("离线", { status: 503 });
        });
      })
  );
});
