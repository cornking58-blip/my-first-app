#!/usr/bin/env python3
"""
Backend API Testing Script for Seed Treatment Endpoints
Tests the new seed treatment endpoints as requested in the review.
"""

import requests
import json
import sys
from urllib.parse import quote

# Backend URL from frontend environment
BACKEND_URL = "https://agronomist-guide-1.preview.emergentagent.com/api"

def test_seed_treatment_search():
    """Test GET /api/seed-treatments/search endpoint"""
    print("🧪 Testing Seed Treatment Search Endpoint...")
    
    # Test 1: Empty query with limit
    print("\n1. Testing empty query with limit=5")
    response = requests.get(f"{BACKEND_URL}/seed-treatments/search?limit=5")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Results count: {len(data)}")
        if data:
            first_result = data[0]
            print(f"First result: {first_result.get('product_name', 'N/A')}")
            
            # Verify required fields
            required_fields = ['product_key', 'product_name', 'formulation', 'active_substances_raw', 
                             'manufacturer', 'registration_status', 'pesticide_type', 'applications_count']
            missing_fields = [field for field in required_fields if field not in first_result]
            if missing_fields:
                print(f"❌ Missing fields: {missing_fields}")
                return False
            else:
                print("✅ All required fields present")
                
            # Verify pesticide_type values
            pesticide_type = first_result.get('pesticide_type')
            if pesticide_type in ['fungicide_seed', 'insecticide_seed']:
                print(f"✅ Valid pesticide_type: {pesticide_type}")
            else:
                print(f"⚠️ Unexpected pesticide_type: {pesticide_type}")
        else:
            print("❌ No results returned")
            return False
    else:
        print(f"❌ Request failed: {response.text}")
        return False
    
    # Test 2: Russian text search
    print("\n2. Testing Russian text search with 'Баксис'")
    response = requests.get(f"{BACKEND_URL}/seed-treatments/search?q=Баксис&limit=10")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Results count: {len(data)}")
        if data:
            print(f"First result: {data[0].get('product_name', 'N/A')}")
            print("✅ Russian text search working")
        else:
            print("⚠️ No results for 'Баксис' - this might be expected")
    else:
        print(f"❌ Russian text search failed: {response.text}")
        return False
    
    # Test 3: only_active filter
    print("\n3. Testing only_active filter")
    response = requests.get(f"{BACKEND_URL}/seed-treatments/search?q=&only_active=true&limit=10")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Active results count: {len(data)}")
        if data:
            # Check if all results are active
            all_active = all(result.get('registration_status') == 'Действует' for result in data)
            if all_active:
                print("✅ only_active filter working correctly")
            else:
                print("⚠️ Some results are not active")
        else:
            print("⚠️ No active results found")
    else:
        print(f"❌ only_active filter test failed: {response.text}")
        return False
    
    return True

def test_seed_treatment_product_card():
    """Test GET /api/seed-treatments/{product_key} endpoint"""
    print("\n🧪 Testing Seed Treatment Product Card Endpoint...")
    
    # First, get a product key from search
    print("1. Getting product key from search...")
    search_response = requests.get(f"{BACKEND_URL}/seed-treatments/search?q=Баксис&limit=1")
    
    if search_response.status_code != 200:
        print("❌ Failed to get product key from search")
        return False
    
    search_data = search_response.json()
    if not search_data:
        # Try with empty query to get any product
        search_response = requests.get(f"{BACKEND_URL}/seed-treatments/search?limit=1")
        if search_response.status_code == 200:
            search_data = search_response.json()
        
    if not search_data:
        print("❌ No products found to test product card")
        return False
    
    product_key = search_data[0]['product_key']
    print(f"Using product key: {product_key}")
    
    # Test 2: Get product card
    print("\n2. Testing product card retrieval...")
    encoded_key = quote(product_key, safe='')
    response = requests.get(f"{BACKEND_URL}/seed-treatments/{encoded_key}")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Product: {data.get('product_name', 'N/A')}")
        
        # Verify required fields
        required_fields = ['product_name', 'formulation', 'active_substances_raw', 'manufacturer', 
                         'registration_number', 'pesticide_type', 'applications']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            print(f"❌ Missing fields: {missing_fields}")
            return False
        else:
            print("✅ All required fields present")
            
        # Verify pesticide_type field
        pesticide_type = data.get('pesticide_type')
        if pesticide_type:
            print(f"✅ pesticide_type field present: {pesticide_type}")
        else:
            print("❌ pesticide_type field missing")
            return False
            
        # Verify applications array
        applications = data.get('applications', [])
        print(f"Applications count: {len(applications)}")
        print("✅ Product card working correctly")
    else:
        print(f"❌ Product card request failed: {response.text}")
        return False
    
    # Test 3: Test 404 for invalid key
    print("\n3. Testing 404 for invalid key...")
    response = requests.get(f"{BACKEND_URL}/seed-treatments/invalid-key-12345")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 404:
        print("✅ 404 handling working correctly")
    else:
        print(f"❌ Expected 404, got {response.status_code}")
        return False
    
    return True

def test_seed_treatment_compare():
    """Test POST /api/seed-treatments/compare-advanced endpoint"""
    print("\n🧪 Testing Seed Treatment Compare Advanced Endpoint...")
    
    # First, get two product keys from search
    print("1. Getting product keys for comparison...")
    search_response = requests.get(f"{BACKEND_URL}/seed-treatments/search?limit=2")
    
    if search_response.status_code != 200:
        print("❌ Failed to get product keys from search")
        return False
    
    search_data = search_response.json()
    if len(search_data) < 2:
        print("❌ Need at least 2 products for comparison test")
        return False
    
    left_key = search_data[0]['product_key']
    right_key = search_data[1]['product_key']
    print(f"Left product: {search_data[0]['product_name']}")
    print(f"Right product: {search_data[1]['product_name']}")
    
    # Test 2: Compare products with prices
    print("\n2. Testing comparison with price analysis...")
    compare_data = {
        "left_key": left_key,
        "right_key": right_key,
        "left_price": 1500,
        "right_price": 2000
    }
    
    response = requests.post(f"{BACKEND_URL}/seed-treatments/compare-advanced", 
                           json=compare_data,
                           headers={'Content-Type': 'application/json'})
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        # Verify response structure
        required_sections = ['left', 'right', 'analysis', 'price_analysis']
        missing_sections = [section for section in required_sections if section not in data]
        if missing_sections:
            print(f"❌ Missing sections: {missing_sections}")
            return False
        
        # Verify left and right have pesticide_type
        left_pesticide_type = data['left'].get('pesticide_type')
        right_pesticide_type = data['right'].get('pesticide_type')
        
        if left_pesticide_type:
            print(f"✅ Left pesticide_type: {left_pesticide_type}")
        else:
            print("❌ Left pesticide_type missing")
            return False
            
        if right_pesticide_type:
            print(f"✅ Right pesticide_type: {right_pesticide_type}")
        else:
            print("❌ Right pesticide_type missing")
            return False
        
        # Verify analysis sections
        analysis = data['analysis']
        analysis_sections = ['identical_substances', 'similar_by_category', 
                           'left_unique_substances', 'right_unique_substances']
        for section in analysis_sections:
            if section in analysis:
                print(f"✅ Analysis section '{section}' present")
            else:
                print(f"❌ Analysis section '{section}' missing")
                return False
        
        # Verify price analysis
        price_analysis = data['price_analysis']
        if price_analysis:
            print("✅ Price analysis present")
        else:
            print("❌ Price analysis missing")
            return False
        
        print("✅ Compare advanced working correctly")
    else:
        print(f"❌ Compare request failed: {response.text}")
        return False
    
    return True

def test_stats_endpoint():
    """Test GET /api/stats endpoint for seed_treatments section"""
    print("\n🧪 Testing Stats Endpoint for Seed Treatments...")
    
    response = requests.get(f"{BACKEND_URL}/stats")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        # Verify all three sections exist
        required_sections = ['herbicides', 'insecticides', 'seed_treatments']
        missing_sections = [section for section in required_sections if section not in data]
        
        if missing_sections:
            print(f"❌ Missing sections: {missing_sections}")
            return False
        
        # Check seed_treatments section
        seed_treatments_stats = data.get('seed_treatments', {})
        if seed_treatments_stats:
            print(f"✅ Seed treatments stats: {seed_treatments_stats}")
            
            # Verify expected fields
            expected_fields = ['total_records', 'unique_products', 'active_registrations']
            for field in expected_fields:
                if field in seed_treatments_stats:
                    print(f"  {field}: {seed_treatments_stats[field]}")
                else:
                    print(f"❌ Missing field in seed_treatments stats: {field}")
                    return False
        else:
            print("❌ seed_treatments section empty or missing")
            return False
        
        print("✅ Stats endpoint working correctly")
    else:
        print(f"❌ Stats request failed: {response.text}")
        return False
    
    return True

def test_regression_endpoints():
    """Test existing endpoints to ensure no regression"""
    print("\n🧪 Testing Regression - Existing Endpoints...")
    
    # Test herbicides search
    print("1. Testing herbicides search...")
    response = requests.get(f"{BACKEND_URL}/herbicides/search?q=&limit=3")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Herbicides search: {len(data)} results")
    else:
        print(f"❌ Herbicides search failed: {response.status_code}")
        return False
    
    # Test insecticides search
    print("2. Testing insecticides search...")
    response = requests.get(f"{BACKEND_URL}/insecticides/search?q=&limit=3")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Insecticides search: {len(data)} results")
    else:
        print(f"❌ Insecticides search failed: {response.status_code}")
        return False
    
    return True

def main():
    """Run all seed treatment endpoint tests"""
    print("🚀 Starting Seed Treatment Backend API Tests")
    print(f"Backend URL: {BACKEND_URL}")
    print("=" * 60)
    
    tests = [
        ("Seed Treatment Search", test_seed_treatment_search),
        ("Seed Treatment Product Card", test_seed_treatment_product_card),
        ("Seed Treatment Compare Advanced", test_seed_treatment_compare),
        ("Stats Endpoint", test_stats_endpoint),
        ("Regression Tests", test_regression_endpoints)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"\n✅ {test_name}: PASSED")
            else:
                print(f"\n❌ {test_name}: FAILED")
        except Exception as e:
            print(f"\n💥 {test_name}: ERROR - {str(e)}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())