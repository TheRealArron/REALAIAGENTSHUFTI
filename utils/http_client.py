"""Rate-limited HTTP client for web requests."""

import asyncio
import random
import time
from typing import Dict, Optional, Any, Union
from urllib.parse import urljoin, urlparse
import aiohttp
import requests
from fake_useragent import UserAgent
from ratelimit import limits, sleep_and_retry
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import settings
from config.constants import DEFAULT_HEADERS, RATE_LIMITS, RETRY_CONFIG
from utils.logger import log_api_call, log_rate_limit, log_error, log_debug


class RateLimitedSession:
    """Synchronous HTTP session with rate limiting and retry logic."""

    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
        self._setup_session()
        self._last_request_time = 0

    def _setup_session(self):
        """Configure session with retries and headers."""
        # Setup retry strategy
        retry_strategy = Retry(
            total=RETRY_CONFIG['max_retries'],
            backoff_factor=RETRY_CONFIG['backoff_factor'],
            status_forcelist=RETRY_CONFIG['status_codes_to_retry']
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update(DEFAULT_HEADERS)
        self.session.headers['User-Agent'] = settings.USER_AGENT or self.ua.random

    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        elapsed = current_time - self._last_request_time

        min_delay = settings.REQUEST_DELAY_MIN
        max_delay = settings.REQUEST_DELAY_MAX
        required_delay = random.uniform(min_delay, max_delay)

        if elapsed < required_delay:
            wait_time = required_delay - elapsed
            log_rate_limit("http_request", wait_time)
            time.sleep(wait_time)

        self._last_request_time = time.time()

    @sleep_and_retry
    @limits(calls=RATE_LIMITS['requests_per_minute'], period=60)
    def get(self, url: str, **kwargs) -> requests.Response:
        """Rate-limited GET request."""
        self._enforce_rate_limit()
        start_time = time.time()

        try:
            response = self.session.get(url, timeout=RETRY_CONFIG['timeout'], **kwargs)
            response.raise_for_status()

            response_time = time.time() - start_time
            log_api_call("http", "GET", True, response_time)
            log_debug(f"GET {url} - Status: {response.status_code}")

            return response

        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            log_api_call("http", "GET", False, response_time)
            log_error(f"GET request failed: {url}", error=str(e))
            raise

    @sleep_and_retry
    @limits(calls=RATE_LIMITS['requests_per_minute'], period=60)
    def post(self, url: str, **kwargs) -> requests.Response:
        """Rate-limited POST request."""
        self._enforce_rate_limit()
        start_time = time.time()

        try:
            response = self.session.post(url, timeout=RETRY_CONFIG['timeout'], **kwargs)
            response.raise_for_status()

            response_time = time.time() - start_time
            log_api_call("http", "POST", True, response_time)
            log_debug(f"POST {url} - Status: {response.status_code}")

            return response

        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            log_api_call("http", "POST", False, response_time)
            log_error(f"POST request failed: {url}", error=str(e))
            raise


class AsyncHTTPClient:
    """Asynchronous HTTP client with rate limiting."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.ua = UserAgent()
        self._semaphore = asyncio.Semaphore(settings.CONCURRENT_REQUESTS)
        self._last_request_time = 0

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self):
        """Initialize the aiohttp session."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=RETRY_CONFIG['timeout'])
            connector = aiohttp.TCPConnector(limit=settings.CONCURRENT_REQUESTS)

            headers = DEFAULT_HEADERS.copy()
            headers['User-Agent'] = settings.USER_AGENT or self.ua.random

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=headers
            )

    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        elapsed = current_time - self._last_request_time

        min_delay = settings.REQUEST_DELAY_MIN
        max_delay = settings.REQUEST_DELAY_MAX
        required_delay = random.uniform(min_delay, max_delay)

        if elapsed < required_delay:
            wait_time = required_delay - elapsed
            log_rate_limit("async_http_request", wait_time)
            await asyncio.sleep(wait_time)

        self._last_request_time = time.time()

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Rate-limited async GET request."""
        async with self._semaphore:
            await self._enforce_rate_limit()

            if not self.session:
                await self.start()

            start_time = time.time()

            try:
                async with self.session.get(url, **kwargs) as response:
                    response.raise_for_status()

                    response_time = time.time() - start_time
                    log_api_call("async_http", "GET", True, response_time)
                    log_debug(f"Async GET {url} - Status: {response.status}")

                    return response

            except aiohttp.ClientError as e:
                response_time = time.time() - start_time
                log_api_call("async_http", "GET", False, response_time)
                log_error(f"Async GET request failed: {url}", error=str(e))
                raise

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Rate-limited async POST request."""
        async with self._semaphore:
            await self._enforce_rate_limit()

            if not self.session:
                await self.start()

            start_time = time.time()

            try:
                async with self.session.post(url, **kwargs) as response:
                    response.raise_for_status()

                    response_time = time.time() - start_time
                    log_api_call("async_http", "POST", True, response_time)
                    log_debug(f"Async POST {url} - Status: {response.status}")

                    return response

            except aiohttp.ClientError as e:
                response_time = time.time() - start_time
                log_api_call("async_http", "POST", False, response_time)
                log_error(f"Async POST request failed: {url}", error=str(e))
                raise


class ShuftiHTTPClient:
    """Specialized HTTP client for Shufti.jp with domain-specific features."""

    def __init__(self):
        self.sync_client = RateLimitedSession()
        self.base_url = settings.SHUFTI_BASE_URL
        self.logged_in = False
        self.csrf_token: Optional[str] = None

    def build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        return urljoin(self.base_url, endpoint.lstrip('/'))

    def get_headers_for_request(self, additional_headers: Dict[str, str] = None) -> Dict[str, str]:
        """Get headers including CSRF token if available."""
        headers = {}
        if self.csrf_token:
            headers['X-CSRF-Token'] = self.csrf_token
        if additional_headers:
            headers.update(additional_headers)
        return headers

    def extract_csrf_token(self, response: requests.Response) -> Optional[str]:
        """Extract CSRF token from response."""
        from bs4 import BeautifulSoup

        try:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for CSRF token in meta tags
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            if csrf_meta:
                return csrf_meta.get('content')

            # Look for CSRF token in hidden inputs
            csrf_input = soup.find('input', {'name': '_token'})
            if csrf_input:
                return csrf_input.get('value')

            return None

        except Exception as e:
            log_error("Failed to extract CSRF token", error=str(e))
            return None

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """GET request to Shufti endpoint."""
        url = self.build_url(endpoint)
        headers = self.get_headers_for_request(kwargs.pop('headers', {}))

        response = self.sync_client.get(url, headers=headers, **kwargs)

        # Update CSRF token if found
        if csrf_token := self.extract_csrf_token(response):
            self.csrf_token = csrf_token
            log_debug("Updated CSRF token")

        return response

    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """POST request to Shufti endpoint."""
        url = self.build_url(endpoint)
        headers = self.get_headers_for_request(kwargs.pop('headers', {}))

        # Add CSRF token to data if available
        data = kwargs.get('data', {})
        if self.csrf_token and isinstance(data, dict):
            data['_token'] = self.csrf_token
            kwargs['data'] = data

        return self.sync_client.post(url, headers=headers, **kwargs)

    def set_login_status(self, logged_in: bool):
        """Update login status."""
        self.logged_in = logged_in
        log_debug(f"Login status updated: {logged_in}")


# Global HTTP client instances
http_client = RateLimitedSession()
shufti_client = ShuftiHTTPClient()