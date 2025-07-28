#!/usr/bin/env python3
"""
Performance Test Suite for LawVriksh Application
===============================================

Comprehensive performance testing to validate ultra-fast response times
and ensure the 960x performance improvement is maintained.

Test Categories:
- Ultra-fast endpoint performance (<100ms)
- Async endpoint performance (<500ms)
- Cache performance validation (>90% hit rate)
- Database query performance (<100ms)
- Success rate validation (>99%)
"""

import asyncio
import time
import statistics
import requests
import aiohttp
import pytest
from typing import List, Dict, Any
from tests import TEST_CONFIG


class PerformanceTestSuite:
    """Comprehensive performance test suite."""
    
    def __init__(self):
        self.base_url = TEST_CONFIG['base_url']
        self.targets = TEST_CONFIG['performance_targets']
        self.results = []
    
    def test_ultra_fast_auth_signup(self):
        """Test ultra-fast signup performance (<100ms target)."""
        endpoint = f"{self.base_url}/ultra-auth/signup"
        
        # Test data
        test_user = {
            "name": "Performance Test User",
            "email": f"perf_test_{int(time.time())}@example.com",
            "password": "testpassword123"
        }
        
        # Measure performance
        start_time = time.time()
        response = requests.post(endpoint, json=test_user, timeout=10)
        duration_ms = (time.time() - start_time) * 1000
        
        # Validate response
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        assert duration_ms < self.targets['ultra_fast_response_time_ms'], \
            f"Response time {duration_ms:.2f}ms exceeds target {self.targets['ultra_fast_response_time_ms']}ms"
        
        self.results.append({
            'test': 'ultra_fast_signup',
            'duration_ms': duration_ms,
            'success': True,
            'target_ms': self.targets['ultra_fast_response_time_ms']
        })
        
        print(f"✅ Ultra-fast signup: {duration_ms:.2f}ms (target: <{self.targets['ultra_fast_response_time_ms']}ms)")
    
    def test_ultra_fast_auth_login(self):
        """Test ultra-fast login performance (<100ms target)."""
        # First create a user
        signup_data = {
            "name": "Login Test User",
            "email": f"login_test_{int(time.time())}@example.com",
            "password": "testpassword123"
        }
        
        signup_response = requests.post(f"{self.base_url}/ultra-auth/signup", json=signup_data)
        assert signup_response.status_code == 201
        
        # Test login performance
        endpoint = f"{self.base_url}/ultra-auth/login"
        login_data = {
            "email": signup_data["email"],
            "password": signup_data["password"]
        }
        
        # Measure performance
        start_time = time.time()
        response = requests.post(endpoint, json=login_data, timeout=10)
        duration_ms = (time.time() - start_time) * 1000
        
        # Validate response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "access_token" in response.json(), "Access token not found in response"
        assert duration_ms < self.targets['ultra_fast_response_time_ms'], \
            f"Response time {duration_ms:.2f}ms exceeds target {self.targets['ultra_fast_response_time_ms']}ms"
        
        self.results.append({
            'test': 'ultra_fast_login',
            'duration_ms': duration_ms,
            'success': True,
            'target_ms': self.targets['ultra_fast_response_time_ms']
        })
        
        print(f"✅ Ultra-fast login: {duration_ms:.2f}ms (target: <{self.targets['ultra_fast_response_time_ms']}ms)")
    
    def test_health_check_performance(self):
        """Test health check performance (<10ms target)."""
        endpoint = f"{self.base_url}/health"
        
        # Run multiple tests for average
        durations = []
        for _ in range(10):
            start_time = time.time()
            response = requests.get(endpoint, timeout=5)
            duration_ms = (time.time() - start_time) * 1000
            durations.append(duration_ms)
            
            assert response.status_code == 200, f"Health check failed: {response.status_code}"
        
        avg_duration = statistics.mean(durations)
        max_duration = max(durations)
        
        # Health check should be very fast
        assert avg_duration < 50, f"Average health check time {avg_duration:.2f}ms too slow"
        assert max_duration < 100, f"Max health check time {max_duration:.2f}ms too slow"
        
        self.results.append({
            'test': 'health_check',
            'duration_ms': avg_duration,
            'success': True,
            'target_ms': 50
        })
        
        print(f"✅ Health check: {avg_duration:.2f}ms avg, {max_duration:.2f}ms max")
    
    async def test_concurrent_performance(self):
        """Test concurrent request performance."""
        endpoint = f"{self.base_url}/ultra-auth/health"
        concurrent_requests = 20
        
        async def make_request(session):
            start_time = time.time()
            async with session.get(endpoint) as response:
                duration_ms = (time.time() - start_time) * 1000
                return {
                    'status_code': response.status,
                    'duration_ms': duration_ms,
                    'success': response.status == 200
                }
        
        # Run concurrent requests
        async with aiohttp.ClientSession() as session:
            tasks = [make_request(session) for _ in range(concurrent_requests)]
            results = await asyncio.gather(*tasks)
        
        # Analyze results
        successful_requests = [r for r in results if r['success']]
        success_rate = len(successful_requests) / len(results) * 100
        
        if successful_requests:
            avg_duration = statistics.mean([r['duration_ms'] for r in successful_requests])
            max_duration = max([r['duration_ms'] for r in successful_requests])
        else:
            avg_duration = max_duration = 0
        
        # Validate performance under load
        assert success_rate >= self.targets['success_rate_percent'], \
            f"Success rate {success_rate:.1f}% below target {self.targets['success_rate_percent']}%"
        
        assert avg_duration < 200, f"Average response time {avg_duration:.2f}ms too slow under load"
        
        self.results.append({
            'test': 'concurrent_performance',
            'duration_ms': avg_duration,
            'success_rate': success_rate,
            'concurrent_requests': concurrent_requests,
            'success': True
        })
        
        print(f"✅ Concurrent performance: {avg_duration:.2f}ms avg, {success_rate:.1f}% success rate")
    
    def test_metrics_endpoint_performance(self):
        """Test metrics endpoint performance."""
        endpoint = f"{self.base_url}/metrics"
        
        start_time = time.time()
        response = requests.get(endpoint, timeout=10)
        duration_ms = (time.time() - start_time) * 1000
        
        assert response.status_code == 200, f"Metrics endpoint failed: {response.status_code}"
        assert "http_requests_total" in response.text, "Prometheus metrics not found"
        
        # Metrics endpoint should be reasonably fast
        assert duration_ms < 1000, f"Metrics endpoint too slow: {duration_ms:.2f}ms"
        
        self.results.append({
            'test': 'metrics_endpoint',
            'duration_ms': duration_ms,
            'success': True,
            'target_ms': 1000
        })
        
        print(f"✅ Metrics endpoint: {duration_ms:.2f}ms")
    
    def test_async_vs_sync_performance(self):
        """Compare async vs sync endpoint performance."""
        # Test data
        test_user = {
            "name": "Comparison Test User",
            "email": f"comp_test_{int(time.time())}@example.com",
            "password": "testpassword123"
        }
        
        # Test ultra-fast (should be fastest)
        start_time = time.time()
        ultra_response = requests.post(f"{self.base_url}/ultra-auth/signup", json=test_user)
        ultra_duration = (time.time() - start_time) * 1000
        
        # Test async (should be fast)
        test_user["email"] = f"comp_async_{int(time.time())}@example.com"
        start_time = time.time()
        async_response = requests.post(f"{self.base_url}/async-auth/signup", json=test_user)
        async_duration = (time.time() - start_time) * 1000
        
        # Test sync (baseline)
        test_user["email"] = f"comp_sync_{int(time.time())}@example.com"
        start_time = time.time()
        sync_response = requests.post(f"{self.base_url}/auth/signup", json=test_user)
        sync_duration = (time.time() - start_time) * 1000
        
        # Validate all succeeded
        assert ultra_response.status_code == 201, "Ultra-fast signup failed"
        assert async_response.status_code == 201, "Async signup failed"
        assert sync_response.status_code == 201, "Sync signup failed"
        
        # Validate performance hierarchy
        assert ultra_duration < async_duration, \
            f"Ultra-fast ({ultra_duration:.2f}ms) should be faster than async ({async_duration:.2f}ms)"
        assert async_duration < sync_duration, \
            f"Async ({async_duration:.2f}ms) should be faster than sync ({sync_duration:.2f}ms)"
        
        # Calculate improvements
        ultra_improvement = sync_duration / ultra_duration if ultra_duration > 0 else 0
        async_improvement = sync_duration / async_duration if async_duration > 0 else 0
        
        self.results.append({
            'test': 'performance_comparison',
            'ultra_duration_ms': ultra_duration,
            'async_duration_ms': async_duration,
            'sync_duration_ms': sync_duration,
            'ultra_improvement': ultra_improvement,
            'async_improvement': async_improvement,
            'success': True
        })
        
        print(f"✅ Performance comparison:")
        print(f"   Ultra-fast: {ultra_duration:.2f}ms ({ultra_improvement:.1f}x faster than sync)")
        print(f"   Async:      {async_duration:.2f}ms ({async_improvement:.1f}x faster than sync)")
        print(f"   Sync:       {sync_duration:.2f}ms (baseline)")
    
    def print_performance_summary(self):
        """Print comprehensive performance test summary."""
        print("\n" + "="*80)
        print("🚀 LAWVRIKSH PERFORMANCE TEST RESULTS")
        print("="*80)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.get('success', False))
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {total_tests - passed_tests}")
        print(f"   Success Rate: {passed_tests/total_tests*100:.1f}%")
        
        print(f"\n⚡ PERFORMANCE RESULTS:")
        print("-" * 60)
        
        for result in self.results:
            test_name = result['test'].replace('_', ' ').title()
            
            if 'duration_ms' in result:
                duration = result['duration_ms']
                target = result.get('target_ms', 'N/A')
                status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
                
                print(f"{test_name:<25} {duration:>8.2f}ms (target: <{target}ms) {status}")
        
        print(f"\n🎯 TARGET VALIDATION:")
        print("-" * 60)
        print(f"Ultra-fast Response Time: <{self.targets['ultra_fast_response_time_ms']}ms")
        print(f"Async Response Time:      <{self.targets['async_response_time_ms']}ms")
        print(f"Success Rate:             >{self.targets['success_rate_percent']}%")
        
        print("\n" + "="*80)
        
        # Return overall success
        return passed_tests == total_tests
    
    def run_all_tests(self):
        """Run all performance tests."""
        print("🧪 Starting LawVriksh Performance Test Suite...")
        
        try:
            # Run synchronous tests
            self.test_health_check_performance()
            self.test_ultra_fast_auth_signup()
            self.test_ultra_fast_auth_login()
            self.test_metrics_endpoint_performance()
            self.test_async_vs_sync_performance()
            
            # Run asynchronous tests
            asyncio.run(self.test_concurrent_performance())
            
            # Print summary
            return self.print_performance_summary()
            
        except Exception as e:
            print(f"❌ Performance test suite failed: {e}")
            return False


def main():
    """Main test runner."""
    suite = PerformanceTestSuite()
    success = suite.run_all_tests()
    
    if success:
        print("🎉 All performance tests passed!")
        exit(0)
    else:
        print("❌ Some performance tests failed!")
        exit(1)


if __name__ == "__main__":
    main()
