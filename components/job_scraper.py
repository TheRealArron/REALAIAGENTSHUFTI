import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from config.constants import BASE_URL, LOGIN_URL
from utils.logger import append_log
from components.job_filter import filter_jobs  # MCP-based import

class JobScraper:
    def __init__(self, email, password, max_pages=2, delay=5):
        self.email = email
        self.password = password
        self.max_pages = max_pages
        self.delay = delay

    async def login(self, page):
        try:
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            await page.fill("#username", self.email)
            await page.fill("#password", self.password)
            await page.wait_for_selector("#submit:not([disabled])", timeout=10000)
            await page.click("#submit")
            await page.wait_for_load_state("load", timeout=100_
