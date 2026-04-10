"""
Redis缓存模块 - redis_cache.py

提供分析结果的Redis缓存，支持TTL过期和优雅降级。
"""
import json
from typing import Optional, Any

class RedisCache:
    def __init__(self, host='localhost', port=6379, db=0, ttl=3600):
        self.ttl = ttl
        self.available = False
        self.client = None
        
        try:
            import redis
            self.client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self.client.ping()
            self.available = True
        except Exception:
            self.client = None
    
    def get(self, key: str) -> Optional[Any]:
        if not self.available:
            return None
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
        except Exception:
            pass
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not self.available:
            return False
        try:
            self.client.setex(key, ttl or self.ttl, json.dumps(value))
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        if not self.available:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception:
            return False
