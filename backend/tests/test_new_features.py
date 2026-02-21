"""
Test New Features (Iteration 10):
- Demo Mode toggle endpoints (GET /api/demo/status, POST /api/demo/toggle)
- Hindi voice button presence (browser SpeechSynthesis)
- Tick marks animation (sent/delivered/read)
- /app/pitch.md file validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDemoModeEndpoints:
    """Demo Mode toggle API tests"""
    
    def test_demo_status_returns_boolean(self):
        """GET /api/demo/status returns {demo_mode: true/false}"""
        response = requests.get(f"{BASE_URL}/api/demo/status")
        assert response.status_code == 200
        data = response.json()
        assert "demo_mode" in data
        assert isinstance(data["demo_mode"], bool)
        print(f"Demo status: {data['demo_mode']}")
    
    def test_demo_toggle_changes_state(self):
        """POST /api/demo/toggle toggles demo_mode and returns new state"""
        # Get initial state
        initial = requests.get(f"{BASE_URL}/api/demo/status").json()
        initial_state = initial["demo_mode"]
        
        # Toggle
        toggle_response = requests.post(f"{BASE_URL}/api/demo/toggle")
        assert toggle_response.status_code == 200
        toggled = toggle_response.json()
        assert "demo_mode" in toggled
        assert toggled["demo_mode"] != initial_state
        print(f"Toggled from {initial_state} to {toggled['demo_mode']}")
    
    def test_demo_toggle_roundtrip(self):
        """Toggle works round-trip (true→false→true)"""
        # Get initial state
        initial = requests.get(f"{BASE_URL}/api/demo/status").json()["demo_mode"]
        
        # First toggle
        first_toggle = requests.post(f"{BASE_URL}/api/demo/toggle").json()["demo_mode"]
        assert first_toggle != initial
        
        # Second toggle - should return to initial
        second_toggle = requests.post(f"{BASE_URL}/api/demo/toggle").json()["demo_mode"]
        assert second_toggle == initial
        print(f"Round-trip: {initial} → {first_toggle} → {second_toggle}")


class TestPitchFile:
    """Verify /app/pitch.md exists and contains required sections"""
    
    def test_pitch_file_exists(self):
        """Check /app/pitch.md exists"""
        assert os.path.exists("/app/pitch.md"), "pitch.md should exist"
    
    def test_pitch_file_sections(self):
        """Check pitch.md contains required sections"""
        with open("/app/pitch.md", "r") as f:
            content = f.read()
        
        required_sections = [
            "Problem",
            "Demo",
            "How It Works",
            "Impact",
            "The Ask"
        ]
        
        for section in required_sections:
            assert section in content, f"Missing section: {section}"
            print(f"Found section: {section}")
    
    def test_pitch_file_demo_phrase(self):
        """Check pitch.md contains demo phrase"""
        with open("/app/pitch.md", "r") as f:
            content = f.read()
        
        assert "Mera beta 10th pass hai" in content, "Missing demo phrase"
        print("Demo phrase found")
    
    def test_pitch_file_quick_reference_table(self):
        """Check pitch.md contains quick reference table"""
        with open("/app/pitch.md", "r") as f:
            content = f.read()
        
        assert "Quick Reference" in content, "Missing Quick Reference section"
        assert "Demo phrase" in content, "Missing demo phrase in table"
        print("Quick reference table found")


class TestChatEndpointWithNewFeatures:
    """Verify chat response includes status for tick marks"""
    
    def test_chat_message_has_status(self):
        """Verify user message status is returned (sent/delivered/read)"""
        # Send a message
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": "test_tick_user",
            "content": "test message",
            "language": "hi"
        })
        assert response.status_code == 200
        data = response.json()
        
        # Check user_message has status
        assert "user_message" in data
        assert "status" in data["user_message"]
        status = data["user_message"]["status"]
        assert status in ["sent", "delivered", "read"]
        print(f"User message status: {status}")
        
        # Check bot_message has status
        assert "bot_message" in data
        assert "status" in data["bot_message"]
        print(f"Bot message status: {data['bot_message']['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
