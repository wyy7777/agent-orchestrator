"""OpenTelemetry 可观测性配置。

支持 OTLP 导出（兼容 Jaeger、Zipkin、Grafana Tempo 等后端）。
通过环境变量控制：

    OTEL_ENABLED=true               # 启用 OpenTelemetry（默认 false）
    OTEL_SERVICE_NAME=agent-orch    # 服务名
    OTEL_EXPORTER_OTLP_ENDPOINT=    # OTLP 导出地址（如 http://jaeger:4318）
    OTEL_TRACES_SAMPLER_RATIO=0.1   # 采样率（默认 10%）
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# 环境变量配置
OTEL_ENABLED = os.environ.get("OTEL_ENABLED", "").lower() in ("true", "1", "yes")


def setup_opentelemetry() -> bool:
    """初始化 OpenTelemetry SDK。返回是否成功启用。"""
    if not OTEL_ENABLED:
        logger.info("OpenTelemetry 未启用（设置 OTEL_ENABLED=true 启用）")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        service_name = os.environ.get("OTEL_SERVICE_NAME", "agent-orch")
        sampler_ratio = float(os.environ.get("OTEL_TRACES_SAMPLER_RATIO", "0.1"))
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        enable_console = os.environ.get("OTEL_CONSOLE_EXPORTER", "").lower() in ("true", "1")

        # 资源属性
        resource = Resource.create({
            "service.name": service_name,
            "service.version": "1.3.0",
            "telemetry.sdk.language": "python",
        })

        # TracerProvider
        tracer_provider = TracerProvider(
            resource=resource,
        )

        # OTLP 导出器（推送到 Jaeger / Tempo 等后端）
        if otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP Span 导出器已配置: {otlp_endpoint}")

        # 控制台导出器（调试用）
        if enable_console:
            tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.info("控制台 Span 导出器已启用")

        # 设置全局 TracerProvider
        trace.set_tracer_provider(tracer_provider)

        logger.info(
            f"OpenTelemetry 已启用 (service={service_name}, "
            f"sampler_ratio={sampler_ratio}, "
            f"otlp={otlp_endpoint or 'disabled'}, "
            f"console={enable_console})"
        )
        return True

    except ImportError as e:
        logger.warning(f"OpenTelemetry 依赖未安装，跳过: {e}")
        return False
    except Exception as e:
        logger.warning(f"OpenTelemetry 初始化失败: {e}")
        return False


def instrument_fastapi(app):
    """为 FastAPI 应用添加自动插桩。"""
    if not OTEL_ENABLED:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI 自动插桩已启用")
    except Exception as e:
        logger.warning(f"FastAPI 插桩失败: {e}")


def instrument_httpx():
    """为 httpx 客户端添加自动插桩。"""
    if not OTEL_ENABLED:
        return
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("httpx 自动插桩已启用")
    except Exception as e:
        logger.warning(f"httpx 插桩失败: {e}")
