#!/usr/bin/env python3
"""
Backend API Testing for Herbicides MVP
Tests all backend endpoints with various scenarios
"""

import requests
import json
import urllib.parse
from typing import Dict, List, Any
import sys

# Backend URL from frontend .env
BACKEND_URL = "https://agronomist-guide-1.preview.emergentagent.com/api"

class HerbicidesAPITester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "response_data": response_data
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        if not success and response_data:
            print(f"   Response: {response_data}")
        print()

    def test_health_endpoint(self):
        """Test GET /api/health"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy" and "records_count" in data:
                    self.log_test(
                        "Health Check", 
                        True, 
                        f"Status: {data['status']}, Records: {data.get('records_count', 0)}"
                    )
                    return data.get('records_count', 0)
                else:
                    self.log_test("Health Check", False, "Invalid response format", data)
                    return 0
            else:
                self.log_test("Health Check", False, f"HTTP {response.status_code}", response.text)
                return 0
                
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")
            return 0

    def test_search_basic(self):
        """Test basic search without query"""
        try:
            response = self.session.get(f"{self.base_url}/herbicides/search?limit=5", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    first_item = data[0]
                    required_fields = ["product_key", "product_name", "applications_count"]
                    if all(field in first_item for field in required_fields):
                        self.log_test(
                            "Search Basic (limit=5)", 
                            True, 
                            f"Returned {len(data)} products"
                        )
                        return data
                    else:
                        self.log_test("Search Basic", False, "Missing required fields", first_item)
                        return []
                else:
                    self.log_test("Search Basic", False, "Empty or invalid response", data)
                    return []
            else:
                self.log_test("Search Basic", False, f"HTTP {response.status_code}", response.text)
                return []
                
        except Exception as e:
            self.log_test("Search Basic", False, f"Exception: {str(e)}")
            return []

    def test_search_russian_text(self):
        """Test search with Russian text"""
        test_queries = [
            ("пшеница", "wheat"),
            ("кукуруза", "corn"), 
            ("соя", "soy")
        ]
        
        results = {}
        for query, description in test_queries:
            try:
                params = {"q": query, "limit": 10}
                response = self.session.get(f"{self.base_url}/herbicides/search", params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        results[query] = data
                        self.log_test(
                            f"Search Russian Text ({description})", 
                            True, 
                            f"Query '{query}' returned {len(data)} results"
                        )
                    else:
                        self.log_test(f"Search Russian Text ({description})", False, "Invalid response format", data)
                else:
                    self.log_test(f"Search Russian Text ({description})", False, f"HTTP {response.status_code}", response.text)
                    
            except Exception as e:
                self.log_test(f"Search Russian Text ({description})", False, f"Exception: {str(e)}")
        
        return results

    def test_search_active_filter(self):
        """Test search with only_active filter"""
        try:
            # Test with only_active=true
            params = {"q": "пшеница", "only_active": True, "limit": 10}
            response = self.session.get(f"{self.base_url}/herbicides/search", params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Check if all results have active status
                    active_count = sum(1 for item in data if item.get("registration_status") == "Действует")
                    self.log_test(
                        "Search Active Filter", 
                        True, 
                        f"Returned {len(data)} results, {active_count} with active status"
                    )
                    return data
                else:
                    self.log_test("Search Active Filter", False, "Invalid response format", data)
                    return []
            else:
                self.log_test("Search Active Filter", False, f"HTTP {response.status_code}", response.text)
                return []
                
        except Exception as e:
            self.log_test("Search Active Filter", False, f"Exception: {str(e)}")
            return []

    def test_product_card(self, sample_products: List[Dict]):
        """Test product card endpoint"""
        if not sample_products:
            self.log_test("Product Card", False, "No sample products available for testing")
            return None
            
        # Use first product from search results
        product = sample_products[0]
        product_key = product.get("product_key")
        
        if not product_key:
            self.log_test("Product Card", False, "No product_key in sample product")
            return None
            
        try:
            # URL encode the product key (contains | character)
            encoded_key = urllib.parse.quote(product_key, safe='')
            response = self.session.get(f"{self.base_url}/herbicides/{encoded_key}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["product_key", "product_name", "applications"]
                if all(field in data for field in required_fields):
                    apps_count = len(data.get("applications", []))
                    self.log_test(
                        "Product Card", 
                        True, 
                        f"Product: {data.get('product_name')}, Applications: {apps_count}"
                    )
                    return data
                else:
                    self.log_test("Product Card", False, "Missing required fields", data)
                    return None
            else:
                self.log_test("Product Card", False, f"HTTP {response.status_code}", response.text)
                return None
                
        except Exception as e:
            self.log_test("Product Card", False, f"Exception: {str(e)}")
            return None

    def test_compare_products(self, sample_products: List[Dict]):
        """Test product comparison endpoint"""
        if len(sample_products) < 2:
            self.log_test("Product Compare", False, "Need at least 2 products for comparison")
            return None
            
        left_key = sample_products[0].get("product_key")
        right_key = sample_products[1].get("product_key")
        
        if not left_key or not right_key:
            self.log_test("Product Compare", False, "Missing product keys in sample products")
            return None
            
        try:
            payload = {
                "left_key": left_key,
                "right_key": right_key
            }
            
            response = self.session.post(
                f"{self.base_url}/herbicides/compare", 
                json=payload, 
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["left", "right", "comparison"]
                if all(field in data for field in required_fields):
                    comparison = data.get("comparison", {})
                    common_crops = len(comparison.get("common_crops", []))
                    self.log_test(
                        "Product Compare", 
                        True, 
                        f"Compared {data['left']['product_name']} vs {data['right']['product_name']}, Common crops: {common_crops}"
                    )
                    return data
                else:
                    self.log_test("Product Compare", False, "Missing required fields", data)
                    return None
            else:
                self.log_test("Product Compare", False, f"HTTP {response.status_code}", response.text)
                return None
                
        except Exception as e:
            self.log_test("Product Compare", False, f"Exception: {str(e)}")
            return None

    def test_stats_endpoint(self):
        """Test GET /api/stats"""
        try:
            response = self.session.get(f"{self.base_url}/stats", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["total_records", "unique_products", "active_registrations"]
                if all(field in data for field in required_fields):
                    self.log_test(
                        "Stats Endpoint", 
                        True, 
                        f"Total: {data['total_records']}, Unique: {data['unique_products']}, Active: {data['active_registrations']}"
                    )
                    return data
                else:
                    self.log_test("Stats Endpoint", False, "Missing required fields", data)
                    return None
            else:
                self.log_test("Stats Endpoint", False, f"HTTP {response.status_code}", response.text)
                return None
                
        except Exception as e:
            self.log_test("Stats Endpoint", False, f"Exception: {str(e)}")
            return None

    def run_all_tests(self):
        """Run all backend API tests"""
        print(f"🧪 Starting Backend API Tests")
        print(f"Backend URL: {self.base_url}")
        print("=" * 60)
        
        # Test 1: Health check
        records_count = self.test_health_endpoint()
        
        # Test 2: Basic search
        sample_products = self.test_search_basic()
        
        # Test 3: Russian text search
        self.test_search_russian_text()
        
        # Test 4: Active filter
        self.test_search_active_filter()
        
        # Test 5: Product card (needs sample products)
        self.test_product_card(sample_products)
        
        # Test 6: Product comparison (needs sample products)
        self.test_compare_products(sample_products)
        
        # Test 7: Stats endpoint
        self.test_stats_endpoint()
        
        # Summary
        print("=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r["success"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if total - passed > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        return passed == total

def main():
    """Main test runner"""
    tester = HerbicidesAPITester(BACKEND_URL)
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()