"""Scan functionality with payment flow support."""

import os
import sys
import time
import webbrowser
import requests
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from rich.panel import Panel
import click

# Import configuration functions from utils module
from clausi.utils.config import get_api_token, save_api_token
from clausi.utils.emoji import get as emoji
from clausi.utils.console import console

def check_payment_required(api_url: str, mode: str = "full") -> bool:
    """Check if payment is required before proceeding with scan."""
    try:
        response = requests.post(
            f"{api_url}/api/clausi/check-payment-required",
            headers={"Content-Type": "application/json"},
            json={"mode": mode},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()

            if data.get("payment_required"):
                checkout_url = data.get("checkout_url")

                if checkout_url:
                    console.print("\n" + "=" * 60)
                    console.print(f"{emoji('credit_card')} PAYMENT REQUIRED")
                    console.print("=" * 60)
                    console.print(f"\n{emoji('info')} Opening payment page in your browser...")

                    try:
                        webbrowser.open(checkout_url)
                    except Exception as e:
                        console.print(f"[red]Could not open browser: {e}[/red]")

                    console.print(f"\n{emoji('clipboard')} PAYMENT INSTRUCTIONS:")
                    console.print(f"   {emoji('credit_card')} Use test card: 4242 4242 4242 4242")
                    console.print("   Any future date")
                    console.print("   Any 3-digit CVC")
                    console.print("   Any email address")
                    console.print("\n   Complete your payment in the browser")
                    console.print("   After payment, run your scan command again")

                    # Wait a moment for browser to open
                    time.sleep(2)

                    console.print(f"\n🔗 Payment URL also available at:")
                    console.print(f"   {checkout_url}")
                    console.print("\n" + "=" * 60)

                    return False  # Return False to indicate payment required
                return False

        return True
    except Exception as e:
        console.print(f"{emoji('crossmark')} Error checking payment: {str(e)}")
        return True

def handle_scan_response(response: requests.Response, api_url: str, openai_key: str, provider: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle different response types from the scan endpoint."""

    if response.status_code == 200:
        # Success - handle normal response
        return response.json()

    elif response.status_code == 401:
        # Trial token created - save and retry
        response_data = response.json()
        api_token = response_data.get("api_token")
        credits = response_data.get("credits")

        console.print(f"{emoji('party')} Trial account created!")
        console.print(f"   Credits: {credits}")
        console.print(f"   Token: {api_token[:8]}...")
        console.print("\n   Saving token and retrying scan...")

        # Save token to config file
        save_api_token(api_token)

        # Retry the scan with the new token
        return retry_scan_with_token(api_url, openai_key, provider, data, api_token)

    elif response.status_code == 402:
        # Payment required - open browser and show instructions
        handle_payment_required(response)
        return None

    else:
        # Other errors - handle gracefully
        console.print(f"\n{emoji('crossmark')} [bold red]Scan Failed[/bold red]")

        # Check if response is HTML (Cloudflare errors, etc.)
        content_type = response.headers.get('Content-Type', '')
        is_html = 'text/html' in content_type or response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html')

        if response.status_code == 524:
            console.print(f"[yellow]Server Timeout (Error 524)[/yellow]")
            console.print("\nThe backend server took too long to respond.")
            console.print("This usually happens when:")
            console.print("  - Scanning a very large codebase")
            console.print("  - The backend is overloaded")
            console.print("\nTry:")
            console.print("  1. Reduce the number of files (use --ignore)")
            console.print("  2. Use --preset critical-only to scan fewer clauses")
            console.print("  3. Wait a few minutes and try again")
        elif response.status_code >= 500:
            console.print(f"[yellow]Server Error ({response.status_code})[/yellow]")
            console.print("\nThe backend server encountered an error.")
            console.print("Please try again in a few minutes.")
            if not is_html:
                console.print(f"\n[dim]Details: {response.text[:200]}[/dim]")
        elif response.status_code == 503:
            console.print(f"[yellow]Service Unavailable (Error 503)[/yellow]")
            console.print("\nThe backend service is temporarily unavailable.")
            console.print("Please try again in a few minutes.")
        elif is_html:
            # HTML response (likely Cloudflare error page)
            console.print(f"[yellow]HTTP Error {response.status_code}[/yellow]")
            console.print("\nReceived an HTML error page from the server.")
            console.print("This may be a network issue or server error.")
            console.print("\nPlease check:")
            console.print("  - Your internet connection")
            console.print("  - Try again in a few minutes")
            console.print(f"\n[dim]API URL: {api_url}[/dim]")
        else:
            # JSON or text error
            console.print(f"[yellow]HTTP Error {response.status_code}[/yellow]")
            try:
                error_data = response.json()
                console.print(f"\n{error_data.get('detail', error_data.get('message', response.text[:200]))}")
            except:
                console.print(f"\n{response.text[:200]}")

        sys.exit(1)

def handle_payment_required(response: requests.Response):
    """Handle 402 Payment Required response."""
    try:
        payment_data = response.json()
        checkout_url = payment_data.get("checkout_url")
        
        if not checkout_url:
            console.print(f"{emoji('crossmark')} No payment URL found in response")
            return

        console.print("\n" + "=" * 60)
        console.print(f"{emoji('credit_card')} PAYMENT REQUIRED")
        console.print("=" * 60)

        console.print(f"\n{emoji('info')} Opening payment page in your browser...")
        console.print(f"   URL: {checkout_url}")

        # Open browser automatically
        try:
            webbrowser.open(checkout_url)
        except Exception as e:
            console.print(f"[red]Could not open browser: {e}[/red]")

        console.print(f"\n{emoji('clipboard')} PAYMENT INSTRUCTIONS:")
        console.print(f"   {emoji('credit_card')} Use test card: 4242 4242 4242 4242")
        console.print("   Any future date")
        console.print("   Any 3-digit CVC")
        console.print("   Any email address")
        console.print("\n   Complete your payment in the browser")
        console.print("   After payment, run your scan command again")
        
        # Wait a moment for browser to open
        time.sleep(2)
        
        console.print(f"\n🔗 Payment URL also available at:")
        console.print(f"   {checkout_url}")
        console.print("\n" + "=" * 60)
        
        # Exit gracefully
        sys.exit(0)

    except Exception as e:
        console.print(f"{emoji('crossmark')} Error handling payment: {str(e)}")
        sys.exit(1)

def retry_scan_with_token(api_url: str, openai_key: str, provider: str, data: Dict[str, Any], token: str) -> Optional[Dict[str, Any]]:
    """Retry the scan with the provided token."""
    try:
        # Prepare headers with appropriate API key header based on provider
        headers = {"Content-Type": "application/json", "X-Clausi-Token": token}

        # Use correct header name based on provider (modular approach)
        if provider == "claude":
            headers["X-Anthropic-Key"] = openai_key
        else:  # openai
            headers["X-OpenAI-Key"] = openai_key

        response = requests.post(
            f"{api_url}/api/clausi/scan",
            json=data,
            headers=headers,
            timeout=300
        )

        return handle_scan_response(response, api_url, openai_key, provider, data)

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error retrying scan: {str(e)}[/red]")
        return None

def make_async_scan_request(api_url: str, openai_key: str, provider: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make async scan request with job polling (prevents timeouts on large scans).

    Args:
        api_url: Backend API URL
        openai_key: API key (despite the name, can be Anthropic or OpenAI key)
        provider: AI provider ("claude" or "openai")
        data: Request payload

    Returns:
        Scan result or None on error
    """
    import time
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

    try:
        # Prepare headers with appropriate API key header based on provider
        headers = {"Content-Type": "application/json"}

        # Only add API key header if we have one (not using Claude Code CLI)
        if openai_key:
            if provider == "claude":
                headers["X-Anthropic-Key"] = openai_key
            else:  # openai
                headers["X-OpenAI-Key"] = openai_key

        # Add token if available
        token = get_api_token()
        if token:
            headers["X-Clausi-Token"] = token

        console.print(f"{emoji('search')} Starting async scan...")

        # Start async scan job
        response = requests.post(
            f"{api_url}/api/clausi/scan/async",
            json=data,
            headers=headers,
            timeout=30  # Short timeout for starting job
        )
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data.get("job_id")

        if not job_id:
            console.print("[red]Failed to start async scan: No job ID returned[/red]")
            return None

        console.print(f"{emoji('info')} Job started: {job_id}")
        console.print(f"{emoji('hourglass')} Polling for progress...")

        # Poll job status with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Scanning...", total=100)

            last_status = None
            while True:
                # Poll job status
                status_response = requests.get(
                    f"{api_url}/api/clausi/jobs/{job_id}/status",
                    timeout=10
                )
                status_response.raise_for_status()
                status_data = status_response.json()

                job_status = status_data.get("status")
                job_progress = status_data.get("progress", {})
                progress_pct = job_progress.get("percentage", 0)
                progress_msg = job_progress.get("message", "Processing...")

                # Update progress bar
                progress.update(task, completed=progress_pct, description=f"[cyan]{progress_msg}")

                # Check if job is complete
                if job_status == "completed":
                    progress.update(task, completed=100, description="[green]Scan complete!")
                    break
                elif job_status == "failed":
                    error_msg = status_data.get("error", "Unknown error")
                    console.print(f"[red]Scan failed: {error_msg}[/red]")
                    return None

                # Avoid spamming the API
                time.sleep(2)  # Poll every 2 seconds

        # Get final result
        console.print(f"{emoji('checkmark')} Retrieving scan results...")
        result_response = requests.get(
            f"{api_url}/api/clausi/jobs/{job_id}/result",
            timeout=10
        )
        result_response.raise_for_status()
        result_data = result_response.json()

        console.print(f"{emoji('checkmark')} Scan completed successfully!")
        return result_data

    except requests.exceptions.Timeout:
        console.print(f"\n{emoji('crossmark')} [bold red]Request Timeout[/bold red]")
        console.print("\nThe async scan polling timed out.")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        console.print(f"\n{emoji('crossmark')} [bold red]Connection Error[/bold red]")
        console.print("\nCould not connect to the Clausi API.")
        console.print(f"\n[dim]API URL: {api_url}[/dim]")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        console.print(f"\n{emoji('crossmark')} [bold red]Network Error[/bold red]")
        console.print(f"\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n{emoji('crossmark')} [bold red]Error[/bold red]")
        console.print(f"\n{str(e)}")
        sys.exit(1)


def make_scan_request(api_url: str, openai_key: str, provider: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make scan request with payment flow support.

    Args:
        api_url: Backend API URL
        openai_key: API key (despite the name, can be Anthropic or OpenAI key)
        provider: AI provider ("claude" or "openai")
        data: Request payload
    """
    try:
        # Prepare headers with appropriate API key header based on provider
        headers = {"Content-Type": "application/json"}

        # Only add API key header if we have one (not using Claude Code CLI)
        if openai_key:
            # Use correct header name based on provider (modular approach)
            if provider == "claude":
                headers["X-Anthropic-Key"] = openai_key
            else:  # openai
                headers["X-OpenAI-Key"] = openai_key

        # Add token if available
        token = get_api_token()
        if token:
            headers["X-Clausi-Token"] = token

        console.print(f"{emoji('search')} Scanning for compliance...")

        response = requests.post(
            f"{api_url}/api/clausi/scan",
            json=data,
            headers=headers,
            timeout=300
        )

        # Handle different response types
        return handle_scan_response(response, api_url, openai_key, provider, data)

    except requests.exceptions.Timeout:
        console.print(f"\n{emoji('crossmark')} [bold red]Request Timeout[/bold red]")
        console.print("\nThe scan request timed out after 5 minutes.")
        console.print("This usually happens when:")
        console.print("  - Scanning a very large codebase")
        console.print("  - The backend is processing too many requests")
        console.print("\nTry:")
        console.print("  1. Reduce the number of files (use --ignore)")
        console.print("  2. Use --preset critical-only to scan fewer clauses")
        console.print("  3. Wait a few minutes and try again")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        console.print(f"\n{emoji('crossmark')} [bold red]Connection Error[/bold red]")
        console.print("\nCould not connect to the Clausi API.")
        console.print("\nPlease check:")
        console.print("  - Your internet connection")
        console.print("  - The API URL is correct")
        console.print(f"\n[dim]API URL: {api_url}[/dim]")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        console.print(f"\n{emoji('crossmark')} [bold red]Network Error[/bold red]")
        console.print(f"\n{str(e)}")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n{emoji('crossmark')} [bold red]Unexpected Error[/bold red]")
        console.print(f"\n{str(e)}")
        sys.exit(1) 