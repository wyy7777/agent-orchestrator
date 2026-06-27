"""日志配置：控制台 + 文件旋转 + JSON 格式 + 噪声抑制。"""
import json
import logging
import logging.handlers
import time
from datetime import UTC, datetime
from pathlib import Path


class DeduplicationFilter(logging.Filter):
    """日志去重过滤器：相同消息在指定时间内只输出一次。

    防止高频重复日志（如 WebSocket ping、DB 重试）淹没磁盘。
    """

    def __init__(self, interval_seconds: float = 10.0, max_cache: int = 500):
        super().__init__()
        self._interval = interval_seconds
        self._cache: dict[str, float] = {}  # message_hash → last_emitted_time
        self._max_cache = max_cache

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True  # 警告和错误不过滤

        key = f"{record.name}:{record.getMessage()}"
        now = time.monotonic()
        last = self._cache.get(key)
        if last is not None and (now - last) < self._interval:
            return False  # 重复消息，抑制

        self._cache[key] = now
        # 限制缓存大小，防止内存泄漏
        if len(self._cache) > self._max_cache:
            oldest = min(self._cache.values())
            self._cache = {k: v for k, v in self._cache.items() if v > oldest}
        return True


class JSONFormatter(logging.Formatter):
    """JSON 格式化器，便于日志聚合和分析。"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "task_id"):
            log_entry["task_id"] = record.task_id
        if hasattr(record, "step_name"):
            log_entry["step_name"] = record.step_name
        return json.dumps(log_entry, ensure_ascii=False)


# 默认抑制的噪声日志器（生产环境建议 WARNING）
_NOISY_LOGGERS: dict[str, int] = {
    "sqlalchemy.engine": logging.WARNING,        # 抑制 SQL 语句日志
    "sqlalchemy.engine.Engine": logging.WARNING,
    "sqlalchemy.pool": logging.WARNING,
    "uvicorn": logging.INFO,                      # 保持 HTTP 请求日志
    "uvicorn.access": logging.WARNING,            # 抑制访问日志
    "uvicorn.error": logging.INFO,
    "httpx": logging.WARNING,                     # 抑制 HTTP 客户端日志
    "httpcore": logging.WARNING,
    "websockets": logging.WARNING,                # 抑制 WebSocket 协议日志
    "asyncio": logging.WARNING,                   # 抑制 asyncio 调试日志
    "apscheduler": logging.WARNING,               # 抑制调度器日志
}


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    backup_count: int = 7,
    dedup_interval: float = 10.0,
):
    """配置日志：控制台输出 + 文件旋转（每天轮转，保留指定天数）。

    Args:
        log_dir: 日志目录
        log_level: 根日志级别
        backup_count: 日轮转保留天数（默认 7 天）
        dedup_interval: 重复消息抑制间隔（秒），0 表示不抑制
    """
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # 启动时检查并截断过大的日志文件（超过 500MB 的清空，让新日志从头开始）
    for fname in ["app.log", "error.log"]:
        fpath = log_path / fname
        if fpath.exists() and fpath.stat().st_size > 500 * 1024 * 1024:
            # 重命名旧文件以便手动恢复，然后创建新文件
            import shutil
            backup = fpath.with_suffix(f".bak.{int(time.time())}")
            shutil.move(str(fpath), str(backup))
            print(f"[startup] 日志文件过大 ({fname}>{500}MB)，已备份至: {backup.name}")

    # 根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 清除已有处理器（避免重复）
    root_logger.handlers.clear()

    # 人类可读格式（控制台）
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # JSON 格式（文件）
    json_formatter = JSONFormatter()

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 去重过滤器（控制台和文件均生效）
    if dedup_interval > 0:
        dedup_filter = DeduplicationFilter(interval_seconds=dedup_interval)
        root_logger.addFilter(dedup_filter)

    # 文件处理器：大小轮转（每 100MB 轮转，保留指定天数，JSON 格式）
    # 使用 RotatingFileHandler 确保日志体积可控，避免开发环境频繁重启导致午夜轮转不触发
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "app.log",
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # 错误日志单独文件（大小轮转，保留更久）
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / "error.log",
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=max(backup_count, 30),  # 错误日志至少保留 30 个备份
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    root_logger.addHandler(error_handler)

    # 抑制噪声第三方库日志
    for logger_name, level in _NOISY_LOGGERS.items():
        logging.getLogger(logger_name).setLevel(level)

    logging.getLogger(__name__).info(
        f"日志已配置：{log_path.absolute()} "
        f"(level={log_level}, backup={backup_count}, dedup={dedup_interval}s, "
        f"main=100MB/rot, error=50MB/rot)"
    )
