#!/usr/bin/env python3
"""
Test suite for crawler module (scraper and parser)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

from modules.crawler.scraper import JobScraper
from modules.crawler.parser import JobParser
from config.settings import Settings
from utils.http_client import HTTPClient


class TestJobScraper:
    """Test cases for JobScraper"""

    @pytest.fixture
    def mock_http_client(self):
        """Mock HTTP client"""
        client = Mock(spec=HTTPClient)
        client.get = AsyncMock()
        client.post = AsyncMock()
        return client

    @pytest.fixture
    def scraper(self, mock_http_client):
        """Create scraper instance with mocked dependencies"""
        with patch('modules.crawler.scraper.HTTPClient', return_value=mock_http_client):
            return JobScraper()

    @pytest.mark.asyncio
    async def test_initialization(self, scraper):
        """Test scraper initialization"""
        assert scraper is not None
        assert hasattr(scraper, 'http_client')
        assert hasattr(scraper, 'logger')
        assert hasattr(scraper, 'base_url')

    @pytest.mark.asyncio
    async def test_get_job_listings_success(self, scraper, mock_http_client):
        """Test successful job listings retrieval"""
        # Mock response
        mock_response = {
            'status': 200,
            'content': '''
            <div class="job-list">
                <div class="job-item" data-job-id="123">
                    <h3>Test Job 1</h3>
                    <span class="price">¥1000</span>
                    <div class="description">Test description</div>
                </div>
                <div class="job-item" data-job-id="456">
                    <h3>Test Job 2</h3>
                    <span class="price">¥2000</span>
                    <div class="description">Another test</div>
                </div>
            </div>
            '''
        }
        mock_http_client.get.return_value = mock_response

        # Test
        jobs = await scraper.get_job_listings()

        # Assertions
        assert isinstance(jobs, list)
        assert len(jobs) > 0
        mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_listings_empty(self, scraper, mock_http_client):
        """Test empty job listings response"""
        mock_response = {
            'status': 200,
            'content': '<div class="job-list"></div>'
        }
        mock_http_client.get.return_value = mock_response

        jobs = await scraper.get_job_listings()

        assert isinstance(jobs, list)
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_get_job_listings_http_error(self, scraper, mock_http_client):
        """Test HTTP error handling"""
        mock_http_client.get.return_value = {'status': 500, 'content': 'Server Error'}

        jobs = await scraper.get_job_listings()

        assert jobs == []

    @pytest.mark.asyncio
    async def test_get_job_details_success(self, scraper, mock_http_client):
        """Test successful job details retrieval"""
        job_id = "123"
        mock_response = {
            'status': 200,
            'content': '''
            <div class="job-detail">
                <h1>Detailed Job Title</h1>
                <div class="job-price">¥1500</div>
                <div class="job-description">Detailed description here</div>
                <div class="job-requirements">Requirements list</div>
                <div class="job-location">Tokyo</div>
                <div class="job-deadline">2024-12-31</div>
            </div>
            '''
        }
        mock_http_client.get.return_value = mock_response

        details = await scraper.get_job_details(job_id)

        assert details is not None
        assert isinstance(details, dict)
        mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_details_not_found(self, scraper, mock_http_client):
        """Test job details not found"""
        mock_http_client.get.return_value = {'status': 404, 'content': 'Not Found'}

        details = await scraper.get_job_details("nonexistent")

        assert details is None

    @pytest.mark.asyncio
    async def test_search_jobs_with_filters(self, scraper, mock_http_client):
        """Test job search with filters"""
        filters = {
            'category': 'programming',
            'location': 'tokyo',
            'min_price': 1000,
            'max_price': 5000
        }

        mock_response = {
            'status': 200,
            'content': '<div class="job-list"><div class="job-item">Filtered job</div></div>'
        }
        mock_http_client.get.return_value = mock_response

        jobs = await scraper.search_jobs(filters)

        assert isinstance(jobs, list)
        # Check that filters were applied in the request
        call_args = mock_http_client.get.call_args
        assert 'params' in call_args.kwargs or len(call_args.args) > 1

    @pytest.mark.asyncio
    async def test_rate_limiting(self, scraper, mock_http_client):
        """Test rate limiting functionality"""
        mock_http_client.get.return_value = {'status': 200, 'content': '<div></div>'}

        # Make multiple rapid requests
        start_time = datetime.now()

        await scraper.get_job_listings()
        await scraper.get_job_listings()

        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()

        # Should have some delay due to rate limiting
        assert elapsed >= 0.5  # Minimum expected delay


class TestJobParser:
    """Test cases for JobParser"""

    @pytest.fixture
    def parser(self):
        """Create parser instance"""
        return JobParser()

    def test_parse_job_listing_complete(self, parser):
        """Test parsing complete job listing"""
        html = '''
        <div class="job-item" data-job-id="123">
            <h3 class="job-title">Web Developer Position</h3>
            <span class="job-price">¥3000</span>
            <div class="job-description">Looking for experienced developer</div>
            <div class="job-category">Programming</div>
            <div class="job-location">Tokyo, Japan</div>
            <div class="job-deadline">2024-12-31</div>
            <div class="job-difficulty">Medium</div>
            <a href="/jobs/123" class="job-link">View Details</a>
        </div>
        '''

        result = parser.parse_job_listing(html)

        assert result is not None
        assert result['id'] == '123'
        assert result['title'] == 'Web Developer Position'
        assert result['price'] == 3000
        assert result['description'] == 'Looking for experienced developer'
        assert result['category'] == 'Programming'
        assert result['location'] == 'Tokyo, Japan'
        assert result['url'] == '/jobs/123'

    def test_parse_job_listing_minimal(self, parser):
        """Test parsing minimal job listing"""
        html = '''
        <div class="job-item" data-job-id="456">
            <h3>Simple Job</h3>
            <span class="job-price">¥1000</span>
        </div>
        '''

        result = parser.parse_job_listing(html)

        assert result is not None
        assert result['id'] == '456'
        assert result['title'] == 'Simple Job'
        assert result['price'] == 1000

    def test_parse_job_listing_invalid(self, parser):
        """Test parsing invalid HTML"""
        html = '<div>No job data here</div>'

        result = parser.parse_job_listing(html)

        assert result is None

    def test_parse_job_details_complete(self, parser):
        """Test parsing complete job details"""
        html = '''
        <div class="job-detail">
            <h1 class="job-title">Senior Developer Role</h1>
            <div class="job-price">¥5000</div>
            <div class="job-description">
                <p>We are looking for a senior developer with:</p>
                <ul>
                    <li>5+ years experience</li>
                    <li>Python expertise</li>
                    <li>Team leadership skills</li>
                </ul>
            </div>
            <div class="job-requirements">
                <h3>Requirements:</h3>
                <p>Bachelor's degree required</p>
            </div>
            <div class="job-location">Shibuya, Tokyo</div>
            <div class="job-deadline">2024-12-25</div>
            <div class="job-category">Technology</div>
            <div class="client-info">
                <span class="client-name">Tech Corp</span>
                <span class="client-rating">4.8/5</span>
            </div>
        </div>
        '''

        result = parser.parse_job_details(html)

        assert result is not None
        assert result['title'] == 'Senior Developer Role'
        assert result['price'] == 5000
        assert 'senior developer' in result['description'].lower()
        assert 'requirements' in result
        assert result['location'] == 'Shibuya, Tokyo'
        assert result['category'] == 'Technology'
        assert 'client_info' in result

    def test_parse_price_variations(self, parser):
        """Test parsing different price formats"""
        test_cases = [
            ('¥1000', 1000),
            ('¥1,000', 1000),
            ('¥10,000', 10000),
            ('1000円', 1000),
            ('¥1000-2000', 1000),  # Should take minimum
            ('時給¥1500', 1500),
            ('No price', 0)
        ]

        for price_text, expected in test_cases:
            result = parser.extract_price(price_text)
            assert result == expected, f"Failed for {price_text}: expected {expected}, got {result}"

    def test_parse_date_formats(self, parser):
        """Test parsing different date formats"""
        test_cases = [
            ('2024-12-31', '2024-12-31'),
            ('12/31/2024', '2024-12-31'),
            ('2024年12月31日', '2024-12-31'),
            ('来週末', None),  # Relative dates should return None for now
            ('', None)
        ]

        for date_text, expected in test_cases:
            result = parser.parse_date(date_text)
            if expected:
                assert result == expected
            else:
                assert result is None

    def test_extract_job_ids(self, parser):
        """Test extracting job IDs from HTML"""
        html = '''
        <div class="job-list">
            <div class="job-item" data-job-id="123">Job 1</div>
            <div class="job-item" data-job-id="456">Job 2</div>
            <div class="job-item" data-job-id="789">Job 3</div>
        </div>
        '''

        ids = parser.extract_job_ids(html)

        assert isinstance(ids, list)
        assert len(ids) == 3
        assert '123' in ids
        assert '456' in ids
        assert '789' in ids

    def test_sanitize_text(self, parser):
        """Test text sanitization"""
        test_cases = [
            ('  Normal text  ', 'Normal text'),
            ('Text\nwith\nnewlines', 'Text with newlines'),
            ('Text\twith\ttabs', 'Text with tabs'),
            ('Multiple   spaces', 'Multiple spaces'),
            ('<script>alert("hack")</script>Text', 'Text'),  # HTML should be stripped
        ]

        for input_text, expected in test_cases:
            result = parser.sanitize_text(input_text)
            assert result == expected

    def test_parse_multiple_jobs(self, parser):
        """Test parsing multiple jobs from listings page"""
        html = '''
        <div class="job-list">
            <div class="job-item" data-job-id="1">
                <h3>Job 1</h3><span class="job-price">¥1000</span>
            </div>
            <div class="job-item" data-job-id="2">
                <h3>Job 2</h3><span class="job-price">¥2000</span>
            </div>
            <div class="job-item" data-job-id="3">
                <h3>Job 3</h3><span class="job-price">¥3000</span>
            </div>
        </div>
        '''

        jobs = parser.parse_job_listings(html)

        assert isinstance(jobs, list)
        assert len(jobs) == 3
        assert all('id' in job and 'title' in job for job in jobs)
        assert jobs[0]['price'] == 1000
        assert jobs[1]['price'] == 2000
        assert jobs[2]['price'] == 3000


# Integration tests
class TestCrawlerIntegration:
    """Integration tests for scraper and parser working together"""

    @pytest.mark.asyncio
    async def test_scrape_and_parse_workflow(self):
        """Test complete scrape and parse workflow"""
        with patch('modules.crawler.scraper.HTTPClient') as mock_client_class:
            # Setup mock
            mock_client = Mock()
            mock_client.get = AsyncMock(return_value={
                'status': 200,
                'content': '''
                <div class="job-list">
                    <div class="job-item" data-job-id="test123">
                        <h3>Integration Test Job</h3>
                        <span class="job-price">¥2500</span>
                        <div class="job-description">Test integration</div>
                    </div>
                </div>
                '''
            })
            mock_client_class.return_value = mock_client

            # Create scraper and get jobs
            scraper = JobScraper()
            jobs = await scraper.get_job_listings()

            # Verify results
            assert len(jobs) == 1
            job = jobs[0]
            assert job['id'] == 'test123'
            assert job['title'] == 'Integration Test Job'
            assert job['price'] == 2500


# Pytest configuration and fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_crawler.py -v
    pytest.main([__file__, "-v"])