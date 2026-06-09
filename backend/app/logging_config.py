"""日志配置：控制台 + 文件旋转。"""
import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_dir: str = "logs", log_level: str = "INFO"):
    """配置日志：控制台输出 + 文件旋转（每天轮转，保留 30 天）。"""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # 根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 清除已有处理器（避免重复）
    root_logger.handlers.clear()

    # 格式
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（每天轮转，保留 30 天）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_path / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
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
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    logging.getLogger(__name__).info(f"日志已配置：{log_path.absolute()}")
