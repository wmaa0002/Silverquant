"""
日志工具模块 - 统一管理日志配置

所有日志统一存放在 logs/ 目录下，按功能分类：
- logs/pipeline/: 核心数据流水线日志
- logs/backtest/: 回测日志
- logs/init/: 数据初始化日志
- logs/check/: 数据检查日志
"""

import logging
import os
from datetime import datetime
from typing import Optional

# 日志基础目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
LOG_BASE_DIR = os.path.join(PROJECT_ROOT, 'logs')


def get_log_dir(subdir: str) -> str:
    """获取日志子目录，不存在则创建"""
    log_dir = os.path.join(LOG_BASE_DIR, subdir)
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def get_log_path(name: str, subdir: str, date_suffix: bool = True) -> str:
    """
    生成日志文件路径

    Args:
        name: 日志名称
        subdir: 日志子目录 (pipeline/backtest/init/check)
        date_suffix: 是否添加日期后缀

    Returns:
        完整的日志文件路径
    """
    log_dir = get_log_dir(subdir)
    if date_suffix:
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"{name}_{date_str}.log"
    else:
        filename = f"{name}.log"
    return os.path.join(log_dir, filename)


def setup_logger(
    name: str,
    subdir: str = 'pipeline',
    log_filename: Optional[str] = None,
    date_suffix: bool = True,
    level: int = logging.INFO
) -> logging.Logger:
    """
    设置统一格式的日志记录器

    Args:
        name: logger名称 (用于创建子logger)
        subdir: 日志子目录 (pipeline/backtest/init/check)
        log_filename: 日志文件名，默认使用name
        date_suffix: 是否添加日期后缀，默认True
        level: 日志级别，默认INFO

    Returns:
        配置好的logger
    """
    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 日志文件路径
    if log_filename is None:
        log_filename = name
    log_path = get_log_path(log_filename, subdir, date_suffix)

    # 文件handler
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(level)

    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # 统一格式
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str, subdir: str = 'pipeline') -> logging.Logger:
    """
    获取已配置的logger (单例模式)

    Args:
        name: logger名称
        subdir: 日志子目录

    Returns:
        已配置的logger
    """
    return setup_logger(name, subdir)