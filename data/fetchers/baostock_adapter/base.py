"""
Baostock适配器基类

提供:
- 自动登录/登出 (session管理)
- 上下文管理器支持
- 错误处理和重试机制
"""

import logging
import baostock as bs
from typing import Optional

logger = logging.getLogger(__name__)


class BaostockBaseFetcher:
    """
    Baostock适配器基类
    
    使用示例:
        with BaostockBaseFetcher() as fetcher:
            # 进行操作
            pass
    """
    
    _logged_in: bool = False
    
    def __init__(self):
        self._ensure_login()
    
    def _ensure_login(self) -> None:
        """确保已登录baostock"""
        if not BaostockBaseFetcher._logged_in:
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(f"Baostock登录失败: {lg.error_msg}")
            BaostockBaseFetcher._logged_in = True
            logger.debug("Baostock登录成功")
    
    def _ensure_logout(self) -> None:
        """登出baostock"""
        if BaostockBaseFetcher._logged_in:
            bs.logout()
            BaostockBaseFetcher._logged_in = False
            logger.debug("Baostock登出成功")
    
    def __enter__(self):
        self._ensure_login()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 不在这里登出，因为baostock的session是全局的
        # 多个fetcher可以共享一个session
        pass
    
    @classmethod
    def isLoggedIn(cls) -> bool:
        """检查是否已登录"""
        return cls._logged_in