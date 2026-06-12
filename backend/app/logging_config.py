"""日志配置：控制台 + 文件旋转 + JSON 格式。"""
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """JSON 格式化器，便于日志聚合和分析。"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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


def setup_logging(log_dir: str = "logs", log_level: str = "INFO"):
    """配置日志：控制台输出 + 文件旋转（每天轮转，保留 30 天）。"""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

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

    # 文件处理器（每天轮转，保留 30 天，JSON 格式）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # 错误日志单独文件
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path / "error.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    root_logger.addHandler(error_handler)

    logging.getLogger(__name__).info(f"日志已配置：{log_path.absolute()}")
