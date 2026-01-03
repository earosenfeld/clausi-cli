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

                    console.print(f"\n{emoji('clipboard')} Complete your payment in the browser")
                    console.print("   After payment, run your scan command again")

                    # Wait a moment for browser to open
                    time.sleep(2)

                    console.print(f"\n{emoji('link')} Payment URL also available at:")
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
        credits = response_data.get("credits", 0)

        # Convert credits to dollars for user-facing display (hybrid approach: 1 credit = $0.10)
        trial_balance = credits * 0.10

        console.print(f"{emoji('party')} Account created!")
        console.print(f"   Starting balance: ${trial_balance:.2f}")
        console.print("\n   Saving credentials and starting scan...")

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

        if response.status_code == 503:
            # Check if this is a Claude CLI health check failure
            try:
                error_data = response.json()
                if isinstance(error_data.get("detail"), dict) and error_data["detail"].get("error") == "claude_cli_unavailable":
                    detail = error_data["detail"]
                    error_type = detail.get("error_type", "unknown")
                    message = detail.get("message", "Claude CLI is unavailable")
                    action = detail.get("action_required", "")

                    console.print(f"\n{emoji('crossmark')} [bold red]Claude CLI Unavailable[/bold red]")
                    console.print(f"\n[yellow]{message}[/yellow]")

                    if error_type == "no_credits":
                        console.print("\n[bold]Your Claude Code subscription has run out of credits.[/bold]")
                        console.print("\n[cyan]How to fix:[/cyan]")
                        console.print("  1. Check your Claude Code subscription at https://claude.ai/settings")
                        console.print("  2. Upgrade or renew your plan if needed")
                        console.print("  3. Alternatively, use BYOK mode: clausi scan . --claude")
                    elif error_type == "not_authenticated":
                        console.print("\n[bold]Claude Code CLI is not logged in.[/bold]")
                        console.print("\n[cyan]How to fix:[/cyan]")
                        console.print("  1. Open a terminal and run: claude login")
                        console.print("  2. Complete the authentication flow")
                        console.print("  3. Then retry your scan")
                    elif error_type == "watcher_not_running":
                        console.print("\n[bold]The Claude CLI watcher service is not running.[/bold]")
                        console.print("\n[cyan]How to fix:[/cyan]")
                        console.print("  1. Restart the backend with start_backend.bat (Windows)")
                        console.print("     or bash start_backend.sh (Linux/Mac)")
                        console.print("  2. Check that bash processes are running")
                    elif error_type == "timeout":
                        console.print("\n[bold]Claude CLI is not responding.[/bold]")
                        console.print("\n[cyan]How to fix:[/cyan]")
                        console.print("  1. Check if the watcher is running: tasklist | findstr bash")
                        console.print("  2. Restart the backend if needed")
                        console.print("  3. Check the claude_watcher.log for errors")
                    else:
                        console.print(f"\n[cyan]How to fix:[/cyan]")
                        console.print(f"  {action}")

                    if detail.get("details"):
                        console.print(f"\n[dim]Technical details: {detail['details'][:300]}[/dim]")

                    sys.exit(1)
            except (ValueError, KeyError):
                pass  # Not a JSON response or not our specific error, fall through

            # Generic 503 handling
            console.print(f"[yellow]Service Unavailable (Error 503)[/yellow]")
            console.print("\nThe backend service is temporarily unavailable.")
            console.print("Please try again in a few minutes.")
        elif response.status_code == 524:
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
    """Handle 402 Payment Required response - redirect to dashboard."""
    try:
        payment_data = response.json()
        checkout_url = payment_data.get("checkout_url")
        credits_remaining = payment_data.get("credits_remaining", 0)

        if not checkout_url:
            console.print(f"{emoji('crossmark')} No payment URL found in response")
            return

        # Convert tokens to dollars for user-facing display (hybrid approach)
        balance_dollars = credits_remaining * 0.10

        console.print("\n" + "=" * 60)
        console.print(f"{emoji('warning')} INSUFFICIENT BALANCE")
        console.print("=" * 60)

        console.print(f"\n{emoji('info')} Balance remaining: ${balance_dollars:.2f}")
        console.print("\nOpening your dashboard to add funds...")

        # Open browser automatically
        try:
            webbrowser.open(checkout_url)
            console.print(f"{emoji('checkmark')} Dashboard opened in your browser")
        except Exception as e:
            console.print(f"[red]Could not open browser: {e}[/red]")
            console.print(f"\nPlease visit: {checkout_url}")

        console.print(f"\n{emoji('clipboard')} NEXT STEPS:")
        console.print("   1. Complete your purchase in the browser")
        console.print("   2. Return here and re-run your scan command")
        console.print("\n   Example:")
        console.print("   $ clausi scan .")

        console.print(f"\n{emoji('link')} Dashboard URL:")
        console.print(f"   {checkout_url}")
        console.print("\n" + "=" * 60)

        # Exit with code 2 (payment required) - not 0, so interactive mode knows scan didn't complete
        sys.exit(2)

    except Exception as e:
        console.print(f"{emoji('crossmark')} Error handling payment: {str(e)}")
        sys.exit(1)

def retry_scan_with_token(api_url: str, openai_key: str, provider: str, data: Dict[str, Any], token: str) -> Optional[Dict[str, Any]]:
    """Retry the scan with the provided token."""
    try:
        # Prepare headers with appropriate API key header based on provider
        headers = {"Content-Type": "application/json", "X-Clausi-Key": token}

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

    job_id = None  # Track job_id for error messages
    try:
        # Prepare headers with appropriate API key header based on provider
        headers = {"Content-Type": "application/json"}

        # Only add API key header if we have one (not using Clausi hosted AI)
        if openai_key:
            if provider == "claude":
                headers["X-Anthropic-Key"] = openai_key
            elif provider == "openai":
                headers["X-OpenAI-Key"] = openai_key

        # Check for token - require login if not found
        token = get_api_token()
        if not token:
            # Customize message based on whether using BYOK
            if openai_key:
                console.print(f"\n{emoji('warning')} Clausi account required (even with your own API key).")
                console.print(f"   There's a $0.50 platform fee for BYOK scans.")
                console.print(f"   Starting login...\n")
            else:
                console.print(f"\n{emoji('warning')} No account found. Starting login...\n")

            # Auto-start the login flow
            import subprocess
            result = subprocess.run(["clausi", "login"], shell=True)

            # Check if login succeeded
            token = get_api_token()
            if token:
                console.print(f"\n{emoji('checkmark')} Login successful! Continuing with scan...\n")
                headers["X-Clausi-Key"] = token
            else:
                console.print(f"\n{emoji('crossmark')} Login was not completed.")
                console.print(f"{emoji('info')} Run 'clausi login' to try again.\n")
                return None
        else:
            headers["X-Clausi-Key"] = token

        console.print(f"{emoji('search')} Starting async scan...")

        # Start async scan job
        response = requests.post(
            f"{api_url}/api/clausi/scan/async",
            json=data,
            headers=headers,
            timeout=30  # Short timeout for starting job
        )

        # Handle 401 (unauthorized) and 402 (payment required) before raise_for_status
        if response.status_code == 401:
            # Token invalid or expired - prompt to login again
            console.print(f"\n{emoji('warning')} Your session has expired or token is invalid.\n")
            console.print("Please login again:")
            console.print(f"   clausi login")
            return None

        if response.status_code == 402:
            # Payment required - open browser
            handle_payment_required(response)
            return None

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
            consecutive_errors = 0
            max_consecutive_errors = 5  # Allow up to 5 consecutive errors before giving up

            while True:
                # Poll job status (include auth headers)
                poll_headers = {"X-Clausi-Key": token} if token else {}

                try:
                    status_response = requests.get(
                        f"{api_url}/api/clausi/jobs/{job_id}/status",
                        headers=poll_headers,
                        timeout=30  # Shorter timeout for status polls
                    )

                    # Handle 524 Cloudflare timeout with retry
                    if status_response.status_code == 524:
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            console.print(f"\n{emoji('crossmark')} [bold red]Connection Lost[/bold red]")
                            console.print(f"\nReceived {consecutive_errors} consecutive 524 errors.")
                            console.print(f"The backend may have restarted or be overloaded.")
                            console.print(f"\n[dim]Job ID: {job_id}[/dim]")
                            console.print(f"\nTry running the scan again - results may be cached.")
                            sys.exit(1)
                        # Wait and retry with exponential backoff
                        wait_time = min(2 ** consecutive_errors, 30)  # Max 30 second wait
                        progress.update(task, description=f"[yellow]Connection issue, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue

                    # Handle 503 Service Unavailable with retry
                    if status_response.status_code == 503:
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            console.print(f"\n{emoji('crossmark')} [bold red]Service Unavailable[/bold red]")
                            console.print(f"\nThe backend service is unavailable.")
                            console.print(f"\n[dim]Job ID: {job_id}[/dim]")
                            sys.exit(1)
                        wait_time = min(2 ** consecutive_errors, 30)
                        progress.update(task, description=f"[yellow]Service unavailable, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue

                    # Handle 404 Job Not Found (server restarted, job state lost)
                    if status_response.status_code == 404:
                        console.print(f"\n{emoji('crossmark')} [bold red]Scan Job Lost[/bold red]")
                        console.print(f"\nThe backend lost track of your scan job.")
                        console.print(f"This usually happens when the backend restarts during a scan.")
                        console.print(f"\n[dim]Job ID: {job_id}[/dim]")
                        console.print(f"\n[cyan]What to do:[/cyan]")
                        console.print(f"  1. Re-run the scan - previously analyzed files are cached")
                        console.print(f"  2. The re-scan should be much faster due to caching")
                        sys.exit(1)

                    # Handle other HTTP errors
                    status_response.raise_for_status()

                    # Success - reset error counter
                    consecutive_errors = 0
                    status_data = status_response.json()

                except requests.exceptions.Timeout:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        console.print(f"\n{emoji('crossmark')} [bold red]Connection Timeout[/bold red]")
                        console.print(f"\nStatus polling timed out {consecutive_errors} times.")
                        console.print(f"\n[dim]Job ID: {job_id}[/dim]")
                        console.print(f"\nThe scan may still complete. Try again later.")
                        sys.exit(1)
                    wait_time = min(2 ** consecutive_errors, 30)
                    progress.update(task, description=f"[yellow]Timeout, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                except requests.exceptions.ConnectionError:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        console.print(f"\n{emoji('crossmark')} [bold red]Connection Lost[/bold red]")
                        console.print(f"\nLost connection to the backend.")
                        console.print(f"\n[dim]Job ID: {job_id}[/dim]")
                        sys.exit(1)
                    wait_time = min(2 ** consecutive_errors, 30)
                    progress.update(task, description=f"[yellow]Connection lost, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue

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
        result_headers = {"X-Clausi-Key": token} if token else {}
        result_response = requests.get(
            f"{api_url}/api/clausi/jobs/{job_id}/result",
            headers=result_headers,
            timeout=60  # Increased timeout for large results
        )
        result_response.raise_for_status()
        result_data = result_response.json()

        console.print(f"{emoji('checkmark')} Scan completed successfully!")
        return result_data

    except requests.exceptions.Timeout:
        console.print(f"\n{emoji('crossmark')} [bold red]Request Timeout[/bold red]")
        console.print("\nThe status polling request timed out.")
        console.print(f"\n[yellow]Note:[/yellow] The job may still be running on the backend.")
        if job_id:
            console.print(f"[dim]Job ID: {job_id}[/dim]")
        console.print("\nTry running the scan again - results may be cached.")
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

        # Only add API key header if we have one (not using Clausi hosted AI)
        if openai_key:
            # Use correct header name based on provider (modular approach)
            if provider == "claude":
                headers["X-Anthropic-Key"] = openai_key
            elif provider == "openai":
                headers["X-OpenAI-Key"] = openai_key

        # Add token if available
        token = get_api_token()
        if token:
            headers["X-Clausi-Key"] = token

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