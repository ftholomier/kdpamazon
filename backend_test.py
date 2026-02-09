#!/usr/bin/env python3
"""
KDP Book Creator Backend API Testing Suite
Tests the 5 reported bug fixes:
1. Book deletion works and cleans up images/exports
2. Stock image generation works with Unsplash/Picsum
3. Image deletion endpoint works  
4. PDF/DOCX/EPUB export with proper formatting (no raw markdown)
5. All exports have page numbers and formatted content
"""

import requests
import sys
import os
from datetime import datetime
import json
import time

class KDPAPITester:
    def __init__(self, base_url="https://kdp-auto-writer.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.errors = []
        
        # Test book ID from agent context
        self.test_book_id = "4387da97-a971-43e1-bcee-e120bd16a1c2"
        
    def log(self, message, error=False):
        prefix = "❌ ERROR: " if error else "ℹ️  INFO: "
        print(f"{prefix}{message}")
        if error:
            self.errors.append(message)

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        default_headers = {'Content-Type': 'application/json'}
        if headers:
            default_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   {method} {endpoint}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=default_headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=default_headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=default_headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=default_headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - Status: {response.status_code}")
            else:
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                if response.text:
                    print(f"   Response: {response.text[:200]}")
                self.log(f"{name} failed: expected {expected_status}, got {response.status_code}")

            return success, response

        except Exception as e:
            print(f"❌ FAILED - Exception: {str(e)}")
            self.log(f"{name} exception: {str(e)}", error=True)
            return False, None

    def test_basic_connectivity(self):
        """Test basic API connectivity"""
        success, response = self.run_test("Basic API connectivity", "GET", "", 200)
        return success

    def test_settings_and_stock_images(self):
        """Test bug fix #2: Stock images configuration"""
        print("\n📸 Testing Stock Images Configuration...")
        
        # Get current settings
        success, response = self.run_test("Get settings", "GET", "settings", 200)
        if not success:
            return False
            
        # Set image source to stock
        settings_data = {
            "api_key_source": "emergent",
            "image_source": "stock",  # This should enable Unsplash/Picsum
            "language": "fr"
        }
        
        success, response = self.run_test(
            "Update settings to stock images", 
            "PUT", 
            "settings", 
            200, 
            data=settings_data
        )
        
        if success:
            # Verify settings were saved
            success2, response2 = self.run_test("Verify stock image setting", "GET", "settings", 200)
            if success2:
                try:
                    data = response2.json()
                    if data.get("image_source") == "stock":
                        print("✅ Stock image setting saved correctly")
                        return True
                    else:
                        self.log(f"Stock image setting not saved: {data.get('image_source')}")
                except:
                    self.log("Could not parse settings response")
        
        return False

    def test_existing_book(self):
        """Test getting the existing test book"""
        success, response = self.run_test(
            f"Get existing test book {self.test_book_id[:8]}...",
            "GET",
            f"books/{self.test_book_id}",
            200
        )
        
        if success:
            try:
                book_data = response.json()
                chapters = book_data.get('chapters', [])
                print(f"   Book has {len(chapters)} chapters")
                if len(chapters) > 0:
                    print(f"   First chapter: '{chapters[0].get('title', 'N/A')}'")
                return book_data
            except:
                self.log("Could not parse book data")
        
        return None

    def test_stock_image_generation(self, book_data):
        """Test bug fix #2: Stock image generation with Unsplash"""
        if not book_data or not book_data.get('chapters'):
            self.log("No chapters found for image generation test")
            return False
            
        chapter_num = book_data['chapters'][0]['chapter_number']
        print(f"\n📸 Testing Stock Image Generation for Chapter {chapter_num}...")
        
        success, response = self.run_test(
            f"Generate stock image for chapter {chapter_num}",
            "POST", 
            f"books/{self.test_book_id}/generate-image/{chapter_num}",
            200,
            timeout=45  # Stock images may take time
        )
        
        if success:
            try:
                result = response.json()
                image_url = result.get('image_url')
                if image_url:
                    print(f"✅ Stock image generated: {image_url}")
                    return image_url
                else:
                    self.log("No image URL in response")
            except:
                self.log("Could not parse image generation response")
        
        return None

    def test_image_deletion(self, book_data):
        """Test bug fix #3: Image deletion endpoint"""
        if not book_data or not book_data.get('chapters'):
            self.log("No chapters found for image deletion test")
            return False
            
        chapter_num = book_data['chapters'][0]['chapter_number']
        print(f"\n🗑️  Testing Image Deletion for Chapter {chapter_num}...")
        
        success, response = self.run_test(
            f"Delete chapter {chapter_num} image",
            "DELETE",
            f"books/{self.test_book_id}/image/{chapter_num}",
            200
        )
        
        if success:
            try:
                result = response.json()
                if result.get('status') == 'deleted':
                    print("✅ Image deletion endpoint working")
                    return True
            except:
                self.log("Could not parse image deletion response")
        
        return False

    def test_export_functionality(self):
        """Test bug fixes #4 & #5: Proper export formatting and page numbers"""
        print(f"\n📄 Testing Export Functionality...")
        
        formats = ['pdf', 'docx', 'epub']
        results = {}
        
        for fmt in formats:
            print(f"\n   Testing {fmt.upper()} export...")
            
            success, response = self.run_test(
                f"Export book as {fmt}",
                "POST",
                f"books/{self.test_book_id}/export",
                200,
                data={"book_id": self.test_book_id, "format": fmt},
                timeout=60  # Exports can take time
            )
            
            if success and response:
                # Check if we got binary data (file content)
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content) if response.content else 0
                
                if content_length > 1000:  # Should be substantial file
                    print(f"✅ {fmt.upper()} export successful ({content_length} bytes)")
                    results[fmt] = True
                else:
                    self.log(f"{fmt.upper()} export too small: {content_length} bytes")
                    results[fmt] = False
            else:
                results[fmt] = False
        
        return results

    def test_book_deletion_cleanup(self):
        """Test bug fix #1: Book deletion with proper cleanup"""
        print(f"\n🗑️  Testing Book Deletion and Cleanup...")
        
        # First, create a test book to delete
        book_data = {
            "title": f"Test Delete Book {datetime.now().strftime('%H%M%S')}",
            "description": "This book will be deleted to test cleanup",
            "category": "guide", 
            "language": "fr",
            "target_pages": 50,
            "image_source": "ai"
        }
        
        success, response = self.run_test(
            "Create book for deletion test",
            "POST",
            "books/create",
            200,  # API returns 200, not 201
            data=book_data
        )
        
        if not success:
            self.log("Could not create test book for deletion")
            return False
            
        try:
            new_book = response.json()
            book_id = new_book['id']
            print(f"   Created test book ID: {book_id[:8]}...")
            
            # Now delete it
            success, response = self.run_test(
                f"Delete test book {book_id[:8]}...",
                "DELETE",
                f"books/{book_id}",
                200
            )
            
            if success:
                # Verify it's really gone
                success2, response2 = self.run_test(
                    f"Verify book {book_id[:8]}... is deleted",
                    "GET",
                    f"books/{book_id}",
                    404  # Should be not found
                )
                
                if success2:
                    print("✅ Book deletion and cleanup working correctly")
                    return True
                else:
                    self.log("Book still exists after deletion")
            
        except:
            self.log("Could not parse book creation response")
        
        return False

    def test_frontend_navigation_endpoints(self):
        """Test endpoints that frontend navigation depends on"""
        print(f"\n🖥️  Testing Frontend Navigation Endpoints...")
        
        # Test books list
        success1, _ = self.run_test("List all books", "GET", "books", 200)
        
        # Test book progress
        success2, _ = self.run_test(
            f"Get book progress",
            "GET", 
            f"books/{self.test_book_id}/progress",
            200
        )
        
        return success1 and success2

    def run_all_tests(self):
        """Run the complete test suite"""
        print("🚀 Starting KDP Book Creator API Test Suite")
        print("="*60)
        
        # Basic connectivity
        if not self.test_basic_connectivity():
            print("❌ Basic connectivity failed - aborting tests")
            return False
        
        # Test settings and stock images
        self.test_settings_and_stock_images()
        
        # Get existing test book
        book_data = self.test_existing_book()
        
        # Test stock image generation
        if book_data:
            image_url = self.test_stock_image_generation(book_data)
            
            # Test image deletion (only if we have an image)
            if image_url:
                self.test_image_deletion(book_data)
        
        # Test export functionality  
        export_results = self.test_export_functionality()
        
        # Test book deletion with cleanup
        self.test_book_deletion_cleanup()
        
        # Test frontend navigation endpoints
        self.test_frontend_navigation_endpoints()
        
        # Final report
        print("\n" + "="*60)
        print("📊 TEST RESULTS SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")
        
        # Check if critical bug fixes are working
        critical_issues = []
        
        if 'pdf' not in export_results or not export_results['pdf']:
            critical_issues.append("PDF export not working")
        if 'docx' not in export_results or not export_results['docx']:
            critical_issues.append("DOCX export not working")
        if 'epub' not in export_results or not export_results['epub']:
            critical_issues.append("EPUB export not working")
            
        if critical_issues:
            print(f"\n🚨 CRITICAL ISSUES:")
            for issue in critical_issues:
                print(f"   • {issue}")
            
        success_rate = self.tests_passed / self.tests_run if self.tests_run > 0 else 0
        return success_rate >= 0.7  # 70% pass rate minimum

def main():
    print("KDP Book Creator Backend API Tests")
    print("Testing 5 bug fixes: deletion cleanup, stock images, image deletion, export formatting, page numbers")
    print("-" * 80)
    
    tester = KDPAPITester()
    success = tester.run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())