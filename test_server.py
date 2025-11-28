#!/usr/bin/env python3
"""
Test script to verify the server functionality
"""
import requests
import json
import time
import subprocess
import sys
import os

def test_server():
    """Test the quiz server functionality"""
    
    print("🧪 Testing Quiz Server...")
    
    # Test the root endpoint
    try:
        print("\n📝 Testing root endpoint...")
        response = requests.get("http://localhost:8000/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 200
        print("✅ Root endpoint working!")
    except Exception as e:
        print(f"❌ Root endpoint test failed: {e}")
        return False
    
    # Test quiz endpoint with correct secret
    try:
        print("\n📝 Testing quiz endpoint with correct secret...")
        test_payload = {
            "email": "test@example.com",
            "secret": "23SHWEBGPT",  # Using default secret
            "url": "https://httpbin.org/json"  # Simple test URL
        }
        
        response = requests.post(
            "http://localhost:8000/quiz",
            json=test_payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Should get immediate 200 response
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert data.get("status") == "accepted"
        print("✅ Quiz endpoint working! Got immediate 200 response.")
        
        # Wait a bit for background processing
        print("\n⏳ Waiting for background processing...")
        time.sleep(2)
        
    except Exception as e:
        print(f"❌ Quiz endpoint test failed: {e}")
        return False
    
    # Test quiz endpoint with incorrect secret
    try:
        print("\n📝 Testing quiz endpoint with incorrect secret...")
        test_payload = {
            "email": "test@example.com",
            "secret": "wrong_secret",
            "url": "https://httpbin.org/json"
        }
        
        response = requests.post(
            "http://localhost:8000/quiz",
            json=test_payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Should get 403 for wrong secret
        assert response.status_code == 403
        print("✅ Incorrect secret properly rejected!")
        
    except Exception as e:
        print(f"❌ Incorrect secret test failed: {e}")
        return False
    
    print("\n🎉 All tests passed!")
    return True

def start_server_and_test():
    """Start server and run tests"""
    print("🚀 Starting server for testing...")
    
    # Start server in background
    server_process = subprocess.Popen([
        sys.executable, "main.py"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    try:
        # Wait for server to start
        print("⏳ Waiting for server to start...")
        time.sleep(5)
        
        # Run tests
        success = test_server()
        
        return success
        
    finally:
        # Cleanup
        print("\n🛑 Stopping server...")
        server_process.terminate()
        server_process.wait()
        print("✅ Server stopped")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-only":
        # Just run tests (assuming server is already running)
        success = test_server()
    else:
        # Start server and test
        success = start_server_and_test()
    
    sys.exit(0 if success else 1)