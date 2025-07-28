"""
High-Performance Redis Caching Layer
===================================

This module provides a comprehensive Redis caching system for sub-second
response times, implementing multiple caching strategies and patterns.

Features:
- Multi-level caching (L1: Memory, L2: Redis)
- Async and sync Redis operations
- Cache warming and invalidation
- Compression for large objects
- TTL management and cache statistics
- Connection pooling and failover
"""

import asyncio
import json
import pickle
import gzip
import time
import logging
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import asynccontextmanager

try:
    import redis
    import aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    aioredis = None

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    avg_response_time: float = 0.0
    memory_hits: int = 0
    redis_hits: int = 0


class RedisCache:
    """High-performance Redis caching with fallback to memory."""
    
    def __init__(self, 
                 redis_url: str = None,
                 memory_cache_size: int = 1000,
                 default_ttl: int = 3600,
                 compression_threshold: int = 1024):
        
        self.redis_url = redis_url or settings.REDIS_URL
        self.memory_cache_size = memory_cache_size
        self.default_ttl = default_ttl
        self.compression_threshold = compression_threshold
        
        # Connection pools
        self.redis_pool = None
        self.async_redis_pool = None
        
        # Memory cache (L1) - LRU
        self.memory_cache: Dict[str, Dict] = {}
        self.memory_access_order: List[str] = []
        
        # Statistics
        self.stats = CacheStats()
        
        # Initialize connections
        self._init_redis_connections()
    
    def _init_redis_connections(self):
        """Initialize Redis connection pools."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using memory-only cache")
            return
        
        try:
            # Sync Redis connection pool
            self.redis_pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30
            )
            
            # Test connection
            r = redis.Redis(connection_pool=self.redis_pool)
            r.ping()
            
            logger.info("Redis connection pool initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            self.redis_pool = None
    
    async def _init_async_redis(self):
        """Initialize async Redis connection pool."""
        if not REDIS_AVAILABLE or self.async_redis_pool:
            return
        
        try:
            self.async_redis_pool = aioredis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            async with aioredis.Redis(connection_pool=self.async_redis_pool) as r:
                await r.ping()
            
            logger.info("Async Redis connection pool initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize async Redis: {e}")
            self.async_redis_pool = None
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize and optionally compress value."""
        try:
            # Serialize with pickle for Python objects
            serialized = pickle.dumps(value)
            
            # Compress if above threshold
            if len(serialized) > self.compression_threshold:
                compressed = gzip.compress(serialized)
                return b'compressed:' + compressed
            
            return b'raw:' + serialized
            
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            # Fallback to JSON for simple objects
            try:
                json_data = json.dumps(value, default=str).encode('utf-8')
                return b'json:' + json_data
            except:
                raise ValueError(f"Cannot serialize value: {type(value)}")
    
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize and decompress value."""
        try:
            if data.startswith(b'compressed:'):
                compressed_data = data[11:]  # Remove 'compressed:' prefix
                decompressed = gzip.decompress(compressed_data)
                return pickle.loads(decompressed)
            
            elif data.startswith(b'raw:'):
                raw_data = data[4:]  # Remove 'raw:' prefix
                return pickle.loads(raw_data)
            
            elif data.startswith(b'json:'):
                json_data = data[5:]  # Remove 'json:' prefix
                return json.loads(json_data.decode('utf-8'))
            
            else:
                # Legacy format - try pickle directly
                return pickle.loads(data)
                
        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            return None
    
    def _update_memory_cache(self, key: str, value: Any, ttl: int):
        """Update L1 memory cache with LRU eviction."""
        try:
            # Remove if already exists
            if key in self.memory_cache:
                self.memory_access_order.remove(key)
            
            # Add to cache
            expires_at = time.time() + ttl if ttl > 0 else None
            self.memory_cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': time.time()
            }
            self.memory_access_order.append(key)
            
            # Evict if over capacity
            while len(self.memory_cache) > self.memory_cache_size:
                oldest_key = self.memory_access_order.pop(0)
                del self.memory_cache[oldest_key]
                
        except Exception as e:
            logger.error(f"Memory cache update error: {e}")
    
    def _get_from_memory_cache(self, key: str) -> Optional[Any]:
        """Get value from L1 memory cache."""
        try:
            if key not in self.memory_cache:
                return None
            
            entry = self.memory_cache[key]
            
            # Check expiration
            if entry['expires_at'] and time.time() > entry['expires_at']:
                del self.memory_cache[key]
                self.memory_access_order.remove(key)
                return None
            
            # Update access order (LRU)
            self.memory_access_order.remove(key)
            self.memory_access_order.append(key)
            
            self.stats.memory_hits += 1
            return entry['value']
            
        except Exception as e:
            logger.error(f"Memory cache get error: {e}")
            return None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (memory first, then Redis)."""
        start_time = time.time()
        
        try:
            # Try L1 memory cache first
            value = self._get_from_memory_cache(key)
            if value is not None:
                self.stats.hits += 1
                response_time = time.time() - start_time
                self._update_avg_response_time(response_time)
                return value
            
            # Try L2 Redis cache
            if self.redis_pool:
                try:
                    r = redis.Redis(connection_pool=self.redis_pool)
                    cached_data = r.get(key)
                    
                    if cached_data:
                        value = self._deserialize_value(cached_data)
                        if value is not None:
                            # Promote to memory cache
                            self._update_memory_cache(key, value, 300)  # 5 min in memory
                            
                            self.stats.hits += 1
                            self.stats.redis_hits += 1
                            response_time = time.time() - start_time
                            self._update_avg_response_time(response_time)
                            return value
                            
                except Exception as e:
                    logger.error(f"Redis get error: {e}")
                    self.stats.errors += 1
            
            # Cache miss
            self.stats.misses += 1
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.stats.errors += 1
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache (both memory and Redis)."""
        try:
            ttl = ttl or self.default_ttl
            
            # Update memory cache
            self._update_memory_cache(key, value, ttl)
            
            # Update Redis cache
            if self.redis_pool:
                try:
                    r = redis.Redis(connection_pool=self.redis_pool)
                    serialized_value = self._serialize_value(value)
                    
                    if ttl > 0:
                        r.setex(key, ttl, serialized_value)
                    else:
                        r.set(key, serialized_value)
                    
                except Exception as e:
                    logger.error(f"Redis set error: {e}")
                    self.stats.errors += 1
            
            self.stats.sets += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.stats.errors += 1
            return False
    
    async def get_async(self, key: str) -> Optional[Any]:
        """Get value from cache asynchronously."""
        start_time = time.time()
        
        try:
            # Try L1 memory cache first
            value = self._get_from_memory_cache(key)
            if value is not None:
                self.stats.hits += 1
                response_time = time.time() - start_time
                self._update_avg_response_time(response_time)
                return value
            
            # Initialize async Redis if needed
            await self._init_async_redis()
            
            # Try L2 Redis cache
            if self.async_redis_pool:
                try:
                    async with aioredis.Redis(connection_pool=self.async_redis_pool) as r:
                        cached_data = await r.get(key)
                        
                        if cached_data:
                            value = self._deserialize_value(cached_data)
                            if value is not None:
                                # Promote to memory cache
                                self._update_memory_cache(key, value, 300)
                                
                                self.stats.hits += 1
                                self.stats.redis_hits += 1
                                response_time = time.time() - start_time
                                self._update_avg_response_time(response_time)
                                return value
                                
                except Exception as e:
                    logger.error(f"Async Redis get error: {e}")
                    self.stats.errors += 1
            
            # Cache miss
            self.stats.misses += 1
            return None
            
        except Exception as e:
            logger.error(f"Async cache get error: {e}")
            self.stats.errors += 1
            return None
    
    async def set_async(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache asynchronously."""
        try:
            ttl = ttl or self.default_ttl
            
            # Update memory cache
            self._update_memory_cache(key, value, ttl)
            
            # Initialize async Redis if needed
            await self._init_async_redis()
            
            # Update Redis cache
            if self.async_redis_pool:
                try:
                    async with aioredis.Redis(connection_pool=self.async_redis_pool) as r:
                        serialized_value = self._serialize_value(value)
                        
                        if ttl > 0:
                            await r.setex(key, ttl, serialized_value)
                        else:
                            await r.set(key, serialized_value)
                    
                except Exception as e:
                    logger.error(f"Async Redis set error: {e}")
                    self.stats.errors += 1
            
            self.stats.sets += 1
            return True
            
        except Exception as e:
            logger.error(f"Async cache set error: {e}")
            self.stats.errors += 1
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            # Remove from memory cache
            if key in self.memory_cache:
                del self.memory_cache[key]
                self.memory_access_order.remove(key)
            
            # Remove from Redis
            if self.redis_pool:
                try:
                    r = redis.Redis(connection_pool=self.redis_pool)
                    r.delete(key)
                except Exception as e:
                    logger.error(f"Redis delete error: {e}")
                    self.stats.errors += 1
            
            self.stats.deletes += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            self.stats.errors += 1
            return False
    
    def _update_avg_response_time(self, response_time: float):
        """Update average response time."""
        total_ops = self.stats.hits + self.stats.misses
        if total_ops > 0:
            current_avg = self.stats.avg_response_time
            self.stats.avg_response_time = (current_avg * (total_ops - 1) + response_time) / total_ops
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_ops = self.stats.hits + self.stats.misses
        hit_rate = (self.stats.hits / total_ops * 100) if total_ops > 0 else 0
        
        return {
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "hit_rate_percent": round(hit_rate, 2),
            "sets": self.stats.sets,
            "deletes": self.stats.deletes,
            "errors": self.stats.errors,
            "avg_response_time_ms": round(self.stats.avg_response_time * 1000, 2),
            "memory_hits": self.stats.memory_hits,
            "redis_hits": self.stats.redis_hits,
            "memory_cache_size": len(self.memory_cache),
            "redis_available": self.redis_pool is not None
        }
    
    def clear_memory_cache(self):
        """Clear L1 memory cache."""
        self.memory_cache.clear()
        self.memory_access_order.clear()
    
    def health_check(self) -> Dict[str, Any]:
        """Perform cache health check."""
        health = {
            "memory_cache": True,
            "redis_cache": False,
            "async_redis": False
        }
        
        # Test Redis connection
        if self.redis_pool:
            try:
                r = redis.Redis(connection_pool=self.redis_pool)
                r.ping()
                health["redis_cache"] = True
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")
        
        return health


# Global cache instance
cache = RedisCache()


# Convenience functions
def get_cached(key: str) -> Optional[Any]:
    """Get value from cache."""
    return cache.get(key)


def set_cached(key: str, value: Any, ttl: int = None) -> bool:
    """Set value in cache."""
    return cache.set(key, value, ttl)


async def get_cached_async(key: str) -> Optional[Any]:
    """Get value from cache asynchronously."""
    return await cache.get_async(key)


async def set_cached_async(key: str, value: Any, ttl: int = None) -> bool:
    """Set value in cache asynchronously."""
    return await cache.set_async(key, value, ttl)
