import sys
from pathlib import Path
from loguru import logger
from app.conf.app_config import app_config
from app.core.context import req_ctx_id_var


# 动态格式化函数
def dynamic_log_format(record):
    # 优先从 extra 拿，拿不到就去 contextvar 拿，再拿不到就给默认值 '1'
    request_id = record["extra"].get("request_id") or req_ctx_id_var.get()

    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        f"<magenta>request_id - {request_id}</magenta> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>\n"
    )


# 注入request_id到日志记录中
def inject_request_id(record):
    request_id = req_ctx_id_var.get()
    record["extra"]["request_id"] = request_id


# 封装成一个显式初始化的函数，在入口中直接调用
def init_logger():
    global logger
    logger.remove()

    # 给日志打补丁，使其支持注入request_id
    logger = logger.patch(inject_request_id)
    if app_config.logging.console.enable:
        logger.add(sink=sys.stdout, level=app_config.logging.console.level, format=dynamic_log_format)
    if app_config.logging.file.enable:
        path = Path(app_config.logging.file.path)
        path.mkdir(parents=True, exist_ok=True)
        logger.add(
            sink=path / "app.log",
            level=app_config.logging.file.level,
            format=dynamic_log_format,
            rotation=app_config.logging.file.rotation,
            retention=app_config.logging.file.retention,
            encoding="utf-8"
        )
