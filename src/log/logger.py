import sys
import os
from loguru import logger

def setup_logger(log_level="INFO", log_dir="logs"):
    """设置 Loguru 日志配置
    
    Args:
        log_level: 日志级别，默认为 INFO
        log_dir: 日志文件存储目录，默认为 logs
        
    Returns:
        已配置的日志器
    """
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # 添加文件处理器
    logger.add(
        os.path.join(log_dir, "mcp-{time:YYYY-MM-DD}.log"),
        rotation="00:00",  # 每天轮换
        retention="7 days",  # 保留7天
        level=log_level,
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{line} - {message}"
    )
    
    return logger

# 创建一个全局日志器实例
logger = setup_logger()