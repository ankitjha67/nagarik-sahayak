#!/usr/bin/env python3

import requests
import sys
import json
import time
import uuid
from datetime import datetime

class NagarikSahayakAPITester:
    def __init__(self):
        self.base_url = "https://citizen-helper.preview.emergentagent.com/api"
        self.user_id = None
        self.phone = f"999{uuid.uuid4().hex[:7]}"  # Fresh number for profiler test
        self.audio_msg_id = None
        self.pdf_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        
        print(f"🧪 Testing Citizen Helper API - Audio & Profiler Features")
        print(f"🔍 API Base: {self.base_url}")
        print(f"📱 Test Phone: {self.phone}")
        print(f"📅 Test Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

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
                    details += f": {', '.join(scheme_titles[:2])}..."
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
                profile_data = profile.get("profile_data", {})
                details = f"Phone: {profile.get('phone')}, Profile Complete: {profile.get('profile_complete', False)}"
                self.log_test("Get Profile", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Get Profile", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Get Profile", False, f"Error: {str(e)}")
            return False

    def test_profiler_complete_flow(self):
        """Test the complete profiler agent flow"""
        if not self.user_id:
            self.log_test("Profiler Complete Flow", False, "No user_id available")
            return False
            
        try:
            # Step 1: Greeting - should ask for name
            response = requests.post(f"{self.base_url}/chat", json={
                "user_id": self.user_id,
                "content": "नमस्ते",
                "language": "hi"
            }, timeout=15)
            
            if response.status_code != 200:
                self.log_test("Profiler Step 1", False, f"Status: {response.status_code}")
                return False
                
            data = response.json()
            bot_msg = data.get("bot_message", {})
            
            step1_success = (
                "नाम" in bot_msg.get("content", "") and
                bot_msg.get("type") == "profiler" and
                bot_msg.get("profiler_field") == "name"
            )
            self.log_test("Profiler Step 1 - Ask Name", step1_success, 
                         f"Type: {bot_msg.get('type')}, Field: {bot_msg.get('profiler_field')}")
            
            # Step 2: Provide name - should ask age
            response = requests.post(f"{self.base_url}/chat", json={
                "user_id": self.user_id,
                "content": "राहुल शर्मा",
                "language": "hi"
            }, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                bot_msg = data.get("bot_message", {})
                step2_success = (
                    "उम्र" in bot_msg.get("content", "") and
                    bot_msg.get("profiler_field") == "age"
                )
                self.log_test("Profiler Step 2 - Ask Age", step2_success,
                             f"Field: {bot_msg.get('profiler_field')}")
            else:
                self.log_test("Profiler Step 2 - Ask Age", False, f"Status: {response.status_code}")
                return False
                
            # Step 3: Provide age - should ask income
            response = requests.post(f"{self.base_url}/chat", json={
                "user_id": self.user_id,
                "content": "35",
                "language": "hi"
            }, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                bot_msg = data.get("bot_message", {})
                step3_success = (
                    "आय" in bot_msg.get("content", "") and
                    bot_msg.get("profiler_field") == "income"
                )
                self.log_test("Profiler Step 3 - Ask Income", step3_success,
                             f"Field: {bot_msg.get('profiler_field')}")
            else:
                self.log_test("Profiler Step 3 - Ask Income", False, f"Status: {response.status_code}")
                return False
                
            # Step 4: Provide income - should ask state
            response = requests.post(f"{self.base_url}/chat", json={
                "user_id": self.user_id,
                "content": "25000",
                "language": "hi"
            }, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                bot_msg = data.get("bot_message", {})
                step4_success = (
                    "राज्य" in bot_msg.get("content", "") and
                    bot_msg.get("profiler_field") == "state"
                )
                self.log_test("Profiler Step 4 - Ask State", step4_success,
                             f"Field: {bot_msg.get('profiler_field')}")
            else:
                self.log_test("Profiler Step 4 - Ask State", False, f"Status: {response.status_code}")
                return False
                
            # Step 5: Provide state - should complete and trigger eligibility + PDF generation
            response = requests.post(f"{self.base_url}/chat", json={
                "user_id": self.user_id,
                "content": "उत्तर प्रदेश",
                "language": "hi"
            }, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                bot_msg = data.get("bot_message", {})
                
                has_eligibility = "पात्रता" in bot_msg.get("content", "")
                has_tool_call = len(bot_msg.get("tool_calls", [])) > 0
                is_complete = bot_msg.get("type") == "profiler_complete"
                has_pdf_url = bool(bot_msg.get("pdf_url"))  # Should now auto-generate PDF
                
                step5_success = has_eligibility and has_tool_call and is_complete and has_pdf_url
                self.log_test("Profiler Step 5 - Complete & Eligibility + PDF", step5_success,
                             f"Eligibility: {has_eligibility}, Tool calls: {len(bot_msg.get('tool_calls', []))}, Type: {bot_msg.get('type')}, PDF URL: {has_pdf_url}")
                
                # Check tool call details
                if has_tool_call:
                    tool_calls = bot_msg.get("tool_calls", [])
                    eligibility_tool = any(tc.get("tool_name") == "eligibility_matcher" for tc in tool_calls)
                    self.log_test("Eligibility Tool Call", eligibility_tool,
                                 f"Tool names: {[tc.get('tool_name') for tc in tool_calls]}")
                
                # Store PDF ID for later testing
                if has_pdf_url and not hasattr(self, 'pdf_id'):
                    pdf_url = bot_msg.get("pdf_url", "")
                    if "/api/pdf/" in pdf_url:
                        self.pdf_id = pdf_url.split("/api/pdf/")[1]
                    
                return step1_success and step2_success and step3_success and step4_success and step5_success
            else:
                self.log_test("Profiler Step 5 - Complete & Eligibility + PDF", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Profiler Complete Flow", False, f"Error: {str(e)}")
            return False

    def test_profile_data_persistence(self):
        """Test profile data saved correctly in MongoDB"""
        if not self.user_id:
            self.log_test("Profile Data Persistence", False, "No user_id available")
            return False
            
        try:
            response = requests.get(f"{self.base_url}/profile/{self.user_id}", timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                profile_data = user_data.get("profile_data", {})
                profile_complete = user_data.get("profile_complete", False)
                
                # Verify all fields saved correctly
                name_correct = profile_data.get("name") == "राहुल शर्मा"
                age_correct = profile_data.get("age") == 35
                income_correct = profile_data.get("income") == 25000
                state_correct = profile_data.get("state") == "उत्तर प्रदेश"
                
                success = name_correct and age_correct and income_correct and state_correct and profile_complete
                details = f"Name: {name_correct}, Age: {age_correct} ({profile_data.get('age')}), Income: {income_correct} ({profile_data.get('income')}), State: {state_correct}, Complete: {profile_complete}"
                self.log_test("Profile Data Persistence", success, details)
                return success
            else:
                self.log_test("Profile Data Persistence", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Profile Data Persistence", False, f"Error: {str(e)}")
            return False

    def test_invalid_age_handling(self):
        """Test profiler handles invalid age input"""
        # Create new user for this test
        test_phone = f"888{uuid.uuid4().hex[:7]}"
        
        try:
            # Setup new user
            requests.post(f"{self.base_url}/auth/send-otp", json={"phone": test_phone}, timeout=10)
            verify_response = requests.post(f"{self.base_url}/auth/verify-otp",
                                          json={"phone": test_phone, "otp": "1234"}, timeout=10)
            
            if verify_response.status_code != 200:
                self.log_test("Invalid Age Test Setup", False, "Failed to create test user")
                return False
                
            test_user_id = verify_response.json().get("user_id")
            
            # Start profiler and provide name
            requests.post(f"{self.base_url}/chat", json={
                "user_id": test_user_id,
                "content": "Hello",
                "language": "hi"
            }, timeout=10)
            
            requests.post(f"{self.base_url}/chat", json={
                "user_id": test_user_id,
                "content": "टेस्ट यूजर",
                "language": "hi"
            }, timeout=10)
            
            # Provide invalid age
            response = requests.post(f"{self.base_url}/chat", json={
                "user_id": test_user_id,
                "content": "invalid_age_text",
                "language": "hi"
            }, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                bot_msg = data.get("bot_message", {})
                
                # Should re-ask age with error message
                still_asking_age = bot_msg.get("profiler_field") == "age"
                has_error_instruction = "संख्या में" in bot_msg.get("content", "")
                
                success = still_asking_age and has_error_instruction
                self.log_test("Invalid Age Handling", success,
                             f"Still asking age: {still_asking_age}, Has error msg: {has_error_instruction}")
                return success
            else:
                self.log_test("Invalid Age Handling", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Invalid Age Handling", False, f"Error: {str(e)}")
            return False

    def test_audio_transcribe_endpoint(self):
        """Test POST /api/transcribe returns audio_url field"""
        try:
            # Create minimal webm audio file
            test_audio_data = b'\x1a\x45\xdf\xa3\xa3B\x86\x81\x01B\xf7\x81\x01B\xf2\x81\x04B\xf3\x81\x08B\x82\x84webm'
            
            files = {'audio': ('test.webm', test_audio_data, 'audio/webm')}
            data = {'user_id': self.user_id or 'test_user'}
            
            response = requests.post(f"{self.base_url}/transcribe", 
                                   files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                user_msg = result.get("user_message", {})
                audio_url = user_msg.get("audio_url")
                
                if audio_url:
                    self.audio_msg_id = audio_url.split("/")[-1]
                    self.log_test("Audio Transcribe - Returns audio_url", True, f"Audio URL: {audio_url}")
                    return True
                else:
                    self.log_test("Audio Transcribe - Returns audio_url", False, "No audio_url in response")
                    return False
            else:
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", "")
                except:
                    error_detail = f"Status: {response.status_code}"
                    
                if "SARVAM_API_KEY" in error_detail:
                    self.log_test("Audio Transcribe - Returns audio_url", False, "SARVAM_API_KEY not configured")
                else:
                    self.log_test("Audio Transcribe - Returns audio_url", False, error_detail)
                return False
                
        except Exception as e:
            self.log_test("Audio Transcribe - Returns audio_url", False, f"Error: {str(e)}")
            return False

    def test_audio_playback_endpoint(self):
        """Test GET /api/audio/{msg_id} serves audio file"""
        if not self.audio_msg_id:
            self.log_test("Audio Playback Endpoint", False, "No audio_msg_id from transcribe test")
            return False
            
        try:
            response = requests.get(f"{self.base_url}/audio/{self.audio_msg_id}", timeout=15)
            
            success = response.status_code == 200
            content_type = response.headers.get('content-type', '')
            
            details = f"Content-Type: {content_type}"
            if success and 'audio' in content_type:
                details += f", Size: {len(response.content)} bytes"
                
            self.log_test("Audio Playback Endpoint", success, details, 200, response.status_code)
            return success
            
        except Exception as e:
            self.log_test("Audio Playback Endpoint", False, f"Error: {str(e)}")
            return False

    def test_post_profiler_normal_chat(self):
        """Test normal chat resumes after profiler completion"""
        if not self.user_id:
            self.log_test("Post-Profiler Normal Chat", False, "No user_id available")
            return False
            
        try:
            response = requests.post(f"{self.base_url}/chat", json={
                "user_id": self.user_id,
                "content": "पीएम किसान के बारे में बताएं",
                "language": "hi"
            }, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                bot_msg = data.get("bot_message", {})
                
                # Should not be profiler type anymore and should have scheme info
                not_profiler = bot_msg.get("type") != "profiler"
                has_kisan_info = "किसान" in bot_msg.get("content", "")
                has_tool_calls = len(bot_msg.get("tool_calls", [])) > 0
                
                success = not_profiler and has_kisan_info and has_tool_calls
                self.log_test("Post-Profiler Normal Chat", success,
                             f"Not profiler: {not_profiler}, Has किसान info: {has_kisan_info}, Tool calls: {len(bot_msg.get('tool_calls', []))}")
                return success
            else:
                self.log_test("Post-Profiler Normal Chat", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Post-Profiler Normal Chat", False, f"Error: {str(e)}")
            return False

    def test_update_profile(self):
        """Test profile update (legacy test)"""
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
        """Test MCP tools listing endpoint - should include both search_schemes and eligibility_matcher"""
        try:
            response = requests.get(f"{self.base_url}/mcp/tools", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", [])
                success = isinstance(tools, list) and len(tools) >= 2
                
                # Check for both tools
                search_tool = next((t for t in tools if t.get("name") == "search_schemes"), None)
                eligibility_tool = next((t for t in tools if t.get("name") == "eligibility_matcher"), None)
                
                search_present = search_tool is not None
                eligibility_present = eligibility_tool is not None
                
                success = success and search_present and eligibility_present
                
                details = f"Found {len(tools)} MCP tools - search_schemes: {search_present}, eligibility_matcher: {eligibility_present}"
                if search_tool and eligibility_tool:
                    details += f" | Eligibility tool desc: '{eligibility_tool.get('description', '')[:50]}...'"
                
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

    def test_eligibility_check_low_income(self):
        """Test eligibility_check with low income profile - should be eligible for all schemes"""
        try:
            payload = {
                "profile": {
                    "name": "राम कुमार",
                    "age": 30,
                    "income": 15000,  # Low income ₹15K/month
                    "state": "उत्तर प्रदेश"
                }
            }
            response = requests.post(f"{self.base_url}/eligibility-check", json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                success = (
                    data.get("match_found") == True and
                    len(results) == 3 and  # All 3 schemes
                    all(r.get("eligible") == True for r in results[:2])  # PM-KISAN & Ayushman should be eligible
                )
                
                # Check specific eligibility reasons
                pm_kisan = next((r for r in results if "PM-KISAN" in r.get("scheme", "")), None)
                ayushman = next((r for r in results if "Ayushman" in r.get("scheme", "")), None)
                
                details = f"Results: {len(results)} schemes, PM-KISAN eligible: {pm_kisan.get('eligible') if pm_kisan else 'N/A'}, Ayushman eligible: {ayushman.get('eligible') if ayushman else 'N/A'}"
                
                self.log_test("Eligibility Check - Low Income", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Eligibility Check - Low Income", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Eligibility Check - Low Income", False, f"Error: {str(e)}")
            return False

    def test_eligibility_check_high_income(self):
        """Test eligibility_check with high income (₹3L/month) - PM-KISAN & Ayushman should be ineligible"""
        try:
            payload = {
                "profile": {
                    "name": "अमित सिंह",
                    "age": 35,
                    "income": 300000,  # High income ₹3L/month
                    "state": "महाराष्ट्र"
                }
            }
            response = requests.post(f"{self.base_url}/eligibility-check", json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                # Find PM-KISAN and Ayushman results
                pm_kisan = next((r for r in results if "PM-KISAN" in r.get("scheme", "")), None)
                ayushman = next((r for r in results if "Ayushman" in r.get("scheme", "")), None)
                
                success = (
                    len(results) == 3 and
                    pm_kisan and not pm_kisan.get("eligible") and  # PM-KISAN should be ineligible
                    ayushman and not ayushman.get("eligible") and  # Ayushman should be ineligible
                    "₹300,000" in pm_kisan.get("reason", "") and  # Should mention income limit exceeded
                    "exceeds" in pm_kisan.get("reason", "").lower()
                )
                
                details = f"PM-KISAN ineligible: {not pm_kisan.get('eligible') if pm_kisan else 'N/A'}, Ayushman ineligible: {not ayushman.get('eligible') if ayushman else 'N/A'}, Income reason: {'₹300,000' in pm_kisan.get('reason', '') if pm_kisan else 'N/A'}"
                
                self.log_test("Eligibility Check - High Income", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Eligibility Check - High Income", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Eligibility Check - High Income", False, f"Error: {str(e)}")
            return False

    def test_eligibility_check_minor_age(self):
        """Test eligibility_check with minor age (15 years) - PM-KISAN & Sukanya should be ineligible"""
        try:
            payload = {
                "profile": {
                    "name": "रोहित कुमार",
                    "age": 15,  # Minor age
                    "income": 20000,
                    "state": "बिहार"
                }
            }
            response = requests.post(f"{self.base_url}/eligibility-check", json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                # Find PM-KISAN and Sukanya results
                pm_kisan = next((r for r in results if "PM-KISAN" in r.get("scheme", "")), None)
                sukanya = next((r for r in results if "Sukanya" in r.get("scheme", "")), None)
                
                success = (
                    len(results) == 3 and
                    pm_kisan and not pm_kisan.get("eligible") and  # PM-KISAN should be ineligible due to age
                    "Age 15" in pm_kisan.get("reason", "") and
                    "below minimum 18" in pm_kisan.get("reason", "")
                )
                
                details = f"PM-KISAN age ineligible: {not pm_kisan.get('eligible') if pm_kisan else 'N/A'}, Age reason present: {'Age 15' in pm_kisan.get('reason', '') if pm_kisan else 'N/A'}"
                
                self.log_test("Eligibility Check - Minor Age", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Eligibility Check - Minor Age", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Eligibility Check - Minor Age", False, f"Error: {str(e)}")
            return False

    def test_eligibility_check_with_user_id(self):
        """Test eligibility_check using user_id (fetch profile from DB)"""
        if not self.user_id:
            self.log_test("Eligibility Check - User ID", False, "No user_id available")
            return False
            
        try:
            payload = {"user_id": self.user_id}
            response = requests.post(f"{self.base_url}/eligibility-check", json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                success = (
                    data.get("match_found") == True and
                    len(results) >= 3 and
                    all("scheme" in r for r in results) and
                    all("eligible" in r for r in results) and
                    all("reason" in r for r in results)
                )
                
                details = f"Fetched profile via user_id, {len(results)} schemes evaluated, all have required fields"
                self.log_test("Eligibility Check - User ID", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Eligibility Check - User ID", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Eligibility Check - User ID", False, f"Error: {str(e)}")
            return False

    def test_eligibility_check_with_query_filter(self):
        """Test eligibility_check with query filter (e.g., 'ayushman') - should return only matched scheme"""
        try:
            payload = {
                "profile": {
                    "name": "सुनीता देवी",
                    "age": 28,
                    "income": 18000,
                    "state": "राजस्थान"
                },
                "query": "ayushman health"
            }
            response = requests.post(f"{self.base_url}/eligibility-check", json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                # Should only return Ayushman scheme due to query filter
                has_ayushman = any("Ayushman" in r.get("scheme", "") for r in results)
                has_only_ayushman = len(results) == 1 and has_ayushman
                
                success = has_only_ayushman
                details = f"Query filter 'ayushman': {len(results)} results, Ayushman present: {has_ayushman}, Only Ayushman: {has_only_ayushman}"
                
                self.log_test("Eligibility Check - Query Filter", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Eligibility Check - Query Filter", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Eligibility Check - Query Filter", False, f"Error: {str(e)}")
            return False

    def test_existing_user_eligibility_check(self):
        """Test eligibility_check with existing profiled user ID from credentials"""
        try:
            # Use the existing profiled user from credentials
            existing_user_id = "59e728b4-0808-4a95-8c34-5e5530dc7da8"
            payload = {"user_id": existing_user_id}
            response = requests.post(f"{self.base_url}/eligibility-check", json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                success = (
                    data.get("match_found") == True and
                    len(results) >= 3 and
                    all(isinstance(r.get("eligible"), bool) for r in results) and
                    all(r.get("reason") for r in results)  # All should have reasons
                )
                
                eligible_count = sum(1 for r in results if r.get("eligible"))
                details = f"Existing user: {len(results)} schemes, {eligible_count} eligible, all have reasons"
                
                self.log_test("Eligibility Check - Existing User", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Eligibility Check - Existing User", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Eligibility Check - Existing User", False, f"Error: {str(e)}")
            return False

    def test_generate_pdf_with_inline_profile(self):
        """Test POST /api/generate-pdf with inline profile"""
        try:
            payload = {
                "profile": {
                    "name": "सुधा देवी",
                    "age": 32,
                    "income": 18000,
                    "state": "उत्तर प्रदेश"
                }
            }
            response = requests.post(f"{self.base_url}/generate-pdf", json=payload, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                success = (
                    data.get("success") == True and
                    "pdf_url" in data and
                    "pdf_id" in data and
                    "eligible_count" in data and
                    "results" in data and
                    isinstance(data.get("results"), list) and
                    len(data.get("results", [])) >= 3
                )
                
                eligible_count = data.get("eligible_count", 0)
                pdf_url = data.get("pdf_url", "")
                details = f"PDF URL: {pdf_url}, Eligible: {eligible_count}/{len(data.get('results', []))}"
                
                self.log_test("Generate PDF - Inline Profile", success, details, 200, response.status_code)
                
                # Store pdf_id for later test
                self.pdf_id = data.get("pdf_id")
                return success
            else:
                self.log_test("Generate PDF - Inline Profile", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Generate PDF - Inline Profile", False, f"Error: {str(e)}")
            return False

    def test_generate_pdf_with_user_id(self):
        """Test POST /api/generate-pdf with user_id (fetch profile from DB)"""
        if not self.user_id:
            self.log_test("Generate PDF - User ID", False, "No user_id available")
            return False
        
        try:
            # First check if profile is complete
            profile_resp = requests.get(f"{self.base_url}/profile/{self.user_id}", timeout=10)
            if profile_resp.status_code != 200:
                self.log_test("Generate PDF - User ID", False, "Could not fetch user profile")
                return False
                
            profile_data = profile_resp.json()
            if not profile_data.get("profile_complete", False):
                self.log_test("Generate PDF - User ID", False, "User profile not complete - need to run profiler flow first")
                return False
            
            payload = {"user_id": self.user_id}
            response = requests.post(f"{self.base_url}/generate-pdf", json=payload, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                success = (
                    data.get("success") == True and
                    "pdf_url" in data and
                    "pdf_id" in data and
                    "eligible_count" in data and
                    "results" in data
                )
                
                details = f"PDF generated for user {self.user_id[:8]}..., eligible: {data.get('eligible_count')}"
                self.log_test("Generate PDF - User ID", success, details, 200, response.status_code)
                
                # Store pdf_id if not already stored
                if success and not hasattr(self, 'pdf_id'):
                    self.pdf_id = data.get("pdf_id")
                return success
            else:
                try:
                    error_details = response.json().get("detail", "")
                except:
                    error_details = f"Status: {response.status_code}"
                self.log_test("Generate PDF - User ID", False, f"HTTP Error: {error_details}", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Generate PDF - User ID", False, f"Error: {str(e)}")
            return False

    def test_generate_pdf_incomplete_profile(self):
        """Test POST /api/generate-pdf with incomplete profile (no name) - should return 400"""
        try:
            payload = {
                "profile": {
                    "age": 25,
                    "income": 20000,
                    "state": "बिहार"
                    # Missing name
                }
            }
            response = requests.post(f"{self.base_url}/generate-pdf", json=payload, timeout=15)
            
            success = response.status_code == 400
            details = "Correctly rejected incomplete profile (missing name)"
            
            self.log_test("Generate PDF - Incomplete Profile", success, details, 400, response.status_code)
            return success
        except Exception as e:
            self.log_test("Generate PDF - Incomplete Profile", False, f"Error: {str(e)}")
            return False

    def test_serve_pdf(self):
        """Test GET /api/pdf/{pdf_id} - should return PDF file"""
        if not hasattr(self, 'pdf_id') or not self.pdf_id:
            self.log_test("Serve PDF", False, "No pdf_id available from generate test")
            return False
            
        try:
            response = requests.get(f"{self.base_url}/pdf/{self.pdf_id}", timeout=15)
            
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                content_disposition = response.headers.get("content-disposition", "")
                
                success = (
                    "application/pdf" in content_type and
                    "Nagarik_Sahayak_Report_" in content_disposition and
                    len(response.content) > 1000  # PDF should be substantial
                )
                
                details = f"Content-Type: {content_type}, Size: {len(response.content)} bytes"
                self.log_test("Serve PDF", success, details, 200, response.status_code)
                return success
            else:
                self.log_test("Serve PDF", False, f"HTTP Error", 200, response.status_code)
                return False
        except Exception as e:
            self.log_test("Serve PDF", False, f"Error: {str(e)}")
            return False

    def test_serve_pdf_nonexistent(self):
        """Test GET /api/pdf/nonexistent - should return 404"""
        try:
            response = requests.get(f"{self.base_url}/pdf/nonexistent-id", timeout=10)
            
            success = response.status_code == 404
            details = "Correctly returned 404 for non-existent PDF"
            
            self.log_test("Serve PDF - Nonexistent", success, details, 404, response.status_code)
            return success
        except Exception as e:
            self.log_test("Serve PDF - Nonexistent", False, f"Error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run complete API test suite focusing on NEW PDF generation features"""
        print("🚀 Starting PDF Generation Feature Tests\n")
        
        # Test 1: Health Check
        if not self.test_health_check():
            print("💥 Critical: API health check failed. Stopping tests.")
            return self.print_summary()
        
        # Test 2: Authentication Flow (need fresh user for profiler)
        if not self.test_send_otp():
            print("💥 Critical: OTP sending failed. Stopping tests.")
            return self.print_summary()
            
        if not self.test_verify_otp():
            print("💥 Critical: OTP verification failed. Stopping tests.")
            return self.print_summary()
        
        # Test 3: PROFILER AGENT FLOW (creates complete profile + auto-generates PDF)
        print("\n🤖 Testing Updated Profiler Agent Flow...")
        self.test_profiler_complete_flow()  # Should now generate PDF automatically
        self.test_profile_data_persistence() 
        
        # Test 4: PDF GENERATION FEATURES (now user has complete profile)
        print("\n📄 Testing PDF Generation Features...")
        self.test_generate_pdf_with_inline_profile()
        self.test_generate_pdf_with_user_id()  # Should now work after profiler completion
        self.test_generate_pdf_incomplete_profile()
        self.test_serve_pdf()
        self.test_serve_pdf_nonexistent()
        
        # Test 5: ELIGIBILITY_MATCHER FEATURES (used by PDF generation)
        print("\n🔍 Testing Eligibility Matcher Features...")
        self.test_eligibility_check_low_income()
        self.test_eligibility_check_high_income()
        self.test_eligibility_check_minor_age()
        self.test_eligibility_check_with_user_id()
        self.test_eligibility_check_with_query_filter()
        self.test_existing_user_eligibility_check()
        
        # Test 6: UPDATED MCP TOOLS
        print("\n🛠️ Testing Updated MCP Tools...")
        self.test_mcp_tools_list()  # Now checks for both search_schemes AND eligibility_matcher
        
        # Test 7: POST-PROFILER CHAT
        print("\n💬 Testing Post-Profiler Chat...")
        self.test_post_profiler_normal_chat()
        
        # Test 8: Core functionality still works
        print("\n📱 Testing Core Features...")
        self.test_get_schemes()
        self.test_get_profile()
        self.test_search_schemes_kisan()
        self.test_search_schemes_health()
        
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