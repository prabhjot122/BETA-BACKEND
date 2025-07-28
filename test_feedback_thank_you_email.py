#!/usr/bin/env python3
"""
Test script to verify the feedback thank you email functionality
"""

import requests
import json
import sys
import time

def test_feedback_submission_with_email():
    """Test submitting feedback and verify thank you email is sent"""
    
    # API endpoint
    url = "http://localhost:8000/feedback/submit"
    
    # Test data
    test_data = {
        "email": "test.user@example.com",
        "name": "Test User",
        "biggest_hurdle": "A",
        "professional_fear": "A",
        "platform_impact": "This platform would revolutionize my career by providing easy access to share insights and connect with peers in the legal community."
    }
    
    print("🧪 Testing Feedback Submission with Thank You Email")
    print("=" * 60)
    print(f"📧 Test email: {test_data['email']}")
    print(f"👤 Test name: {test_data['name']}")
    print()
    
    try:
        # Submit feedback
        print("📤 Submitting feedback...")
        response = requests.post(url, json=test_data, timeout=30)
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Feedback submitted successfully!")
            print(f"📝 Feedback ID: {data.get('feedback_id')}")
            print(f"💬 Message: {data.get('message')}")
            
            # Give some time for email processing
            print("\n⏳ Waiting for email processing...")
            time.sleep(3)
            
            print("\n📧 Email Processing Results:")
            print("- Check the server logs for email sending status")
            print("- Look for log messages containing:")
            print("  * 'Thank you email sent successfully'")
            print("  * 'Failed to send thank you email'")
            print("  * 'Error sending thank you email'")
            
            return True
            
        else:
            print(f"❌ Failed to submit feedback: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        print("💡 Make sure the server is running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_email_function_directly():
    """Test the email function directly"""
    print("\n🧪 Testing Email Function Directly")
    print("=" * 40)
    
    try:
        # Import the email function
        from app.services.email_service import send_feedback_thank_you_email
        
        print("📧 Testing direct email function call...")
        result = send_feedback_thank_you_email("test.direct@example.com", "Direct Test User")
        
        if result:
            print("✅ Email function executed successfully!")
        else:
            print("⚠️ Email function returned False (check SMTP configuration)")
            
        return result
        
    except ImportError as e:
        print(f"❌ Could not import email function: {e}")
        print("💡 Make sure you're running this from the correct directory")
        return False
    except Exception as e:
        print(f"❌ Error testing email function: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Feedback Thank You Email Test Suite")
    print("=" * 50)
    
    # Test 1: Direct email function test
    email_test_passed = test_email_function_directly()
    
    # Test 2: Full feedback submission test
    feedback_test_passed = test_feedback_submission_with_email()
    
    print("\n📊 Test Results Summary")
    print("=" * 30)
    print(f"📧 Direct Email Test: {'✅ PASSED' if email_test_passed else '❌ FAILED'}")
    print(f"📝 Feedback Submission Test: {'✅ PASSED' if feedback_test_passed else '❌ FAILED'}")
    
    if email_test_passed and feedback_test_passed:
        print("\n🎉 All tests passed! Thank you email functionality is working.")
    else:
        print("\n⚠️ Some tests failed. Check the error messages above.")
        print("\n🔧 Troubleshooting Tips:")
        print("1. Ensure the server is running (python -m uvicorn app.main:app --reload)")
        print("2. Check SMTP configuration in app/core/config.py")
        print("3. Verify email service credentials are set correctly")
        print("4. Check server logs for detailed error messages")
    
    return email_test_passed and feedback_test_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
