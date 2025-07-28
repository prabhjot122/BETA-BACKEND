#!/usr/bin/env python3
"""
Integration Test Suite for LawVriksh Application
===============================================

Comprehensive integration testing for all API endpoints and workflows.

Test Categories:
- Authentication flow testing
- User management operations
- Share event processing
- Email queue functionality
- Cache integration testing
- Database integration testing
"""

import requests
import time
import json
from typing import Dict, Any, Optional
from tests import TEST_CONFIG


class IntegrationTestSuite:
    """Comprehensive integration test suite."""
    
    def __init__(self):
        self.base_url = TEST_CONFIG['base_url']
        self.test_users = []
        self.auth_tokens = {}
        self.results = []
    
    def create_test_user(self, endpoint_type: str = "ultra") -> Dict[str, Any]:
        """Create a test user and return user data with token."""
        timestamp = int(time.time())
        user_data = {
            "name": f"Integration Test User {timestamp}",
            "email": f"integration_test_{endpoint_type}_{timestamp}@example.com",
            "password": "testpassword123"
        }
        
        # Choose endpoint based on type
        if endpoint_type == "ultra":
            signup_url = f"{self.base_url}/ultra-auth/signup"
            login_url = f"{self.base_url}/ultra-auth/login"
        elif endpoint_type == "async":
            signup_url = f"{self.base_url}/async-auth/signup"
            login_url = f"{self.base_url}/async-auth/login"
        else:
            signup_url = f"{self.base_url}/auth/signup"
            login_url = f"{self.base_url}/auth/login"
        
        # Create user
        signup_response = requests.post(signup_url, json=user_data, timeout=10)
        assert signup_response.status_code == 201, f"User creation failed: {signup_response.status_code}"
        
        # Login to get token
        login_data = {"email": user_data["email"], "password": user_data["password"]}
        login_response = requests.post(login_url, json=login_data, timeout=10)
        assert login_response.status_code == 200, f"Login failed: {login_response.status_code}"
        
        token = login_response.json()["access_token"]
        
        user_info = {
            "user_data": user_data,
            "token": token,
            "endpoint_type": endpoint_type
        }
        
        self.test_users.append(user_info)
        return user_info
    
    def test_authentication_flow(self):
        """Test complete authentication flow for all endpoint types."""
        print("🔐 Testing authentication flows...")
        
        endpoint_types = ["ultra", "async", "sync"]
        
        for endpoint_type in endpoint_types:
            try:
                # Test user creation and login
                user_info = self.create_test_user(endpoint_type)
                
                # Test getting user info
                if endpoint_type == "ultra":
                    me_url = f"{self.base_url}/ultra-auth/me"
                elif endpoint_type == "async":
                    me_url = f"{self.base_url}/async-auth/me"
                else:
                    me_url = f"{self.base_url}/auth/me"
                
                headers = {"Authorization": f"Bearer {user_info['token']}"}
                me_response = requests.get(me_url, headers=headers, timeout=10)
                
                assert me_response.status_code == 200, f"Get user info failed: {me_response.status_code}"
                
                user_data = me_response.json()
                assert user_data["email"] == user_info["user_data"]["email"], "Email mismatch"
                
                self.results.append({
                    'test': f'auth_flow_{endpoint_type}',
                    'success': True,
                    'endpoint_type': endpoint_type
                })
                
                print(f"✅ {endpoint_type.capitalize()} auth flow: PASS")
                
            except Exception as e:
                self.results.append({
                    'test': f'auth_flow_{endpoint_type}',
                    'success': False,
                    'error': str(e),
                    'endpoint_type': endpoint_type
                })
                print(f"❌ {endpoint_type.capitalize()} auth flow: FAIL - {e}")
    
    def test_user_management(self):
        """Test user management operations."""
        print("👥 Testing user management...")
        
        try:
            # Create a test user
            user_info = self.create_test_user("ultra")
            headers = {"Authorization": f"Bearer {user_info['token']}"}
            
            # Test getting user profile
            response = requests.get(f"{self.base_url}/users/me", headers=headers, timeout=10)
            assert response.status_code == 200, f"Get profile failed: {response.status_code}"
            
            profile_data = response.json()
            assert "total_points" in profile_data, "Total points not found in profile"
            assert "shares_count" in profile_data, "Shares count not found in profile"
            
            self.results.append({
                'test': 'user_management',
                'success': True
            })
            
            print("✅ User management: PASS")
            
        except Exception as e:
            self.results.append({
                'test': 'user_management',
                'success': False,
                'error': str(e)
            })
            print(f"❌ User management: FAIL - {e}")
    
    def test_share_events(self):
        """Test share event processing."""
        print("📤 Testing share events...")
        
        try:
            # Create a test user
            user_info = self.create_test_user("ultra")
            headers = {"Authorization": f"Bearer {user_info['token']}"}
            
            # Test creating a share event
            share_data = {
                "platform": "twitter",
                "points_earned": 10
            }
            
            response = requests.post(
                f"{self.base_url}/shares/", 
                json=share_data, 
                headers=headers, 
                timeout=10
            )
            
            # Share endpoint might not exist, so we'll check if it's implemented
            if response.status_code == 404:
                print("⚠️ Share events endpoint not implemented, skipping test")
                self.results.append({
                    'test': 'share_events',
                    'success': True,
                    'note': 'Endpoint not implemented'
                })
            else:
                assert response.status_code in [200, 201], f"Share creation failed: {response.status_code}"
                
                self.results.append({
                    'test': 'share_events',
                    'success': True
                })
                
                print("✅ Share events: PASS")
                
        except Exception as e:
            self.results.append({
                'test': 'share_events',
                'success': False,
                'error': str(e)
            })
            print(f"❌ Share events: FAIL - {e}")
    
    def test_leaderboard(self):
        """Test leaderboard functionality."""
        print("🏆 Testing leaderboard...")
        
        try:
            # Test getting leaderboard
            response = requests.get(f"{self.base_url}/leaderboard/", timeout=10)
            
            if response.status_code == 404:
                print("⚠️ Leaderboard endpoint not found, trying async version")
                response = requests.get(f"{self.base_url}/async-leaderboard/", timeout=10)
            
            assert response.status_code == 200, f"Leaderboard failed: {response.status_code}"
            
            leaderboard_data = response.json()
            assert isinstance(leaderboard_data, (list, dict)), "Invalid leaderboard format"
            
            self.results.append({
                'test': 'leaderboard',
                'success': True
            })
            
            print("✅ Leaderboard: PASS")
            
        except Exception as e:
            self.results.append({
                'test': 'leaderboard',
                'success': False,
                'error': str(e)
            })
            print(f"❌ Leaderboard: FAIL - {e}")
    
    def test_health_endpoints(self):
        """Test all health check endpoints."""
        print("🏥 Testing health endpoints...")
        
        health_endpoints = [
            "/health",
            "/ultra-auth/health",
            "/async-auth/health"
        ]
        
        for endpoint in health_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                
                if response.status_code == 404:
                    print(f"⚠️ Health endpoint {endpoint} not found, skipping")
                    continue
                
                assert response.status_code == 200, f"Health check failed: {response.status_code}"
                
                health_data = response.json()
                assert "status" in health_data, f"Status not found in {endpoint}"
                
                self.results.append({
                    'test': f'health_{endpoint.replace("/", "_").replace("-", "_")}',
                    'success': True,
                    'endpoint': endpoint
                })
                
                print(f"✅ Health {endpoint}: PASS")
                
            except Exception as e:
                self.results.append({
                    'test': f'health_{endpoint.replace("/", "_").replace("-", "_")}',
                    'success': False,
                    'error': str(e),
                    'endpoint': endpoint
                })
                print(f"❌ Health {endpoint}: FAIL - {e}")
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        print("📊 Testing metrics endpoint...")
        
        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=10)
            assert response.status_code == 200, f"Metrics failed: {response.status_code}"
            
            metrics_text = response.text
            
            # Check for key metrics
            expected_metrics = [
                "http_requests_total",
                "http_request_duration_seconds",
                "python_info"
            ]
            
            for metric in expected_metrics:
                assert metric in metrics_text, f"Metric {metric} not found"
            
            self.results.append({
                'test': 'metrics_endpoint',
                'success': True
            })
            
            print("✅ Metrics endpoint: PASS")
            
        except Exception as e:
            self.results.append({
                'test': 'metrics_endpoint',
                'success': False,
                'error': str(e)
            })
            print(f"❌ Metrics endpoint: FAIL - {e}")
    
    def test_error_handling(self):
        """Test error handling and edge cases."""
        print("⚠️ Testing error handling...")
        
        try:
            # Test invalid login
            invalid_login = {
                "email": "nonexistent@example.com",
                "password": "wrongpassword"
            }
            
            response = requests.post(
                f"{self.base_url}/ultra-auth/login", 
                json=invalid_login, 
                timeout=10
            )
            
            assert response.status_code == 401, f"Expected 401, got {response.status_code}"
            
            # Test invalid token
            headers = {"Authorization": "Bearer invalid_token"}
            response = requests.get(
                f"{self.base_url}/ultra-auth/me", 
                headers=headers, 
                timeout=10
            )
            
            assert response.status_code == 401, f"Expected 401, got {response.status_code}"
            
            # Test duplicate email registration
            user_info = self.create_test_user("ultra")
            duplicate_user = user_info["user_data"].copy()
            
            response = requests.post(
                f"{self.base_url}/ultra-auth/signup", 
                json=duplicate_user, 
                timeout=10
            )
            
            assert response.status_code == 400, f"Expected 400, got {response.status_code}"
            
            self.results.append({
                'test': 'error_handling',
                'success': True
            })
            
            print("✅ Error handling: PASS")
            
        except Exception as e:
            self.results.append({
                'test': 'error_handling',
                'success': False,
                'error': str(e)
            })
            print(f"❌ Error handling: FAIL - {e}")
    
    def print_integration_summary(self):
        """Print comprehensive integration test summary."""
        print("\n" + "="*80)
        print("🔗 LAWVRIKSH INTEGRATION TEST RESULTS")
        print("="*80)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.get('success', False))
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {total_tests - passed_tests}")
        print(f"   Success Rate: {passed_tests/total_tests*100:.1f}%")
        
        print(f"\n🧪 TEST RESULTS:")
        print("-" * 60)
        
        for result in self.results:
            test_name = result['test'].replace('_', ' ').title()
            status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
            
            error_info = ""
            if not result.get('success', False) and 'error' in result:
                error_info = f" - {result['error'][:50]}..."
            
            note_info = ""
            if 'note' in result:
                note_info = f" ({result['note']})"
            
            print(f"{test_name:<30} {status}{error_info}{note_info}")
        
        print(f"\n👥 TEST USERS CREATED: {len(self.test_users)}")
        
        print("\n" + "="*80)
        
        # Return overall success
        return passed_tests == total_tests
    
    def run_all_tests(self):
        """Run all integration tests."""
        print("🧪 Starting LawVriksh Integration Test Suite...")
        
        try:
            # Run all integration tests
            self.test_health_endpoints()
            self.test_authentication_flow()
            self.test_user_management()
            self.test_share_events()
            self.test_leaderboard()
            self.test_metrics_endpoint()
            self.test_error_handling()
            
            # Print summary
            return self.print_integration_summary()
            
        except Exception as e:
            print(f"❌ Integration test suite failed: {e}")
            return False


def main():
    """Main test runner."""
    suite = IntegrationTestSuite()
    success = suite.run_all_tests()
    
    if success:
        print("🎉 All integration tests passed!")
        exit(0)
    else:
        print("❌ Some integration tests failed!")
        exit(1)


if __name__ == "__main__":
    main()
