"""HTTP client utilities for OLX scraping with proper headers and configuration."""

import logging
import time
from typing import Optional, Dict, Any

import requests


logger = logging.getLogger(__name__)


class OlxHttpClient:
    """HTTP client for OLX scraping with proper headers and rate limiting."""

    def __init__(self):
        """Initialize the HTTP client."""
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 second between requests

        # Set up proper headers for GraphQL API
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Content-Type": "application/json",
            }
        )

    def get(self, url: str, timeout: int = 30, **kwargs) -> requests.Response:
        """Make a GET request with rate limiting and proper error handling.

        Args:
            url (str): The URL to request
            timeout (int): Request timeout in seconds (default: 30)
            **kwargs: Additional arguments to pass to requests.get()

        Returns:
            requests.Response: The response object

        Raises:
            requests.RequestException: If the request fails
        """
        return self._make_request("GET", url, timeout=timeout, **kwargs)

    def post(
        self, url: str, data: Dict[str, Any], timeout: int = 30, **kwargs
    ) -> requests.Response:
        """Make a POST request with rate limiting and proper error handling.

        Args:
            url (str): The URL to request
            data (Dict[str, Any]): The JSON data to send
            timeout (int): Request timeout in seconds (default: 30)
            **kwargs: Additional arguments to pass to requests.post()

        Returns:
            requests.Response: The response object

        Raises:
            requests.RequestException: If the request fails
        """
        return self._make_request("POST", url, json=data, timeout=timeout, **kwargs)

    def _make_request(
        self, method: str, url: str, timeout: int = 30, **kwargs
    ) -> requests.Response:
        """Make a request with rate limiting and proper error handling.

        Args:
            method (str): HTTP method (GET, POST, etc.)
            url (str): The URL to request
            timeout (int): Request timeout in seconds (default: 30)
            **kwargs: Additional arguments to pass to the request

        Returns:
            requests.Response: The response object

        Raises:
            requests.RequestException: If the request fails
        """
        # Rate limiting
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            time.sleep(sleep_time)

        # Update last request time
        self.last_request_time = time.time()

        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=timeout, **kwargs)
            elif method.upper() == "POST":
                response = self.session.post(url, timeout=timeout, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response

        except requests.RequestException as e:
            logger.exception("request failed", extra={"url": url}, exc_info=e)
            raise

    def close(self):
        """Close the session."""
        self.session.close()


# Global client instance
_http_client: Optional[OlxHttpClient] = None


def get_http_client() -> OlxHttpClient:
    """Get or create the global HTTP client instance.

    Returns:
        OlxHttpClient: The HTTP client instance
    """
    global _http_client
    if _http_client is None:
        _http_client = OlxHttpClient()
    return _http_client


def make_request(url: str, timeout: int = 30, **kwargs) -> str:
    """Make a request and return HTML content.

    Args:
        url (str): The URL to request
        timeout (int): Request timeout in seconds (default: 30)
        **kwargs: Additional arguments to pass to the request

    Returns:
        str: The HTML content of the response

    Raises:
        requests.RequestException: If the request fails
    """
    client = get_http_client()
    response = client.get(url, timeout=timeout, **kwargs)
    return response.text


def make_graphql_request(
    url: str, query: str, variables: Dict[str, Any], timeout: int = 30
) -> Dict[str, Any]:
    """Make a GraphQL request and return JSON response.

    Args:
        url (str): The GraphQL endpoint URL
        query (str): The GraphQL query string
        variables (Dict[str, Any]): The GraphQL variables
        timeout (int): Request timeout in seconds (default: 30)

    Returns:
        Dict[str, Any]: The JSON response as a dictionary

    Raises:
        requests.RequestException: If the request fails
    """
    client = get_http_client()
    payload = {"query": query, "variables": variables}
    response = client.post(url, payload, timeout=timeout)

    # Check if response is JSON
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        logger.error(
            "Expected JSON response but got content-type",
            extra={"content_type": content_type, "snippet": response.text[:200]},
        )
        raise requests.RequestException(
            f"Expected JSON response but got {content_type}"
        )

    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as e:
        logger.exception("Failed to decode JSON response", exc_info=e)
        raise


def cleanup():
    """Clean up the HTTP client session."""
    global _http_client
    if _http_client is not None:
        _http_client.close()
        _http_client = None
