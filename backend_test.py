import requests
import sys
import json
from datetime import datetime

class KDPApiTester:
    def __init__(self, base_url="https://kdp-auto-writer.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.api_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"  URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                return True, response.json() if response.content else {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                if response.content:
                    print(f"  Response: {response.text[:200]}")
                self.failed_tests.append({
                    "test": name, 
                    "expected": expected_status, 
                    "actual": response.status_code,
                    "error": response.text[:200] if response.content else "No content"
                })
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Timeout after {timeout}s")
            self.failed_tests.append({"test": name, "error": f"Timeout after {timeout}s"})
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({"test": name, "error": str(e)})
            return False, {}

    def test_api_root(self):
        """Test API root endpoint"""
        return self.run_test("API Root", "GET", "/", 200)

    def test_settings(self):
        """Test settings endpoints"""
        print("\n=== SETTINGS TESTS ===")
        
        # Test GET settings
        success1, settings = self.run_test("GET Settings", "GET", "/settings", 200)
        
        # Test PUT settings
        settings_data = {
            "api_key_source": "emergent",
            "custom_api_key": None,
            "image_source": "ai", 
            "language": "en"
        }
        success2, _ = self.run_test("PUT Settings", "PUT", "/settings", 200, settings_data)
        
        return success1 and success2

    def test_themes(self):
        """Test theme discovery"""
        print("\n=== THEMES TESTS ===")
        
        theme_request = {
            "category": "guide",
            "language": "en"
        }
        return self.run_test("Discover Themes", "POST", "/themes/discover", 200, theme_request, timeout=60)

    def test_ideas(self):
        """Test idea generation"""
        print("\n=== IDEAS TESTS ===")
        
        idea_request = {
            "theme": "cooking healthy meals",
            "language": "en"
        }
        return self.run_test("Generate Ideas", "POST", "/ideas/generate", 200, idea_request, timeout=60)

    def test_books_crud(self):
        """Test book CRUD operations"""
        print("\n=== BOOKS CRUD TESTS ===")
        
        # Create book
        book_data = {
            "title": "Test Recipe Book",
            "subtitle": "Quick and Easy Meals",
            "description": "A collection of healthy recipes for busy people",
            "category": "recipe",
            "language": "en",
            "target_pages": 80,
            "image_source": "ai"
        }
        
        success1, book = self.run_test("Create Book", "POST", "/books/create", 200, book_data)
        if not success1 or not book.get('id'):
            return False
        
        book_id = book['id']
        print(f"  Created book with ID: {book_id}")
        
        # Get all books
        success2, books_list = self.run_test("List Books", "GET", "/books", 200)
        
        # Get specific book
        success3, book_detail = self.run_test("Get Book Detail", "GET", f"/books/{book_id}", 200)
        
        # Get book progress
        success4, progress = self.run_test("Get Book Progress", "GET", f"/books/{book_id}/progress", 200)
        
        # Generate outline
        success5, outline = self.run_test("Generate Outline", "POST", f"/books/{book_id}/generate-outline", 200, timeout=90)
        
        # Update outline (approve it)
        if success5 and outline.get('outline'):
            approve_data = {
                "book_id": book_id,
                "outline": outline['outline']
            }
            success6, _ = self.run_test("Update/Approve Outline", "PUT", f"/books/{book_id}/outline", 200, approve_data)
        else:
            success6 = False
            print("⚠️  Skipping outline approval - no outline generated")
        
        # Generate single chapter (chapter 1)
        success7, chapter = self.run_test("Generate Chapter 1", "POST", f"/books/{book_id}/generate-chapter/1", 200, timeout=120)
        
        # Delete book
        success8, _ = self.run_test("Delete Book", "DELETE", f"/books/{book_id}", 200)
        
        return all([success1, success2, success3, success4, success5, success6, success7, success8])

    def test_export_endpoints(self):
        """Test export functionality with a simple book"""
        print("\n=== EXPORT TESTS ===")
        
        # Create a minimal book for export testing
        book_data = {
            "title": "Export Test Book",
            "subtitle": "Testing Export",
            "description": "A book to test export functionality",
            "category": "guide",
            "language": "en",
            "target_pages": 20,
            "image_source": "ai"
        }
        
        success1, book = self.run_test("Create Export Test Book", "POST", "/books/create", 200, book_data)
        if not success1 or not book.get('id'):
            print("❌ Cannot test exports - book creation failed")
            return False
            
        book_id = book['id']
        
        # Generate a minimal outline
        success2, outline = self.run_test("Generate Export Book Outline", "POST", f"/books/{book_id}/generate-outline", 200, timeout=90)
        if not success2:
            print("❌ Cannot test exports - outline generation failed")
            return False
        
        # Generate one chapter for export
        success3, _ = self.run_test("Generate Export Book Chapter", "POST", f"/books/{book_id}/generate-chapter/1", 200, timeout=120)
        if not success3:
            print("❌ Cannot test exports - chapter generation failed")
            return False
        
        # Test PDF export (file download)
        export_data = {"book_id": book_id, "format": "pdf"}
        success4, _ = self.run_test("Export PDF", "POST", f"/books/{book_id}/export", 200, export_data, timeout=60)
        
        # Clean up
        self.run_test("Delete Export Test Book", "DELETE", f"/books/{book_id}", 200)
        
        return success4

def main():
    print("🚀 Starting KDP API Testing...")
    print("=" * 50)
    
    tester = KDPApiTester()
    
    # Run all tests
    tests = [
        ("API Root", tester.test_api_root),
        ("Settings", tester.test_settings),
        ("Themes", tester.test_themes),
        ("Ideas", tester.test_ideas),
        ("Books CRUD", tester.test_books_crud),
        ("Export", tester.test_export_endpoints),
    ]
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name.upper()} {'='*20}")
        try:
            test_func()
        except Exception as e:
            print(f"❌ Test suite {test_name} crashed: {str(e)}")
            tester.failed_tests.append({"test": f"{test_name} Suite", "error": str(e)})
    
    # Summary
    print(f"\n{'='*50}")
    print(f"📊 TEST SUMMARY")
    print(f"{'='*50}")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Tests failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run*100) if tester.tests_run > 0 else 0:.1f}%")
    
    if tester.failed_tests:
        print(f"\n❌ FAILED TESTS:")
        for i, failure in enumerate(tester.failed_tests, 1):
            print(f"  {i}. {failure.get('test', 'Unknown')}: {failure.get('error', 'Unknown error')}")
    
    print(f"\n🏁 Testing completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Return exit code based on success rate
    success_rate = (tester.tests_passed/tester.tests_run*100) if tester.tests_run > 0 else 0
    return 0 if success_rate > 70 else 1

if __name__ == "__main__":
    sys.exit(main())