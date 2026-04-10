"""
Tushare适配器基类 - 提供tushare API调用基础设施

提供:
- Token管理
- 速率限制
- 重试机制（指数退避）
- 429错误处理
- 日期格式解析
"""
import os
import sys
import time
import logging
from typing import Any, Callable, Optional, TypeVar

import tushare as ts

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from data.fetchers.rate_limiter import tushare_limiter

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TushareBaseFetcher:
    """
    Tushare API调用基类
    
    提供通用的API调用能力，包括:
    - 自动token管理
    - 速率限制（50次/分钟）
    - 重试机制（3次，指数退避）
    - 429错误处理
    - 日期格式标准化
    """
    
    # Tushare API限制: 50次/分钟
    MAX_RETRIES = 3
    RATE_LIMIT_PERIOD = 60  # 秒
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化Tushare适配器
        
        Args:
            token: Tushare token。如果为None，从环境变量TUSHARE_TOKEN读取
        """
        self._token = token or os.environ.get('TUSHARE_TOKEN')
        self._api = None
        
        if not self._token:
            logger.warning("TUSHARE_TOKEN未设置，部分功能可能不可用")
    
    def _ensure_api(self) -> bool:
        """
        确保API已初始化
        
        Returns:
            True: API已就绪
            False: Token未设置
        """
        if self._api is None:
            if not self._token:
                logger.error("Tushare token未设置，无法初始化API")
                return False
            ts.set_token(self._token)
            self._api = ts.pro_api()
        return True
    
    def _call_api(
        self,
        api_method: Callable[..., T],
        *args,
        max_retries: int = MAX_RETRIES,
        **kwargs
    ) -> T:
        """
        通用的API调用方法，带速率限制和重试机制
        
        Args:
            api_method: API方法
            *args: 位置参数
            max_retries: 最大重试次数
            **kwargs: 关键字参数
            
        Returns:
            API返回结果
            
        Raises:
            Exception: 重试次数耗尽后抛出
        """
        if not self._ensure_api():
            raise RuntimeError("Tushare API未初始化，请设置TUSHARE_TOKEN")
        
        for attempt in range(max_retries):
            try:
                # 应用速率限制
                tushare_limiter.wait_if_needed()
                
                result = api_method(*args, **kwargs)
                return result
                
            except Exception as e:
                error_msg = str(e)
                
                # 429错误：速率限制
                if self._is_rate_limit_error(e):
                    retry_after = self._handle_rate_limit(attempt, max_retries)
                    continue
                
                # 其他错误，记录并重试
                logger.warning(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
                
                if attempt == max_retries - 1:
                    logger.error(f"API调用失败，已重试{max_retries}次: {error_msg}")
                    raise
                
                # 指数退避: 1, 2, 3秒
                sleep_time = (attempt + 1)
                logger.info(f"等待{sleep_time}秒后重试...")
                time.sleep(sleep_time)
        
        raise RuntimeError("重试次数耗尽")
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """
        判断是否是速率限制错误
        
        Args:
            error: 异常对象
            
        Returns:
            True: 是速率限制错误
        """
        error_msg = str(error).lower()
        return '429' in error_msg or 'rate limit' in error_msg or 'too many requests' in error_msg
    
    def _handle_rate_limit(self, attempt: int, max_retries: int) -> float:
        """
        处理速率限制错误
        
        Args:
            attempt: 当前尝试次数
            max_retries: 最大重试次数
            
        Returns:
            等待时间（秒）
        """
        if attempt >= max_retries - 1:
            raise RuntimeError("触发速率限制，重试次数耗尽")
        
        # Tushare通常返回429时建议等待60秒
        sleep_time = self.RATE_LIMIT_PERIOD
        logger.warning(f"触发速率限制(429)，等待{sleep_time}秒后重试...")
        time.sleep(sleep_time)
        return sleep_time
    
    def _parse_date(self, date_value: Any) -> str:
        """
        解析日期为Tushare标准格式(YYYYMMDD)
        
        Args:
            date_value: 日期值，支持:
                - str: '20240101', '2024-01-01', '2024/01/01'
                - datetime.date
                - datetime.datetime
                - int: 20240101
                
        Returns:
            YYYYMMDD格式字符串
            
        Raises:
            ValueError: 无法解析的日期格式
        """
        if date_value is None:
            return ''
        
        if isinstance(date_value, str):
            # 移除常见分隔符
            date_str = date_value.replace('-', '').replace('/', '')
            if len(date_str) == 8 and date_str.isdigit():
                return date_str
            raise ValueError(f"无法解析日期字符串: {date_value}")
        
        if isinstance(date_value, int):
            date_str = str(date_value)
            if len(date_str) == 8 and date_str.isdigit():
                return date_str
            raise ValueError(f"无法解析日期整数: {date_value}")
        
        if hasattr(date_value, 'strftime'):
            return date_value.strftime('%Y%m%d')
        
        raise ValueError(f"无法解析日期类型: {type(date_value)}")
    
    @property
    def api(self):
        """获取API实例（延迟初始化）"""
        if self._ensure_api():
            return self._api
        return None