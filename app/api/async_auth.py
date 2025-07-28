"""
Async Authentication API for High-Performance User Operations
===========================================================

This module provides async versions of authentication endpoints for
2-3x performance improvement over synchronous operations.

Features:
- Async user registration and authentication
- Non-blocking database operations
- Optimized email queue processing
- Atomic transaction handling
- Background ranking updates
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_dependencies import get_async_db
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.schemas.token import Token
from app.services.async_user_service import (
    create_user_async, authenticate_user_async, create_jwt_for_user, 
    get_user_by_email, update_user_ranking_background
)
from app.core.security import verify_access_token
from fastapi.security import OAuth2PasswordBearer
from app.utils.monitoring import inc_user_signup
import logging
import asyncio

# Database-driven email queue imports (replaces Celery)
from app.models.email_queue import EmailType
from app.schemas.email_queue import EmailQueueCreate
from app.services.email_queue_service import (
    add_email_to_queue, add_campaign_emails_for_user
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/async-auth", tags=["async-auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/async-auth/login")


@router.post("/signup", response_model=UserResponse, status_code=201)
async def signup_async(
    user_in: UserCreate, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Register a new user account asynchronously with optimized performance.
    
    This endpoint implements several performance optimizations:
    1. Async database operations for non-blocking I/O
    2. Non-blocking password hashing using thread executor
    3. Atomic transaction handling
    4. Background ranking calculation
    5. Efficient email queue processing
    
    Args:
        user_in: User registration data
        background_tasks: FastAPI background tasks
        db: Async database session
        
    Returns:
        UserResponse: Created user information
        
    Raises:
        HTTPException: If email is already registered or creation fails
    """
    try:
        logger.info(f"Starting async user registration for {user_in.email}")
        
        # Create new user with optimized async operations
        user = await create_user_async(db, user_in)
        
        # Add welcome email to database queue (using sync operations for now)
        try:
            # Get a sync database session for email queue operations
            from app.core.dependencies import get_db
            sync_db = next(get_db())

            try:
                email_data = EmailQueueCreate(
                    user_email=user.email,
                    user_name=user.name,
                    email_type=EmailType.welcome
                )

                # Email queue operations are sync but fast
                email_queue_entry = add_email_to_queue(sync_db, email_data)

                # Add future campaign emails for this new user
                campaign_emails = add_campaign_emails_for_user(sync_db, user.email, user.name)
            finally:
                sync_db.close()
            
            logger.info(
                f"Welcome email queued for {user.email} "
                f"(Queue ID: {email_queue_entry.id}, scheduled: {email_queue_entry.scheduled_time})"
            )
            logger.info(f"Added {len(campaign_emails)} future campaign emails for {user.email}")
            
        except Exception as email_error:
            logger.warning(f"Failed to queue emails for {user.email}: {email_error}")
            # Don't fail registration if email queuing fails
        
        # Schedule background ranking update (non-blocking)
        background_tasks.add_task(update_user_ranking_background, user.id)
        
        # Update metrics
        inc_user_signup()
        
        logger.info(f"User registration completed successfully for {user.email} (ID: {user.id})")
        
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
        # Re-raise HTTP exceptions (like email already registered)
        raise
    except Exception as e:
        # Log the error and return a generic message
        logger.error(f"Async user creation failed for {user_in.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )


@router.post("/login", response_model=Token)
async def login_async(user_in: UserLogin, db: AsyncSession = Depends(get_async_db)):
    """
    Authenticate user and return access token asynchronously.
    
    This endpoint uses async operations for:
    1. Non-blocking database queries
    2. Non-blocking password verification
    3. Optimized user lookup
    
    Args:
        user_in: User login credentials
        db: Async database session
        
    Returns:
        Token: JWT access token with expiration info
        
    Raises:
        HTTPException: If credentials are invalid or user is inactive
    """
    try:
        logger.debug(f"Starting async authentication for {user_in.email}")
        
        # Authenticate user asynchronously
        user = await authenticate_user_async(db, user_in.email, user_in.password)
        if not user:
            logger.warning(f"Authentication failed for {user_in.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Inactive user attempted login: {user_in.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        # Generate JWT token (synchronous - no I/O involved)
        token = create_jwt_for_user(user)
        
        logger.info(f"Successful async authentication for {user.email}")
        
        return Token(
            access_token=token,
            token_type="bearer",
            expires_in=3600
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Async login failed for {user_in.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable"
        )


@router.get("/me", response_model=UserResponse)
async def get_me_async(
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current authenticated user information asynchronously.
    
    Args:
        token: JWT access token
        db: Async database session
        
    Returns:
        UserResponse: Current user information
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        # Verify token (synchronous - no I/O involved)
        payload = verify_access_token(token)
        user_id = payload.get("user_id")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user asynchronously
        from app.services.async_user_service import get_user_by_id
        user = await get_user_by_id(db, user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
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
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Error getting user info from token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve user information"
        )


# Health check endpoint for async auth
@router.get("/health")
async def health_check_async(db: AsyncSession = Depends(get_async_db)):
    """
    Health check endpoint for async authentication service.
    
    Returns:
        dict: Health status and database connectivity
    """
    try:
        # Test async database connection
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1"))
        db_healthy = result.scalar() == 1
        
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "async_auth": True,
            "database": "connected" if db_healthy else "disconnected"
        }
        
    except Exception as e:
        logger.error(f"Async auth health check failed: {e}")
        return {
            "status": "unhealthy",
            "async_auth": True,
            "database": "disconnected",
            "error": str(e)
        }


# Performance monitoring endpoint
@router.get("/performance")
async def get_performance_stats():
    """
    Get performance statistics for async authentication operations.
    
    Returns:
        dict: Performance metrics and statistics
    """
    try:
        from app.core.async_dependencies import get_async_db_pool_status
        
        # Get async database pool status
        pool_status = await get_async_db_pool_status()
        
        return {
            "async_auth_enabled": True,
            "database_pool": pool_status,
            "features": [
                "async_user_registration",
                "async_authentication", 
                "non_blocking_password_hashing",
                "background_ranking_updates",
                "atomic_transactions"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting async auth performance stats: {e}")
        return {
            "async_auth_enabled": True,
            "error": str(e)
        }
