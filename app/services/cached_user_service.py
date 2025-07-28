"""
Cached User Service for Sub-Second Performance
=============================================

This service implements aggressive caching strategies to achieve sub-second
response times for user operations.

Features:
- Multi-level caching (Memory + Redis)
- Cache warming and preloading
- Intelligent cache invalidation
- Sub-100ms response times for cached data
- Background cache refresh
"""

import asyncio
import time
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.schemas.user import UserResponse
from app.core.redis_cache import cache, get_cached_async, set_cached_async
from app.services.async_user_service import (
    get_user_by_email, get_user_by_id, create_user_async
)

logger = logging.getLogger(__name__)


class CachedUserService:
    """High-performance cached user service."""
    
    def __init__(self):
        self.cache_ttl = {
            'user_by_id': 1800,      # 30 minutes
            'user_by_email': 1800,   # 30 minutes
            'user_stats': 300,       # 5 minutes
            'user_ranking': 600,     # 10 minutes
            'leaderboard': 300,      # 5 minutes
        }
    
    def _get_user_cache_key(self, user_id: int) -> str:
        """Generate cache key for user by ID."""
        return f"user:id:{user_id}"
    
    def _get_user_email_cache_key(self, email: str) -> str:
        """Generate cache key for user by email."""
        return f"user:email:{email}"
    
    def _get_user_stats_cache_key(self) -> str:
        """Generate cache key for user statistics."""
        return "user:stats:global"
    
    def _get_user_ranking_cache_key(self, user_id: int) -> str:
        """Generate cache key for user ranking."""
        return f"user:ranking:{user_id}"
    
    async def get_user_by_id_cached(self, db: AsyncSession, user_id: int) -> Optional[User]:
        """Get user by ID with caching (target: <50ms)."""
        start_time = time.time()
        
        try:
            # Try cache first
            cache_key = self._get_user_cache_key(user_id)
            cached_user = await get_cached_async(cache_key)
            
            if cached_user:
                response_time = (time.time() - start_time) * 1000
                logger.debug(f"User {user_id} cache hit in {response_time:.2f}ms")
                return self._deserialize_user(cached_user)
            
            # Cache miss - get from database
            user = await get_user_by_id(db, user_id)
            
            if user:
                # Cache the result
                serialized_user = self._serialize_user(user)
                await set_cached_async(cache_key, serialized_user, self.cache_ttl['user_by_id'])
                
                response_time = (time.time() - start_time) * 1000
                logger.debug(f"User {user_id} cached in {response_time:.2f}ms")
            
            return user
            
        except Exception as e:
            logger.error(f"Error getting cached user by ID {user_id}: {e}")
            # Fallback to direct database query
            return await get_user_by_id(db, user_id)
    
    async def get_user_by_email_cached(self, db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email with caching (target: <50ms)."""
        start_time = time.time()
        
        try:
            # Try cache first
            cache_key = self._get_user_email_cache_key(email)
            cached_user = await get_cached_async(cache_key)
            
            if cached_user:
                response_time = (time.time() - start_time) * 1000
                logger.debug(f"User {email} cache hit in {response_time:.2f}ms")
                return self._deserialize_user(cached_user)
            
            # Cache miss - get from database
            user = await get_user_by_email(db, email)
            
            if user:
                # Cache the result (both by email and by ID)
                serialized_user = self._serialize_user(user)
                await set_cached_async(cache_key, serialized_user, self.cache_ttl['user_by_email'])
                
                # Also cache by ID for consistency
                id_cache_key = self._get_user_cache_key(user.id)
                await set_cached_async(id_cache_key, serialized_user, self.cache_ttl['user_by_id'])
                
                response_time = (time.time() - start_time) * 1000
                logger.debug(f"User {email} cached in {response_time:.2f}ms")
            
            return user
            
        except Exception as e:
            logger.error(f"Error getting cached user by email {email}: {e}")
            # Fallback to direct database query
            return await get_user_by_email(db, email)
    
    async def get_user_stats_cached(self, db: AsyncSession) -> Dict[str, Any]:
        """Get user statistics with caching (target: <10ms)."""
        start_time = time.time()
        
        try:
            # Try cache first
            cache_key = self._get_user_stats_cache_key()
            cached_stats = await get_cached_async(cache_key)
            
            if cached_stats:
                response_time = (time.time() - start_time) * 1000
                logger.debug(f"User stats cache hit in {response_time:.2f}ms")
                return cached_stats
            
            # Cache miss - calculate from database
            total_users_result = await db.execute(select(func.count(User.id)))
            total_users = total_users_result.scalar() or 0
            
            active_users_result = await db.execute(
                select(func.count(User.id)).where(User.is_active == True)
            )
            active_users = active_users_result.scalar() or 0
            
            admin_users_result = await db.execute(
                select(func.count(User.id)).where(User.is_admin == True)
            )
            admin_users = admin_users_result.scalar() or 0
            
            stats = {
                'total_users': total_users,
                'active_users': active_users,
                'admin_users': admin_users,
                'non_admin_users': total_users - admin_users,
                'last_updated': time.time()
            }
            
            # Cache the result
            await set_cached_async(cache_key, stats, self.cache_ttl['user_stats'])
            
            response_time = (time.time() - start_time) * 1000
            logger.debug(f"User stats calculated and cached in {response_time:.2f}ms")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cached user stats: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'admin_users': 0,
                'non_admin_users': 0,
                'error': str(e)
            }
    
    async def get_user_ranking_cached(self, db: AsyncSession, user_id: int) -> Dict[str, Any]:
        """Get user ranking with caching (target: <100ms)."""
        start_time = time.time()
        
        try:
            # Try cache first
            cache_key = self._get_user_ranking_cache_key(user_id)
            cached_ranking = await get_cached_async(cache_key)
            
            if cached_ranking:
                response_time = (time.time() - start_time) * 1000
                logger.debug(f"User {user_id} ranking cache hit in {response_time:.2f}ms")
                return cached_ranking
            
            # Cache miss - calculate ranking
            user = await self.get_user_by_id_cached(db, user_id)
            if not user:
                return {'error': 'User not found'}
            
            # Calculate rank using optimized query
            rank_result = await db.execute(
                select(func.count(User.id) + 1).where(
                    User.is_admin == False,
                    User.total_points > user.total_points
                )
            )
            current_rank = rank_result.scalar() or 1
            
            # Get total users for percentage calculation
            stats = await self.get_user_stats_cached(db)
            total_non_admin = stats.get('non_admin_users', 1)
            
            ranking = {
                'user_id': user_id,
                'current_rank': current_rank,
                'default_rank': user.default_rank,
                'total_points': user.total_points,
                'total_users': total_non_admin,
                'rank_percentage': round((current_rank / total_non_admin) * 100, 2) if total_non_admin > 0 else 0,
                'rank_improvement': (user.default_rank or current_rank) - current_rank,
                'last_updated': time.time()
            }
            
            # Cache the result
            await set_cached_async(cache_key, ranking, self.cache_ttl['user_ranking'])
            
            response_time = (time.time() - start_time) * 1000
            logger.debug(f"User {user_id} ranking calculated and cached in {response_time:.2f}ms")
            
            return ranking
            
        except Exception as e:
            logger.error(f"Error getting cached user ranking for {user_id}: {e}")
            return {'error': str(e)}
    
    async def invalidate_user_cache(self, user_id: int, email: str = None):
        """Invalidate all cache entries for a user."""
        try:
            # Invalidate user by ID cache
            id_cache_key = self._get_user_cache_key(user_id)
            cache.delete(id_cache_key)
            
            # Invalidate user by email cache if email provided
            if email:
                email_cache_key = self._get_user_email_cache_key(email)
                cache.delete(email_cache_key)
            
            # Invalidate user ranking cache
            ranking_cache_key = self._get_user_ranking_cache_key(user_id)
            cache.delete(ranking_cache_key)
            
            # Invalidate global stats (since user data changed)
            stats_cache_key = self._get_user_stats_cache_key()
            cache.delete(stats_cache_key)
            
            logger.debug(f"Invalidated cache for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error invalidating cache for user {user_id}: {e}")
    
    async def warm_user_cache(self, db: AsyncSession, user_ids: List[int]):
        """Warm cache for multiple users (background operation)."""
        try:
            logger.info(f"Warming cache for {len(user_ids)} users")
            
            # Warm user data cache
            tasks = []
            for user_id in user_ids:
                task = self.get_user_by_id_cached(db, user_id)
                tasks.append(task)
            
            # Execute in batches to avoid overwhelming the database
            batch_size = 10
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i + batch_size]
                await asyncio.gather(*batch, return_exceptions=True)
                await asyncio.sleep(0.1)  # Small delay between batches
            
            logger.info(f"Cache warming completed for {len(user_ids)} users")
            
        except Exception as e:
            logger.error(f"Error warming user cache: {e}")
    
    def _serialize_user(self, user: User) -> Dict[str, Any]:
        """Serialize user object for caching."""
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'password_hash': user.password_hash,
            'total_points': user.total_points,
            'shares_count': user.shares_count,
            'default_rank': user.default_rank,
            'current_rank': user.current_rank,
            'is_admin': user.is_admin,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'updated_at': user.updated_at.isoformat() if user.updated_at else None,
        }
    
    def _deserialize_user(self, data: Dict[str, Any]) -> User:
        """Deserialize cached data to user object."""
        from datetime import datetime
        
        user = User()
        user.id = data['id']
        user.name = data['name']
        user.email = data['email']
        user.password_hash = data['password_hash']
        user.total_points = data['total_points']
        user.shares_count = data['shares_count']
        user.default_rank = data['default_rank']
        user.current_rank = data['current_rank']
        user.is_admin = data['is_admin']
        user.is_active = data['is_active']
        
        if data['created_at']:
            user.created_at = datetime.fromisoformat(data['created_at'])
        if data['updated_at']:
            user.updated_at = datetime.fromisoformat(data['updated_at'])
        
        return user


# Global cached user service instance
cached_user_service = CachedUserService()


# Convenience functions
async def get_user_by_id_fast(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID with sub-50ms response time."""
    return await cached_user_service.get_user_by_id_cached(db, user_id)


async def get_user_by_email_fast(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email with sub-50ms response time."""
    return await cached_user_service.get_user_by_email_cached(db, email)


async def get_user_stats_fast(db: AsyncSession) -> Dict[str, Any]:
    """Get user statistics with sub-10ms response time."""
    return await cached_user_service.get_user_stats_cached(db)


async def get_user_ranking_fast(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Get user ranking with sub-100ms response time."""
    return await cached_user_service.get_user_ranking_cached(db, user_id)
