"""
Prometheus Middleware for FastAPI
================================

This middleware automatically collects Prometheus metrics for all HTTP requests,
providing comprehensive observability without manual instrumentation.

Features:
- Automatic request/response metrics collection
- Performance timing and sizing
- Error tracking and status code distribution
- Cache performance monitoring
- Database operation tracking
- Custom business metrics integration
"""

import time
import logging
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.metrics import (
    metrics, 
    http_requests_active,
    error_rate_total,
    PROMETHEUS_AVAILABLE
)

logger = logging.getLogger(__name__)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic Prometheus metrics collection.
    
    This middleware tracks:
    - Request count by method, endpoint, and status code
    - Request/response duration and size
    - Active request count
    - Error rates and types
    - Performance percentiles
    """
    
    def __init__(self, app: ASGIApp, app_name: str = "lawvriksh-api"):
        super().__init__(app)
        self.app_name = app_name
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        if not PROMETHEUS_AVAILABLE:
            return await call_next(request)
        
        # Skip metrics collection for the metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)
        
        # Extract request information
        method = request.method
        path = request.url.path
        endpoint = self._get_endpoint_name(path)
        
        # Get request size
        request_size = self._get_request_size(request)
        
        # Track active requests
        http_requests_active.inc()
        
        # Start timing
        start_time = time.time()
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate metrics
            duration = time.time() - start_time
            status_code = response.status_code
            response_size = self._get_response_size(response)
            
            # Determine API version
            version = self._get_api_version(path)
            
            # Record metrics
            metrics.record_request(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                duration=duration,
                request_size=request_size,
                response_size=response_size,
                version=version
            )
            
            # Log slow requests
            if duration > 1.0:  # Log requests slower than 1 second
                logger.warning(
                    f"Slow request: {method} {path} took {duration:.3f}s "
                    f"(status: {status_code})"
                )
            
            # Log errors
            if status_code >= 400:
                error_type = self._get_error_type(status_code)
                severity = "error" if status_code >= 500 else "warning"
                
                if PROMETHEUS_AVAILABLE:
                    error_rate_total.labels(
                        error_type=error_type,
                        endpoint=endpoint,
                        severity=severity
                    ).inc()
                
                logger.error(
                    f"Request error: {method} {path} returned {status_code} "
                    f"in {duration:.3f}s"
                )
            
            return response
            
        except Exception as e:
            # Handle exceptions
            duration = time.time() - start_time
            
            # Record error metrics
            if PROMETHEUS_AVAILABLE:
                error_rate_total.labels(
                    error_type=type(e).__name__,
                    endpoint=endpoint,
                    severity="error"
                ).inc()
            
            # Record failed request
            metrics.record_request(
                method=method,
                endpoint=endpoint,
                status_code=500,
                duration=duration,
                request_size=request_size,
                response_size=0,
                version=self._get_api_version(path)
            )
            
            logger.error(
                f"Request exception: {method} {path} failed with {type(e).__name__}: {e} "
                f"after {duration:.3f}s"
            )
            
            raise
            
        finally:
            # Always decrement active requests
            if PROMETHEUS_AVAILABLE:
                http_requests_active.dec()
    
    def _get_endpoint_name(self, path: str) -> str:
        """
        Extract a clean endpoint name from the request path.
        
        This normalizes paths with IDs and parameters to avoid
        high cardinality in metrics.
        """
        # Remove query parameters
        path = path.split('?')[0]
        
        # Normalize common patterns
        path_parts = path.strip('/').split('/')
        normalized_parts = []
        
        for part in path_parts:
            # Replace numeric IDs with placeholder
            if part.isdigit():
                normalized_parts.append('{id}')
            # Replace UUIDs with placeholder
            elif len(part) == 36 and part.count('-') == 4:
                normalized_parts.append('{uuid}')
            # Replace email-like patterns
            elif '@' in part:
                normalized_parts.append('{email}')
            else:
                normalized_parts.append(part)
        
        normalized_path = '/' + '/'.join(normalized_parts) if normalized_parts else '/'
        
        # Limit endpoint name length to avoid memory issues
        if len(normalized_path) > 100:
            normalized_path = normalized_path[:97] + '...'
        
        return normalized_path
    
    def _get_api_version(self, path: str) -> str:
        """Extract API version from path."""
        if '/ultra-auth/' in path:
            return 'ultra'
        elif '/async-auth/' in path:
            return 'async'
        elif '/auth/' in path:
            return 'sync'
        elif '/api/v' in path:
            # Extract version like /api/v1/
            parts = path.split('/')
            for part in parts:
                if part.startswith('v') and part[1:].isdigit():
                    return part
        
        return 'v1'  # Default version
    
    def _get_request_size(self, request: Request) -> int:
        """Get request size in bytes."""
        try:
            content_length = request.headers.get('content-length')
            if content_length:
                return int(content_length)
        except (ValueError, TypeError):
            pass
        
        return 0
    
    def _get_response_size(self, response: Response) -> int:
        """Get response size in bytes."""
        try:
            content_length = response.headers.get('content-length')
            if content_length:
                return int(content_length)
            
            # Estimate size from body if available
            if hasattr(response, 'body') and response.body:
                return len(response.body)
                
        except (ValueError, TypeError, AttributeError):
            pass
        
        return 0
    
    def _get_error_type(self, status_code: int) -> str:
        """Get error type based on status code."""
        if status_code == 400:
            return "bad_request"
        elif status_code == 401:
            return "unauthorized"
        elif status_code == 403:
            return "forbidden"
        elif status_code == 404:
            return "not_found"
        elif status_code == 422:
            return "validation_error"
        elif status_code == 429:
            return "rate_limit"
        elif status_code == 500:
            return "internal_server_error"
        elif status_code == 502:
            return "bad_gateway"
        elif status_code == 503:
            return "service_unavailable"
        elif status_code == 504:
            return "gateway_timeout"
        elif 400 <= status_code < 500:
            return "client_error"
        elif 500 <= status_code < 600:
            return "server_error"
        else:
            return "unknown_error"


class DatabaseMetricsMiddleware:
    """
    Middleware for tracking database operations.
    
    This can be used as a context manager or decorator
    to automatically track database operation metrics.
    """
    
    def __init__(self, operation: str, table: str):
        self.operation = operation
        self.table = table
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            status = "error" if exc_type else "success"
            
            metrics.record_db_operation(
                operation=self.operation,
                table=self.table,
                duration=duration,
                status=status
            )
            
            if exc_type:
                logger.error(
                    f"Database operation failed: {self.operation} on {self.table} "
                    f"after {duration:.3f}s - {exc_type.__name__}: {exc_val}"
                )
            elif duration > 0.1:  # Log slow queries
                logger.warning(
                    f"Slow database operation: {self.operation} on {self.table} "
                    f"took {duration:.3f}s"
                )


class CacheMetricsMiddleware:
    """
    Middleware for tracking cache operations.
    
    This can be used as a context manager to automatically
    track cache operation metrics.
    """
    
    def __init__(self, operation: str, cache_type: str = "redis", 
                 key_pattern: str = "unknown"):
        self.operation = operation
        self.cache_type = cache_type
        self.key_pattern = key_pattern
        self.start_time = None
        self.hit = False
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            
            metrics.record_cache_operation(
                operation=self.operation,
                cache_type=self.cache_type,
                duration=duration,
                hit=self.hit,
                key_pattern=self.key_pattern
            )
    
    def set_hit(self, hit: bool):
        """Mark whether this was a cache hit or miss."""
        self.hit = hit


# Convenience functions for manual instrumentation
def track_db_operation(operation: str, table: str):
    """Context manager for tracking database operations."""
    return DatabaseMetricsMiddleware(operation, table)


def track_cache_operation(operation: str, cache_type: str = "redis", 
                         key_pattern: str = "unknown"):
    """Context manager for tracking cache operations."""
    return CacheMetricsMiddleware(operation, cache_type, key_pattern)


# Export commonly used classes and functions
__all__ = [
    'PrometheusMiddleware',
    'DatabaseMetricsMiddleware', 
    'CacheMetricsMiddleware',
    'track_db_operation',
    'track_cache_operation'
]
