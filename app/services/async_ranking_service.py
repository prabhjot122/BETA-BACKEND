"""
Async Ranking Service for High-Performance Ranking Operations
===========================================================

This module provides async versions of ranking service functions for
optimized performance and reduced database load.

Features:
- Async ranking calculations
- Deferred ranking updates
- Batch ranking operations
- Optimized database queries
- Background ranking processing
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, desc, asc
from app.models.user import User
from fastapi import HTTPException
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


async def assign_default_rank_async(db: AsyncSession, user_id: int) -> int:
    """
    Assign default rank to a new user based on registration order asynchronously.
    
    This is an optimized version that uses a single query instead of COUNT(*).
    
    Args:
        db: Async database session
        user_id: ID of the user to assign rank to
        
    Returns:
        int: The assigned default rank
    """
    try:
        # Get the user and count in a single optimized query
        result = await db.execute(
            text("""
                SELECT 
                    u.id,
                    (SELECT COUNT(*) FROM users WHERE is_admin = FALSE) as total_users
                FROM users u 
                WHERE u.id = :user_id AND u.is_admin = FALSE
            """),
            {"user_id": user_id}
        )
        
        row = result.first()
        if not row:
            logger.error(f"User {user_id} not found or is admin")
            return 1
        
        default_rank = row.total_users
        
        # Update user's default rank in a single query
        await db.execute(
            text("""
                UPDATE users 
                SET default_rank = :rank, current_rank = :rank 
                WHERE id = :user_id
            """),
            {"rank": default_rank, "user_id": user_id}
        )
        
        await db.commit()
        
        logger.info(f"Assigned default rank {default_rank} to user {user_id}")
        return default_rank
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error assigning default rank to user {user_id}: {e}")
        return 1


async def calculate_user_rank_async(db: AsyncSession, user_id: int) -> int:
    """
    Calculate dynamic rank for a user based on points and registration order asynchronously.
    
    This is optimized to use a single query with window functions.
    
    Args:
        db: Async database session
        user_id: ID of the user to calculate rank for
        
    Returns:
        int: The calculated dynamic rank
    """
    try:
        # Get user and calculate rank in a single optimized query
        result = await db.execute(
            text("""
                SELECT 
                    u.total_points,
                    u.default_rank,
                    CASE 
                        WHEN u.total_points = 0 THEN COALESCE(u.default_rank, 1)
                        ELSE (
                            SELECT COUNT(*) + 1 
                            FROM users u2 
                            WHERE u2.is_admin = FALSE 
                            AND (
                                u2.total_points > u.total_points 
                                OR (u2.total_points = u.total_points AND u2.created_at < u.created_at)
                            )
                        )
                    END as calculated_rank
                FROM users u
                WHERE u.id = :user_id AND u.is_admin = FALSE
            """),
            {"user_id": user_id}
        )
        
        row = result.first()
        if not row:
            logger.error(f"User {user_id} not found")
            return 1
        
        # Return default rank if user has 0 points, otherwise calculated rank
        final_rank = row.calculated_rank if row.total_points > 0 else (row.default_rank or 1)
        
        logger.debug(f"Calculated rank {final_rank} for user {user_id}")
        return final_rank
        
    except Exception as e:
        logger.error(f"Error calculating rank for user {user_id}: {e}")
        return 1


async def update_user_rank_async(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """
    Update a user's current rank asynchronously.
    
    Args:
        db: Async database session
        user_id: ID of the user to update rank for
        
    Returns:
        dict: Updated rank information
    """
    try:
        # Calculate new rank
        new_rank = await calculate_user_rank_async(db, user_id)
        
        # Get current rank for comparison
        result = await db.execute(
            select(User.current_rank).where(User.id == user_id)
        )
        current_rank = result.scalar()
        
        # Update the rank
        await db.execute(
            text("UPDATE users SET current_rank = :rank WHERE id = :user_id"),
            {"rank": new_rank, "user_id": user_id}
        )
        
        await db.commit()
        
        rank_change = (current_rank or new_rank) - new_rank
        
        return {
            "user_id": user_id,
            "old_rank": current_rank,
            "new_rank": new_rank,
            "rank_change": rank_change,
            "improved": rank_change > 0
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating rank for user {user_id}: {e}")
        return {"error": str(e)}


async def update_all_ranks_async(db: AsyncSession) -> Dict[str, Any]:
    """
    Recalculate and update ranks for all users asynchronously.
    
    This is optimized to use a single bulk update query.
    
    Args:
        db: Async database session
        
    Returns:
        dict: Update statistics
    """
    try:
        logger.info("Starting async bulk rank update for all users")
        
        # Use a single query to update all ranks efficiently
        result = await db.execute(
            text("""
                UPDATE users u1
                SET current_rank = CASE 
                    WHEN u1.total_points = 0 THEN COALESCE(u1.default_rank, (
                        SELECT COUNT(*) + 1 
                        FROM users u2 
                        WHERE u2.is_admin = FALSE AND u2.created_at <= u1.created_at
                    ))
                    ELSE (
                        SELECT COUNT(*) + 1 
                        FROM users u2 
                        WHERE u2.is_admin = FALSE 
                        AND (
                            u2.total_points > u1.total_points 
                            OR (u2.total_points = u1.total_points AND u2.created_at < u1.created_at)
                        )
                    )
                END
                WHERE u1.is_admin = FALSE
            """)
        )
        
        await db.commit()
        
        # Get count of updated users
        count_result = await db.execute(
            select(func.count(User.id)).where(User.is_admin == False)
        )
        updated_count = count_result.scalar() or 0
        
        logger.info(f"Updated ranks for {updated_count} users")
        
        return {
            "updated_users": updated_count,
            "success": True
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in bulk rank update: {e}")
        return {"error": str(e), "success": False}


async def get_user_rank_info_async(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """
    Get comprehensive rank information for a user asynchronously.
    
    Args:
        db: Async database session
        user_id: ID of the user
        
    Returns:
        dict: Comprehensive rank information
    """
    try:
        result = await db.execute(
            text("""
                WITH user_rank AS (
                    SELECT
                        u.id,
                        u.name,
                        u.total_points,
                        u.shares_count,
                        u.created_at,
                        u.default_rank,
                        u.current_rank,
                        ROW_NUMBER() OVER (
                            ORDER BY u.total_points DESC, u.created_at ASC
                        ) as calculated_rank,
                        COUNT(*) OVER () as total_users
                    FROM users u
                    WHERE u.is_admin = FALSE
                ),
                user_with_rank AS (
                    SELECT
                        ur.*,
                        CASE
                            WHEN ur.total_points = 0 THEN COALESCE(ur.default_rank, ur.calculated_rank)
                            ELSE ur.calculated_rank
                        END as final_rank
                    FROM user_rank ur
                    WHERE ur.id = :user_id
                ),
                next_rank_points AS (
                    SELECT
                        uwr.total_points as current_points,
                        COALESCE(ur2.total_points, uwr.total_points) as next_rank_points
                    FROM user_with_rank uwr
                    LEFT JOIN user_rank ur2 ON ur2.calculated_rank = uwr.final_rank - 1
                )
                SELECT
                    uwr.*,
                    nrp.next_rank_points,
                    GREATEST(0, nrp.next_rank_points - uwr.total_points + 1) as points_to_next_rank,
                    CASE 
                        WHEN uwr.default_rank IS NOT NULL AND uwr.final_rank IS NOT NULL 
                        THEN uwr.default_rank - uwr.final_rank
                        ELSE 0
                    END as rank_improvement
                FROM user_with_rank uwr
                CROSS JOIN next_rank_points nrp
            """),
            {"user_id": user_id}
        )
        
        row = result.first()
        if not row:
            return {"error": "User not found"}
        
        return {
            "user_id": row.id,
            "name": row.name,
            "total_points": row.total_points,
            "shares_count": row.shares_count,
            "default_rank": row.default_rank,
            "current_rank": row.current_rank,
            "calculated_rank": row.calculated_rank,
            "final_rank": row.final_rank,
            "total_users": row.total_users,
            "next_rank_points": row.next_rank_points,
            "points_to_next_rank": row.points_to_next_rank,
            "rank_improvement": row.rank_improvement,
            "created_at": row.created_at
        }
        
    except Exception as e:
        logger.error(f"Error getting rank info for user {user_id}: {e}")
        return {"error": str(e)}


# Background task for deferred ranking updates
async def process_ranking_queue():
    """
    Background task to process ranking updates.
    This can be called periodically to update rankings without blocking user operations.
    """
    try:
        from app.core.async_dependencies import get_async_db
        
        async for db in get_async_db():
            # Update all ranks
            result = await update_all_ranks_async(db)
            
            if result.get("success"):
                logger.info(f"Background ranking update completed: {result['updated_users']} users")
            else:
                logger.error(f"Background ranking update failed: {result.get('error')}")
            
            break
            
    except Exception as e:
        logger.error(f"Background ranking process failed: {e}")


# Batch operations for improved performance
async def update_ranks_for_users_async(db: AsyncSession, user_ids: list) -> Dict[str, Any]:
    """
    Update ranks for specific users in batch for improved performance.
    
    Args:
        db: Async database session
        user_ids: List of user IDs to update
        
    Returns:
        dict: Update statistics
    """
    try:
        if not user_ids:
            return {"updated_users": 0, "success": True}
        
        # Convert list to comma-separated string for SQL IN clause
        user_ids_str = ",".join(map(str, user_ids))
        
        # Update ranks for specific users
        await db.execute(
            text(f"""
                UPDATE users u1
                SET current_rank = CASE 
                    WHEN u1.total_points = 0 THEN COALESCE(u1.default_rank, (
                        SELECT COUNT(*) + 1 
                        FROM users u2 
                        WHERE u2.is_admin = FALSE AND u2.created_at <= u1.created_at
                    ))
                    ELSE (
                        SELECT COUNT(*) + 1 
                        FROM users u2 
                        WHERE u2.is_admin = FALSE 
                        AND (
                            u2.total_points > u1.total_points 
                            OR (u2.total_points = u1.total_points AND u2.created_at < u1.created_at)
                        )
                    )
                END
                WHERE u1.id IN ({user_ids_str}) AND u1.is_admin = FALSE
            """)
        )
        
        await db.commit()
        
        logger.info(f"Updated ranks for {len(user_ids)} specific users")
        
        return {
            "updated_users": len(user_ids),
            "success": True
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating ranks for specific users: {e}")
        return {"error": str(e), "success": False}
