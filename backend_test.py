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

    def test_mcp_tools_list(self):
        """Test MCP tools listing endpoint"""
        try:
            response = requests.get(f"{self.base_url}/mcp/tools", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", [])
                success = isinstance(tools, list) and len(tools) > 0
                
                # Check for search_schemes tool
                search_tool = next((t for t in tools if t.get("name") == "search_schemes"), None)
                if search_tool:
                    details = f"Found {len(tools)} MCP tools, search_schemes tool present with description: '{search_tool.get('description', '')[:50]}...'"
                    success = success and "search" in search_tool.get("description", "").lower()
                else:
                    success = False
                    details = f"Found {len(tools)} tools but search_schemes tool missing"
                
                self.log_test("MCP Tools List", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("MCP Tools List", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("MCP Tools List", False, f"Error: {str(e)}")
            return False

    def test_search_schemes_kisan(self):
        """Test search_schemes with farmer kisan query"""
        try:
            payload = {"query": "farmer kisan eligibility"}
            response = requests.post(f"{self.base_url}/search-schemes", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                success = (
                    data.get("match_found") == True and
                    "PM-KISAN" in str(data.get("documents_scanned", [])) and
                    "PM-KISAN" in data.get("result_text", "")
                )
                details = f"Match found: {data.get('match_found')}, Documents: {data.get('documents_scanned', [])[:2]}"
                self.log_test("Search Schemes - Kisan Query", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Search Schemes - Kisan Query", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Search Schemes - Kisan Query", False, f"Error: {str(e)}")
            return False

    def test_search_schemes_health(self):
        """Test search_schemes with health insurance query"""
        try:
            payload = {"query": "health insurance ayushman"}
            response = requests.post(f"{self.base_url}/search-schemes", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                success = (
                    data.get("match_found") == True and
                    "Ayushman Bharat" in data.get("result_text", "")
                )
                details = f"Match found: {data.get('match_found')}, Ayushman detected in response"
                self.log_test("Search Schemes - Health Query", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Search Schemes - Health Query", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Search Schemes - Health Query", False, f"Error: {str(e)}")
            return False

    def test_search_schemes_sukanya(self):
        """Test search_schemes with girl child savings query"""
        try:
            payload = {"query": "girl child savings sukanya"}
            response = requests.post(f"{self.base_url}/search-schemes", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                success = (
                    data.get("match_found") == True and
                    "Sukanya" in data.get("result_text", "")
                )
                details = f"Match found: {data.get('match_found')}, Sukanya detected in response"
                self.log_test("Search Schemes - Sukanya Query", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Search Schemes - Sukanya Query", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Search Schemes - Sukanya Query", False, f"Error: {str(e)}")
            return False

    def test_search_schemes_no_match(self):
        """Test search_schemes with unrelated query"""
        try:
            payload = {"query": "passport renewal visa"}
            response = requests.post(f"{self.base_url}/search-schemes", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                success = (
                    data.get("match_found") == False and
                    "I don't know" in data.get("result_text", "")
                )
                details = f"Match found: {data.get('match_found')}, 'I don't know' message returned"
                self.log_test("Search Schemes - No Match Query", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Search Schemes - No Match Query", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Search Schemes - No Match Query", False, f"Error: {str(e)}")
            return False

    def test_chat_with_scheme_query(self):
        """Test chat with scheme-related question that should trigger MCP tool"""
        if not self.user_id:
            self.log_test("Chat with Scheme Query", False, "No user_id available (login failed)")
            return False
            
        try:
            payload = {"user_id": self.user_id, "content": "kisan eligibility", "language": "hi"}
            response = requests.post(f"{self.base_url}/chat", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                bot_msg = data.get("bot_message", {})
                tool_calls = bot_msg.get("tool_calls", [])
                
                success = (
                    len(tool_calls) > 0 and
                    any(tc.get("tool_name") == "search_schemes" for tc in tool_calls) and
                    any("PM-KISAN" in str(tc.get("documents_scanned", [])) for tc in tool_calls)
                )
                
                details = f"Tool calls: {len(tool_calls)}, Search tool invoked: {any(tc.get('tool_name') == 'search_schemes' for tc in tool_calls)}"
                self.log_test("Chat with Scheme Query", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Chat with Scheme Query", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Chat with Scheme Query", False, f"Error: {str(e)}")
            return False

    def test_chat_with_greeting(self):
        """Test chat with greeting that should NOT trigger MCP tool"""
        if not self.user_id:
            self.log_test("Chat with Greeting", False, "No user_id available (login failed)")
            return False
            
        try:
            payload = {"user_id": self.user_id, "content": "hello", "language": "hi"}
            response = requests.post(f"{self.base_url}/chat", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                bot_msg = data.get("bot_message", {})
                tool_calls = bot_msg.get("tool_calls", [])
                
                success = len(tool_calls) == 0  # No tool calls for greeting
                details = f"Tool calls: {len(tool_calls)} (should be 0 for greeting)"
                self.log_test("Chat with Greeting", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Chat with Greeting", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Chat with Greeting", False, f"Error: {str(e)}")
            return False

    def test_transcribe_audio(self):
        """Test NEW /api/transcribe endpoint with Sarvam Saaras v3"""
        if not self.user_id:
            self.log_test("Transcribe Audio", False, "No user_id available (login failed)")
            return False
            
        try:
            # Use localhost for file uploads as external proxy blocks large uploads
            transcribe_url = "http://localhost:8001/api/transcribe"
            
            # Check if test audio file exists
            audio_path = "/tmp/test_speech.mp3"
            
            with open(audio_path, "rb") as f:
                files = {"audio": ("test_speech.mp3", f, "audio/mp3")}
                data = {"user_id": self.user_id}
                
                response = requests.post(transcribe_url, files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                success = (
                    result.get("success") == True and
                    "transcript_hi" in result and
                    "transcript_en" in result and
                    "user_message" in result and
                    "bot_message" in result
                )
                
                user_msg = result.get("user_message", {})
                bot_msg = result.get("bot_message", {})
                
                # Verify user message has transcription fields
                success = success and (
                    user_msg.get("type") == "transcription" and
                    "transcript_hi" in user_msg and
                    "transcript_en" in user_msg
                )
                
                hi_text = result.get("transcript_hi", "")[:50]
                en_text = result.get("transcript_en", "")[:50]
                details = f"Hindi: '{hi_text}...', English: '{en_text}...', Type: {user_msg.get('type')}"
                
                self.log_test("Transcribe Audio", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Transcribe Audio", False, f"HTTP Error", 200, response.status_code)
                return False
        except FileNotFoundError:
            self.log_test("Transcribe Audio", False, "Test audio file /tmp/test_speech.mp3 not found")
            return False
        except Exception as e:
            self.log_test("Transcribe Audio", False, f"Error: {str(e)}")
            return False

    def test_chat_history_with_transcription(self):
        """Test that chat history preserves transcription messages"""
        if not self.user_id:
            self.log_test("Chat History with Transcription", False, "No user_id available (login failed)")
            return False
            
        try:
            response = requests.get(f"{self.base_url}/chat/history/{self.user_id}", timeout=10)
            
            if response.status_code == 200:
                messages = response.json()
                
                # Look for transcription messages
                transcription_msgs = [m for m in messages if m.get("type") == "transcription"]
                success = len(transcription_msgs) > 0
                
                if success:
                    # Verify transcription message structure
                    trans_msg = transcription_msgs[-1]  # Get latest
                    success = (
                        "transcript_hi" in trans_msg and
                        "transcript_en" in trans_msg and
                        trans_msg.get("role") == "user"
                    )
                    details = f"Found {len(transcription_msgs)} transcription messages with proper structure"
                else:
                    details = f"No transcription messages found in {len(messages)} total messages"
                
                self.log_test("Chat History with Transcription", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Chat History with Transcription", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Chat History with Transcription", False, f"Error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run complete API test suite"""
        print("🚀 Starting Nagarik Sahayak API Test Suite (with MCP Testing)\n")
        
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
        
        # Test 5: NEW MCP Functionality
        print("🔧 Testing NEW MCP Tool Functionality...")
        self.test_mcp_tools_list()
        self.test_search_schemes_kisan()
        self.test_search_schemes_health()
        self.test_search_schemes_sukanya()
        self.test_search_schemes_no_match()
        self.test_chat_with_scheme_query()
        self.test_chat_with_greeting()
        
        # Test 6: NEW Transcription Feature (Sarvam Saaras v3)
        print("🎙️  Testing NEW Transcription Feature...")
        self.test_transcribe_audio()
        self.test_chat_history_with_transcription()
        
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