#!/usr/bin/env python3
"""
Backend API Testing for Herbicides and Insecticides MVP
Tests all endpoints including the new insecticide functionality
"""

import requests
import json
import sys
from urllib.parse import quote

# Backend URL from environment
BACKEND_URL = "https://agronomist-guide-1.preview.emergentagent.com/api"

def test_health_endpoint():
    """Test health check endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed")
            print(f"   Database: {data.get('database')}")
            print(f"   Records: {data.get('records_count')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_stats_endpoint():
    """Test updated stats endpoint with both herbicide and insecticide data"""
    print("\n🔍 Testing stats endpoint...")
    try:
        response = requests.get(f"{BACKEND_URL}/stats", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Stats endpoint working")
            print(f"   Herbicides - Total: {data.get('total_records')}, Unique: {data.get('unique_products')}, Active: {data.get('active_registrations')}")
            
            insecticides = data.get('insecticides', {})
            print(f"   Insecticides - Total: {insecticides.get('total_records')}, Unique: {insecticides.get('unique_products')}, Active: {insecticides.get('active_registrations')}")
            
            # Verify insecticide data exists
            if insecticides.get('total_records', 0) > 0:
                print(f"✅ Insecticide data found: {insecticides.get('total_records')} records")
                return True
            else:
                print(f"❌ No insecticide data found")
                return False
        else:
            print(f"❌ Stats failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Stats error: {e}")
        return False

def test_insecticide_search():
    """Test insecticide search endpoint with various parameters"""
    print("\n🔍 Testing insecticide search endpoint...")
    
    # Test 1: Empty query with limit
    print("  Test 1: Empty query with limit=5")
    try:
        response = requests.get(f"{BACKEND_URL}/insecticides/search?limit=5", timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Empty search returned {len(data)} results")
            if len(data) > 0:
                print(f"     Sample product: {data[0].get('product_name')}")
                # Store first product for later testing
                global first_insecticide_key
                first_insecticide_key = data[0].get('product_key')
        else:
            print(f"  ❌ Empty search failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Empty search error: {e}")
        return False
    
    # Test 2: Russian text search
    print("  Test 2: Russian text search (Органза)")
    try:
        response = requests.get(f"{BACKEND_URL}/insecticides/search?q=Органза&limit=10", timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Russian search returned {len(data)} results")
            if len(data) > 0:
                print(f"     Found product: {data[0].get('product_name')}")
                # Store second product for comparison testing
                global second_insecticide_key
                second_insecticide_key = data[0].get('product_key')
        else:
            print(f"  ❌ Russian search failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Russian search error: {e}")
        return False
    
    # Test 3: Only active filter
    print("  Test 3: Only active filter")
    try:
        response = requests.get(f"{BACKEND_URL}/insecticides/search?q=&only_active=true&limit=10", timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Active filter returned {len(data)} results")
            # Verify all results are active
            active_count = sum(1 for item in data if item.get('registration_status') == 'Действует')
            print(f"     Active products: {active_count}/{len(data)}")
            
            # Verify response structure
            if len(data) > 0:
                sample = data[0]
                required_fields = ['product_key', 'product_name', 'formulation', 'active_substances_raw', 'manufacturer', 'registration_status', 'applications_count']
                missing_fields = [field for field in required_fields if field not in sample]
                if missing_fields:
                    print(f"  ❌ Missing fields in response: {missing_fields}")
                    return False
                else:
                    print(f"  ✅ All required fields present in response")
        else:
            print(f"  ❌ Active filter failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Active filter error: {e}")
        return False
    
    return True

def test_insecticide_product_card():
    """Test insecticide product card endpoint"""
    print("\n🔍 Testing insecticide product card endpoint...")
    
    if 'first_insecticide_key' not in globals():
        print("  ❌ No product key available from search test")
        return False
    
    # Test 1: Valid product key
    print(f"  Test 1: Valid product key")
    try:
        # URL encode the product key since it contains special characters
        encoded_key = quote(first_insecticide_key, safe='')
        response = requests.get(f"{BACKEND_URL}/insecticides/{encoded_key}", timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Product card retrieved")
            print(f"     Product: {data.get('product_name')}")
            print(f"     Applications: {len(data.get('applications', []))}")
            
            # Verify response structure
            required_fields = ['product_name', 'formulation', 'active_substances_raw', 'manufacturer', 'registration_number', 'applications']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"  ❌ Missing fields in response: {missing_fields}")
                return False
            else:
                print(f"  ✅ All required fields present")
        else:
            print(f"  ❌ Product card failed: {response.status_code}")
            print(f"     Response: {response.text}")
            return False
    except Exception as e:
        print(f"  ❌ Product card error: {e}")
        return False
    
    # Test 2: Invalid product key (404 test)
    print("  Test 2: Invalid product key (404 test)")
    try:
        response = requests.get(f"{BACKEND_URL}/insecticides/invalid-key", timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 404:
            print(f"  ✅ 404 correctly returned for invalid key")
        else:
            print(f"  ❌ Expected 404, got {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Invalid key test error: {e}")
        return False
    
    return True

def test_insecticide_compare_advanced():
    """Test advanced insecticide comparison endpoint"""
    print("\n🔍 Testing insecticide advanced comparison endpoint...")
    
    if 'first_insecticide_key' not in globals() or 'second_insecticide_key' not in globals():
        print("  ❌ Need two product keys from search test")
        return False
    
    # Test 1: Valid comparison with prices
    print("  Test 1: Valid comparison with prices")
    try:
        payload = {
            "left_key": first_insecticide_key,
            "right_key": second_insecticide_key,
            "left_price": 1500.0,
            "right_price": 2000.0
        }
        
        response = requests.post(
            f"{BACKEND_URL}/insecticides/compare-advanced",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Comparison successful")
            print(f"     Left product: {data.get('left', {}).get('product_name')}")
            print(f"     Right product: {data.get('right', {}).get('product_name')}")
            
            # Verify response structure
            required_sections = ['left', 'right', 'analysis', 'price_analysis']
            missing_sections = [section for section in required_sections if section not in data]
            if missing_sections:
                print(f"  ❌ Missing sections in response: {missing_sections}")
                return False
            
            # Verify analysis structure
            analysis = data.get('analysis', {})
            required_analysis = ['identical_substances', 'similar_by_category', 'left_unique_substances', 'right_unique_substances']
            missing_analysis = [field for field in required_analysis if field not in analysis]
            if missing_analysis:
                print(f"  ❌ Missing analysis fields: {missing_analysis}")
                return False
            
            print(f"  ✅ All required sections present")
            print(f"     Identical substances: {len(analysis.get('identical_substances', []))}")
            print(f"     Similar by category: {len(analysis.get('similar_by_category', []))}")
            
        else:
            print(f"  ❌ Comparison failed: {response.status_code}")
            print(f"     Response: {response.text}")
            return False
    except Exception as e:
        print(f"  ❌ Comparison error: {e}")
        return False
    
    # Test 2: Invalid product keys (404 test)
    print("  Test 2: Invalid product keys (404 test)")
    try:
        payload = {
            "left_key": "invalid-key-1",
            "right_key": "invalid-key-2",
            "left_price": 1000.0,
            "right_price": 1200.0
        }
        
        response = requests.post(
            f"{BACKEND_URL}/insecticides/compare-advanced",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 404:
            print(f"  ✅ 404 correctly returned for invalid keys")
        else:
            print(f"  ❌ Expected 404, got {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Invalid keys test error: {e}")
        return False
    
    return True

def test_existing_herbicide_endpoints():
    """Test that existing herbicide endpoints still work"""
    print("\n🔍 Testing existing herbicide endpoints...")
    
    # Test herbicide search
    print("  Test 1: Herbicide search")
    try:
        response = requests.get(f"{BACKEND_URL}/herbicides/search?q=глифосат&limit=3", timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Herbicide search returned {len(data)} results")
            if len(data) > 0:
                print(f"     Sample: {data[0].get('product_name')}")
        else:
            print(f"  ❌ Herbicide search failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Herbicide search error: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🚀 Starting Backend API Tests for Herbicides & Insecticides MVP")
    print("=" * 70)
    
    test_results = []
    
    # Test health endpoint
    test_results.append(("Health Check", test_health_endpoint()))
    
    # Test updated stats endpoint
    test_results.append(("Stats Endpoint", test_stats_endpoint()))
    
    # Test new insecticide endpoints
    test_results.append(("Insecticide Search", test_insecticide_search()))
    test_results.append(("Insecticide Product Card", test_insecticide_product_card()))
    test_results.append(("Insecticide Advanced Compare", test_insecticide_compare_advanced()))
    
    # Test existing herbicide endpoints still work
    test_results.append(("Existing Herbicide Endpoints", test_existing_herbicide_endpoints()))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<35} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed + failed} tests, {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"💥 {failed} test(s) failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())