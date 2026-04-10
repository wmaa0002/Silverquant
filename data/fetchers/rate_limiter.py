"""
进程内限流器 - 控制API调用频率

使用固定窗口算法，每个进程独立计数，不依赖外部存储。
"""
import threading
import time
from typing import Optional


class RateLimiter:
    """
    进程内限流器
    
    使用固定窗口算法，在指定时间周期内限制调用次数。
    线程安全，使用threading.Lock保护共享状态。
    
    Attributes:
        name: 限流器名称（用于日志）
        max_calls: 时间周期内允许的最大调用次数
        period: 时间周期（秒）
    """
    
    def __init__(self, name: str, max_calls: int, period: float):
        """
        初始化限流器
        
        Args:
            name: 限流器名称（用于日志）
            max_calls: 时间周期内允许的最大调用次数
            period: 时间周期（秒）
        """
        self.name = name
        self.max_calls = max_calls
        self.period = period
        
        self._lock = threading.Lock()
        self._calls: list[float] = []  # 记录每次调用的时间戳
    
    def acquire(self) -> bool:
        """
        尝试获取调用令牌
        
        Returns:
            True: 获取成功，可以调用
            False: 超过限制，拒绝调用
        """
        with self._lock:
            self._clean_expired()
            
            if len(self._calls) < self.max_calls:
                self._calls.append(time.time())
                return True
            return False
    
    def wait_if_needed(self) -> bool:
        """
        如果超过限制则等待，直到可以调用或超时
        
        Returns:
            True: 成功等待并获得令牌
            False: 未实现（保留）
        """
        with self._lock:
            self._clean_expired()
            
            if len(self._calls) < self.max_calls:
                self._calls.append(time.time())
                return True
            
            # 计算距离窗口重置还需要多久
            oldest = self._calls[0]
            sleep_time = oldest + self.period - time.time()
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            # 重新清理并记录
            self._clean_expired()
            self._calls.append(time.time())
            return True
    
    def _clean_expired(self) -> None:
        """清理超出时间窗口的调用记录"""
        now = time.time()
        cutoff = now - self.period
        self._calls = [t for t in self._calls if t > cutoff]
    
    def reset(self) -> None:
        """重置限流器状态"""
        with self._lock:
            self._calls.clear()
    
    def get_remaining(self) -> int:
        """获取剩余可用调用次数"""
        with self._lock:
            self._clean_expired()
            return max(0, self.max_calls - len(self._calls))
    
    def __enter__(self) -> 'RateLimiter':
        """上下文管理器入口"""
        self.wait_if_needed()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        pass


# ==================== 预配置限流器实例 ====================

# Tushare: 500次/分钟 (部分接口支持更高额度)
tushare_limiter = RateLimiter('tushare', 500, 60)

# Akshare: 100次/分钟
akshare_limiter = RateLimiter('akshare', 100, 60)

# Baostock: 200次/分钟
baostock_limiter = RateLimiter('baostock', 200, 60)