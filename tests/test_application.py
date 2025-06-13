#!/usr/bin/env python3
"""
Test suite for application module (job_matcher and applicator)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

from modules.application.job_matcher import JobMatcher
from modules.application.applicator import JobApplicator
from modules.llm.ai_service import AIService
from utils.http_client import HTTPClient
from config.settings import Settings


class TestJobMatcher:
    """Test cases for JobMatcher"""

    @pytest.fixture
    def mock_ai_service(self):
        """Mock AI service"""
        service = Mock(spec=AIService)
        service.analyze_job_match = AsyncMock()
        service.extract_requirements = AsyncMock()
        service.generate_skills_assessment = AsyncMock()
        return service

    @pytest.fixture
    def job_matcher(self, mock_ai_service):
        """Create job matcher with mocked dependencies"""
        with patch('modules.application.job_matcher.AIService', return_value=mock_ai_service):
            return JobMatcher()

    @pytest.fixture
    def sample_job(self):
        """Sample job data for testing"""
        return {
            'id': 'job123',
            'title': 'Python Developer',
            'description': 'Looking for Python developer with Flask experience',
            'requirements': 'Python, Flask, REST API, 2+ years experience',
            'price': 3000,
            'category': 'Programming',
            'location': 'Tokyo',
            'deadline': '2024-12-31',
            'difficulty': 'Medium'
        }

    @pytest.fixture
    def sample_profile(self):
        """Sample user profile for testing"""
        return {
            'skills': ['Python', 'Flask', 'Django', 'REST API', 'PostgreSQL'],
            'experience_years': 3,
            'categories': ['Programming', 'Web Development'],
            'location_preference': ['Tokyo', 'Remote'],
            'min_price': 2000,
            'max_workload': 40,
            'languages': ['Japanese', 'English']
        }

    @pytest.mark.asyncio
    async def test_analyze_job_compatibility_high_match(self, job_matcher, mock_ai_service, sample_job, sample_profile):
        """Test high compatibility job analysis"""
        # Mock AI response for high match
        mock_ai_service.analyze_job_match.return_value = {
            'compatibility_score': 0.85,
            'skill_match': 0.90,
            'experience_match': 0.80,
            'missing_skills': [],
            'confidence': 0.85,
            'reasoning': 'Strong match with required skills'
        }

        result = await job_matcher.analyze_job_compatibility(sample_job, sample_profile)

        assert result is not None
        assert result['compatibility_score'] == 0.85
        assert result['skill_match'] == 0.90
        assert result['is_good_match'] == True
        mock_ai_service.analyze_job_match.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_job_compatibility_low_match(self, job_matcher, mock_ai_service, sample_job, sample_profile):
        """Test low compatibility job analysis"""
        # Mock AI response for low match
        mock_ai_service.analyze_job_match.return_value = {
            'compatibility_score': 0.35,
            'skill_match': 0.40,
            'experience_match': 0.30,
            'missing_skills': ['React', 'Node.js'],
            'confidence': 0.75,
            'reasoning': 'Missing key frontend skills'
        }

        result = await job_matcher.analyze_job_compatibility(sample_job, sample_profile)

        assert result is not None
        assert result['compatibility_score'] == 0.35
        assert result['is_good_match'] == False
        assert 'React' in result['missing_skills']

    @pytest.mark.asyncio
    async def test_filter_jobs_by_criteria_price(self, job_matcher, sample_profile):
        """Test filtering jobs by price criteria"""
        jobs = [
            {'id': '1', 'price': 1500, 'title': 'Low Pay Job'},
            {'id': '2', 'price': 2500, 'title': 'Good Pay Job'},
            {'id': '3', 'price': 4000, 'title': 'High Pay Job'},
        ]

        filtered = await job_matcher.filter_jobs_by_criteria(jobs, sample_profile)

        # Should filter out jobs below min_price (2000)
        assert len(filtered) == 2
        assert all(job['price'] >= 2000 for job in filtered)
        assert filtered[0]['id'] == '2'
        assert filtered[1]['id'] == '3'

    @pytest.mark.asyncio
    async def test_filter_jobs_by_criteria_category(self, job_matcher, sample_profile):
        """Test filtering jobs by category"""
        jobs = [
            {'id': '1', 'category': 'Programming', 'price': 3000, 'title': 'Dev Job'},
            {'id': '2', 'category': 'Design', 'price': 3000, 'title': 'Design Job'},
            {'id': '3', 'category': 'Web Development', 'price': 3000, 'title': 'Web Job'},
        ]

        filtered = await job_matcher.filter_jobs_by_criteria(jobs, sample_profile)

        # Should only include jobs in preferred categories
        assert len(filtered) == 2
        categories = [job['category'] for job in filtered]
        assert 'Programming' in categories
        assert 'Web Development' in categories
        assert 'Design' not in categories

    @pytest.mark.asyncio
    async def test_filter_jobs_by_criteria_location(self, job_matcher, sample_profile):
        """Test filtering jobs by location"""
        jobs = [
            {'id': '1', 'location': 'Tokyo', 'price': 3000, 'category': 'Programming'},
            {'id': '2', 'location': 'Osaka', 'price': 3000, 'category': 'Programming'},
            {'id': '3', 'location': 'Remote', 'price': 3000, 'category': 'Programming'},
        ]

        filtered = await job_matcher.filter_jobs_by_criteria(jobs, sample_profile)

        # Should include Tokyo and Remote jobs
        assert len(filtered) == 2
        locations = [job['location'] for job in filtered]
        assert 'Tokyo' in locations
        assert 'Remote' in locations
        assert 'Osaka' not in locations

    @pytest.mark.asyncio
    async def test_rank_jobs_by_match_score(self, job_matcher, mock_ai_service):
        """Test ranking jobs by match score"""
        jobs = [
            {'id': '1', 'title': 'Job 1'},
            {'id': '2', 'title': 'Job 2'},
            {'id': '3', 'title': 'Job 3'}
        ]

        # Mock different compatibility scores
        mock_ai_service.analyze_job_match.side_effect = [
            {'compatibility_score': 0.60, 'is_good_match': True},
            {'compatibility_score': 0.85, 'is_good_match': True},
            {'compatibility_score': 0.40, 'is_good_match': False}
        ]

        profile = {'skills': ['Python']}
        ranked = await job_matcher.rank_jobs_by_match_score(jobs, profile)

        # Should be sorted by compatibility score (highest first)
        assert len(ranked) == 3
        assert ranked[0]['compatibility_score'] == 0.85
        assert ranked[1]['compatibility_score'] == 0.60
        assert ranked[2]['compatibility_score'] == 0.40

    @pytest.mark.asyncio
    async def test_extract_job_requirements_success(self, job_matcher, mock_ai_service, sample_job):
        """Test extracting job requirements"""
        mock_ai_service.extract_requirements.return_value = {
            'technical_skills': ['Python', 'Flask', 'REST API'],
            'experience_level': 'Mid-level (2-4 years)',
            'soft_skills': ['Communication', 'Team work'],
            'education': 'Bachelor\'s degree preferred',
            'certifications': [],
            'must_have': ['Python', 'Flask'],
            'nice_to_have': ['Docker', 'AWS']
        }

        requirements = await job_matcher.extract_job_requirements(sample_job)

        assert requirements is not None
        assert 'technical_skills' in requirements
        assert 'Python' in requirements['technical_skills']
        assert 'Flask' in requirements['must_have']
        mock_ai_service.extract_requirements.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_skill_overlap(self, job_matcher):
        """Test skill overlap calculation"""
        user_skills = ['Python', 'Flask', 'Django', 'PostgreSQL', 'Redis']
        job_requirements = ['Python', 'Flask', 'REST API', 'MongoDB']

        overlap = job_matcher.calculate_skill_overlap(user_skills, job_requirements)

        assert overlap['overlap_count'] == 2  # Python, Flask
        assert overlap['overlap_percentage'] == 0.5  # 2/4 required skills
        assert 'Python' in overlap['matching_skills']
        assert 'Flask' in overlap['matching_skills']
        assert 'REST API' in overlap['missing_skills']

    @pytest.mark.asyncio
    async def test_find_best_matches_integration(self, job_matcher, mock_ai_service, sample_profile):
        """Test complete job matching workflow"""
        jobs = [
            {
                'id': '1', 'title': 'Python Dev', 'price': 3000,
                'category': 'Programming', 'location': 'Tokyo',
                'description': 'Python and Flask developer needed'
            },
            {
                'id': '2', 'title': 'Java Dev', 'price': 1500,  # Below min price
                'category': 'Programming', 'location': 'Tokyo',
                'description': 'Java developer needed'
            },
            {
                'id': '3', 'title': 'Design Work', 'price': 3000,
                'category': 'Design', 'location': 'Tokyo',  # Wrong category
                'description': 'UI/UX designer needed'
            }
        ]

        # Mock AI responses
        mock_ai_service.analyze_job_match.side_effect = [
            {'compatibility_score': 0.85, 'is_good_match': True},
            {'compatibility_score': 0.45, 'is_good_match': False}
        ]

        matches = await job_matcher.find_best_matches(jobs, sample_profile)

        # Should return only the good Python job (filtered by price and category)
        assert len(matches) == 1
        assert matches[0]['id'] == '1'
        assert matches[0]['compatibility_score'] == 0.85


class TestJobApplicator:
    """Test cases for JobApplicator"""

    @pytest.fixture
    def mock_http_client(self):
        """Mock HTTP client"""
        client = Mock(spec=HTTPClient)
        client.get = AsyncMock()
        client.post = AsyncMock()
        return client

    @pytest.fixture
    def mock_ai_service(self):
        """Mock AI service"""
        service = Mock(spec=AIService)
        service.generate_application_message = AsyncMock()
        service.translate_text = AsyncMock()
        return service

    @pytest.fixture
    def job_applicator(self, mock_http_client, mock_ai_service):
        """Create job applicator with mocked dependencies"""
        with patch('modules.application.applicator.HTTPClient', return_value=mock_http_client), \
                patch('modules.application.applicator.AIService', return_value=mock_ai_service):
            return JobApplicator()

    @pytest.fixture
    def sample_application_data(self):
        """Sample application data"""
        return {
            'job_id': 'job123',
            'job_title': 'Python Developer',
            'job_description': 'Looking for Python developer',
            'user_profile': {
                'name': 'Test User',
                'skills': ['Python', 'Flask'],
                'experience': '3 years of Python development'
            },
            'cover_message': 'I am interested in this position'
        }

    @pytest.mark.asyncio
    async def test_generate_application_message_success(self, job_applicator, mock_ai_service, sample_application_data):
        """Test successful application message generation"""
        mock_ai_service.generate_application_message.return_value = {
            'message': 'Dear hiring manager, I am very interested in the Python Developer position...',
            'subject': 'Application for Python Developer Position',
            'key_points': ['Python expertise', 'Flask experience', 'Team collaboration']
        }

        result = await job_applicator.generate_application_message(
            sample_application_data['job_title'],
            sample_application_data['job_description'],
            sample_application_data['user_profile']
        )

        assert result is not None
        assert 'message' in result
        assert 'subject' in result
        assert len(result['message']) > 50  # Should be substantial
        mock_ai_service.generate_application_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_application_success(self, job_applicator, mock_http_client, mock_ai_service,
                                              sample_application_data):
        """Test successful job application submission"""
        # Mock application message generation
        mock_ai_service.generate_application_message.return_value = {
            'message': 'Generated application message',
            'subject': 'Job Application'
        }

        # Mock successful HTTP response
        mock_http_client.post.return_value = {
            'status': 200,
            'content': '{"success": true, "application_id": "app123"}'
        }

        result = await job_applicator.submit_application(sample_application_data)

        assert result is not None
        assert result['success'] == True
        assert result['application_id'] == 'app123'
        mock_http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_application_http_error(self, job_applicator, mock_http_client, mock_ai_service,
                                                 sample_application_data):
        """Test application submission with HTTP error"""
        mock_ai_service.generate_application_message.return_value = {
            'message': 'Generated message',
            'subject': 'Application'
        }

        # Mock HTTP error
        mock_http_client.post.return_value = {
            'status': 400,
            'content': 'Bad Request'
        }

        result = await job_applicator.submit_application(sample_application_data)

        assert result is not None
        assert result['success'] == False
        assert 'error' in result

    @pytest.mark.asyncio
    async def test_check_application_status_success(self, job_applicator, mock_http_client):
        """Test checking application status"""
        application_id = "app123"
        mock_http_client.get.return_value = {
            'status': 200,
            'content': '''
            <div class="application-status">
                <span class="status">Under Review</span>
                <div class="status-details">Your application is being reviewed</div>
                <div class="last-updated">2024-01-15</div>
            </div>
            '''
        }

        status = await job_applicator.check_application_status(application_id)

        assert status is not None
        assert status['status'] == 'Under Review'
        assert 'last_updated' in status
        mock_http_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_application_status_not_found(self, job_applicator, mock_http_client):
        """Test checking status for non-existent application"""
        mock_http_client.get.return_value = {
            'status': 404,
            'content': 'Not Found'
        }

        status = await job_applicator.check_application_status("nonexistent")

        assert status is None

    @pytest.mark.asyncio
    async def test_validate_application_data_valid(self, job_applicator):
        """Test validation of valid application data"""
        valid_data = {
            'job_id': 'job123',
            'job_title': 'Developer',
            'job_description': 'Looking for developer',
            'user_profile': {
                'name': 'John Doe',
                'skills': ['Python'],
                'experience': '2 years'
            }
        }

        is_valid, errors = job_applicator.validate_application_data(valid_data)

        assert is_valid == True
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_application_data_missing_fields(self, job_applicator):
        """Test validation with missing required fields"""
        invalid_data = {
            'job_id': 'job123',
            # Missing job_title, job_description, user_profile
        }

        is_valid, errors = job_applicator.validate_application_data(invalid_data)

        assert is_valid == False
        assert len(errors) > 0
        assert any('job_title' in error for error in errors)

    @pytest.mark.asyncio
    async def test_format_application_message(self, job_applicator):
        """Test application message formatting"""
        template_data = {
            'job_title': 'Python Developer',
            'company_name': 'Tech Corp',
            'user_name': 'John Doe',
            'relevant_skills': ['Python', 'Flask'],
            'experience_years': 3
        }

        formatted = job_applicator.format_application_message(template_data)

        assert formatted is not None
        assert 'Python Developer' in formatted
        assert 'John Doe' in formatted
        assert 'Python' in formatted

    @pytest.mark.asyncio
    async def test_track_application_history(self, job_applicator):
        """Test application history tracking"""
        application_data = {
            'job_id': 'job123',
            'job_title': 'Developer',
            'application_id': 'app123',
            'status': 'submitted',
            'submitted_at': datetime.now().isoformat()
        }

        # Track application
        job_applicator.track_application(application_data)

        # Retrieve history
        history = job_applicator.get_application_history()

        assert len(history) == 1
        assert history[0]['job_id'] == 'job123'
        assert history[0]['application_id'] == 'app123'

    @pytest.mark.asyncio
    async def test_batch_application_submission(self, job_applicator, mock_ai_service, mock_http_client):
        """Test submitting multiple applications"""
        jobs = [
            {'id': 'job1', 'title': 'Python Dev 1', 'description': 'Python job 1'},
            {'id': 'job2', 'title': 'Python Dev 2', 'description': 'Python job 2'}
        ]

        user_profile = {
            'name': 'Test User',
            'skills': ['Python'],
            'experience': '2 years'
        }

        # Mock responses
        mock_ai_service.generate_application_message.return_value = {
            'message': 'Generated message',
            'subject': 'Application'
        }

        mock_http_client.post.return_value = {
            'status': 200,
            'content': '{"success": true, "application_id": "app123"}'
        }

        results = await job_applicator.submit_batch_applications(jobs, user_profile)

        assert len(results) == 2
        assert all(result['success'] for result in results)
        assert mock_http_client.post.call_count == 2


# Integration tests
class TestApplicationIntegration:
    """Integration tests for job matching and application workflow"""

    @pytest.mark.asyncio
    async def test_complete_application_workflow(self):
        """Test complete workflow from job matching to application"""
        with patch('modules.application.job_matcher.AIService') as mock_ai_matcher, \
                patch('modules.application.applicator.AIService') as mock_ai_applicator, \
                patch('modules.application.applicator.HTTPClient') as mock_http:
            # Setup mocks
            mock_ai_matcher.return_value.analyze_job_match = AsyncMock(return_value={
                'compatibility_score': 0.85,
                'is_good_match': True
            })

            mock_ai_applicator.return_value.generate_application_message = AsyncMock(return_value={
                'message': 'Application message',
                'subject': 'Job Application'
            })

            mock_http.return_value.post = AsyncMock(return_value={
                'status': 200,
                'content': '{"success": true, "application_id": "app123"}'
            })

            # Test workflow
            matcher = JobMatcher()
            applicator = JobApplicator()

            job = {
                'id': 'job123',
                'title': 'Python Developer',
                'description': 'Python development role',
                'price': 3000,
                'category': 'Programming',
                'location': 'Tokyo'
            }

            profile = {
                'skills': ['Python', 'Flask'],
                'experience_years': 3,
                'categories': ['Programming'],
                'location_preference': ['Tokyo'],
                'min_price': 2000
            }

            # Step 1: Match job
            compatibility = await matcher.analyze_job_compatibility(job, profile)
            assert compatibility['is_good_match'] == True

            # Step 2: Apply to job
            application_data = {
                'job_id': job['id'],
                'job_title': job['title'],
                'job_description': job['description'],
                'user_profile': profile
            }

            result = await applicator.submit_application(application_data)
            assert result['success'] == True
            assert 'application_id' in result


# Pytest configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_application.py -v
    pytest.main([__file__, "-v"])