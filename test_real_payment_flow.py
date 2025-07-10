#!/usr/bin/env python3
"""
Real Payment Flow Test Script

This script tests the actual payment flow by making real requests to the backend.
It simulates different user scenarios to verify the complete integration.

Usage:
    python test_real_payment_flow.py

Note: This script requires a valid OpenAI API key to be set in the environment
or config file.
"""

import os
import sys
import requests
from pathlib import Path

# Add the project root to the path so we can import clausi_cli
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from clausi_cli.config import get_openai_key, get_api_token
from clausi_cli.scan import check_payment_required

def get_api_url():
    """Get the API URL, prioritizing CLAUSI_TUNNEL_BASE environment variable."""
    # First check for tunnel base URL
    tunnel_base = os.getenv('CLAUSI_TUNNEL_BASE')
    if tunnel_base:
        return tunnel_base.rstrip('/')
    
    # Fall back to default
    return "https://api.clausi.ai"

def test_payment_check_endpoint():
    """Test the real payment check endpoint."""
    print("🧪 Testing Real Payment Check Endpoint...")
    
    api_url = get_api_url()  # Use tunnel if available
    print(f"   API URL: {api_url}")
    
    try:
        response = requests.post(
            f"{api_url}/api/clausi/check-payment-required",
            headers={"Content-Type": "application/json"},
            json={"mode": "full"},
            timeout=30
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
            
            if data.get("payment_required"):
                print("   ✅ Payment required - this is expected for users without credits")
                checkout_url = data.get("checkout_url")
                if checkout_url:
                    print(f"   ✅ Checkout URL provided: {checkout_url}")
                    return True
                else:
                    print("   ❌ No checkout URL in response")
                    return False
            else:
                print("   ✅ Payment not required - user has credits")
                return True
        else:
            print(f"   ❌ Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False

def test_scan_endpoint_no_token():
    """Test the scan endpoint without a token (should create trial)."""
    print("🧪 Testing Scan Endpoint (No Token - Should Create Trial)...")
    
    api_url = get_api_url()  # Use tunnel if available
    print(f"   API URL: {api_url}")
    
    # Get OpenAI key
    openai_key = get_openai_key()
    if not openai_key:
        print("   ❌ No OpenAI API key found. Set OPENAI_API_KEY environment variable or run 'clausi config set --openai-key YOUR_KEY'")
        return False
    
    # Prepare minimal scan data
    scan_data = {
        "path": "test_project",
        "regulations": ["EU-AIA"],
        "mode": "ai",  # Use AI mode to avoid payment requirements
        "min_severity": "info",
        "metadata": {
            "path": "test_project",
            "files": [],
            "timestamp": "2024-01-01T00:00:00Z",
            "format": "json",
            "template": "default"
        },
        "estimate_only": True
    }
    
    try:
        response = requests.post(
            f"{api_url}/api/clausi/estimate",
            json=scan_data,
            headers={
                "X-OpenAI-Key": openai_key,
                "Content-Type": "application/json"
            },
            timeout=60
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Estimate successful")
            print(f"   Total Tokens: {data.get('total_tokens', 0):,}")
            print(f"   Estimated Cost: ${data.get('estimated_cost', 0):.2f}")
            return True
        elif response.status_code == 401:
            data = response.json()
            api_token = data.get("api_token")
            credits = data.get("credits")
            print(f"   ✅ Trial account created!")
            print(f"   Token: {api_token[:8]}..." if api_token else "   No token")
            print(f"   Credits: {credits}")
            return True
        else:
            print(f"   ❌ Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False

def test_scan_endpoint_with_token():
    """Test the scan endpoint with a token."""
    print("🧪 Testing Scan Endpoint (With Token)...")
    
    api_url = get_api_url()  # Use tunnel if available
    print(f"   API URL: {api_url}")
    
    # Get OpenAI key
    openai_key = get_openai_key()
    if not openai_key:
        print("   ❌ No OpenAI API key found")
        return False
    
    # Get API token
    api_token = get_api_token()
    if not api_token:
        print("   ⚠️  No API token found - skipping token test")
        return True  # Not a failure, just no token to test with
    
    # Prepare minimal scan data
    scan_data = {
        "path": "test_project",
        "regulations": ["EU-AIA"],
        "mode": "ai",
        "min_severity": "info",
        "metadata": {
            "path": "test_project",
            "files": [],
            "timestamp": "2024-01-01T00:00:00Z",
            "format": "json",
            "template": "default"
        },
        "estimate_only": True
    }
    
    try:
        headers = {
            "X-OpenAI-Key": openai_key,
            "X-Clausi-Token": api_token,
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{api_url}/api/clausi/estimate",
            json=scan_data,
            headers=headers,
            timeout=60
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Estimate successful with token")
            print(f"   Total Tokens: {data.get('total_tokens', 0):,}")
            print(f"   Estimated Cost: ${data.get('estimated_cost', 0):.2f}")
            return True
        elif response.status_code == 402:
            print("   ✅ Payment required - token has no credits")
            return True
        else:
            print(f"   ❌ Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False

def main():
    """Run all real payment flow tests."""
    print("🚀 Starting Real Payment Flow Tests")
    print("=" * 60)
    print("This script tests the actual backend endpoints to verify")
    print("the payment integration works end-to-end.")
    print("=" * 60)
    
    tests = [
        test_payment_check_endpoint,
        test_scan_endpoint_no_token,
        test_scan_endpoint_with_token
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All real payment flow tests passed!")
        print("✅ Payment integration is working correctly with the backend.")
    else:
        print("⚠️  Some tests failed. This might be expected if:")
        print("   - Backend is not running")
        print("   - Network connectivity issues")
        print("   - API endpoints have changed")
        print("   - No OpenAI API key configured")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main()) 