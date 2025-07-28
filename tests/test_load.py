#!/usr/bin/env python3
"""
Load Test Suite for LawVriksh Application
========================================

Comprehensive load testing to validate performance under high concurrency
and ensure the application maintains ultra-fast response times under stress.

Test Categories:
- Concurrent user simulation
- Stress testing with high load
- Success rate validation under load
- Performance degradation analysis
- Resource utilization monitoring
"""

import asyncio
import aiohttp
import time
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from tests import TEST_CONFIG


class LoadTestSuite:
    """Comprehensive load test suite."""
    
    def __init__(self):
        self.base_url = TEST_CONFIG['base_url']
        self.load_config = TEST_CONFIG['load_test_config']
        self.targets = TEST_CONFIG['performance_targets']
        self.results = []
    
    async def simulate_user_session(self, session: aiohttp.ClientSession, user_id: int) -> Dict[str, Any]:
        """Simulate a complete user session."""
        user_results = {
            'user_id': user_id,
            'operations': [],
            'total_duration': 0,
            'success_count': 0,
            'error_count': 0
        }
        
        session_start = time.time()
        
        try:
            # 1. Health check
            start_time = time.time()
            async with session.get(f"{self.base_url}/health") as response:
                duration = time.time() - start_time
                success = response.status == 200
                
                user_results['operations'].append({
                    'operation': 'health_check',
                    'duration': duration,
                    'success': success,
                    'status_code': response.status
                })
                
                if success:
                    user_results['success_count'] += 1
                else:
                    user_results['error_count'] += 1
            
            # 2. User registration
            user_data = {
                "name": f"Load Test User {user_id}",
                "email": f"load_test_{user_id}_{int(time.time())}@example.com",
                "password": "testpassword123"
            }
            
            start_time = time.time()
            async with session.post(f"{self.base_url}/ultra-auth/signup", json=user_data) as response:
                duration = time.time() - start_time
                success = response.status == 201
                
                user_results['operations'].append({
                    'operation': 'signup',
                    'duration': duration,
                    'success': success,
                    'status_code': response.status
                })
                
                if success:
                    user_results['success_count'] += 1
                    signup_data = await response.json()
                else:
                    user_results['error_count'] += 1
                    signup_data = None
            
            # 3. User login (if signup succeeded)
            if signup_data:
                login_data = {
                    "email": user_data["email"],
                    "password": user_data["password"]
                }
                
                start_time = time.time()
                async with session.post(f"{self.base_url}/ultra-auth/login", json=login_data) as response:
                    duration = time.time() - start_time
                    success = response.status == 200
                    
                    user_results['operations'].append({
                        'operation': 'login',
                        'duration': duration,
                        'success': success,
                        'status_code': response.status
                    })
                    
                    if success:
                        user_results['success_count'] += 1
                        login_response = await response.json()
                        token = login_response.get('access_token')
                    else:
                        user_results['error_count'] += 1
                        token = None
                
                # 4. Get user info (if login succeeded)
                if token:
                    headers = {"Authorization": f"Bearer {token}"}
                    
                    start_time = time.time()
                    async with session.get(f"{self.base_url}/ultra-auth/me", headers=headers) as response:
                        duration = time.time() - start_time
                        success = response.status == 200
                        
                        user_results['operations'].append({
                            'operation': 'get_user_info',
                            'duration': duration,
                            'success': success,
                            'status_code': response.status
                        })
                        
                        if success:
                            user_results['success_count'] += 1
                        else:
                            user_results['error_count'] += 1
            
            # 5. Multiple health checks to simulate ongoing usage
            for i in range(3):
                start_time = time.time()
                async with session.get(f"{self.base_url}/ultra-auth/health") as response:
                    duration = time.time() - start_time
                    success = response.status == 200
                    
                    user_results['operations'].append({
                        'operation': f'health_check_{i+2}',
                        'duration': duration,
                        'success': success,
                        'status_code': response.status
                    })
                    
                    if success:
                        user_results['success_count'] += 1
                    else:
                        user_results['error_count'] += 1
                
                # Small delay between requests
                await asyncio.sleep(0.1)
        
        except Exception as e:
            user_results['error_count'] += 1
            user_results['operations'].append({
                'operation': 'session_error',
                'duration': 0,
                'success': False,
                'error': str(e)
            })
        
        user_results['total_duration'] = time.time() - session_start
        return user_results
    
    async def run_concurrent_load_test(self, concurrent_users: int = 50, duration_seconds: int = 60):
        """Run concurrent load test with specified parameters."""
        print(f"🚀 Starting load test: {concurrent_users} concurrent users for {duration_seconds}s")
        
        # Create connector with appropriate limits
        connector = aiohttp.TCPConnector(
            limit=concurrent_users * 2,
            limit_per_host=concurrent_users * 2,
            ttl_dns_cache=300,
            use_dns_cache=True
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Start user sessions
            tasks = []
            for user_id in range(concurrent_users):
                task = asyncio.create_task(self.simulate_user_session(session, user_id))
                tasks.append(task)
                
                # Stagger user starts to simulate realistic load
                if user_id % 10 == 0:
                    await asyncio.sleep(0.5)
            
            # Wait for all sessions to complete
            print(f"⏳ Running {len(tasks)} concurrent user sessions...")
            start_time = time.time()
            
            user_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            total_duration = time.time() - start_time
            
            # Filter out exceptions
            valid_results = [r for r in user_results if isinstance(r, dict)]
            exceptions = [r for r in user_results if not isinstance(r, dict)]
            
            print(f"✅ Load test completed in {total_duration:.2f}s")
            print(f"   Valid sessions: {len(valid_results)}")
            print(f"   Exceptions: {len(exceptions)}")
            
            return self.analyze_load_test_results(valid_results, total_duration, concurrent_users)
    
    def analyze_load_test_results(self, user_results: List[Dict], total_duration: float, concurrent_users: int) -> Dict[str, Any]:
        """Analyze load test results and calculate metrics."""
        print("📊 Analyzing load test results...")
        
        # Aggregate all operations
        all_operations = []
        total_operations = 0
        total_successes = 0
        total_errors = 0
        
        for user_result in user_results:
            total_operations += len(user_result['operations'])
            total_successes += user_result['success_count']
            total_errors += user_result['error_count']
            all_operations.extend(user_result['operations'])
        
        # Calculate success rate
        success_rate = (total_successes / total_operations * 100) if total_operations > 0 else 0
        
        # Calculate response time statistics
        successful_operations = [op for op in all_operations if op['success']]
        
        if successful_operations:
            response_times = [op['duration'] * 1000 for op in successful_operations]  # Convert to ms
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 1 else avg_response_time
            p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) > 1 else avg_response_time
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = median_response_time = p95_response_time = p99_response_time = 0
            min_response_time = max_response_time = 0
        
        # Calculate throughput
        throughput = total_operations / total_duration if total_duration > 0 else 0
        
        # Analyze by operation type
        operation_stats = {}
        for op in all_operations:
            op_type = op['operation']
            if op_type not in operation_stats:
                operation_stats[op_type] = {
                    'count': 0,
                    'successes': 0,
                    'errors': 0,
                    'durations': []
                }
            
            operation_stats[op_type]['count'] += 1
            if op['success']:
                operation_stats[op_type]['successes'] += 1
                operation_stats[op_type]['durations'].append(op['duration'] * 1000)
            else:
                operation_stats[op_type]['errors'] += 1
        
        # Calculate operation-specific metrics
        for op_type, stats in operation_stats.items():
            if stats['durations']:
                stats['avg_duration'] = statistics.mean(stats['durations'])
                stats['success_rate'] = stats['successes'] / stats['count'] * 100
            else:
                stats['avg_duration'] = 0
                stats['success_rate'] = 0
        
        results = {
            'concurrent_users': concurrent_users,
            'total_duration': total_duration,
            'total_operations': total_operations,
            'total_successes': total_successes,
            'total_errors': total_errors,
            'success_rate': success_rate,
            'throughput': throughput,
            'avg_response_time': avg_response_time,
            'median_response_time': median_response_time,
            'p95_response_time': p95_response_time,
            'p99_response_time': p99_response_time,
            'min_response_time': min_response_time,
            'max_response_time': max_response_time,
            'operation_stats': operation_stats
        }
        
        self.results.append(results)
        return results
    
    def print_load_test_summary(self, results: Dict[str, Any]):
        """Print detailed load test summary."""
        print("\n" + "="*80)
        print("🚀 LOAD TEST RESULTS")
        print("="*80)
        
        print(f"\n📊 OVERALL METRICS:")
        print(f"   Concurrent Users:     {results['concurrent_users']}")
        print(f"   Test Duration:        {results['total_duration']:.2f}s")
        print(f"   Total Operations:     {results['total_operations']}")
        print(f"   Successful Operations: {results['total_successes']}")
        print(f"   Failed Operations:    {results['total_errors']}")
        print(f"   Success Rate:         {results['success_rate']:.2f}%")
        print(f"   Throughput:           {results['throughput']:.2f} ops/sec")
        
        print(f"\n⚡ RESPONSE TIME METRICS:")
        print(f"   Average:              {results['avg_response_time']:.2f}ms")
        print(f"   Median:               {results['median_response_time']:.2f}ms")
        print(f"   95th Percentile:      {results['p95_response_time']:.2f}ms")
        print(f"   99th Percentile:      {results['p99_response_time']:.2f}ms")
        print(f"   Min:                  {results['min_response_time']:.2f}ms")
        print(f"   Max:                  {results['max_response_time']:.2f}ms")
        
        print(f"\n🎯 TARGET VALIDATION:")
        success_rate_pass = results['success_rate'] >= self.targets['success_rate_percent']
        response_time_pass = results['p95_response_time'] <= 500  # 500ms for load test
        
        print(f"   Success Rate Target:  >{self.targets['success_rate_percent']}% {'✅ PASS' if success_rate_pass else '❌ FAIL'}")
        print(f"   Response Time Target: <500ms (P95) {'✅ PASS' if response_time_pass else '❌ FAIL'}")
        
        print(f"\n📋 OPERATION BREAKDOWN:")
        print("-" * 60)
        for op_type, stats in results['operation_stats'].items():
            print(f"   {op_type:<20} {stats['count']:>6} ops, {stats['success_rate']:>6.1f}% success, {stats['avg_duration']:>8.2f}ms avg")
        
        print("\n" + "="*80)
        
        return success_rate_pass and response_time_pass
    
    def run_stress_test(self):
        """Run stress test with increasing load."""
        print("💪 Starting stress test with increasing load...")
        
        stress_levels = [10, 25, 50, 75, 100]
        stress_results = []
        
        for concurrent_users in stress_levels:
            print(f"\n🔥 Stress level: {concurrent_users} concurrent users")
            
            try:
                result = asyncio.run(self.run_concurrent_load_test(
                    concurrent_users=concurrent_users,
                    duration_seconds=30  # Shorter duration for stress test
                ))
                
                stress_results.append(result)
                
                # Check if system is still performing well
                if result['success_rate'] < 90:
                    print(f"⚠️ Success rate dropped to {result['success_rate']:.1f}% at {concurrent_users} users")
                    break
                
                if result['p95_response_time'] > 2000:  # 2 seconds
                    print(f"⚠️ Response time degraded to {result['p95_response_time']:.0f}ms at {concurrent_users} users")
                    break
                
                # Brief pause between stress levels
                time.sleep(5)
                
            except Exception as e:
                print(f"❌ Stress test failed at {concurrent_users} users: {e}")
                break
        
        return stress_results
    
    def run_all_tests(self):
        """Run all load tests."""
        print("🧪 Starting LawVriksh Load Test Suite...")
        
        try:
            # Run standard load test
            print("\n" + "="*50)
            print("STANDARD LOAD TEST")
            print("="*50)
            
            load_result = asyncio.run(self.run_concurrent_load_test(
                concurrent_users=self.load_config['concurrent_users'],
                duration_seconds=self.load_config['test_duration_seconds']
            ))
            
            load_test_pass = self.print_load_test_summary(load_result)
            
            # Run stress test
            print("\n" + "="*50)
            print("STRESS TEST")
            print("="*50)
            
            stress_results = self.run_stress_test()
            
            print(f"\n📊 STRESS TEST SUMMARY:")
            print(f"   Tested up to {len(stress_results)} stress levels")
            if stress_results:
                max_users = max(r['concurrent_users'] for r in stress_results)
                print(f"   Maximum concurrent users: {max_users}")
            
            return load_test_pass
            
        except Exception as e:
            print(f"❌ Load test suite failed: {e}")
            return False


def main():
    """Main test runner."""
    suite = LoadTestSuite()
    success = suite.run_all_tests()
    
    if success:
        print("🎉 Load tests passed!")
        exit(0)
    else:
        print("❌ Load tests failed!")
        exit(1)


if __name__ == "__main__":
    main()
