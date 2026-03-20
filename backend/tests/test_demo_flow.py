"""
Demo Flow Backend Tests
Tests the hardcoded demo mode for stage presentations.
- Exact phrase: 'Mera beta 10th pass hai' → profiler_complete + 2 eligible schemes + PDF
- Hindi variations, education keywords
- Response time < 2 seconds
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


class TestDemoFlowBackend:
    """Backend tests for hardcoded demo flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get a fresh user ID for each test"""
        # Send OTP
        otp_resp = requests.post(
            f"{BASE_URL}/api/auth/send-otp",
            json={"phone": "9876543210"}
        )
        assert otp_resp.status_code == 200
        
        # Verify OTP
        verify_resp = requests.post(
            f"{BASE_URL}/api/auth/verify-otp",
            json={"phone": "9876543210", "otp": "123456"}
        )
        assert verify_resp.status_code == 200
        data = verify_resp.json()
        assert data["success"] is True
        self.user_id = data["user_id"]
    
    def test_exact_demo_trigger_returns_profiler_complete(self):
        """Test: POST /api/chat with 'Mera beta 10th pass hai' returns type='profiler_complete'"""
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "user_id": self.user_id,
                "content": "Mera beta 10th pass hai",
                "language": "hi"
            }
        )
        duration = time.time() - start
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        
        # Verify response type
        assert data["bot_message"]["type"] == "profiler_complete"
        
        # Response time < 2 seconds
        assert duration < 2.0, f"Response took {duration:.2f}s, expected < 2s"
        print(f"Response time: {duration:.3f}s")
    
    def test_demo_response_contains_rajesh_kumar_profile(self):
        """Test: Response profile shows Rajesh Kumar, age 42, income 18000, state Karnataka"""
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "user_id": self.user_id,
                "content": "Mera beta 10th pass hai",
                "language": "hi"
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Check tool_calls contain profile data
        tool_calls = data["bot_message"]["tool_calls"]
        assert len(tool_calls) > 0
        
        profile = tool_calls[0]["tool_input"]["profile"]
        assert profile["name"] == "Rajesh Kumar"
        assert profile["age"] == 42
        assert profile["income"] == 18000
        assert profile["state"] == "Karnataka"
        assert profile["child"] == "Son, 10th pass"
        print(f"Profile verified: {profile}")
    
    def test_demo_response_contains_two_eligible_schemes(self):
        """Test: Response includes 2 eligible schemes: Vidyasiri + PM-KISAN"""
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "user_id": self.user_id,
                "content": "Mera beta 10th pass hai",
                "language": "hi"
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        eligibility_results = data["bot_message"]["eligibility_results"]
        assert len(eligibility_results) == 2, f"Expected 2 schemes, got {len(eligibility_results)}"
        
        scheme_names = [r["scheme"] for r in eligibility_results]
        assert "Vidyasiri Scholarship" in scheme_names
        assert "PM-KISAN Samman Nidhi" in scheme_names
        
        # Both should be eligible
        for result in eligibility_results:
            assert result["eligible"] is True, f"{result['scheme']} should be eligible"
        
        print(f"Schemes: {scheme_names}")
    
    def test_demo_response_includes_downloadable_pdf_url(self):
        """Test: Response includes pdf_url that is downloadable at GET /api/pdf/{id}"""
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "user_id": self.user_id,
                "content": "Mera beta 10th pass hai",
                "language": "hi"
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        pdf_url = data["bot_message"]["pdf_url"]
        assert pdf_url, "pdf_url should not be empty"
        assert pdf_url.startswith("/api/pdf/"), f"pdf_url should start with /api/pdf/, got {pdf_url}"
        
        # Test PDF download
        pdf_resp = requests.get(f"{BASE_URL}{pdf_url}")
        assert pdf_resp.status_code == 200, f"PDF download failed: {pdf_resp.status_code}"
        assert pdf_resp.headers.get("content-type") == "application/pdf"
        assert len(pdf_resp.content) > 1000, "PDF should have substantial content"
        
        print(f"PDF URL: {pdf_url}, Size: {len(pdf_resp.content)} bytes")
    
    def test_hindi_variation_trigger(self):
        """Test: Hindi variation 'मेरा बेटा 10th पास है' triggers demo"""
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "user_id": self.user_id,
                "content": "मेरा बेटा 10th पास है",
                "language": "hi"
            }
        )
        duration = time.time() - start
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot_message"]["type"] == "profiler_complete"
        assert len(data["bot_message"]["eligibility_results"]) == 2
        assert duration < 2.0, f"Response took {duration:.2f}s"
        print(f"Hindi trigger response time: {duration:.3f}s")
    
    def test_scholarship_keyword_trigger(self):
        """Test: 'scholarship' keyword triggers demo"""
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "user_id": self.user_id,
                "content": "scholarship",
                "language": "hi"
            }
        )
        duration = time.time() - start
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot_message"]["type"] == "profiler_complete"
        assert len(data["bot_message"]["eligibility_results"]) == 2
        assert duration < 2.0
        print(f"Scholarship keyword response time: {duration:.3f}s")
    
    def test_10th_pass_keyword_trigger(self):
        """Test: '10th pass' keyword triggers demo"""
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "user_id": self.user_id,
                "content": "10th pass",
                "language": "hi"
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot_message"]["type"] == "profiler_complete"
        assert len(data["bot_message"]["eligibility_results"]) == 2
        print("10th pass trigger works")
    
    def test_student_keyword_trigger(self):
        """Test: 'student' keyword triggers demo"""
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "user_id": self.user_id,
                "content": "student",
                "language": "hi"
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot_message"]["type"] == "profiler_complete"
        assert len(data["bot_message"]["eligibility_results"]) == 2
        print("student trigger works")
    
    def test_tool_calls_contain_documents_scanned(self):
        """Test: Response tool_calls show 2 documents scanned"""
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "user_id": self.user_id,
                "content": "Mera beta 10th pass hai",
                "language": "hi"
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        tool_calls = data["bot_message"]["tool_calls"]
        assert len(tool_calls) > 0
        
        docs = tool_calls[0]["documents_scanned"]
        assert len(docs) == 2
        assert "Vidyasiri Scholarship Guidelines" in docs
        assert "PM-KISAN Operational Guidelines" in docs
        print(f"Documents scanned: {docs}")
    
    def test_response_time_under_2_seconds(self):
        """Test: Demo response completes in < 2 seconds (multiple runs)"""
        times = []
        for i in range(3):
            start = time.time()
            resp = requests.post(
                f"{BASE_URL}/api/chat",
                json={
                    "user_id": self.user_id,
                    "content": "Mera beta 10th pass hai",
                    "language": "hi"
                }
            )
            duration = time.time() - start
            times.append(duration)
            assert resp.status_code == 200
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        assert max_time < 2.0, f"Max response time {max_time:.2f}s exceeds 2s"
        print(f"Response times: {[f'{t:.3f}s' for t in times]}, Avg: {avg_time:.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
