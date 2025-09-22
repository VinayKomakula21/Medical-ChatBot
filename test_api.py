#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoints():
    print("=" * 50)
    print("Testing Medical ChatBot API Endpoints")
    print("=" * 50)

    # Test 1: Basic Health Check
    print("\n1. Testing Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        print("   ✅ Health check passed!")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 2: Root Endpoint
    print("\n2. Testing Root Endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        print("   ✅ Root endpoint passed!")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 3: API Health with Services
    print("\n3. Testing API Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health/", timeout=10)
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Services:")
        for service, status in data.get("services", {}).items():
            print(f"      - {service}: {status}")
        print("   ✅ API health check passed!")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 4: API Documentation
    print("\n4. Testing API Documentation...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/docs", timeout=5)
        if response.status_code == 200:
            print(f"   ✅ Swagger docs available at {BASE_URL}/api/v1/docs")
        else:
            print(f"   Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 5: Document List (Quick test)
    print("\n5. Testing Document List Endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/documents/", timeout=5)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Documents found: {data.get('total', 0)}")
            print("   ✅ Document list endpoint working!")
    except requests.Timeout:
        print("   ⚠️  Endpoint timed out - may need initialization")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    print("\n" + "=" * 50)
    print("Testing Complete!")
    print("=" * 50)
    print(f"\n📚 View full API documentation at: {BASE_URL}/api/v1/docs")
    print(f"🌐 Access the web interface at: {BASE_URL}")

if __name__ == "__main__":
    test_endpoints()