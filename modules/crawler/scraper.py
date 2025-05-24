"""
Job listing scraper with rate limiting for Shufti platform.
Implements respectful crawling with delays and error handling.
"""

import asyncio
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs
import random

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from utils.logger import logger
from utils.http_client import HTTPClient
from config.constants import SCRAPING_DELAYS, USER_AGENTS
from config.settings import get_settings


class ShuftiScraper:
    """
    Scraper for Shufti job listings with rate limiting and respectful crawling.
    """

    def __init__(self):
        self.settings = get_settings()
        self.http_client = HTTPClient()
        self.base_url = "https://app.shufti.jp"
        self.jobs_url = f"{self.base_url}/jobs/search"
        self.driver = None
        self.last_request_time = 0

    def _setup_driver(self) -> webdriver.Chrome:
        """Setup Chrome driver with appropriate options."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")

            # Additional privacy options
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            return driver
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            raise

    async def _rate_limit(self):
        """Implement rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        min_delay = SCRAPING_DELAYS['MIN_DELAY']
        max_delay = SCRAPING_DELAYS['MAX_DELAY']

        if time_since_last < min_delay:
            delay = min_delay - time_since_last
            # Add some randomness to avoid detection
            delay += random.uniform(0, max_delay - min_delay)
            logger.info(f"Rate limiting: waiting {delay:.2f} seconds")
            await asyncio.sleep(delay)

        self.last_request_time = time.time()

    async def get_job_listings_page(self, page: int = 1, filters: Dict = None) -> str:
        """
        Get job listings page HTML with filters.

        Args:
            page: Page number to retrieve
            filters: Dictionary of filters to apply

        Returns:
            HTML content of the page
        """
        await self._rate_limit()

        try:
            if not self.driver:
                self.driver = self._setup_driver()

            # Build URL with parameters
            url = self.jobs_url
            params = {"page": page}

            if filters:
                params.update(filters)

            # Navigate to the page
            self.driver.get(url)

            # Apply filters if provided
            if filters:
                await self._apply_filters(filters)

            # Wait for job listings to load
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "job-card")))

            # Get page source
            html_content = self.driver.page_source
            logger.info(f"Successfully retrieved page {page}")

            return html_content

        except TimeoutException:
            logger.warning(f"Timeout waiting for job listings on page {page}")
            return ""
        except Exception as e:
            logger.error(f"Error retrieving page {page}: {e}")
            return ""

    async def _apply_filters(self, filters: Dict):
        """Apply search filters on the page."""
        try:
            # Example filter applications - adjust based on actual Shufti UI
            if 'keyword' in filters:
                keyword_input = self.driver.find_element(By.NAME, "keyword")
                keyword_input.clear()
                keyword_input.send_keys(filters['keyword'])

            if 'category' in filters:
                category_select = self.driver.find_element(By.NAME, "category")
                category_select.send_keys(filters['category'])

            if 'location' in filters:
                location_input = self.driver.find_element(By.NAME, "location")
                location_input.clear()
                location_input.send_keys(filters['location'])

            # Submit the form or trigger search
            search_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            search_button.click()

            # Wait for results to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "job-card"))
            )

        except NoSuchElementException as e:
            logger.warning(f"Filter element not found: {e}")
        except Exception as e:
            logger.error(f"Error applying filters: {e}")

    async def get_job_details(self, job_url: str) -> str:
        """
        Get detailed job information from job detail page.

        Args:
            job_url: URL of the job detail page

        Returns:
            HTML content of the job detail page
        """
        await self._rate_limit()

        try:
            if not self.driver:
                self.driver = self._setup_driver()

            # Navigate to job detail page
            full_url = urljoin(self.base_url, job_url)
            self.driver.get(full_url)

            # Wait for job details to load
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "job-detail")))

            html_content = self.driver.page_source
            logger.info(f"Successfully retrieved job details from {job_url}")

            return html_content

        except TimeoutException:
            logger.warning(f"Timeout waiting for job details: {job_url}")
            return ""
        except Exception as e:
            logger.error(f"Error retrieving job details {job_url}: {e}")
            return ""

    async def scrape_all_jobs(self, max_pages: int = 5, filters: Dict = None) -> List[Dict]:
        """
        Scrape all available jobs across multiple pages.

        Args:
            max_pages: Maximum number of pages to scrape
            filters: Filters to apply to job search

        Returns:
            List of job dictionaries with basic information
        """
        all_jobs = []

        try:
            for page in range(1, max_pages + 1):
                logger.info(f"Scraping page {page}/{max_pages}")

                html_content = await self.get_job_listings_page(page, filters)
                if not html_content:
                    logger.warning(f"No content found for page {page}, stopping")
                    break

                # Parse job listings from the page
                from modules.crawler.parser import ShuftiParser
                parser = ShuftiParser()
                page_jobs = parser.parse_job_listings(html_content)

                if not page_jobs:
                    logger.info(f"No jobs found on page {page}, stopping")
                    break

                all_jobs.extend(page_jobs)
                logger.info(f"Found {len(page_jobs)} jobs on page {page}")

                # Extra delay between pages
                await asyncio.sleep(random.uniform(2, 4))

            logger.info(f"Total jobs scraped: {len(all_jobs)}")
            return all_jobs

        except Exception as e:
            logger.error(f"Error during bulk scraping: {e}")
            return all_jobs

    async def scrape_job_with_details(self, job_basic_info: Dict) -> Optional[Dict]:
        """
        Scrape complete job information including details page.

        Args:
            job_basic_info: Basic job info from listings page

        Returns:
            Complete job information dictionary
        """
        try:
            job_url = job_basic_info.get('url')
            if not job_url:
                logger.warning("No URL found in job basic info")
                return None

            # Get detailed job information
            detail_html = await self.get_job_details(job_url)
            if not detail_html:
                return job_basic_info

            # Parse detailed information
            from modules.crawler.parser import ShuftiParser
            parser = ShuftiParser()
            detailed_info = parser.parse_job_details(detail_html)

            # Merge basic and detailed information
            complete_job = {**job_basic_info, **detailed_info}

            return complete_job

        except Exception as e:
            logger.error(f"Error scraping job details: {e}")
            return job_basic_info

    def close(self):
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.info("Browser driver closed")
            except Exception as e:
                logger.error(f"Error closing driver: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class JobSearchFilter:
    """Helper class for building job search filters."""

    def __init__(self):
        self.filters = {}

    def keyword(self, keyword: str):
        """Add keyword filter."""
        self.filters['keyword'] = keyword
        return self

    def category(self, category: str):
        """Add category filter."""
        self.filters['category'] = category
        return self

    def location(self, location: str):
        """Add location filter."""
        self.filters['location'] = location
        return self

    def salary_min(self, amount: int):
        """Add minimum salary filter."""
        self.filters['salary_min'] = amount
        return self

    def work_type(self, work_type: str):
        """Add work type filter (remote, onsite, hybrid)."""
        self.filters['work_type'] = work_type
        return self

    def build(self) -> Dict:
        """Build the filters dictionary."""
        return self.filters.copy()


# Example usage functions
async def example_basic_scraping():
    """Example of basic job scraping."""
    async with ShuftiScraper() as scraper:
        # Scrape first 3 pages
        jobs = await scraper.scrape_all_jobs(max_pages=3)

        for job in jobs[:5]:  # Show first 5 jobs
            print(f"Job: {job.get('title', 'N/A')}")
            print(f"Company: {job.get('company', 'N/A')}")
            print(f"URL: {job.get('url', 'N/A')}")
            print("-" * 50)


async def example_filtered_scraping():
    """Example of filtered job scraping."""
    filters = (JobSearchFilter()
               .keyword("Python")
               .work_type("remote")
               .build())

    async with ShuftiScraper() as scraper:
        jobs = await scraper.scrape_all_jobs(max_pages=2, filters=filters)
        print(f"Found {len(jobs)} Python remote jobs")


if __name__ == "__main__":
    # Run example
    asyncio.run(example_basic_scraping())