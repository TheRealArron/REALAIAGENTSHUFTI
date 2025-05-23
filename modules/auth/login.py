"""
Authentication Module for Shufti Agent
Handles login, session management, and authentication with Shufti.jp
"""

import requests
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
import json
import re
from bs4 import BeautifulSoup

from config.settings import get_settings
from utils.logger import get_logger
from utils.http_client import get_http_client
from utils.data_store import get_data_store

logger = get_logger(__name__)


class ShuftiAuth:
    """Handle authentication with Shufti.jp"""

    def __init__(self):
        self.settings = get_settings()
        self.http_client = get_http_client()
        self.data_store = get_data_store()

        self.base_url = "https://app.shufti.jp"
        self.login_url = urljoin(self.base_url, "/login")
        self.session_key = "shufti_session"

        # Session state
        self.is_authenticated = False
        self.user_info = {}
        self.session_cookies = {}
        self.csrf_token = None

        # Load existing session if available
        self._load_session()

    def _load_session(self):
        """Load existing session from storage"""
        try:
            session_data = self.data_store.get(self.session_key)
            if session_data:
                self.session_cookies = session_data.get('cookies', {})
                self.user_info = session_data.get('user_info', {})
                self.csrf_token = session_data.get('csrf_token')

                # Update HTTP client with cookies
                if self.session_cookies:
                    self.http_client.session.cookies.update(self.session_cookies)
                    logger.info("Loaded existing session from storage")

                    # Verify session is still valid
                    if self._verify_session():
                        self.is_authenticated = True
                        logger.info("Session verified successfully")
                    else:
                        logger.info("Stored session is invalid, will need to re-authenticate")
                        self._clear_session()

        except Exception as e:
            logger.error(f"Error loading session: {e}")
            self._clear_session()

    def _save_session(self):
        """Save current session to storage"""
        try:
            session_data = {
                'cookies': dict(self.http_client.session.cookies),
                'user_info': self.user_info,
                'csrf_token': self.csrf_token,
                'timestamp': time.time()
            }

            self.data_store.set(self.session_key, session_data)
            logger.info("Session saved to storage")

        except Exception as e:
            logger.error(f"Error saving session: {e}")

    def _clear_session(self):
        """Clear session data"""
        try:
            self.is_authenticated = False
            self.user_info = {}
            self.session_cookies = {}
            self.csrf_token = None

            self.http_client.session.cookies.clear()
            self.data_store.delete(self.session_key)

            logger.info("Session cleared")

        except Exception as e:
            logger.error(f"Error clearing session: {e}")

    def _verify_session(self) -> bool:
        """Verify current session is still valid"""
        try:
            # Try to access a protected page
            response = self.http_client.get("/profile", timeout=10)

            if response and response.status_code == 200:
                # Check if we're still logged in (not redirected to login)
                if "login" not in response.url.lower():
                    return True

            return False

        except Exception as e:
            logger.error(f"Error verifying session: {e}")
            return False

    def _get_csrf_token(self, response_text: str) -> Optional[str]:
        """Extract CSRF token from HTML response"""
        try:
            soup = BeautifulSoup(response_text, 'html.parser')

            # Look for CSRF token in meta tags
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            if csrf_meta:
                return csrf_meta.get('content')

            # Look for CSRF token in forms
            csrf_input = soup.find('input', {'name': '_token'})
            if csrf_input:
                return csrf_input.get('value')

            # Look for CSRF token in hidden inputs
            csrf_hidden = soup.find('input', {'type': 'hidden', 'name': re.compile('csrf|token', re.I)})
            if csrf_hidden:
                return csrf_hidden.get('value')

            # Try to find in script tags
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Look for common CSRF patterns
                    csrf_match = re.search(r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)', script.string, re.I)
                    if csrf_match:
                        return csrf_match.group(1)

            logger.warning("Could not find CSRF token in response")
            return None

        except Exception as e:
            logger.error(f"Error extracting CSRF token: {e}")
            return None

    def login(self, email: str, password: str) -> bool:
        """Login to Shufti.jp"""
        try:
            logger.info(f"Attempting to login with email: {email}")

            # First, get the login page to extract any necessary tokens
            response = self.http_client.get(self.login_url)
            if not response or response.status_code != 200:
                logger.error("Failed to access login page")
                return False

            # Extract CSRF token if needed
            self.csrf_token = self._get_csrf_token(response.text)

            # Prepare login data
            login_data = {
                'email': email,
                'password': password
            }

            # Add CSRF token if found
            if self.csrf_token:
                login_data['_token'] = self.csrf_token

            # Additional common form fields
            soup = BeautifulSoup(response.text, 'html.parser')
            login_form = soup.find('form')

            if login_form:
                # Extract all hidden inputs
                hidden_inputs = login_form.find_all('input', {'type': 'hidden'})
                for hidden_input in hidden_inputs:
                    name = hidden_input.get('name')
                    value = hidden_input.get('value')
                    if name and value and name not in login_data:
                        login_data[name] = value

            # Set proper headers for login
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': self.login_url,
                'Origin': self.base_url
            }

            # Attempt login
            login_response = self.http_client.post(
                self.login_url,
                data=login_data,
                headers=headers,
                allow_redirects=True
            )

            if not login_response:
                logger.error("Login request failed")
                return False

            # Check if login was successful
            if login_response.status_code in [200, 302]:
                # Check for redirect to dashboard or profile
                if any(path in login_response.url for path in ['/dashboard', '/profile', '/jobs']):
                    logger.info("Login successful - redirected to authenticated page")
                    self.is_authenticated = True

                    # Extract user information if possible
                    self._extract_user_info(login_response.text)

                    # Save session
                    self._save_session()
                    return True

                # Check response content for success indicators
                response_text = login_response.text.lower()
                if any(indicator in response_text for indicator in ['dashboard', 'welcome', 'profile', 'logout']):
                    logger.info("Login successful - found success indicators")
                    self.is_authenticated = True
                    self._extract_user_info(login_response.text)
                    self._save_session()
                    return True

                # Check for error messages
                if any(error in response_text for error in ['invalid', 'incorrect', 'error', 'failed']):
                    logger.error("Login failed - invalid credentials")
                    return False

            logger.error(f"Login failed - unexpected response code: {login_response.status_code}")
            return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def _extract_user_info(self, html_content: str):
        """Extract user information from authenticated page"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            user_info = {}

            # Look for user name in common locations
            name_selectors = [
                '.user-name', '.username', '.profile-name',
                '[data-user-name]', '#user-name', '.navbar-nav .dropdown-toggle'
            ]

            for selector in name_selectors:
                element = soup.select_one(selector)
                if element:
                    user_info['name'] = element.get_text(strip=True)
                    break

            # Look for user email
            email_selectors = [
                '.user-email', '.profile-email', '[data-user-email]'
            ]

            for selector in email_selectors:
                element = soup.select_one(selector)
                if element:
                    user_info['email'] = element.get_text(strip=True)
                    break

            # Look for user ID in data attributes or URLs
            user_links = soup.find_all('a', href=re.compile(r'/users?/(\d+)'))
            if user_links:
                href = user_links[0].get('href')
                user_id_match = re.search(r'/users?/(\d+)', href)
                if user_id_match:
                    user_info['user_id'] = user_id_match.group(1)

            self.user_info = user_info
            logger.info(f"Extracted user info: {user_info}")

        except Exception as e:
            logger.error(f"Error extracting user info: {e}")

    def logout(self) -> bool:
        """Logout from Shufti.jp"""
        try:
            logger.info("Attempting to logout")

            # Try common logout endpoints
            logout_urls = [
                '/logout',
                '/auth/logout',
                '/users/sign_out'
            ]

            for logout_path in logout_urls:
                try:
                    logout_data = {}
                    if self.csrf_token:
                        logout_data['_token'] = self.csrf_token

                    response = self.http_client.post(
                        logout_path,
                        data=logout_data,
                        allow_redirects=True
                    )

                    if response and response.status_code in [200, 302]:
                        logger.info("Logout successful")
                        self._clear_session()
                        return True

                except Exception as e:
                    logger.debug(f"Logout attempt failed for {logout_path}: {e}")
                    continue

            # If POST logout fails, try GET
            for logout_path in logout_urls:
                try:
                    response = self.http_client.get(logout_path, allow_redirects=True)
                    if response and response.status_code in [200, 302]:
                        logger.info("Logout successful (GET)")
                        self._clear_session()
                        return True
                except Exception as e:
                    continue

            # Force clear session even if logout request failed
            logger.warning("Could not perform proper logout, clearing local session")
            self._clear_session()
            return True

        except Exception as e:
            logger.error(f"Logout error: {e}")
            self._clear_session()
            return False

    def ensure_authenticated(self, email: str = None, password: str = None) -> bool:
        """Ensure we have a valid authentication session"""
        try:
            # Check if already authenticated
            if self.is_authenticated and self._verify_session():
                logger.info("Already authenticated")
                return True

            # Clear invalid session
            if not self._verify_session():
                self._clear_session()

            # Try to login if credentials provided
            if email and password:
                return self.login(email, password)

            # Try to use stored credentials
            stored_email = self.settings.SHUFTI_EMAIL
            stored_password = self.settings.SHUFTI_PASSWORD

            if stored_email and stored_password:
                return self.login(stored_email, stored_password)

            logger.error("No valid authentication and no credentials provided")
            return False

        except Exception as e:
            logger.error(f"Authentication check error: {e}")
            return False

    def get_authenticated_session(self) -> Optional[requests.Session]:
        """Get authenticated HTTP session"""
        if self.is_authenticated:
            return self.http_client.session
        return None

    def get_user_info(self) -> Dict:
        """Get current user information"""
        return self.user_info.copy()

    def is_session_valid(self) -> bool:
        """Check if current session is valid"""
        return self.is_authenticated and self._verify_session()


# Singleton instance
_auth_service = None


def get_auth_service() -> ShuftiAuth:
    """Get singleton authentication service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = ShuftiAuth()
    return _auth_service