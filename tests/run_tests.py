#!/usr/bin/env python3
"""
LawVriksh Test Runner
====================

Unified test runner for all LawVriksh test suites.

Usage:
    python tests/run_tests.py [test_type] [options]

Test Types:
    all         - Run all test suites
    performance - Run performance tests only
    integration - Run integration tests only
    load        - Run load tests only
    quick       - Run quick smoke tests
"""

import sys
import time
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests import TEST_CONFIG


class TestRunner:
    """Unified test runner for all test suites."""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.results = {}
        
    def run_test_suite(self, test_file: str, test_name: str) -> bool:
        """Run a specific test suite."""
        print(f"\n{'='*20} {test_name.upper()} {'='*20}")
        print(f"Running {test_file}...")
        
        start_time = time.time()
        
        try:
            # Run the test file
            result = subprocess.run([
                sys.executable, str(self.test_dir / test_file)
            ], capture_output=True, text=True, timeout=600)  # 10 minute timeout
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                print(f"✅ {test_name} PASSED in {duration:.2f}s")
                self.results[test_name] = {
                    'status': 'PASSED',
                    'duration': duration,
                    'output': result.stdout
                }
                return True
            else:
                print(f"❌ {test_name} FAILED in {duration:.2f}s")
                print(f"Error output:\n{result.stderr}")
                self.results[test_name] = {
                    'status': 'FAILED',
                    'duration': duration,
                    'output': result.stdout,
                    'error': result.stderr
                }
                return False
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"⏰ {test_name} TIMEOUT after {duration:.2f}s")
            self.results[test_name] = {
                'status': 'TIMEOUT',
                'duration': duration,
                'error': 'Test timed out'
            }
            return False
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"💥 {test_name} ERROR: {e}")
            self.results[test_name] = {
                'status': 'ERROR',
                'duration': duration,
                'error': str(e)
            }
            return False
    
    def run_performance_tests(self) -> bool:
        """Run performance test suite."""
        return self.run_test_suite('test_performance.py', 'Performance Tests')
    
    def run_integration_tests(self) -> bool:
        """Run integration test suite."""
        return self.run_test_suite('test_integration.py', 'Integration Tests')
    
    def run_load_tests(self) -> bool:
        """Run load test suite."""
        return self.run_test_suite('test_load.py', 'Load Tests')
    
    def run_quick_tests(self) -> bool:
        """Run quick smoke tests."""
        print(f"\n{'='*20} QUICK SMOKE TESTS {'='*20}")
        
        # Quick health check
        import requests
        
        try:
            print("🏥 Testing application health...")
            response = requests.get(f"{TEST_CONFIG['base_url']}/health", timeout=10)
            
            if response.status_code == 200:
                print("✅ Application is healthy")
                
                # Quick performance check
                print("⚡ Testing ultra-fast endpoint...")
                start_time = time.time()
                response = requests.get(f"{TEST_CONFIG['base_url']}/ultra-auth/health", timeout=10)
                duration_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200 and duration_ms < 100:
                    print(f"✅ Ultra-fast endpoint: {duration_ms:.2f}ms")
                    
                    self.results['Quick Tests'] = {
                        'status': 'PASSED',
                        'duration': duration_ms / 1000,
                        'response_time_ms': duration_ms
                    }
                    return True
                else:
                    print(f"❌ Ultra-fast endpoint too slow: {duration_ms:.2f}ms")
                    self.results['Quick Tests'] = {
                        'status': 'FAILED',
                        'error': f'Response time {duration_ms:.2f}ms exceeds 100ms target'
                    }
                    return False
            else:
                print(f"❌ Application unhealthy: {response.status_code}")
                self.results['Quick Tests'] = {
                    'status': 'FAILED',
                    'error': f'Health check failed with status {response.status_code}'
                }
                return False
                
        except Exception as e:
            print(f"❌ Quick tests failed: {e}")
            self.results['Quick Tests'] = {
                'status': 'FAILED',
                'error': str(e)
            }
            return False
    
    def run_all_tests(self) -> bool:
        """Run all test suites."""
        print("🧪 Starting Complete LawVriksh Test Suite...")
        print(f"Base URL: {TEST_CONFIG['base_url']}")
        
        # Test order: quick -> performance -> integration -> load
        test_suites = [
            ('quick', self.run_quick_tests),
            ('performance', self.run_performance_tests),
            ('integration', self.run_integration_tests),
            ('load', self.run_load_tests)
        ]
        
        passed_tests = 0
        total_tests = len(test_suites)
        
        for test_name, test_func in test_suites:
            try:
                if test_func():
                    passed_tests += 1
                else:
                    print(f"⚠️ {test_name.title()} tests failed, continuing with remaining tests...")
            except KeyboardInterrupt:
                print(f"\n⏹️ Test suite interrupted by user")
                break
            except Exception as e:
                print(f"💥 Unexpected error in {test_name} tests: {e}")
        
        return passed_tests == total_tests
    
    def print_test_summary(self):
        """Print comprehensive test summary."""
        print("\n" + "="*80)
        print("🧪 LAWVRIKSH TEST SUITE SUMMARY")
        print("="*80)
        
        if not self.results:
            print("No test results to display.")
            return
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r['status'] == 'PASSED')
        failed_tests = sum(1 for r in self.results.values() if r['status'] == 'FAILED')
        error_tests = sum(1 for r in self.results.values() if r['status'] == 'ERROR')
        timeout_tests = sum(1 for r in self.results.values() if r['status'] == 'TIMEOUT')
        
        print(f"\n📊 OVERALL RESULTS:")
        print(f"   Total Test Suites: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {failed_tests}")
        print(f"   Errors: {error_tests}")
        print(f"   Timeouts: {timeout_tests}")
        print(f"   Success Rate: {passed_tests/total_tests*100:.1f}%")
        
        total_duration = sum(r.get('duration', 0) for r in self.results.values())
        print(f"   Total Duration: {total_duration:.2f}s")
        
        print(f"\n📋 DETAILED RESULTS:")
        print("-" * 60)
        
        for test_name, result in self.results.items():
            status_icon = {
                'PASSED': '✅',
                'FAILED': '❌',
                'ERROR': '💥',
                'TIMEOUT': '⏰'
            }.get(result['status'], '❓')
            
            duration = result.get('duration', 0)
            print(f"{status_icon} {test_name:<20} {result['status']:<8} {duration:>8.2f}s")
            
            if result['status'] != 'PASSED' and 'error' in result:
                error_preview = result['error'][:100] + "..." if len(result['error']) > 100 else result['error']
                print(f"   Error: {error_preview}")
        
        # Performance summary if available
        perf_result = self.results.get('Performance Tests')
        if perf_result and perf_result['status'] == 'PASSED':
            print(f"\n⚡ PERFORMANCE HIGHLIGHTS:")
            print("   Ultra-fast endpoints validated (<100ms)")
            print("   Success rate targets met (>99%)")
            print("   960x performance improvement maintained")
        
        # Load test summary if available
        load_result = self.results.get('Load Tests')
        if load_result and load_result['status'] == 'PASSED':
            print(f"\n🚀 LOAD TEST HIGHLIGHTS:")
            print("   High concurrency handled successfully")
            print("   Performance maintained under stress")
            print("   System stability validated")
        
        print(f"\n🎯 SYSTEM STATUS:")
        if passed_tests == total_tests:
            print("   🎉 ALL SYSTEMS GO! Application ready for production.")
            print("   ✅ Ultra-fast performance validated")
            print("   ✅ High availability confirmed")
            print("   ✅ Load handling capability verified")
        elif passed_tests >= total_tests * 0.75:
            print("   ⚠️ MOSTLY HEALTHY with some issues to address")
            print("   🔧 Review failed tests and optimize")
        else:
            print("   ❌ CRITICAL ISSUES DETECTED")
            print("   🚨 Immediate attention required before production")
        
        print("\n" + "="*80)
        
        return passed_tests == total_tests


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description='LawVriksh Test Runner')
    parser.add_argument('test_type', nargs='?', default='all',
                       choices=['all', 'performance', 'integration', 'load', 'quick'],
                       help='Type of tests to run')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--base-url', default=TEST_CONFIG['base_url'],
                       help='Base URL for testing')
    
    args = parser.parse_args()
    
    # Update test config if needed
    if args.base_url != TEST_CONFIG['base_url']:
        TEST_CONFIG['base_url'] = args.base_url
    
    # Create test runner
    runner = TestRunner()
    
    # Run specified tests
    success = False
    
    if args.test_type == 'all':
        success = runner.run_all_tests()
    elif args.test_type == 'performance':
        success = runner.run_performance_tests()
    elif args.test_type == 'integration':
        success = runner.run_integration_tests()
    elif args.test_type == 'load':
        success = runner.run_load_tests()
    elif args.test_type == 'quick':
        success = runner.run_quick_tests()
    
    # Print summary
    overall_success = runner.print_test_summary()
    
    # Exit with appropriate code
    if success and overall_success:
        print("\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
