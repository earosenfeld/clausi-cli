"""API client for Clausi backend."""

import requests
from typing import Dict, Any, Optional
from clausi.utils.console import console


class ClausiClient:
    """Client for interacting with Clausi backend API."""

    def __init__(self, api_url: str, timeout: int = 300):
        """Initialize client.

        Args:
            api_url: Base URL for Clausi API
            timeout: Request timeout in seconds
        """
        self.api_url = api_url
        self.timeout = timeout

    def _get_api_key_header(self, api_key: Optional[str], provider: str) -> Dict[str, str]:
        """Get the appropriate API key header based on provider.

        Args:
            api_key: API key (or None for Clausi AI mode)
            provider: Provider name ('clausi', 'claude', or 'openai')

        Returns:
            Headers dict with appropriate API key header
        """
        headers = {"Content-Type": "application/json"}
        if api_key:
            if provider == "claude":
                headers["X-Anthropic-Key"] = api_key
            elif provider == "openai":
                headers["X-OpenAI-Key"] = api_key
        return headers

    def estimate(self, data: Dict[str, Any], api_key: Optional[str] = None,
                 provider: str = "clausi") -> Optional[Dict[str, Any]]:
        """Get token estimate for scan.

        Args:
            data: Scan request data
            api_key: API key (Anthropic/OpenAI) or None for Clausi AI mode
            provider: Provider name ('clausi', 'claude', or 'openai')

        Returns:
            Estimate response or None on error
        """
        try:
            headers = self._get_api_key_header(api_key, provider)
            response = requests.post(
                f"{self.api_url}/api/clausi/estimate",
                json=data,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")
            return None

    def download_report(self, filename: str, api_key: str) -> Optional[bytes]:
        """Download a report file.

        Args:
            filename: Report filename
            api_key: OpenAI API key

        Returns:
            Report content or None on error
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/clausi/report/{filename}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=60
            )
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Download Error: {e}[/red]")
            return None

    def scan_async(self, data: Dict[str, Any], api_key: Optional[str] = None,
                   provider: str = "clausi") -> Optional[str]:
        """Start an async scan job.

        Args:
            data: Scan request data
            api_key: API key (Anthropic/OpenAI) or None for Clausi AI mode
            provider: Provider name ('clausi', 'claude', or 'openai')

        Returns:
            Job ID or None on error
        """
        try:
            headers = self._get_api_key_header(api_key, provider)
            response = requests.post(
                f"{self.api_url}/api/clausi/scan/async",
                json=data,
                headers=headers,
                timeout=30  # Short timeout for starting job
            )
            response.raise_for_status()
            result = response.json()
            return result.get("job_id")
        except requests.exceptions.RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")
            return None

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a running job.

        Args:
            job_id: Job identifier

        Returns:
            Job status dict or None on error
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/clausi/jobs/{job_id}/status",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")
            return None

    def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get result of a completed job.

        Args:
            job_id: Job identifier

        Returns:
            Job result dict or None on error
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/clausi/jobs/{job_id}/result",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[red]API Error: {e}[/red]")
            return None
