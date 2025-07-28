"""
User Statistics Model for Optimized Ranking Operations
=====================================================

This model maintains denormalized user counters for O(1) ranking operations,
replacing expensive COUNT(*) queries with fast table lookups.

Features:
- Automatic maintenance via database triggers
- Real-time user statistics
- Optimized ranking calculations
- Performance monitoring
"""

from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.sql import func as sql_func
from app.core.database import Base
from datetime import datetime


class UserStats(Base):
    """
    User statistics table for optimized ranking operations.
    
    This table is automatically maintained by database triggers and provides
    O(1) access to user counts instead of expensive COUNT(*) queries.
    """
    __tablename__ = "user_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    total_users = Column(Integer, nullable=False, default=0)
    total_active_users = Column(Integer, nullable=False, default=0)
    total_admin_users = Column(Integer, nullable=False, default=0)
    last_updated = Column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        server_default=sql_func.current_timestamp(),
        server_onupdate=sql_func.current_timestamp()
    )
    created_at = Column(
        DateTime, 
        default=datetime.utcnow,
        server_default=sql_func.current_timestamp()
    )
    
    def __repr__(self):
        return (
            f"<UserStats(total_users={self.total_users}, "
            f"active={self.total_active_users}, "
            f"admin={self.total_admin_users}, "
            f"updated={self.last_updated})>"
        )
    
    @property
    def non_admin_users(self) -> int:
        """Get count of non-admin users."""
        return self.total_users - self.total_admin_users
    
    @property
    def active_non_admin_users(self) -> int:
        """Get count of active non-admin users."""
        return self.total_active_users - self.total_admin_users
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "total_users": self.total_users,
            "total_active_users": self.total_active_users,
            "total_admin_users": self.total_admin_users,
            "non_admin_users": self.non_admin_users,
            "active_non_admin_users": self.active_non_admin_users,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
