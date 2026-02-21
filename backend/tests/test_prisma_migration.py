"""
Test Suite for Prisma Migration - Full API Testing
Tests: Auth, Chat/Profiler flow, Profile, Schemes, Search, DEMO_MODE
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRootAPI:
    """Test root endpoint returns version 2.0.0"""
    
    def test_root_returns_version_2_0_0(self):
        """GET /api/ returns version 2.0.0"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "2.0.0"
        assert "Nagarik Sahayak" in data["message"]
        print("✓ Root API returns version 2.0.0")


class TestAuthAPI:
    """Test authentication endpoints with mock OTP"""
    
    def test_send_otp_success(self):
        """POST /api/auth/send-otp with phone='9999777701' returns success"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": "9999777701"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "OTP sent" in data["message"]
        print("✓ Send OTP returns success for 9999777701")
    
    def test_verify_otp_success(self):
        """POST /api/auth/verify-otp with phone='9999777701' otp='1234' returns success with user_id"""
        # First send OTP
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": "9999777701"})
        
        # Then verify
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": "9999777701", "otp": "1234"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "user_id" in data
        assert data["user_id"] is not None
        # user_id should be MongoDB ObjectId format (24-char hex)
        assert len(data["user_id"]) == 24
        assert re.match(r'^[a-f0-9]{24}$', data["user_id"]), f"user_id {data['user_id']} not ObjectId format"
        print(f"✓ Verify OTP returns success with user_id={data['user_id']}")
        return data["user_id"]
    
    def test_verify_otp_invalid(self):
        """POST /api/auth/verify-otp with wrong OTP returns failure"""
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": "9999777701", "otp": "9999"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        print("✓ Invalid OTP returns failure")


class TestChatProfilerFlow:
    """Test the 4-step profiler flow via Prisma"""
    
    @pytest.fixture(scope="class")
    def user_id(self):
        """Create user with a unique phone number"""
        import time
        # Use timestamp to create unique phone numbers
        phone = f"8888{int(time.time()) % 1000000:06d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "1234"})
        return response.json()["user_id"]
    
    def test_greeting_triggers_name_question(self, user_id):
        """POST /api/chat with greeting triggers profiler asking 'आपका नाम क्या है?'"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id,
            "content": "Hello",
            "language": "hi"
        })
        assert response.status_code == 200
        data = response.json()
        bot_msg = data["bot_message"]
        assert "आपका नाम क्या है" in bot_msg["content"]
        assert bot_msg.get("profiler_field") == "name"
        assert bot_msg.get("type") == "profiler"
        print("✓ Greeting triggers 'आपका नाम क्या है?' (profiler_field='name')")
    
    def test_name_answer_triggers_age_question(self, user_id):
        """POST /api/chat answering name then asks age"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id,
            "content": "Rajesh Kumar",
            "language": "hi"
        })
        assert response.status_code == 200
        data = response.json()
        bot_msg = data["bot_message"]
        assert "उम्र" in bot_msg["content"]
        assert bot_msg.get("profiler_field") == "age"
        print("✓ Name answer triggers age question (profiler_field='age')")
    
    def test_age_answer_triggers_income_question(self, user_id):
        """POST /api/chat answering age then asks income"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id,
            "content": "35",
            "language": "hi"
        })
        assert response.status_code == 200
        data = response.json()
        bot_msg = data["bot_message"]
        assert "आय" in bot_msg["content"]
        assert bot_msg.get("profiler_field") == "income"
        print("✓ Age answer triggers income question (profiler_field='income')")
    
    def test_income_answer_triggers_state_question(self, user_id):
        """POST /api/chat answering income then asks state"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id,
            "content": "50000",
            "language": "hi"
        })
        assert response.status_code == 200
        data = response.json()
        bot_msg = data["bot_message"]
        assert "राज्य" in bot_msg["content"]
        assert bot_msg.get("profiler_field") == "state"
        print("✓ Income answer triggers state question (profiler_field='state')")
    
    def test_state_answer_completes_profile(self, user_id):
        """POST /api/chat answering state completes profile with type='profiler_complete'"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id,
            "content": "Karnataka",
            "language": "hi"
        })
        assert response.status_code == 200
        data = response.json()
        bot_msg = data["bot_message"]
        assert bot_msg.get("type") == "profiler_complete"
        assert "pdf_url" in bot_msg
        assert "eligibility_results" in bot_msg
        assert len(bot_msg["eligibility_results"]) > 0
        print(f"✓ State answer completes profile with type='profiler_complete', pdf_url={bot_msg.get('pdf_url')}")


class TestProfileAPI:
    """Test profile retrieval from Prisma"""
    
    @pytest.fixture(scope="class")
    def user_id(self):
        """Create user with complete profile"""
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": "9999777703"})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": "9999777703", "otp": "1234"})
        uid = response.json()["user_id"]
        
        # Complete profiler flow
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": uid, "content": "hi", "language": "hi"})
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": uid, "content": "Test User", "language": "hi"})
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": uid, "content": "28", "language": "hi"})
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": uid, "content": "75000", "language": "hi"})
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": uid, "content": "Maharashtra", "language": "hi"})
        return uid
    
    def test_get_profile_returns_all_fields(self, user_id):
        """GET /api/profile/{user_id} returns profile with name, age, income, state from Prisma"""
        response = requests.get(f"{BASE_URL}/api/profile/{user_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "profile_data" in data
        profile = data["profile_data"]
        assert profile.get("name") == "Test User"
        assert profile.get("age") == 28
        assert profile.get("income") == 75000
        assert profile.get("state") == "Maharashtra"
        assert profile.get("_complete") == True
        print(f"✓ GET /api/profile/{user_id} returns profile: {profile.get('name')}, {profile.get('age')}, {profile.get('income')}, {profile.get('state')}")


class TestChatHistoryAPI:
    """Test chat history retrieval from Prisma ChatLog"""
    
    def test_get_chat_history(self):
        """GET /api/chat/history/{user_id} returns all chat messages from Prisma ChatLog"""
        # Create user and send messages
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": "9999777704"})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": "9999777704", "otp": "1234"})
        user_id = response.json()["user_id"]
        
        # Send a message
        requests.post(f"{BASE_URL}/api/chat", json={"user_id": user_id, "content": "test message", "language": "hi"})
        
        # Get history
        response = requests.get(f"{BASE_URL}/api/chat/history/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # At least user message + bot response
        print(f"✓ GET /api/chat/history/{user_id} returns {len(data)} messages from Prisma ChatLog")


class TestSchemesAPI:
    """Test schemes endpoints with Prisma Scheme table"""
    
    def test_get_schemes_returns_3(self):
        """GET /api/schemes returns 3 schemes from Prisma Scheme table"""
        response = requests.get(f"{BASE_URL}/api/schemes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        print(f"✓ GET /api/schemes returns {len(data)} schemes from Prisma")


class TestSearchSchemesAPI:
    """Test search-schemes MCP tool"""
    
    def test_search_farmer_returns_match(self):
        """POST /api/search-schemes with query='farmer' returns match"""
        response = requests.post(f"{BASE_URL}/api/search-schemes", json={"query": "farmer"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("match_found") == True
        assert "matched_schemes" in data or "results" in data
        print("✓ POST /api/search-schemes with query='farmer' returns match")


class TestDemoMode:
    """Test DEMO_MODE fast-path response"""
    
    def test_demo_trigger_returns_instant_result(self):
        """POST /api/chat with 'Mera beta 10th pass hai' returns instant Vidyasiri result + PDF"""
        # Check demo mode is enabled
        demo_status = requests.get(f"{BASE_URL}/api/demo/status").json()
        if not demo_status.get("demo_mode"):
            # Enable demo mode
            requests.post(f"{BASE_URL}/api/demo/toggle")
        
        # Create user
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": "9999777705"})
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": "9999777705", "otp": "1234"})
        user_id = response.json()["user_id"]
        
        # Send demo trigger
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id,
            "content": "Mera beta 10th pass hai",
            "language": "hi"
        })
        assert response.status_code == 200
        data = response.json()
        bot_msg = data["bot_message"]
        
        # Check for Vidyasiri result
        assert "विद्यासिरी" in bot_msg["content"] or "Vidyasiri" in bot_msg["content"]
        assert bot_msg.get("pdf_url") is not None
        assert bot_msg.get("type") == "profiler_complete"
        print(f"✓ DEMO_MODE: 'Mera beta 10th pass hai' returns Vidyasiri result + PDF ({bot_msg.get('pdf_url')})")


class TestAnalyticsEndpoints:
    """Test analytics and demo status endpoints"""
    
    def test_analytics_status(self):
        """GET /api/analytics/status returns enabled and dashboard_url"""
        response = requests.get(f"{BASE_URL}/api/analytics/status")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "dashboard_url" in data
        print(f"✓ Analytics status: enabled={data['enabled']}, dashboard_url={data['dashboard_url']}")
    
    def test_demo_status_and_toggle(self):
        """GET /api/demo/status and POST /api/demo/toggle work"""
        # Get status
        response = requests.get(f"{BASE_URL}/api/demo/status")
        assert response.status_code == 200
        initial_state = response.json()["demo_mode"]
        
        # Toggle
        response = requests.post(f"{BASE_URL}/api/demo/toggle")
        assert response.status_code == 200
        new_state = response.json()["demo_mode"]
        assert new_state != initial_state
        
        # Toggle back
        requests.post(f"{BASE_URL}/api/demo/toggle")
        print(f"✓ Demo toggle works: {initial_state} -> {new_state} -> {initial_state}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
