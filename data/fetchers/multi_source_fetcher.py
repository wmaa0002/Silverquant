# -*- coding: utf-8 -*-
"""
[DEPRECATED] 已被 data.updaters.fetcher_dwd.DWDFetcher(source=...) 替代

废弃日期: 2026-04-07
原因: DWDFetcher 已内置断路器模式

多数据源故障切换封装器

功能:
- CircuitBreaker: 断路器模式，跟踪每个数据源的错误率
- MultiSourceFetcher: 自动故障切换，支持健康检查和回滚

数据源优先级: tushare → baostock
切换条件: 错误率>30% 或 响应时间>10秒
"""
import time
import threading
from typing import List, Optional, Dict, Any
from collections import deque
import logging

from config.settings import Settings
from data.fetchers.stock_fetcher import StockFetcher

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    断路器 - 跟踪数据源健康状态，实现故障自动切换
    
    状态机:
    - closed: 正常状态，监控错误率
    - open: 熔断状态，快速失败
    - half-open: 测试恢复状态
    
    使用滑动窗口跟踪成功/失败比率
    """
    
    STATE_CLOSED = 'closed'
    STATE_OPEN = 'open'
    STATE_HALF_OPEN = 'half_open'
    
    def __init__(self, failure_threshold: float = 0.3, timeout: float = 10.0, window_size: int = 100):
        """
        初始化断路器
        
        Args:
            failure_threshold: 失败率阈值 (0.3=30%)
            timeout: 恢复探测超时(秒)
            window_size: 滑动窗口大小
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.window_size = window_size
        
        self._states: Dict[str, str] = {}
        self._windows: Dict[str, deque] = {}
        self._last_failure_time: Dict[str, float] = {}
        self._lock = threading.Lock()
        
        for source in Settings.DATA_SOURCE_PRIORITY:
            self._states[source] = self.STATE_CLOSED
            self._windows[source] = deque(maxlen=window_size)
    
    def record_success(self, source: str) -> None:
        """
        记录成功调用
        
        Args:
            source: 数据源名称
        """
        with self._lock:
            if source not in self._windows:
                self._windows[source] = deque(maxlen=self.window_size)
            
            self._windows[source].append((time.time(), True))
            
            if self._states.get(source) == self.STATE_HALF_OPEN:
                self._states[source] = self.STATE_CLOSED
                logger.info(f"CircuitBreaker: {source} 恢复成功，切换为closed状态")
    
    def record_failure(self, source: str, response_time: Optional[float] = None) -> None:
        """
        记录失败调用
        
        Args:
            source: 数据源名称
            response_time: 响应时间(秒)，可选
        """
        with self._lock:
            if source not in self._windows:
                self._windows[source] = deque(maxlen=self.window_size)
            
            self._windows[source].append((time.time(), False))
            self._last_failure_time[source] = time.time()
            
            if self._should_trip(source):
                self._states[source] = self.STATE_OPEN
                reason = f"错误率超过{int(self.failure_threshold * 100)}%"
                logger.warning(f"CircuitBreaker: {source} 触发断路器({reason})")
    
    def _should_trip(self, source: str) -> bool:
        """
        检查是否应该触发断路器
        
        Args:
            source: 数据源名称
            
        Returns:
            True if failure rate exceeds threshold
        """
        window = self._windows.get(source)
        if not window or len(window) == 0:
            return False
        
        total = len(window)
        
        if total < 10:
            return False
        
        failures = sum(1 for _, success in window if not success)
        failure_rate = failures / total
        
        return failure_rate > self.failure_threshold
    
    def should_attempt(self, source: str) -> bool:
        """检查是否应该尝试某数据源"""
        with self._lock:
            state = self._states.get(source, self.STATE_CLOSED)
            
            if state == self.STATE_CLOSED:
                if self._should_trip(source):
                    self._states[source] = self.STATE_OPEN
                    logger.warning(f"CircuitBreaker: {source} 错误率超过{int(self.failure_threshold * 100)}%，触发断路器")
                    return False
                return True
            
            if state == self.STATE_OPEN:
                last_failure = self._last_failure_time.get(source, 0)
                if time.time() - last_failure > self.timeout:
                    self._states[source] = self.STATE_HALF_OPEN
                    logger.info(f"CircuitBreaker: {source} 进入half_open状态，探测恢复")
                    return True
                return False
            
            if state == self.STATE_HALF_OPEN:
                return True
            
            return True
    
    def get_state(self, source: str) -> str:
        """获取数据源状态"""
        return self._states.get(source, self.STATE_CLOSED)
    
    def get_stats(self, source: str) -> Dict[str, Any]:
        """
        获取数据源统计信息
        
        Args:
            source: 数据源名称
            
        Returns:
            统计字典: total, successes, failures, failure_rate, avg_response_time
        """
        with self._lock:
            window = self._windows.get(source)
            if not window or len(window) == 0:
                return {
                    'total': 0,
                    'successes': 0,
                    'failures': 0,
                    'failure_rate': 0.0,
                    'state': self._states.get(source, self.STATE_CLOSED)
                }
            
            total = len(window)
            successes = sum(1 for _, success in window if success)
            failures = total - successes
            failure_rate = failures / total if total > 0 else 0.0
            
            return {
                'total': total,
                'successes': successes,
                'failures': failures,
                'failure_rate': failure_rate,
                'state': self._states.get(source, self.STATE_CLOSED)
            }
    
    def reset_source(self, source: str) -> None:
        """
        重置数据源状态
        
        Args:
            source: 数据源名称
        """
        with self._lock:
            self._states[source] = self.STATE_CLOSED
            self._windows[source] = deque(maxlen=self.window_size)
            self._last_failure_time.pop(source, None)
            logger.info(f"CircuitBreaker: {source} 已重置")


class MultiSourceFetcher:
    """
    多数据源故障切换封装器
    
    特性:
    - 自动故障切换: 当前数据源失败时自动切换到下一个
    - 断路器模式: 错误率>30%或响应>10秒时触发切换
    - 健康检查回滚: 定期探测高优先级源，恢复后自动切回
    - 线程安全: 支持多线程并发调用
    """
    
    def __init__(self, sources: Optional[List[str]] = None):
        """
        初始化多数据源获取器
        
        Args:
            sources: 数据源优先级列表，None时使用Settings.DATA_SOURCE_PRIORITY
        """
        self.sources = sources or list(Settings.DATA_SOURCE_PRIORITY)
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=Settings.FAILOVER_ERROR_RATE_THRESHOLD,
            timeout=Settings.FAILOVER_RESPONSE_TIME_THRESHOLD,
            window_size=100
        )
        
        self._fetchers: Dict[str, StockFetcher] = {}
        self._fetcher_lock = threading.Lock()
        
        self._current_source: Optional[str] = None
        
        self._last_health_check = 0
        self._health_check_interval = Settings.HEALTH_CHECK_INTERVAL
        
        self._stats: Dict[str, Dict[str, Any]] = {s: {
            'success_count': 0,
            'error_count': 0,
            'total_calls': 0,
            'total_response_time': 0.0
        } for s in self.sources}
        self._stats_lock = threading.Lock()
        
        logger.info(f"MultiSourceFetcher 初始化，优先级: {self.sources}")
    
    def _get_fetcher(self, source: str) -> StockFetcher:
        """
        获取指定数据源的Fetcher实例
        
        Args:
            source: 数据源名称
            
        Returns:
            StockFetcher实例
        """
        with self._fetcher_lock:
            if source not in self._fetchers:
                self._fetchers[source] = StockFetcher(source=source)
            return self._fetchers[source]
    
    def _update_stats(self, source: str, success: bool, response_time: float) -> None:
        """更新统计数据"""
        with self._stats_lock:
            if source in self._stats:
                stats = self._stats[source]
                stats['total_calls'] += 1
                stats['total_response_time'] += response_time
                if success:
                    stats['success_count'] += 1
                else:
                    stats['error_count'] += 1
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有数据源统计"""
        with self._stats_lock:
            result = {}
            for source in self.sources:
                stats = self._stats.get(source, {}).copy()
                if stats.get('total_calls', 0) > 0:
                    stats['avg_response_time'] = stats['total_response_time'] / stats['total_calls']
                else:
                    stats['avg_response_time'] = 0.0
                stats['circuit_state'] = self._circuit_breaker.get_state(source)
                result[source] = stats
            return result
    
    def _try_call(self, source: str, func, *args, **kwargs) -> Any:
        if not self._circuit_breaker.should_attempt(source):
            return False, None
        
        fetcher = self._get_fetcher(source)
        start_time = time.time()
        
        try:
            result = func(fetcher, *args, **kwargs)
            response_time = time.time() - start_time
            
            if response_time > Settings.FAILOVER_RESPONSE_TIME_THRESHOLD:
                self._circuit_breaker.record_failure(source, response_time)
                self._update_stats(source, False, response_time)
                logger.warning(f"{source} 响应时间过长({response_time:.2f}s > {Settings.FAILOVER_RESPONSE_TIME_THRESHOLD}s)，触发切换")
                return False, None
            
            self._circuit_breaker.record_success(source)
            self._update_stats(source, True, response_time)
            return True, result
            
        except Exception as e:
            response_time = time.time() - start_time
            self._circuit_breaker.record_failure(source, response_time)
            self._update_stats(source, False, response_time)
            logger.warning(f"{source} 调用失败: {e}")
            return False, None
    
    def _health_check(self) -> Optional[str]:
        """
        执行健康检查，探测是否有高优先级源恢复
        
        Returns:
            恢复的数据源名称，或None
        """
        current_idx = self.sources.index(self._current_source) if self._current_source in self.sources else len(self.sources)
        
        for i in range(current_idx):
            source = self.sources[i]
            state = self._circuit_breaker.get_state(source)
            
            if state != self._circuit_breaker.STATE_CLOSED:
                try:
                    fetcher = self._get_fetcher(source)
                    fetcher.get_stock_list()
                    self._circuit_breaker.reset_source(source)
                    logger.info(f"健康检查: {source} 已恢复")
                    return source
                except Exception:
                    pass
        
        return None
    
    def get_stock_list(self) -> Optional[Any]:
        if time.time() - self._last_health_check > self._health_check_interval:
            recovered = self._health_check()
            if recovered:
                self._current_source = recovered
                logger.info(f"自动回滚到高优先级数据源: {recovered}")
            self._last_health_check = time.time()
        
        errors = []
        
        for source in self.sources:
            if not self._circuit_breaker.should_attempt(source):
                continue
            
            logger.info(f"尝试从 {source} 获取股票列表")
            self._current_source = source
            
            success, result = self._try_call(source, StockFetcher.get_stock_list)
            
            if success and result is not None and len(result) > 0:
                logger.info(f"成功从 {source} 获取股票列表，共 {len(result)} 条")
                return result
            
            if result is not None:
                errors.append(f"{source}: 返回空数据")
        
        logger.error(f"所有数据源获取股票列表失败: {errors}")
        return None
    
    def get_daily_price(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = 'qfq'
    ) -> Optional[Any]:
        """
        获取日线数据，尝试每个数据源直到成功
        
        Args:
            code: 股票代码 (6位内部格式)
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            adjust: 复权类型 ('qfq', 'hfq', '')
            
        Returns:
            日线数据DataFrame，或None（全部失败）
        """
        if time.time() - self._last_health_check > self._health_check_interval:
            recovered = self._health_check()
            if recovered:
                self._current_source = recovered
                logger.info(f"自动回滚到高优先级数据源: {recovered}")
            self._last_health_check = time.time()
        
        errors = []
        
        for source in self.sources:
            if not self._circuit_breaker.should_attempt(source):
                continue
            
            logger.info(f"尝试从 {source} 获取 {code} 日线数据 ({start_date} ~ {end_date})")
            self._current_source = source
            
            success, result = self._try_call(source, lambda f, c, s, e, a: f.get_daily_price(c, s, e, a), 
                                             code, start_date, end_date, adjust)
            
            if success and result is not None and len(result) > 0:
                logger.info(f"成功从 {source} 获取 {code} 日线数据，共 {len(result)} 条")
                return result
            
            if result is not None:
                errors.append(f"{source}: 返回空数据")
        
        logger.error(f"所有数据源获取 {code} 日线数据失败: {errors}")
        return None
    
    def get_current_source(self) -> Optional[str]:
        """获取当前使用的数据源"""
        return self._current_source
    
    def reset_all(self) -> None:
        """重置所有数据源状态"""
        for source in self.sources:
            self._circuit_breaker.reset_source(source)
        self._current_source = None
        logger.info("MultiSourceFetcher 已重置")


# ==================== 便捷函数 ====================

_default_fetcher: Optional[MultiSourceFetcher] = None
_fetcher_lock = threading.Lock()


def get_multi_source_fetcher() -> MultiSourceFetcher:
    """获取全局MultiSourceFetcher实例（单例）"""
    global _default_fetcher
    with _fetcher_lock:
        if _default_fetcher is None:
            _default_fetcher = MultiSourceFetcher()
        return _default_fetcher


def reset_fetcher() -> None:
    """重置全局Fetcher实例"""
    global _default_fetcher
    with _fetcher_lock:
        if _default_fetcher is not None:
            _default_fetcher.reset_all()
        _default_fetcher = None