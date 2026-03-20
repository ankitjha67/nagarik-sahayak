"""
Test Iteration 14 Features:
- POST /api/upload-pdf accepts PDF file and returns success with pdf_id, pdf_url, filename, size
- POST /api/upload-pdf rejects non-PDF files with 400 error
- POST /api/chat/reset clears chat history and resets user profile
- After /api/chat/reset, profiler asks name again (first question)
- GET /api/schemes returns Sukanya Samriddhi with new PIB URL (not india.gov.in)
"""

import pytest
import requests
import os
import io
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPdfUpload:
    """PDF Upload Endpoint Tests"""
    
    def test_upload_pdf_accepts_valid_pdf(self):
        """POST /api/upload-pdf accepts PDF file and returns success with pdf_id, pdf_url, filename, size"""
        # Create a minimal valid PDF in memory
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n193\n%%EOF'
        
        files = {
            'file': ('test_document.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        data = {'user_id': 'test_upload_user'}
        
        response = requests.post(f"{BASE_URL}/api/upload-pdf", files=files, data=data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert result.get('success') == True, "Expected success=True"
        assert 'pdf_id' in result, "Expected pdf_id in response"
        assert 'pdf_url' in result, "Expected pdf_url in response"
        assert 'filename' in result, "Expected filename in response"
        assert 'size' in result, "Expected size in response"
        
        print(f"PDF Upload successful: pdf_id={result['pdf_id']}, filename={result['filename']}, size={result['size']}")
    
    def test_upload_pdf_rejects_non_pdf(self):
        """POST /api/upload-pdf rejects non-PDF files with 400 error"""
        # Create a text file
        text_content = b'This is not a PDF file, just plain text.'
        
        files = {
            'file': ('test_document.txt', io.BytesIO(text_content), 'text/plain')
        }
        data = {'user_id': 'test_upload_user'}
        
        response = requests.post(f"{BASE_URL}/api/upload-pdf", files=files, data=data)
        assert response.status_code == 400, f"Expected 400 for non-PDF, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert 'detail' in result, "Expected detail in error response"
        print(f"Non-PDF correctly rejected: {result['detail']}")
    
    def test_upload_pdf_rejects_wrong_extension(self):
        """POST /api/upload-pdf rejects files with wrong extension"""
        # Create a file with .jpg extension (even if content is PDF)
        image_content = b'\xff\xd8\xff\xe0\x00\x10JFIF'  # JPEG magic bytes
        
        files = {
            'file': ('test_image.jpg', io.BytesIO(image_content), 'image/jpeg')
        }
        data = {'user_id': 'test_upload_user'}
        
        response = requests.post(f"{BASE_URL}/api/upload-pdf", files=files, data=data)
        assert response.status_code == 400, f"Expected 400 for .jpg file, got {response.status_code}: {response.text}"
        print("Non-PDF extension correctly rejected")


class TestChatReset:
    """Chat Reset Endpoint Tests"""
    
    @pytest.fixture
    def test_user(self):
        """Create a test user with completed profiler"""
        phone = f"999{int(time.time()) % 10000000:07d}"
        
        # Send OTP
        requests.post(f"{BASE_URL}/api/auth/send-otp", json={"phone": phone})
        
        # Verify OTP
        verify_resp = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "123456"})
        assert verify_resp.status_code == 200
        user_id = verify_resp.json()['user_id']
        
        return {"user_id": user_id, "phone": phone}
    
    def test_chat_reset_clears_history(self, test_user):
        """POST /api/chat/reset clears chat history"""
        user_id = test_user['user_id']
        
        # First, create some chat history by sending messages
        requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id,
            "content": "namaste",
            "language": "hi"
        })
        
        # Verify there is chat history
        history_before = requests.get(f"{BASE_URL}/api/chat/history/{user_id}").json()
        assert len(history_before) > 0, "Should have chat history before reset"
        print(f"Chat history before reset: {len(history_before)} messages")
        
        # Reset chat
        reset_resp = requests.post(f"{BASE_URL}/api/chat/reset", json={"user_id": user_id})
        assert reset_resp.status_code == 200
        result = reset_resp.json()
        assert result.get('success') == True, "Expected success=True"
        
        # Verify chat history is cleared
        history_after = requests.get(f"{BASE_URL}/api/chat/history/{user_id}").json()
        assert len(history_after) == 0, f"Chat history should be empty after reset, got {len(history_after)}"
        print("Chat history cleared successfully")
    
    def test_chat_reset_resets_profile(self, test_user):
        """POST /api/chat/reset resets user profile"""
        user_id = test_user['user_id']
        
        # First complete the profiler
        messages = [
            ("namaste", "name"),  # Start -> asks name
            ("Ramesh Kumar", "age"),  # Name -> asks age
            ("35", "income"),  # Age -> asks income
            ("50000", "state"),  # Income -> asks state
            ("Karnataka", None)  # State -> profiler complete
        ]
        
        for content, expected_field in messages:
            requests.post(f"{BASE_URL}/api/chat", json={
                "user_id": user_id,
                "content": content,
                "language": "hi"
            })
        
        # Verify profile is complete
        profile_before = requests.get(f"{BASE_URL}/api/profile/{user_id}").json()
        assert profile_before.get('profile_complete') == True, "Profile should be complete before reset"
        print(f"Profile before reset: complete={profile_before.get('profile_complete')}")
        
        # Reset chat
        requests.post(f"{BASE_URL}/api/chat/reset", json={"user_id": user_id})
        
        # Verify profile is reset
        profile_after = requests.get(f"{BASE_URL}/api/profile/{user_id}").json()
        assert profile_after.get('profile_complete') != True, "Profile should NOT be complete after reset"
        print(f"Profile after reset: complete={profile_after.get('profile_complete', False)}")
    
    def test_after_reset_profiler_asks_name_again(self, test_user):
        """After /api/chat/reset, profiler asks name again (first question)"""
        user_id = test_user['user_id']
        
        # Complete the profiler first
        messages = ["namaste", "Ramesh Kumar", "35", "50000", "Karnataka"]
        for content in messages:
            requests.post(f"{BASE_URL}/api/chat", json={
                "user_id": user_id,
                "content": content,
                "language": "hi"
            })
        
        # Reset chat
        requests.post(f"{BASE_URL}/api/chat/reset", json={"user_id": user_id})
        
        # Send new message
        response = requests.post(f"{BASE_URL}/api/chat", json={
            "user_id": user_id,
            "content": "namaste",
            "language": "hi"
        })
        
        assert response.status_code == 200
        bot_msg = response.json()['bot_message']
        
        # Should ask name (first profiler question)
        # The profiler_field should be 'name'
        profiler_field = bot_msg.get('profiler_field', '')
        content = bot_msg.get('content', '')
        
        # Check if profiler is asking for name (first question)
        assert profiler_field == 'name' or 'नाम' in content, f"Expected name question, got: profiler_field={profiler_field}, content={content[:100]}"
        print(f"After reset, profiler asks: {content[:80]}...")
    
    def test_chat_reset_requires_user_id(self):
        """POST /api/chat/reset returns 400 without user_id"""
        response = requests.post(f"{BASE_URL}/api/chat/reset", json={})
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Reset correctly requires user_id")


class TestSukanyaSchemeUrl:
    """Sukanya Samriddhi Yojana URL Tests"""
    
    def test_schemes_returns_sukanya_with_pib_url(self):
        """GET /api/schemes returns Sukanya Samriddhi with new PIB URL (not india.gov.in)"""
        response = requests.get(f"{BASE_URL}/api/schemes")
        assert response.status_code == 200
        
        schemes = response.json()
        
        # Find Sukanya Samriddhi scheme
        sukanya = None
        for scheme in schemes:
            name = scheme.get('name', '') + scheme.get('title', '')
            if 'sukanya' in name.lower() or 'सुकन्या' in name:
                sukanya = scheme
                break
        
        assert sukanya is not None, "Sukanya Samriddhi scheme not found in /api/schemes"
        
        # Check the PDF URL
        pdf_url = sukanya.get('pdf_url', sukanya.get('pdfUrl', ''))
        print(f"Sukanya Samriddhi PDF URL: {pdf_url}")
        
        # Should NOT be india.gov.in
        assert 'india.gov.in' not in pdf_url, f"URL should NOT contain india.gov.in, got: {pdf_url}"
        
        # Should be static.pib.gov.in
        assert 'static.pib.gov.in' in pdf_url, f"URL should contain static.pib.gov.in, got: {pdf_url}"
        
        print("Sukanya Samriddhi Yojana URL correctly points to PIB")


class TestUploadedPdfDownload:
    """Test uploaded PDF can be downloaded"""
    
    def test_uploaded_pdf_downloadable(self):
        """Uploaded PDF can be downloaded via /api/pdf/{id}"""
        # Create and upload a PDF
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n193\n%%EOF'
        
        files = {
            'file': ('downloadable.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        
        upload_resp = requests.post(f"{BASE_URL}/api/upload-pdf", files=files, data={'user_id': 'test'})
        assert upload_resp.status_code == 200
        
        pdf_id = upload_resp.json()['pdf_id']
        pdf_url = upload_resp.json()['pdf_url']
        
        # Download the PDF
        download_resp = requests.get(f"{BASE_URL}{pdf_url}")
        assert download_resp.status_code == 200
        assert download_resp.headers.get('content-type') == 'application/pdf'
        assert download_resp.content.startswith(b'%PDF')
        print(f"PDF {pdf_id} downloadable at {pdf_url}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
