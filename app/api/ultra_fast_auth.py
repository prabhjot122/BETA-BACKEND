"""
Ultra-Fast Authentication API for Sub-Second Performance
=======================================================

This module provides ultra-optimized authentication endpoints targeting
sub-second response times through aggressive caching and optimization.

Features:
- Sub-100ms cached authentication
- Sub-50ms user data retrieval
- Background cache warming
- Intelligent cache invalidation
- Performance monitoring and metrics
"""

import time
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_dependencies import get_async_db
from app.core.redis_cache import cache
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.schemas.token import Token
from app.services.cached_user_service import (
    cached_user_service, get_user_by_email_fast, get_user_by_id_fast
)
from app.services.async_user_service import (
    create_user_async, authenticate_user_async, create_jwt_for_user
)
from app.core.security import verify_access_token
from fastapi.security import OAuth2PasswordBearer
from app.utils.monitoring import inc_user_signup

# Email queue imports
from app.models.email_queue import EmailType
from app.schemas.email_queue import EmailQueueCreate
from app.services.email_queue_service import add_email_to_queue, add_campaign_emails_for_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ultra-auth", tags=["ultra-fast-auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/ultra-auth/login")


class UltraFastAuthMetrics:
    """Performance metrics for ultra-fast auth."""
    
    def __init__(self):
        self.metrics = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_response_time': 0.0,
            'sub_100ms_responses': 0,
            'sub_500ms_responses': 0,
            'sub_1s_responses': 0,
        }
    
    def record_request(self, response_time: float, cache_hit: bool = False):
        """Record request metrics."""
        self.metrics['total_requests'] += 1
        
        if cache_hit:
            self.metrics['cache_hits'] += 1
        else:
            self.metrics['cache_misses'] += 1
        
        # Update average response time
        current_avg = self.metrics['avg_response_time']
        total_requests = self.metrics['total_requests']
        self.metrics['avg_response_time'] = (current_avg * (total_requests - 1) + response_time) / total_requests
        
        # Track response time buckets
        if response_time < 0.1:
            self.metrics['sub_100ms_responses'] += 1
        elif response_time < 0.5:
            self.metrics['sub_500ms_responses'] += 1
        elif response_time < 1.0:
            self.metrics['sub_1s_responses'] += 1
    
    def get_stats(self) -> dict:
        """Get performance statistics."""
        total = self.metrics['total_requests']
        if total == 0:
            return self.metrics
        
        return {
            **self.metrics,
            'cache_hit_rate': round((self.metrics['cache_hits'] / total) * 100, 2),
            'sub_100ms_rate': round((self.metrics['sub_100ms_responses'] / total) * 100, 2),
            'sub_500ms_rate': round((self.metrics['sub_500ms_responses'] / total) * 100, 2),
            'sub_1s_rate': round((self.metrics['sub_1s_responses'] / total) * 100, 2),
            'avg_response_time_ms': round(self.metrics['avg_response_time'] * 1000, 2)
        }


# Global metrics instance
ultra_metrics = UltraFastAuthMetrics()


@router.post("/signup", response_model=UserResponse, status_code=201)
async def ultra_fast_signup(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Ultra-fast user registration with aggressive optimization.
    
    Target: <500ms response time
    Features:
    - Cached duplicate email check
    - Background email processing
    - Immediate cache warming
    - Deferred ranking calculation
    """
    start_time = time.time()
    
    try:
        logger.info(f"Ultra-fast signup started for {user_in.email}")
        
        # Ultra-fast duplicate check using cache
        existing_user = await get_user_by_email_fast(db, user_in.email)
        if existing_user:
            response_time = time.time() - start_time
            ultra_metrics.record_request(response_time, cache_hit=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user with optimized async operations
        user = await create_user_async(db, user_in)
        
        # Immediately warm cache for the new user
        background_tasks.add_task(warm_new_user_cache, user.id, user.email, db)
        
        # Queue emails in background (non-blocking)
        background_tasks.add_task(queue_welcome_emails, user.email, user.name)
        
        # Update metrics
        inc_user_signup()
        
        response_time = time.time() - start_time
        ultra_metrics.record_request(response_time, cache_hit=False)
        
        logger.info(f"Ultra-fast signup completed for {user.email} in {response_time*1000:.2f}ms")
        
        return UserResponse(
            user_id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at,
            total_points=user.total_points,
            shares_count=user.shares_count,
            default_rank=user.default_rank,
            current_rank=user.current_rank,
            is_admin=user.is_admin
        )
        
    except HTTPException:
        response_time = time.time() - start_time
        ultra_metrics.record_request(response_time)
        raise
    except Exception as e:
        response_time = time.time() - start_time
        ultra_metrics.record_request(response_time)
        logger.error(f"Ultra-fast signup failed for {user_in.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )


@router.post("/login", response_model=Token)
async def ultra_fast_login(
    user_in: UserLogin,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Ultra-fast authentication with sub-100ms cached responses.
    
    Target: <100ms for cached users, <300ms for uncached
    Features:
    - Cached user lookup
    - Optimized password verification
    - JWT token caching
    """
    start_time = time.time()
    
    try:
        logger.debug(f"Ultra-fast login started for {user_in.email}")
        
        # Try cached user lookup first
        user = await get_user_by_email_fast(db, user_in.email)
        cache_hit = user is not None
        
        if not user:
            # Fallback to database lookup
            user = await authenticate_user_async(db, user_in.email, user_in.password)
            if not user:
                response_time = time.time() - start_time
                ultra_metrics.record_request(response_time, cache_hit=False)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                    headers={"WWW-Authenticate": "Bearer"}
                )
        else:
            # Verify password for cached user
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            # Use thread executor for password verification
            loop = asyncio.get_event_loop()
            password_valid = await loop.run_in_executor(
                None, pwd_context.verify, user_in.password, user.password_hash
            )
            
            if not password_valid:
                response_time = time.time() - start_time
                ultra_metrics.record_request(response_time, cache_hit=True)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                    headers={"WWW-Authenticate": "Bearer"}
                )
        
        # Check if user is active
        if not user.is_active:
            response_time = time.time() - start_time
            ultra_metrics.record_request(response_time, cache_hit=cache_hit)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        # Generate JWT token
        token = create_jwt_for_user(user)
        
        response_time = time.time() - start_time
        ultra_metrics.record_request(response_time, cache_hit=cache_hit)
        
        logger.info(f"Ultra-fast login completed for {user.email} in {response_time*1000:.2f}ms (cache_hit: {cache_hit})")
        
        return Token(
            access_token=token,
            token_type="bearer",
            expires_in=3600
        )
        
    except HTTPException:
        raise
    except Exception as e:
        response_time = time.time() - start_time
        ultra_metrics.record_request(response_time)
        logger.error(f"Ultra-fast login failed for {user_in.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable"
        )


@router.get("/me", response_model=UserResponse)
async def ultra_fast_get_me(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Ultra-fast user info retrieval with sub-50ms cached responses.
    
    Target: <50ms for cached users
    """
    start_time = time.time()
    
    try:
        # Verify token
        payload = verify_access_token(token)
        user_id = payload.get("user_id")
        
        if not user_id:
            response_time = time.time() - start_time
            ultra_metrics.record_request(response_time)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user with ultra-fast cached lookup
        user = await get_user_by_id_fast(db, user_id)
        cache_hit = user is not None
        
        if not user:
            response_time = time.time() - start_time
            ultra_metrics.record_request(response_time, cache_hit=False)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        response_time = time.time() - start_time
        ultra_metrics.record_request(response_time, cache_hit=cache_hit)
        
        logger.debug(f"Ultra-fast get_me completed for user {user_id} in {response_time*1000:.2f}ms")
        
        return UserResponse(
            user_id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at,
            total_points=user.total_points,
            shares_count=user.shares_count,
            default_rank=user.default_rank,
            current_rank=user.current_rank,
            is_admin=user.is_admin
        )
        
    except HTTPException:
        raise
    except Exception as e:
        response_time = time.time() - start_time
        ultra_metrics.record_request(response_time)
        logger.error(f"Ultra-fast get_me failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve user information"
        )


@router.get("/performance")
async def get_ultra_performance_stats():
    """Get ultra-fast auth performance statistics."""
    try:
        auth_stats = ultra_metrics.get_stats()
        cache_stats = cache.get_stats()
        cache_health = cache.health_check()
        
        return {
            "ultra_fast_auth": auth_stats,
            "cache_performance": cache_stats,
            "cache_health": cache_health,
            "target_metrics": {
                "signup_target_ms": 500,
                "login_cached_target_ms": 100,
                "login_uncached_target_ms": 300,
                "get_me_target_ms": 50
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting ultra performance stats: {e}")
        return {"error": str(e)}


@router.get("/health")
async def ultra_health_check(db: AsyncSession = Depends(get_async_db)):
    """Ultra-fast health check with performance timing."""
    start_time = time.time()
    
    try:
        # Test database connection
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1"))
        db_healthy = result.scalar() == 1
        
        # Test cache
        cache_healthy = cache.health_check()
        
        response_time = time.time() - start_time
        
        return {
            "status": "healthy" if db_healthy and cache_healthy["redis_cache"] else "degraded",
            "response_time_ms": round(response_time * 1000, 2),
            "database": "connected" if db_healthy else "disconnected",
            "cache": cache_healthy,
            "ultra_fast_auth": True
        }
        
    except Exception as e:
        response_time = time.time() - start_time
        logger.error(f"Ultra health check failed: {e}")
        return {
            "status": "unhealthy",
            "response_time_ms": round(response_time * 1000, 2),
            "database": "disconnected",
            "cache": {"memory_cache": True, "redis_cache": False},
            "error": str(e)
        }


# Background task functions
async def warm_new_user_cache(user_id: int, email: str, db: AsyncSession):
    """Warm cache for newly created user."""
    try:
        # Warm user cache
        await cached_user_service.get_user_by_id_cached(db, user_id)
        await cached_user_service.get_user_by_email_cached(db, email)
        
        # Warm ranking cache
        await cached_user_service.get_user_ranking_cached(db, user_id)
        
        logger.debug(f"Cache warmed for new user {user_id}")
        
    except Exception as e:
        logger.error(f"Error warming cache for new user {user_id}: {e}")


async def queue_welcome_emails(email: str, name: str):
    """Queue welcome emails in background."""
    try:
        from app.core.dependencies import get_db
        sync_db = next(get_db())
        
        try:
            # Queue welcome email
            email_data = EmailQueueCreate(
                user_email=email,
                user_name=name,
                email_type=EmailType.welcome
            )
            add_email_to_queue(sync_db, email_data)
            
            # Queue campaign emails
            add_campaign_emails_for_user(sync_db, email, name)
            
            logger.debug(f"Welcome emails queued for {email}")
            
        finally:
            sync_db.close()
            
    except Exception as e:
        logger.error(f"Error queuing welcome emails for {email}: {e}")
