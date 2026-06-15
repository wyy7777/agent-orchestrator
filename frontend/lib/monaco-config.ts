/**
 * Monaco Editor CDN 配置。
 * 
 * @monaco-editor/react 默认从 cdn.jsdelivr.net 加载 Monaco 核心（~20MB），
 * 在中国大陆此 CDN 经常被墙或极慢，导致编辑器永久 loading。
 * 
 * 此文件配置使用国内可访问的 CDN 镜像。
 */
import { loader } from "@monaco-editor/react";

// 优先使用 bootcdn（国内稳定），unpkg 镜像备用
loader.config({
  paths: {
    vs: "https://cdn.bootcdn.net/ajax/libs/monaco-editor/0.50.0/min/vs",
  },
});

export {};
