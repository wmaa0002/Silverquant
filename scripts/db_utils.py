"""数据库连接工具模块"""

import os
import duckdb
from contextlib import contextmanager

# 数据库路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'Astock3.duckdb')


@contextmanager
def get_db_connection(read_only: bool = True):
    """
    获取数据库连接的上下文管理器

    Args:
        read_only: 是否以只读模式打开连接

    Yields:
        duckdb.DuckDBPyConnection: 数据库连接
    """
    conn = duckdb.connect(DB_PATH, read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()
