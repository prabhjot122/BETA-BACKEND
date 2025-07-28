"""
Optimized Ranking Service for High-Performance Operations
========================================================

This service uses denormalized user_stats table for O(1) ranking operations,
replacing expensive COUNT(*) queries with fast table lookups.

Features:
- O(1) user count operations
- Optimized ranking calculations
- Background ranking updates
- Atomic transaction handling
- Performance monitoring
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text, desc, asc
from app.models.user import User
from app.models.user_stats import UserStats
from fastapi import HTTPException
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


# Sync functions for immediate use
def get_user_count_fast(db: Session) -> int:
    """
    Get total user count using optimized user_stats table (O(1) operation).
    
    Args:
        db: Database session
        
    Returns:
        int: Total user count
    """
    try:
        result = db.query(UserStats.total_users).first()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error getting fast user count: {e}")
        # Fallback to COUNT query
        return db.query(func.count(User.id)).scalar() or 0


def get_non_admin_user_count_fast(db: Session) -> int:
    """
    Get non-admin user count using optimized user_stats table (O(1) operation).
    
    Args:
        db: Database session
        
    Returns:
        int: Non-admin user count
    """
    try:
        result = db.query(UserStats).first()
        if result:
            return result.non_admin_users
        return 0
    except Exception as e:
        logger.error(f"Error getting fast non-admin user count: {e}")
        # Fallback to COUNT query
        return db.query(func.count(User.id)).filter(User.is_admin == False).scalar() or 0


def assign_default_rank_optimized(db: Session, user_id: int) -> int:
    """
    Assign default rank using optimized user_stats table (O(1) operation).
    
    This replaces the expensive COUNT(*) query with a fast table lookup.
    
    Args:
        db: Database session
        user_id: ID of the user to assign rank to
        
    Returns:
        int: The assigned default rank
    """
    try:
        # Get user count from optimized stats table (O(1))
        non_admin_count = get_non_admin_user_count_fast(db)
        default_rank = non_admin_count
        
        # Update user's default rank
        user = db.query(User).filter(User.id == user_id).first()
        if user and not user.is_admin:
            user.default_rank = default_rank
            user.current_rank = default_rank
            db.commit()
            
            logger.info(f"Assigned optimized default rank {default_rank} to user {user_id}")
            return default_rank
        
        return default_rank
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error assigning optimized default rank to user {user_id}: {e}")
        return 1


# Async functions for high-performance operations
async def get_user_count_fast_async(db: AsyncSession) -> int:
    """
    Get total user count using optimized user_stats table asynchronously (O(1) operation).
    
    Args:
        db: Async database session
        
    Returns:
        int: Total user count
    """
    try:
        result = await db.execute(select(UserStats.total_users))
        count = result.scalar()
        return count or 0
    except Exception as e:
        logger.error(f"Error getting fast async user count: {e}")
        # Fallback to COUNT query
        result = await db.execute(select(func.count(User.id)))
        return result.scalar() or 0


async def get_non_admin_user_count_fast_async(db: AsyncSession) -> int:
    """
    Get non-admin user count using optimized user_stats table asynchronously (O(1) operation).
    
    Args:
        db: Async database session
        
    Returns:
        int: Non-admin user count
    """
    try:
        result = await db.execute(select(UserStats))
        stats = result.scalar_one_or_none()
        if stats:
            return stats.non_admin_users
        return 0
    except Exception as e:
        logger.error(f"Error getting fast async non-admin user count: {e}")
        # Fallback to COUNT query
        result = await db.execute(select(func.count(User.id)).where(User.is_admin == False))
        return result.scalar() or 0


async def assign_default_rank_optimized_async(db: AsyncSession, user_id: int) -> int:
    """
    Assign default rank using optimized user_stats table asynchronously (O(1) operation).
    
    This replaces the expensive COUNT(*) query with a fast table lookup.
    
    Args:
        db: Async database session
        user_id: ID of the user to assign rank to
        
    Returns:
        int: The assigned default rank
    """
    try:
        # Get user count from optimized stats table (O(1))
        non_admin_count = await get_non_admin_user_count_fast_async(db)
        default_rank = non_admin_count
        
        # Update user's default rank
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user and not user.is_admin:
            user.default_rank = default_rank
            user.current_rank = default_rank
            await db.commit()
            
            logger.info(f"Assigned optimized async default rank {default_rank} to user {user_id}")
            return default_rank
        
        return default_rank
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error assigning optimized async default rank to user {user_id}: {e}")
        return 1


async def get_user_stats_async(db: AsyncSession) -> Dict[str, Any]:
    """
    Get comprehensive user statistics asynchronously.
    
    Args:
        db: Async database session
        
    Returns:
        dict: User statistics
    """
    try:
        result = await db.execute(select(UserStats))
        stats = result.scalar_one_or_none()
        
        if stats:
            return stats.to_dict()
        
        # If no stats record exists, create one
        await initialize_user_stats_async(db)
        
        # Try again
        result = await db.execute(select(UserStats))
        stats = result.scalar_one_or_none()
        
        return stats.to_dict() if stats else {
            "total_users": 0,
            "total_active_users": 0,
            "total_admin_users": 0,
            "non_admin_users": 0,
            "active_non_admin_users": 0
        }
        
    except Exception as e:
        logger.error(f"Error getting async user stats: {e}")
        return {"error": str(e)}


async def initialize_user_stats_async(db: AsyncSession) -> bool:
    """
    Initialize user_stats table with current user counts asynchronously.
    
    Args:
        db: Async database session
        
    Returns:
        bool: Success status
    """
    try:
        # Calculate current stats
        total_result = await db.execute(select(func.count(User.id)))
        total_users = total_result.scalar() or 0
        
        active_result = await db.execute(select(func.count(User.id)).where(User.is_active == True))
        total_active_users = active_result.scalar() or 0
        
        admin_result = await db.execute(select(func.count(User.id)).where(User.is_admin == True))
        total_admin_users = admin_result.scalar() or 0
        
        # Create or update stats record
        existing_result = await db.execute(select(UserStats))
        existing_stats = existing_result.scalar_one_or_none()
        
        if existing_stats:
            existing_stats.total_users = total_users
            existing_stats.total_active_users = total_active_users
            existing_stats.total_admin_users = total_admin_users
        else:
            new_stats = UserStats(
                total_users=total_users,
                total_active_users=total_active_users,
                total_admin_users=total_admin_users
            )
            db.add(new_stats)
        
        await db.commit()
        
        logger.info(f"Initialized user stats: {total_users} total, {total_active_users} active, {total_admin_users} admin")
        return True
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error initializing user stats: {e}")
        return False


# Background maintenance functions
async def refresh_user_stats_background():
    """
    Background task to refresh user statistics periodically.
    This ensures the stats table stays accurate even if triggers fail.
    """
    try:
        from app.core.async_dependencies import get_async_db
        
        async for db in get_async_db():
            success = await initialize_user_stats_async(db)
            
            if success:
                logger.info("Background user stats refresh completed successfully")
            else:
                logger.error("Background user stats refresh failed")
            
            break
            
    except Exception as e:
        logger.error(f"Background user stats refresh failed: {e}")


# Performance monitoring
class RankingPerformanceMonitor:
    """Monitor performance of ranking operations."""
    
    def __init__(self):
        self.stats = {
            "optimized_rankings": 0,
            "fallback_rankings": 0,
            "avg_ranking_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }
    
    def record_optimized_ranking(self, execution_time: float):
        """Record an optimized ranking operation."""
        self.stats["optimized_rankings"] += 1
        self._update_avg_time(execution_time)
    
    def record_fallback_ranking(self, execution_time: float):
        """Record a fallback ranking operation."""
        self.stats["fallback_rankings"] += 1
        self._update_avg_time(execution_time)
    
    def _update_avg_time(self, execution_time: float):
        """Update average execution time."""
        total_ops = self.stats["optimized_rankings"] + self.stats["fallback_rankings"]
        current_avg = self.stats["avg_ranking_time"]
        self.stats["avg_ranking_time"] = (current_avg * (total_ops - 1) + execution_time) / total_ops
    
    def get_stats(self) -> dict:
        """Get current performance statistics."""
        total_ops = self.stats["optimized_rankings"] + self.stats["fallback_rankings"]
        optimization_rate = (self.stats["optimized_rankings"] / total_ops * 100) if total_ops > 0 else 0
        
        return {
            **self.stats,
            "total_operations": total_ops,
            "optimization_rate_percent": round(optimization_rate, 2)
        }


# Global performance monitor
ranking_perf_monitor = RankingPerformanceMonitor()
