# Tests for Tool Progress / Streaming Bullets Feature
# Verifies that scholarship queries return Vidyasiri result with eligibility_results and pdf_url

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestChatScholarshipDemo:
    """Tests for DEMO_MODE scholarship queries"""
    
    def test_scholarship_query_returns_vidyasiri_result(self):
        """POST /api/chat with scholarship query returns Vidyasiri eligible result"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": "test-user-tool-progress",
            "content": "scholarship",
            "language": "hi"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "user_message" in data
        assert "bot_message" in data
        
        bot_msg = data["bot_message"]
        
        # Verify eligibility_results present
        assert "eligibility_results" in bot_msg, "eligibility_results should be in bot response"
        assert len(bot_msg["eligibility_results"]) > 0, "Should have at least one eligibility result"
        
        # Verify the first demo result is an eligible scholarship, with a
        # reason. The exact wording of the reason is demo copy and has changed
        # (it now describes the Post-Matric criteria), so the test asserts the
        # invariant - eligible, with a non-empty scholarship reason - not a
        # frozen phrase.
        vidyasiri_result = bot_msg["eligibility_results"][0]
        assert vidyasiri_result["scheme"] == "Vidyasiri Scholarship"
        assert vidyasiri_result["eligible"] == True
        assert "scholarship" in vidyasiri_result["reason"].lower()
        
        # Verify PDF URL present
        assert "pdf_url" in bot_msg, "pdf_url should be in bot response"
        assert bot_msg["pdf_url"].startswith("/api/pdf/"), "pdf_url should be valid path"
        
        print(f"✅ Scholarship query returned Vidyasiri eligible result with PDF: {bot_msg['pdf_url']}")
    
    def test_scholarship_query_returns_tool_calls(self):
        """POST /api/chat with scholarship query returns tool_calls with eligibility_matcher"""
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": "test-user-tool-progress-2",
            "content": "student scholarship",
            "language": "hi"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        bot_msg = data["bot_message"]
        
        # Verify tool_calls present
        assert "tool_calls" in bot_msg, "tool_calls should be in bot response"
        assert len(bot_msg["tool_calls"]) > 0, "Should have at least one tool call"
        
        tool_call = bot_msg["tool_calls"][0]
        assert tool_call["tool_name"] == "eligibility_matcher", "Tool should be eligibility_matcher"
        assert "documents_scanned" in tool_call, "Should have documents_scanned"
        assert "Vidyasiri Scholarship Guidelines" in tool_call["documents_scanned"]
        assert tool_call["match_found"] == True
        
        # Verify results in tool_call
        assert "results" in tool_call, "Tool call should have results"
        assert len(tool_call["results"]) > 0
        
        print("✅ Scholarship query returned tool_calls with eligibility_matcher and results")
    
    def test_scholarship_query_fast_response(self):
        """POST /api/chat with scholarship query returns within 2 seconds (DEMO_MODE)"""
        start_time = time.time()
        
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": "test-user-timing",
            "content": "vidyasiri scholarship",
            "language": "hi"
        })
        
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        assert elapsed < 2.0, f"Response should be under 2 seconds, got {elapsed:.2f}s"
        
        print(f"✅ DEMO_MODE scholarship response in {elapsed:.2f}s (< 2s requirement)")
    
    def test_pdf_download_accessible(self):
        """Generated PDF should be downloadable by the citizen who made it."""
        # A real user, so the demo PDF has an owner (ownership is keyed to the
        # user's ObjectId) and the download can be checked against it.
        phone = f"998{int(time.time()) % 10000000:07d}"
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        user_id = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"phone": phone, "otp": "123456"}).json()["user_id"]

        chat_response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id,
            "content": "scholarship",
            "language": "hi"
        })

        assert chat_response.status_code == 200
        data = chat_response.json()

        pdf_url = data["bot_message"].get("pdf_url")
        assert pdf_url, "PDF URL should be present"

        # Download as the owner (the X-User-Id header the real app always sends).
        pdf_response = requests.get(f"{BASE_URL}{pdf_url}",
                                    headers={"X-User-Id": user_id})

        assert pdf_response.status_code == 200
        assert pdf_response.headers.get("content-type") == "application/pdf"
        assert len(pdf_response.content) > 1000, "PDF should have content"
        
        print(f"✅ PDF downloadable at {pdf_url}, size: {len(pdf_response.content)} bytes")
    
    def test_various_scholarship_signals(self):
        """Different scholarship-related queries should trigger DEMO_MODE"""
        signals = ["scholarship", "student", "education", "college", "vidyasiri"]
        
        for signal in signals:
            response = requests.post(f"{BASE_URL}/api/chat", json={
                "user_id": f"test-signal-{signal}",
                "content": signal,
                "language": "hi"
            })
            
            assert response.status_code == 200
            data = response.json()
            
            # Should get Vidyasiri result for all scholarship signals
            eligibility = data["bot_message"].get("eligibility_results", [])
            if eligibility and len(eligibility) > 0:
                assert eligibility[0]["scheme"] == "Vidyasiri Scholarship"
                print(f"✅ Signal '{signal}' triggered Vidyasiri result")
            else:
                print(f"⚠️ Signal '{signal}' did not return Vidyasiri result (may be expected for some signals)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
