#!/usr/bin/env python3
"""
Additional Backend API Edge Case Tests for Herbicides MVP
"""

import requests
import urllib.parse

BACKEND_URL = "https://agronomist-guide-1.preview.emergentagent.com/api"

def test_edge_cases():
    """Test edge cases and error handling"""
    session = requests.Session()
    
    print("🔍 Testing Edge Cases and Error Handling")
    print("=" * 50)
    
    # Test 1: Invalid product key
    try:
        response = session.get(f"{BACKEND_URL}/herbicides/invalid-product-key", timeout=10)
        if response.status_code == 404:
            print("✅ PASS Invalid Product Key - Returns 404")
        else:
            print(f"❌ FAIL Invalid Product Key - Expected 404, got {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL Invalid Product Key - Exception: {e}")
    
    # Test 2: Compare with invalid keys
    try:
        payload = {"left_key": "invalid1", "right_key": "invalid2"}
        response = session.post(f"{BACKEND_URL}/herbicides/compare", json=payload, timeout=10)
        if response.status_code == 404:
            print("✅ PASS Compare Invalid Keys - Returns 404")
        else:
            print(f"❌ FAIL Compare Invalid Keys - Expected 404, got {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL Compare Invalid Keys - Exception: {e}")
    
    # Test 3: Search with very large limit
    try:
        response = session.get(f"{BACKEND_URL}/herbicides/search?limit=1000", timeout=10)
        if response.status_code == 422:  # FastAPI validation error
            print("✅ PASS Large Limit - Validation error as expected")
        elif response.status_code == 200:
            data = response.json()
            print(f"✅ PASS Large Limit - Returned {len(data)} results (capped)")
        else:
            print(f"❌ FAIL Large Limit - Unexpected status {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL Large Limit - Exception: {e}")
    
    # Test 4: Search with empty query
    try:
        response = session.get(f"{BACKEND_URL}/herbicides/search?q=&limit=5", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS Empty Query - Returned {len(data)} results")
        else:
            print(f"❌ FAIL Empty Query - Status {response.status_code}")
    except Exception as e:
        print(f"❌ FAIL Empty Query - Exception: {e}")
    
    # Test 5: Test URL encoding with complex product key
    try:
        # Get a real product key first
        response = session.get(f"{BACKEND_URL}/herbicides/search?limit=1", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                product_key = data[0]["product_key"]
                encoded_key = urllib.parse.quote(product_key, safe='')
                
                response2 = session.get(f"{BACKEND_URL}/herbicides/{encoded_key}", timeout=10)
                if response2.status_code == 200:
                    print("✅ PASS URL Encoding - Complex product key handled correctly")
                else:
                    print(f"❌ FAIL URL Encoding - Status {response2.status_code}")
            else:
                print("❌ FAIL URL Encoding - No products to test with")
        else:
            print("❌ FAIL URL Encoding - Could not get sample product")
    except Exception as e:
        print(f"❌ FAIL URL Encoding - Exception: {e}")

if __name__ == "__main__":
    test_edge_cases()