"""
LawVriksh Test Suite
==================

Comprehensive test suite for the LawVriksh ultra-fast referral platform.

Test Categories:
- Unit Tests: Individual component testing
- Integration Tests: API endpoint testing
- Performance Tests: Response time and throughput validation
- Load Tests: High concurrency and stress testing
- Security Tests: Authentication and authorization testing
- Database Tests: Database operation and optimization testing
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test configuration
TEST_CONFIG = {
    'base_url': 'http://localhost:8000',
    'test_timeout': 30,
    'performance_targets': {
        'ultra_fast_response_time_ms': 100,
        'async_response_time_ms': 500,
        'sync_response_time_ms': 2000,
        'success_rate_percent': 99.0,
        'cache_hit_rate_percent': 90.0
    },
    'load_test_config': {
        'concurrent_users': 50,
        'test_duration_seconds': 60,
        'ramp_up_seconds': 10
    }
}

__version__ = "2.0.0"
__all__ = ['TEST_CONFIG']