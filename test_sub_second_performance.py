#!/usr/bin/env python3
"""
Sub-Second Performance Test Suite
================================

This script tests the ultra-fast optimizations to ensure sub-second response times.

Target Performance:
- Signup: <500ms
- Login (cached): <100ms  
- Login (uncached): <300ms
- Get user info: <50ms
- Health check: <10ms

Usage:
    python test_sub_second_performance.py
"""

import asyncio
import time
import sys
import os
import logging
import statistics
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import requests
import json
from dataclasses import dataclass
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceResult:
    """Performance test result."""
    endpoint: str
    method: str
    success_count: int
    total_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    success_rate: float
    target_ms: float
    meets_target: bool


class SubSecondPerformanceTester:
    """Comprehensive performance tester for sub-second targets."""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.ultra_auth_url = f"{base_url}/ultra-auth"
        self.async_auth_url = f"{base_url}/async-auth"
        self.sync_auth_url = f"{base_url}/auth"
        
        # Performance targets (in seconds)
        self.targets = {
            'ultra_signup': 0.5,      # 500ms
            'ultra_login_cached': 0.1,    # 100ms
            'ultra_login_uncached': 0.3,  # 300ms
            'ultra_get_me': 0.05,     # 50ms
            'ultra_health': 0.01,     # 10ms
            'async_signup': 1.0,      # 1 second
            'async_login': 0.5,       # 500ms
            'sync_signup': 2.0,       # 2 seconds (baseline)
            'sync_login': 1.0,        # 1 second (baseline)
        }
    
    async def test_endpoint_async(self, session, url, method="GET", data=None, headers=None):
        """Test a single endpoint asynchronously."""
        start_time = time.time()
        
        try:
            if method == "POST":
                async with session.post(url, json=data, headers=headers) as response:
                    content = await response.read()
                    end_time = time.time()
                    
                    return {
                        "success": response.status < 400,
                        "status_code": response.status,
                        "response_time": end_time - start_time,
                        "content_length": len(content) if content else 0,
                        "response_data": await response.json() if response.content_type == 'application/json' else None
                    }
            else:
                async with session.get(url, headers=headers) as response:
                    content = await response.read()
                    end_time = time.time()
                    
                    return {
                        "success": response.status < 400,
                        "status_code": response.status,
                        "response_time": end_time - start_time,
                        "content_length": len(content) if content else 0,
                        "response_data": await response.json() if response.content_type == 'application/json' else None
                    }
                    
        except Exception as e:
            end_time = time.time()
            return {
                "success": False,
                "error": str(e),
                "response_time": end_time - start_time,
                "content_length": 0
            }
    
    async def run_concurrent_test(self, endpoint, method="GET", data=None, headers=None, 
                                concurrent_requests=10, test_name="test"):
        """Run concurrent test on an endpoint."""
        logger.info(f"Running {test_name}: {concurrent_requests} concurrent requests to {endpoint}")
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.test_endpoint_async(session, endpoint, method, data, headers)
                for _ in range(concurrent_requests)
            ]
            
            results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Analyze results
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]
        
        if successful_results:
            response_times = [r["response_time"] for r in successful_results]
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 1 else avg_response_time
            p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) > 1 else avg_response_time
        else:
            avg_response_time = min_response_time = max_response_time = p95_response_time = p99_response_time = 0
        
        success_rate = len(successful_results) / len(results) * 100 if results else 0
        target_ms = self.targets.get(test_name, 1.0)
        meets_target = avg_response_time <= target_ms if successful_results else False
        
        return PerformanceResult(
            endpoint=endpoint,
            method=method,
            success_count=len(successful_results),
            total_requests=len(results),
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            success_rate=success_rate,
            target_ms=target_ms,
            meets_target=meets_target
        )
    
    async def test_ultra_fast_endpoints(self):
        """Test ultra-fast endpoints for sub-second performance."""
        results = []
        
        # Test ultra-fast health check (target: <10ms)
        logger.info("Testing ultra-fast health check...")
        health_result = await self.run_concurrent_test(
            f"{self.ultra_auth_url}/health",
            concurrent_requests=20,
            test_name="ultra_health"
        )
        results.append(health_result)
        
        # Test ultra-fast signup (target: <500ms)
        logger.info("Testing ultra-fast signup...")
        signup_data = {
            "name": "Test User",
            "email": f"test_{int(time.time())}@example.com",
            "password": "testpassword123"
        }
        signup_result = await self.run_concurrent_test(
            f"{self.ultra_auth_url}/signup",
            method="POST",
            data=signup_data,
            concurrent_requests=5,  # Lower concurrency for signup
            test_name="ultra_signup"
        )
        results.append(signup_result)
        
        # Test ultra-fast login (target: <300ms uncached, <100ms cached)
        logger.info("Testing ultra-fast login...")
        login_data = {
            "email": signup_data["email"],
            "password": signup_data["password"]
        }
        login_result = await self.run_concurrent_test(
            f"{self.ultra_auth_url}/login",
            method="POST",
            data=login_data,
            concurrent_requests=10,
            test_name="ultra_login_uncached"
        )
        results.append(login_result)
        
        # Test cached login (run again for cache hits)
        logger.info("Testing ultra-fast cached login...")
        cached_login_result = await self.run_concurrent_test(
            f"{self.ultra_auth_url}/login",
            method="POST",
            data=login_data,
            concurrent_requests=20,
            test_name="ultra_login_cached"
        )
        results.append(cached_login_result)
        
        # Test ultra-fast get user info (target: <50ms)
        if login_result.success_count > 0:
            # Get token from login result
            token = None
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.ultra_auth_url}/login", json=login_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        token = data.get("access_token")
            
            if token:
                logger.info("Testing ultra-fast get user info...")
                headers = {"Authorization": f"Bearer {token}"}
                me_result = await self.run_concurrent_test(
                    f"{self.ultra_auth_url}/me",
                    headers=headers,
                    concurrent_requests=20,
                    test_name="ultra_get_me"
                )
                results.append(me_result)
        
        return results
    
    async def test_comparison_endpoints(self):
        """Test comparison with async and sync endpoints."""
        results = []
        
        # Test async endpoints
        logger.info("Testing async signup for comparison...")
        async_signup_data = {
            "name": "Async Test User",
            "email": f"async_test_{int(time.time())}@example.com",
            "password": "testpassword123"
        }
        async_signup_result = await self.run_concurrent_test(
            f"{self.async_auth_url}/signup",
            method="POST",
            data=async_signup_data,
            concurrent_requests=5,
            test_name="async_signup"
        )
        results.append(async_signup_result)
        
        # Test sync endpoints (if server is running)
        try:
            logger.info("Testing sync signup for comparison...")
            sync_signup_data = {
                "name": "Sync Test User",
                "email": f"sync_test_{int(time.time())}@example.com",
                "password": "testpassword123"
            }
            sync_signup_result = await self.run_concurrent_test(
                f"{self.sync_auth_url}/signup",
                method="POST",
                data=sync_signup_data,
                concurrent_requests=5,
                test_name="sync_signup"
            )
            results.append(sync_signup_result)
        except Exception as e:
            logger.warning(f"Sync endpoint test failed: {e}")
        
        return results
    
    def print_results(self, results: List[PerformanceResult]):
        """Print comprehensive performance results."""
        print("\n" + "="*100)
        print("SUB-SECOND PERFORMANCE TEST RESULTS")
        print("="*100)
        
        # Summary table
        print(f"\n{'Endpoint':<25} {'Target':<10} {'Avg Time':<12} {'P95 Time':<12} {'Success Rate':<12} {'Status':<10}")
        print("-" * 100)
        
        for result in results:
            target_str = f"{result.target_ms*1000:.0f}ms"
            avg_str = f"{result.avg_response_time*1000:.1f}ms"
            p95_str = f"{result.p95_response_time*1000:.1f}ms"
            success_str = f"{result.success_rate:.1f}%"
            status = "✅ PASS" if result.meets_target and result.success_rate > 95 else "❌ FAIL"
            
            endpoint_name = result.endpoint.split('/')[-1] or result.endpoint.split('/')[-2]
            
            print(f"{endpoint_name:<25} {target_str:<10} {avg_str:<12} {p95_str:<12} {success_str:<12} {status:<10}")
        
        # Detailed results
        print(f"\n{'='*100}")
        print("DETAILED RESULTS")
        print("="*100)
        
        for result in results:
            print(f"\n📊 {result.endpoint} ({result.method})")
            print(f"   Target: {result.target_ms*1000:.0f}ms")
            print(f"   Requests: {result.total_requests} (Success: {result.success_count})")
            print(f"   Success Rate: {result.success_rate:.2f}%")
            print(f"   Avg Response Time: {result.avg_response_time*1000:.2f}ms")
            print(f"   Min Response Time: {result.min_response_time*1000:.2f}ms")
            print(f"   Max Response Time: {result.max_response_time*1000:.2f}ms")
            print(f"   P95 Response Time: {result.p95_response_time*1000:.2f}ms")
            print(f"   P99 Response Time: {result.p99_response_time*1000:.2f}ms")
            print(f"   Meets Target: {'✅ YES' if result.meets_target else '❌ NO'}")
        
        # Performance summary
        ultra_results = [r for r in results if 'ultra' in r.endpoint]
        if ultra_results:
            avg_ultra_time = statistics.mean([r.avg_response_time for r in ultra_results if r.success_count > 0])
            ultra_success_rate = statistics.mean([r.success_rate for r in ultra_results])
            targets_met = sum(1 for r in ultra_results if r.meets_target and r.success_rate > 95)
            
            print(f"\n🚀 ULTRA-FAST PERFORMANCE SUMMARY:")
            print(f"   Average Response Time: {avg_ultra_time*1000:.2f}ms")
            print(f"   Average Success Rate: {ultra_success_rate:.2f}%")
            print(f"   Targets Met: {targets_met}/{len(ultra_results)}")
            print(f"   Sub-Second Achievement: {'✅ SUCCESS' if avg_ultra_time < 1.0 else '❌ NEEDS IMPROVEMENT'}")
        
        print("\n" + "="*100)


async def main():
    """Main test function."""
    logger.info("Starting Sub-Second Performance Test Suite")
    
    tester = SubSecondPerformanceTester()
    
    try:
        # Test ultra-fast endpoints
        ultra_results = await tester.test_ultra_fast_endpoints()
        
        # Test comparison endpoints
        comparison_results = await tester.test_comparison_endpoints()
        
        # Combine and print results
        all_results = ultra_results + comparison_results
        tester.print_results(all_results)
        
        # Check if we achieved sub-second performance
        ultra_results_only = [r for r in ultra_results if r.success_count > 0]
        if ultra_results_only:
            avg_time = statistics.mean([r.avg_response_time for r in ultra_results_only])
            if avg_time < 1.0:
                print(f"\n🎉 SUCCESS: Achieved sub-second performance! Average: {avg_time*1000:.2f}ms")
            else:
                print(f"\n⚠️  IMPROVEMENT NEEDED: Average time {avg_time*1000:.2f}ms exceeds 1 second")
        
    except Exception as e:
        logger.error(f"Performance test failed: {e}")
        print(f"\n❌ Test failed: {e}")
        print("\nMake sure the server is running with:")
        print("   python start_server.py --workers 8")


if __name__ == "__main__":
    # Install required packages if not available
    try:
        import aiohttp
    except ImportError:
        print("Installing required packages...")
        os.system("pip install aiohttp")
        import aiohttp
    
    asyncio.run(main())
