"""Scan functionality with payment flow support."""

import os
import sys
import time
import webbrowser
import requests
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from rich.console import Console
from rich.panel import Panel
import click

console = Console()

# Import configuration functions from config module
from .config import get_api_token, save_api_token

def check_payment_required(api_url: str, mode: str = "full") -> bool:
    """Check if payment is required before proceeding with scan."""
    console.print(f"[debug] Checking payment requirements before estimate...")
    console.print(f"[debug] Checking payment requirements for mode: {mode}")
    console.print(f"[debug] API URL: {api_url}")
    
    try:
        response = requests.post(
            f"{api_url}/api/clausi/check-payment-required",
            headers={"Content-Type": "application/json"},
            json={"mode": mode},
            timeout=30
        )
        
        console.print(f"[debug] Payment check response status: {response.status_code}")
        console.print(f"[debug] Payment check response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            
            console.print(f"[debug] Payment required value: {data.get('payment_required')}")
            console.print(f"[debug] Payment required type: {type(data.get('payment_required'))}")
            console.print(f"[debug] Payment required == True: {data.get('payment_required') == True}")
            console.print(f"[debug] Payment required == 'true': {data.get('payment_required') == 'true'}")
            console.print(f"[debug] Payment required bool(): {bool(data.get('payment_required'))}")
            
            if data.get("payment_required"):
                console.print(f"[debug] Payment required: {data.get('payment_required')}")
                console.print(f"[debug] Reason: {data.get('reason')}")
                checkout_url = data.get("checkout_url")
                
                if checkout_url:
                    console.print("\n" + "=" * 60)
                    console.print("💳 PAYMENT REQUIRED")
                    console.print("=" * 60)
                    console.print("\n📱 Opening payment page in your browser...")
                    
                    try:
                        webbrowser.open(checkout_url)
                    except Exception as e:
                        console.print(f"[red]Could not open browser: {e}[/red]")
                    
                    console.print("\n📋 PAYMENT INSTRUCTIONS:")
                    console.print("   💳 Use test card: 4242 4242 4242 4242")
                    console.print("   📅 Any future date")
                    console.print("   🔢 Any 3-digit CVC")
                    console.print("   📧 Any email address")
                    console.print("\n   ⏳ Complete your payment in the browser")
                    console.print("   🔄 After payment, run your scan command again")
                    
                    # Wait a moment for browser to open
                    time.sleep(2)
                    
                    console.print(f"\n🔗 Payment URL also available at:")
                    console.print(f"   {checkout_url}")
                    console.print("\n" + "=" * 60)
                    
                    return False  # Return False to indicate payment required
                return False
            else:
                console.print(f"[debug] Payment not required. Reason: {data.get('reason')}")
            
        return True
    except Exception as e:
        console.print(f"❌ Error checking payment: {str(e)}")
        return True

def handle_scan_response(response: requests.Response, api_url: str, openai_key: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle different response types from the scan endpoint."""
    
    if response.status_code == 200:
        # Success - handle normal response
        return response.json()
        
    elif response.status_code == 401:
        # Trial token created - save and retry
        response_data = response.json()
        api_token = response_data.get("api_token")
        credits = response_data.get("credits")
        
        console.print(f"🎉 Trial account created!")
        console.print(f"   Credits: {credits}")
        console.print(f"   Token: {api_token[:8]}...")
        console.print("\n   Saving token and retrying scan...")
        
        # Save token to config file
        save_api_token(api_token)
        
        # Retry the scan with the new token
        return retry_scan_with_token(api_url, openai_key, data, api_token)
        
    elif response.status_code == 402:
        # Payment required - open browser and show instructions
        handle_payment_required(response)
        return None
        
    else:
        # Other errors
        console.print(f"❌ Error: {response.status_code}")
        console.print(f"   {response.text}")
        sys.exit(1)

def handle_payment_required(response: requests.Response):
    """Handle 402 Payment Required response."""
    try:
        payment_data = response.json()
        checkout_url = payment_data.get("checkout_url")
        
        if not checkout_url:
            console.print("❌ No payment URL found in response")
            return
        
        console.print("\n" + "=" * 60)
        console.print("💳 PAYMENT REQUIRED")
        console.print("=" * 60)
        
        console.print("\n📱 Opening payment page in your browser...")
        console.print(f"   URL: {checkout_url}")
        
        # Open browser automatically
        try:
            webbrowser.open(checkout_url)
        except Exception as e:
            console.print(f"[red]Could not open browser: {e}[/red]")
        
        console.print("\n📋 PAYMENT INSTRUCTIONS:")
        console.print("   💳 Use test card: 4242 4242 4242 4242")
        console.print("   📅 Any future date")
        console.print("   🔢 Any 3-digit CVC")
        console.print("   📧 Any email address")
        console.print("\n   ⏳ Complete your payment in the browser")
        console.print("   🔄 After payment, run your scan command again")
        
        # Wait a moment for browser to open
        time.sleep(2)
        
        console.print(f"\n🔗 Payment URL also available at:")
        console.print(f"   {checkout_url}")
        console.print("\n" + "=" * 60)
        
        # Exit gracefully
        sys.exit(0)
        
    except Exception as e:
        console.print(f"❌ Error handling payment: {str(e)}")
        sys.exit(1)

def retry_scan_with_token(api_url: str, openai_key: str, data: Dict[str, Any], token: str) -> Optional[Dict[str, Any]]:
    """Retry the scan with the provided token."""
    try:
        headers = {
            "X-OpenAI-Key": openai_key,
            "X-Clausi-Token": token,
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{api_url}/api/clausi/scan",
            json=data,
            headers=headers,
            timeout=300
        )
        
        return handle_scan_response(response, api_url, openai_key, data)
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error retrying scan: {str(e)}[/red]")
        return None

def make_scan_request(api_url: str, openai_key: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make scan request with payment flow support."""
    try:
        # Prepare headers
        headers = {
            "X-OpenAI-Key": openai_key,
            "Content-Type": "application/json"
        }
        
        # Add token if available
        token = get_api_token()
        if token:
            headers["X-Clausi-Token"] = token
        
        console.print(f"🔍 Scanning for compliance...")
        
        response = requests.post(
            f"{api_url}/api/clausi/scan",
            json=data,
            headers=headers,
            timeout=300
        )
        
        # Handle different response types
        return handle_scan_response(response, api_url, openai_key, data)
        
    except requests.exceptions.RequestException as e:
        console.print(f"❌ Network error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1) 