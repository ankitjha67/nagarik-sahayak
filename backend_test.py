#!/usr/bin/env python3

import requests
import sys
import json
import time
from datetime import datetime

class NagarikSahayakAPITester:
    def __init__(self):
        self.base_url = "https://citizen-helper.preview.emergentagent.com/api"
        self.user_id = None
        self.phone = "9876543210"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        
        print(f"🔍 Testing Nagarik Sahayak API at: {self.base_url}")
        print(f"📅 Test Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

    def log_test(self, name, success, details="", expected_status=None, actual_status=None):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}: PASSED")
            if details:
                print(f"   {details}")
        else:
            self.failed_tests.append({"name": name, "details": details, "expected": expected_status, "actual": actual_status})
            print(f"❌ {name}: FAILED")
            if details:
                print(f"   {details}")
            if expected_status and actual_status:
                print(f"   Expected: {expected_status}, Got: {actual_status}")
        print()

    def test_health_check(self):
        """Test basic API health"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=10)
            success = response.status_code == 200
            details = f"API Health: {response.json()}" if success else f"Status: {response.status_code}"
            self.log_test("API Health Check", success, details, 200, response.status_code)
            return success
        except Exception as e:
            self.log_test("API Health Check", False, f"Connection error: {str(e)}")
            return False

    def test_send_otp(self):
        """Test OTP sending"""
        try:
            payload = {"phone": self.phone}
            response = requests.post(f"{self.base_url}/auth/send-otp", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                success = data.get("success", False)
                self.log_test("Send OTP", success, f"Response: {data['message']}", 200, response.status_code)
                return success
            else:
                self.log_test("Send OTP", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Send OTP", False, f"Error: {str(e)}")
            return False

    def test_verify_otp(self):
        """Test OTP verification"""
        try:
            payload = {"phone": self.phone, "otp": "1234"}
            response = requests.post(f"{self.base_url}/auth/verify-otp", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                success = data.get("success", False)
                if success and data.get("user_id"):
                    self.user_id = data["user_id"]
                    self.log_test("Verify OTP", True, f"User ID: {self.user_id}")
                    return True
                else:
                    self.log_test("Verify OTP", False, f"No user_id returned: {data}")
                    return False
            else:
                self.log_test("Verify OTP", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Verify OTP", False, f"Error: {str(e)}")
            return False

    def test_get_schemes(self):
        """Test schemes retrieval"""
        try:
            response = requests.get(f"{self.base_url}/schemes", timeout=10)
            
            if response.status_code == 200:
                schemes = response.json()
                success = isinstance(schemes, list) and len(schemes) >= 3
                details = f"Found {len(schemes)} schemes"
                if success:
                    scheme_titles = [s.get('title_hi', 'No title') for s in schemes[:3]]
                    details += f": {', '.join(scheme_titles)}"
                self.log_test("Get Schemes", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Get Schemes", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Get Schemes", False, f"Error: {str(e)}")
            return False

    def test_get_profile(self):
        """Test profile retrieval"""
        if not self.user_id:
            self.log_test("Get Profile", False, "No user_id available (login failed)")
            return False
            
        try:
            response = requests.get(f"{self.base_url}/profile/{self.user_id}", timeout=10)
            
            if response.status_code == 200:
                profile = response.json()
                success = profile.get("phone") == self.phone
                details = f"Phone: {profile.get('phone')}, Name: '{profile.get('name', '')}', Lang: {profile.get('language', 'N/A')}"
                self.log_test("Get Profile", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Get Profile", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Get Profile", False, f"Error: {str(e)}")
            return False

    def test_update_profile(self):
        """Test profile update"""
        if not self.user_id:
            self.log_test("Update Profile", False, "No user_id available (login failed)")
            return False
            
        try:
            payload = {"name": "Test User नागरिक", "language": "hi"}
            response = requests.put(f"{self.base_url}/profile/{self.user_id}", json=payload, timeout=10)
            
            if response.status_code == 200:
                profile = response.json()
                success = profile.get("name") == "Test User नागरिक" and profile.get("language") == "hi"
                details = f"Updated - Name: '{profile.get('name')}', Lang: {profile.get('language')}"
                self.log_test("Update Profile", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Update Profile", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Update Profile", False, f"Error: {str(e)}")
            return False

    def test_send_chat_message(self):
        """Test chat message sending"""
        if not self.user_id:
            self.log_test("Send Chat Message", False, "No user_id available (login failed)")
            return False
            
        try:
            payload = {"user_id": self.user_id, "content": "नमस्ते", "language": "hi"}
            response = requests.post(f"{self.base_url}/chat", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                user_msg = data.get("user_message", {})
                bot_msg = data.get("bot_message", {})
                
                success = (user_msg.get("content") == "नमस्ते" and 
                          bot_msg.get("role") == "assistant" and 
                          len(bot_msg.get("content", "")) > 0)
                
                details = f"User: '{user_msg.get('content')}' → Bot: '{bot_msg.get('content', '')[:50]}...'"
                self.log_test("Send Chat Message", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Send Chat Message", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Send Chat Message", False, f"Error: {str(e)}")
            return False

    def test_get_chat_history(self):
        """Test chat history retrieval"""
        if not self.user_id:
            self.log_test("Get Chat History", False, "No user_id available (login failed)")
            return False
            
        try:
            response = requests.get(f"{self.base_url}/chat/history/{self.user_id}", timeout=10)
            
            if response.status_code == 200:
                messages = response.json()
                success = isinstance(messages, list) and len(messages) >= 2  # At least user + bot message
                details = f"Found {len(messages)} messages in history"
                self.log_test("Get Chat History", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Get Chat History", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Get Chat History", False, f"Error: {str(e)}")
            return False

    def test_llm_providers(self):
        """Test LLM providers endpoint"""
        try:
            response = requests.get(f"{self.base_url}/llm-providers", timeout=10)
            
            if response.status_code == 200:
                providers = response.json()
                success = isinstance(providers, dict) and len(providers) > 0
                details = f"Found {len(providers)} LLM providers: {', '.join(providers.keys())}"
                self.log_test("LLM Providers", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("LLM Providers", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("LLM Providers", False, f"Error: {str(e)}")
            return False

    def test_stt_providers(self):
        """Test STT providers endpoint"""
        try:
            response = requests.get(f"{self.base_url}/stt-providers", timeout=10)
            
            if response.status_code == 200:
                providers = response.json()
                success = isinstance(providers, dict) and len(providers) > 0
                details = f"Found {len(providers)} STT providers: {', '.join(providers.keys())}"
                self.log_test("STT Providers", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("STT Providers", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("STT Providers", False, f"Error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run complete API test suite"""
        print("🚀 Starting Nagarik Sahayak API Test Suite\n")
        
        # Test 1: Health Check
        if not self.test_health_check():
            print("💥 Critical: API health check failed. Stopping tests.")
            return self.print_summary()
        
        # Test 2: Authentication Flow
        if not self.test_send_otp():
            print("💥 Critical: OTP sending failed. Stopping tests.")
            return self.print_summary()
            
        if not self.test_verify_otp():
            print("💥 Critical: OTP verification failed. Stopping tests.")
            return self.print_summary()
        
        # Test 3: Core Endpoints
        self.test_get_schemes()
        self.test_get_profile()
        self.test_update_profile()
        self.test_send_chat_message()
        self.test_get_chat_history()
        
        # Test 4: Info Endpoints
        self.test_llm_providers()
        self.test_stt_providers()
        
        return self.print_summary()

    def print_summary(self):
        """Print test execution summary"""
        print("=" * 60)
        print("📊 TEST EXECUTION SUMMARY")
        print("=" * 60)
        print(f"✅ Tests Passed: {self.tests_passed}/{self.tests_run}")
        print(f"❌ Tests Failed: {len(self.failed_tests)}/{self.tests_run}")
        
        if self.failed_tests:
            print(f"\n🔍 FAILED TESTS DETAILS:")
            for i, test in enumerate(self.failed_tests, 1):
                print(f"{i}. {test['name']}")
                print(f"   Details: {test['details']}")
                if test.get('expected') and test.get('actual'):
                    print(f"   Expected: {test['expected']}, Got: {test['actual']}")
                print()
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"🎯 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Backend API Status: GOOD")
            return 0
        elif success_rate >= 60:
            print("⚠️  Backend API Status: NEEDS ATTENTION")
            return 1
        else:
            print("🚨 Backend API Status: CRITICAL ISSUES")
            return 2

def main():
    """Main function"""
    tester = NagarikSahayakAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())