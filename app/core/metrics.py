"""
Prometheus Metrics for LawVriksh Application
==========================================

This module provides comprehensive Prometheus metrics collection for
monitoring application performance, database operations, cache efficiency,
and business metrics.

Features:
- Request/response metrics with detailed labels
- Database operation timing and success rates
- Cache hit/miss ratios and performance
- Business metrics (user registrations, shares, etc.)
- Custom performance counters
- Error tracking and alerting metrics
"""

import time
import functools
import logging
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary, Info,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Mock classes for when Prometheus is not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def time(self): return contextmanager(lambda: (yield))()
        def labels(self, *args, **kwargs): return self
    
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Summary:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def time(self): return contextmanager(lambda: (yield))()
        def labels(self, *args, **kwargs): return self
    
    class Info:
        def __init__(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass

logger = logging.getLogger(__name__)

# Create custom registry for better control
registry = CollectorRegistry()

# =============================================================================
# HTTP Request Metrics
# =============================================================================

# Request counter with detailed labels
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code', 'version'],
    registry=registry
)

# Request duration histogram
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint', 'version'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry
)

# Request size histogram
http_request_size_bytes = Histogram(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

# Response size histogram
http_response_size_bytes = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint', 'status_code'],
    registry=registry
)

# Active requests gauge
http_requests_active = Gauge(
    'http_requests_active',
    'Number of active HTTP requests',
    registry=registry
)

# =============================================================================
# Database Metrics
# =============================================================================

# Database operation counter
db_operations_total = Counter(
    'db_operations_total',
    'Total database operations',
    ['operation', 'table', 'status'],
    registry=registry
)

# Database operation duration
db_operation_duration_seconds = Histogram(
    'db_operation_duration_seconds',
    'Database operation duration in seconds',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=registry
)

# Database connection pool metrics
db_connections_active = Gauge(
    'db_connections_active',
    'Number of active database connections',
    registry=registry
)

db_connections_total = Gauge(
    'db_connections_total',
    'Total database connections in pool',
    registry=registry
)

# Database query cache metrics
db_query_cache_hits_total = Counter(
    'db_query_cache_hits_total',
    'Total database query cache hits',
    registry=registry
)

db_query_cache_misses_total = Counter(
    'db_query_cache_misses_total',
    'Total database query cache misses',
    registry=registry
)

# =============================================================================
# Cache Metrics (Redis)
# =============================================================================

# Cache operations counter
cache_operations_total = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'cache_type', 'status'],
    registry=registry
)

# Cache operation duration
cache_operation_duration_seconds = Histogram(
    'cache_operation_duration_seconds',
    'Cache operation duration in seconds',
    ['operation', 'cache_type'],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    registry=registry
)

# Cache hit/miss ratios
cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type', 'key_pattern'],
    registry=registry
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type', 'key_pattern'],
    registry=registry
)

# Cache memory usage
cache_memory_usage_bytes = Gauge(
    'cache_memory_usage_bytes',
    'Cache memory usage in bytes',
    ['cache_type'],
    registry=registry
)

# Cache keys count
cache_keys_total = Gauge(
    'cache_keys_total',
    'Total number of keys in cache',
    ['cache_type'],
    registry=registry
)

# =============================================================================
# Business Metrics
# =============================================================================

# User registrations
user_registrations_total = Counter(
    'user_registrations_total',
    'Total user registrations',
    ['registration_type', 'status'],
    registry=registry
)

# User logins
user_logins_total = Counter(
    'user_logins_total',
    'Total user logins',
    ['login_type', 'status'],
    registry=registry
)

# Share events
share_events_total = Counter(
    'share_events_total',
    'Total share events',
    ['platform', 'status'],
    registry=registry
)

# Email operations
email_operations_total = Counter(
    'email_operations_total',
    'Total email operations',
    ['email_type', 'status'],
    registry=registry
)

# Active users gauge
active_users_total = Gauge(
    'active_users_total',
    'Total number of active users',
    registry=registry
)

# User ranking operations
ranking_operations_total = Counter(
    'ranking_operations_total',
    'Total ranking operations',
    ['operation_type', 'status'],
    registry=registry
)

ranking_calculation_duration_seconds = Histogram(
    'ranking_calculation_duration_seconds',
    'Ranking calculation duration in seconds',
    ['operation_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=registry
)

# =============================================================================
# Performance Metrics
# =============================================================================

# Response time percentiles
response_time_summary = Summary(
    'response_time_summary_seconds',
    'Response time summary in seconds',
    ['endpoint', 'version'],
    registry=registry
)

# Error rates
error_rate_total = Counter(
    'error_rate_total',
    'Total errors by type',
    ['error_type', 'endpoint', 'severity'],
    registry=registry
)

# Memory usage
memory_usage_bytes = Gauge(
    'memory_usage_bytes',
    'Memory usage in bytes',
    ['memory_type'],
    registry=registry
)

# CPU usage
cpu_usage_percent = Gauge(
    'cpu_usage_percent',
    'CPU usage percentage',
    registry=registry
)

# =============================================================================
# Application Info
# =============================================================================

# Application info
app_info = Info(
    'app_info',
    'Application information',
    registry=registry
)

# =============================================================================
# Metric Helper Functions
# =============================================================================

class MetricsCollector:
    """Helper class for collecting and managing metrics."""
    
    def __init__(self):
        self.start_time = time.time()
        
    def record_request(self, method: str, endpoint: str, status_code: int, 
                      duration: float, request_size: int = 0, response_size: int = 0,
                      version: str = "v1"):
        """Record HTTP request metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
            
        try:
            http_requests_total.labels(
                method=method, 
                endpoint=endpoint, 
                status_code=str(status_code),
                version=version
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method, 
                endpoint=endpoint,
                version=version
            ).observe(duration)
            
            if request_size > 0:
                http_request_size_bytes.labels(
                    method=method, 
                    endpoint=endpoint
                ).observe(request_size)
            
            if response_size > 0:
                http_response_size_bytes.labels(
                    method=method, 
                    endpoint=endpoint, 
                    status_code=str(status_code)
                ).observe(response_size)
                
            response_time_summary.labels(
                endpoint=endpoint,
                version=version
            ).observe(duration)
            
        except Exception as e:
            logger.error(f"Error recording request metrics: {e}")
    
    def record_db_operation(self, operation: str, table: str, duration: float, 
                           status: str = "success"):
        """Record database operation metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
            
        try:
            db_operations_total.labels(
                operation=operation, 
                table=table, 
                status=status
            ).inc()
            
            db_operation_duration_seconds.labels(
                operation=operation, 
                table=table
            ).observe(duration)
            
        except Exception as e:
            logger.error(f"Error recording DB metrics: {e}")
    
    def record_cache_operation(self, operation: str, cache_type: str, 
                              duration: float, hit: bool = False, 
                              key_pattern: str = "unknown"):
        """Record cache operation metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
            
        try:
            status = "hit" if hit else "miss"
            
            cache_operations_total.labels(
                operation=operation, 
                cache_type=cache_type, 
                status=status
            ).inc()
            
            cache_operation_duration_seconds.labels(
                operation=operation, 
                cache_type=cache_type
            ).observe(duration)
            
            if hit:
                cache_hits_total.labels(
                    cache_type=cache_type, 
                    key_pattern=key_pattern
                ).inc()
            else:
                cache_misses_total.labels(
                    cache_type=cache_type, 
                    key_pattern=key_pattern
                ).inc()
                
        except Exception as e:
            logger.error(f"Error recording cache metrics: {e}")
    
    def record_business_event(self, event_type: str, status: str = "success", 
                             **labels):
        """Record business event metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
            
        try:
            if event_type == "user_registration":
                user_registrations_total.labels(
                    registration_type=labels.get("registration_type", "standard"),
                    status=status
                ).inc()
            elif event_type == "user_login":
                user_logins_total.labels(
                    login_type=labels.get("login_type", "standard"),
                    status=status
                ).inc()
            elif event_type == "share_event":
                share_events_total.labels(
                    platform=labels.get("platform", "unknown"),
                    status=status
                ).inc()
            elif event_type == "email_operation":
                email_operations_total.labels(
                    email_type=labels.get("email_type", "unknown"),
                    status=status
                ).inc()
                
        except Exception as e:
            logger.error(f"Error recording business metrics: {e}")
    
    def update_system_metrics(self):
        """Update system-level metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
            
        try:
            import psutil
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage_bytes.labels(memory_type="used").set(memory.used)
            memory_usage_bytes.labels(memory_type="available").set(memory.available)
            memory_usage_bytes.labels(memory_type="total").set(memory.total)
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_usage_percent.set(cpu_percent)
            
        except ImportError:
            logger.warning("psutil not available for system metrics")
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")


# Global metrics collector instance
metrics = MetricsCollector()

# =============================================================================
# Decorators for Automatic Metrics Collection
# =============================================================================

def track_time(metric_name: str = None, labels: Dict[str, str] = None):
    """Decorator to track execution time of functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Record metrics based on function name or custom metric
                if metric_name:
                    # Custom metric recording logic here
                    pass
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                # Record error metrics
                error_rate_total.labels(
                    error_type=type(e).__name__,
                    endpoint=func.__name__,
                    severity="error"
                ).inc()
                raise
        return wrapper
    return decorator


def get_metrics() -> str:
    """Get Prometheus metrics in text format."""
    if not PROMETHEUS_AVAILABLE:
        return "# Prometheus not available\n"
    
    try:
        return generate_latest(registry).decode('utf-8')
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return f"# Error generating metrics: {e}\n"


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST if PROMETHEUS_AVAILABLE else "text/plain"


# Initialize application info
if PROMETHEUS_AVAILABLE:
    try:
        app_info.info({
            'version': '2.0',
            'name': 'lawvriksh-referral',
            'description': 'LawVriksh Referral Platform with Ultra Performance',
            'python_version': '3.11+',
            'features': 'redis_cache,async_db,prometheus_monitoring'
        })
    except Exception as e:
        logger.error(f"Error setting app info: {e}")


# Export commonly used metrics
__all__ = [
    'metrics',
    'get_metrics',
    'get_metrics_content_type',
    'track_time',
    'http_requests_total',
    'http_request_duration_seconds',
    'db_operations_total',
    'cache_operations_total',
    'user_registrations_total',
    'registry'
]
