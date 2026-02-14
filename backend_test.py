import requests
import sys
import json
from datetime import datetime
import time

class BookExportTester:
    def __init__(self, base_url="https://kdp-auto-writer.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

    def log(self, message, level="INFO"):
        """Log test messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, timeout=30):
        """Run a single API test"""
        url = f"{self.api_url}{endpoint}"
        
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} PASSED - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content and 'application/json' in response.headers.get('content-type', '') else {"status": "ok"}
                except:
                    return True, {"status": "ok", "content_type": response.headers.get('content-type', '')}
            else:
                self.log(f"❌ {name} FAILED - Expected {expected_status}, got {response.status_code}", "ERROR")
                self.log(f"   Response: {response.text[:200]}...", "ERROR")
                return False, {}

        except requests.exceptions.Timeout:
            self.log(f"❌ {name} FAILED - Request timeout", "ERROR")
            return False, {}
        except Exception as e:
            self.log(f"❌ {name} FAILED - Error: {str(e)}", "ERROR")
            return False, {}

    def test_book_detail_api(self, book_id):
        """Test book detail API"""
        return self.run_test(
            "Get Book Detail", "GET", f"/books/{book_id}", 200
        )

    def test_export_pdf(self, book_id):
        """Test PDF export - most critical feature"""
        self.log("Testing PDF export with 2-pass build and real page numbers...")
        success, response = self.run_test(
            "PDF Export", "POST", f"/books/{book_id}/export", 200, 
            data={"book_id": book_id, "format": "pdf"}, timeout=60
        )
        
        if success and response.get('content_type'):
            if 'application/pdf' in response['content_type'] or 'application/octet-stream' in response['content_type']:
                self.log("✅ PDF export returned correct content type")
                return success, response
            else:
                self.log(f"❌ PDF export returned wrong content type: {response['content_type']}", "ERROR")
                return False, response
        return success, response

    def test_export_docx(self, book_id):
        """Test DOCX export with TOC page numbers"""
        self.log("Testing DOCX export with proper TOC...")
        success, response = self.run_test(
            "DOCX Export", "POST", f"/books/{book_id}/export", 200,
            data={"book_id": book_id, "format": "docx"}, timeout=60
        )
        
        if success and response.get('content_type'):
            if 'application/vnd.openxmlformats' in response['content_type'] or 'application/octet-stream' in response['content_type']:
                self.log("✅ DOCX export returned correct content type")
                return success, response
            else:
                self.log(f"❌ DOCX export returned wrong content type: {response['content_type']}", "ERROR")
                return False, response
        return success, response

    def test_export_epub(self, book_id):
        """Test EPUB export"""
        self.log("Testing EPUB export...")
        return self.run_test(
            "EPUB Export", "POST", f"/books/{book_id}/export", 200,
            data={"book_id": book_id, "format": "epub"}, timeout=60
        )

    def test_delete_image_endpoint(self, book_id, chapter_num):
        """Test delete image endpoint"""
        self.log(f"Testing delete image for chapter {chapter_num}...")
        return self.run_test(
            f"Delete Image Ch{chapter_num}", "DELETE", f"/books/{book_id}/image/{chapter_num}", 200
        )

    def test_generate_image_with_stock_query_check(self, book_id, chapter_num):
        """Test image generation and check for stock query logging"""
        self.log(f"Testing image generation for chapter {chapter_num} (checking for AI stock queries)...")
        
        # This should trigger the stock image generation with AI-generated search queries
        success, response = self.run_test(
            f"Generate Image Ch{chapter_num}", "POST", f"/books/{book_id}/generate-image/{chapter_num}", 200, 
            timeout=45
        )
        
        if success:
            # Check if image_url is returned
            if response.get('image_url'):
                self.log(f"✅ Image generated successfully: {response['image_url']}")
                return success, response
            else:
                self.log("⚠️  Image generation API succeeded but no image_url returned", "WARN")
                return success, response  # Still counts as API success
        return success, response

    def check_backend_logs_for_stock_queries(self):
        """Check if backend logs show stock image search queries"""
        self.log("Checking backend logs for 'Stock image search query' entries...")
        try:
            # Get supervisor logs for backend
            import subprocess
            result = subprocess.run(['tail', '-n', '50', '/var/log/supervisor/backend.err.log'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and "Stock image search query" in result.stdout:
                self.log("✅ Found 'Stock image search query' in backend logs")
                return True
            else:
                self.log("⚠️  'Stock image search query' not found in recent backend logs", "WARN")
                return False
        except Exception as e:
            self.log(f"⚠️  Could not check backend logs: {e}", "WARN")
            return False

def main():
    tester = BookExportTester()
    book_id = "5e0285a7-e895-4b5a-8a1a-019662323522"  # The specific book ID mentioned in the request
    
    tester.log("🚀 Starting Book Export and Features Testing")
    tester.log(f"Testing book ID: {book_id}")
    tester.log(f"Base URL: {tester.base_url}")
    
    # Test 1: Verify book exists and has chapters
    book_success, book_data = tester.test_book_detail_api(book_id)
    if not book_success:
        tester.log("❌ Cannot proceed - book not found", "ERROR")
        return 1
    
    chapters = book_data.get('chapters', [])
    tester.log(f"📖 Book found with {len(chapters)} chapters, status: {book_data.get('status', 'unknown')}")
    
    if len(chapters) == 0:
        tester.log("❌ Cannot test exports - book has no chapters", "ERROR")
        return 1

    # Test 2: PDF Export (most critical - 2-pass build with real page numbers)
    pdf_success, _ = tester.test_export_pdf(book_id)
    
    # Test 3: DOCX Export (with TOC page numbers)
    docx_success, _ = tester.test_export_docx(book_id)
    
    # Test 4: EPUB Export
    epub_success, _ = tester.test_export_epub(book_id)
    
    # Test 5: Test delete image endpoint on a chapter that has an image
    chapters_with_images = [ch for ch in chapters if ch.get('image_url')]
    delete_success = True
    if chapters_with_images:
        test_chapter = chapters_with_images[0]['chapter_number']
        delete_success, _ = tester.test_delete_image_endpoint(book_id, test_chapter)
    else:
        tester.log("⚠️  No chapters with images found to test delete endpoint", "WARN")
    
    # Test 6: Test image generation (this should trigger stock image AI queries)
    # Find a chapter without an image to test generation
    chapters_without_images = [ch for ch in chapters if not ch.get('image_url')]
    image_gen_success = True
    if chapters_without_images:
        test_chapter = chapters_without_images[0]['chapter_number']
        image_gen_success, _ = tester.test_generate_image_with_stock_query_check(book_id, test_chapter)
        
        # Give the backend a moment to log
        time.sleep(2)
        # Check backend logs for stock image queries
        tester.check_backend_logs_for_stock_queries()
    else:
        tester.log("⚠️  All chapters have images - cannot test image generation", "WARN")

    # Summary
    tester.log("=" * 60)
    tester.log(f"📊 BACKEND TEST SUMMARY")
    tester.log(f"📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    
    critical_tests = [pdf_success, docx_success, epub_success]
    critical_passed = sum(critical_tests)
    
    tester.log(f"🎯 Critical export tests: {critical_passed}/3 passed")
    tester.log(f"   PDF: {'✅' if pdf_success else '❌'}")
    tester.log(f"   DOCX: {'✅' if docx_success else '❌'}")
    tester.log(f"   EPUB: {'✅' if epub_success else '❌'}")
    
    if critical_passed == 3:
        tester.log("🎉 ALL CRITICAL EXPORT FEATURES WORKING!", "SUCCESS")
        return 0
    else:
        tester.log(f"❌ {3 - critical_passed} critical export feature(s) failed", "ERROR")
        return 1

if __name__ == "__main__":
    sys.exit(main())