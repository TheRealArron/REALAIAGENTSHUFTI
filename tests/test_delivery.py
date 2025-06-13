#!/usr/bin/env python3
"""
Test suite for delivery module (task_processor and submission)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json
import tempfile
import os

from modules.delivery.task_processor import TaskProcessor
from modules.delivery.submission import DeliverySubmitter
from modules.llm.ai_service import AIService
from utils.http_client import HTTPClient
from config.settings import Settings


class TestTaskProcessor:
    """Test cases for TaskProcessor"""

    @pytest.fixture
    def mock_ai_service(self):
        """Mock AI service"""
        service = Mock(spec=AIService)
        service.analyze_task_requirements = AsyncMock()
        service.generate_task_solution = AsyncMock()
        service.review_task_quality = AsyncMock()
        service.translate_text = AsyncMock()
        return service

    @pytest.fixture
    def mock_http_client(self):
        """Mock HTTP client"""
        client = Mock(spec=HTTPClient)
        client.get = AsyncMock()
        client.post = AsyncMock()
        client.download_file = AsyncMock()
        return client

    @pytest.fixture
    def task_processor(self, mock_ai_service, mock_http_client):
        """Create task processor with mocked dependencies"""
        with patch('modules.delivery.task_processor.AIService', return_value=mock_ai_service), \
                patch('modules.delivery.task_processor.HTTPClient', return_value=mock_http_client):
            return TaskProcessor()

    @pytest.fixture
    def sample_task(self):
        """Sample task data for testing"""
        return {
            'id': 'task123',
            'job_id': 'job456',
            'title': 'Data Entry Task',
            'description': 'Enter customer data from PDF files into spreadsheet',
            'requirements': 'Accuracy required, Japanese text processing',
            'type': 'data_entry',
            'deadline': '2024-12-31T23:59:59',
            'priority': 'medium',
            'files': [
                {'url': 'https://example.com/file1.pdf', 'name': 'customers1.pdf'},
                {'url': 'https://example.com/file2.pdf', 'name': 'customers2.pdf'}
            ],
            'deliverables': ['completed_spreadsheet.xlsx', 'summary_report.txt']
        }

    @pytest.fixture
    def sample_coding_task(self):
        """Sample coding task for testing"""
        return {
            'id': 'task789',
            'job_id': 'job101',
            'title': 'Python Script Development',
            'description': 'Create a Python script to process CSV files and generate reports',
            'requirements': 'Python 3.8+, pandas, matplotlib for charts',
            'type': 'programming',
            'deadline': '2024-12-25T18:00:00',
            'priority': 'high',
            'specifications': {
                'input_format': 'CSV',
                'output_format': 'PDF report with charts',
                'libraries': ['pandas', 'matplotlib', 'reportlab']
            }
        }

    @pytest.mark.asyncio
    async def test_analyze_task_requirements_success(self, task_processor, mock_ai_service, sample_task):
        """Test successful task requirements analysis"""
        mock_ai_service.analyze_task_requirements.return_value = {
            'task_type': 'data_entry',
            'complexity': 'medium',
            'estimated_time': 4.5,
            'required_skills': ['Data entry', 'Japanese reading', 'Excel'],
            'tools_needed': ['PDF reader', 'Excel/LibreOffice'],
            'key_steps': [
                'Download and review PDF files',
                'Extract customer information',
                'Enter data into spreadsheet',
                'Validate accuracy',
                'Generate summary report'
            ],
            'potential_challenges': ['Japanese text recognition', 'Data validation']
        }

        analysis = await task_processor.analyze_task_requirements(sample_task)

        assert analysis is not None
        assert analysis['task_type'] == 'data_entry'
        assert analysis['complexity'] == 'medium'
        assert analysis['estimated_time'] == 4.5
        assert 'required_skills' in analysis
        assert len(analysis['key_steps']) == 5
        mock_ai_service.analyze_task_requirements.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_data_entry_task(self, task_processor, mock_ai_service, mock_http_client, sample_task):
        """Test processing data entry task"""
        # Mock file downloads
        mock_http_client.download_file.side_effect = [
            {'success': True, 'file_path': '/tmp/file1.pdf'},
            {'success': True, 'file_path': '/tmp/file2.pdf'}
        ]

        # Mock AI analysis
        mock_ai_service.analyze_task_requirements.return_value = {
            'task_type': 'data_entry',
            'key_steps': ['Download files', 'Extract data', 'Create spreadsheet']
        }

        # Mock AI solution generation
        mock_ai_service.generate_task_solution.return_value = {
            'solution': 'Processed data entry task',
            'output_files': ['completed_spreadsheet.xlsx'],
            'summary': 'Successfully processed 100 customer records'
        }

        result = await task_processor.process_task(sample_task)

        assert result is not None
        assert result['success'] == True
        assert 'output_files' in result
        assert 'summary' in result
        assert mock_http_client.download_file.call_count == 2

    @pytest.mark.asyncio
    async def test_process_programming_task(self, task_processor, mock_ai_service, sample_coding_task):
        """Test processing programming task"""
        mock_ai_service.analyze_task_requirements.return_value = {
            'task_type': 'programming',
            'complexity': 'medium',
            'key_steps': ['Analyze requirements', 'Write code', 'Test solution']
        }

        mock_ai_service.generate_task_solution.return_value = {
            'solution': '''
import pandas as pd
import matplotlib.pyplot as plt

def process_csv_data(input_file):
    df = pd.read_csv(input_file)
    # Process data and generate charts
    return df

if __name__ == "__main__":
    process_csv_data("input.csv")
            ''',
            'output_files': ['data_processor.py', 'sample_report.pdf'],
            'summary': 'Created Python script with data processing and visualization'
        }

        result = await task_processor.process_task(sample_coding_task)

        assert result is not None
        assert result['success'] == True
        assert 'import pandas' in result['solution']
        assert 'data_processor.py' in result['output_files']

    @pytest.mark.asyncio
    async def test_download_task_files_success(self, task_processor, mock_http_client, sample_task):
        """Test successful file downloads"""
        mock_http_client.download_file.side_effect = [
            {'success': True, 'file_path': '/tmp/file1.pdf', 'size': 1024},
            {'success': True, 'file_path': '/tmp/file2.pdf', 'size': 2048}
        ]

        downloads = await task_processor.download_task_files(sample_task['files'])

        assert len(downloads) == 2
        assert all(d['success'] for d in downloads)
        assert downloads[0]['file_path'] == '/tmp/file1.pdf'
        assert downloads[1]['size'] == 2048

    @pytest.mark.asyncio
    async def test_download_task_files_partial_failure(self, task_processor, mock_http_client, sample_task):
        """Test file downloads with partial failure"""
        mock_http_client.download_file.side_effect = [
            {'success': True, 'file_path': '/tmp/file1.pdf'},
            {'success': False, 'error': 'File not found'}
        ]

        downloads = await task_processor.download_task_files(sample_task['files'])

        assert len(downloads) == 2
        assert downloads[0]['success'] == True
        assert downloads[1]['success'] == False
        assert 'error' in downloads[1]

    @pytest.mark.asyncio
    async def test_validate_task_completion_success(self, task_processor, mock_ai_service):
        """Test successful task completion validation"""
        task_result = {
            'output_files': ['result.xlsx', 'summary.txt'],
            'summary': 'Task completed successfully',
            'solution': 'Detailed solution content'
        }

        requirements = {
            'deliverables': ['result.xlsx', 'summary.txt'],
            'quality_criteria': ['Accuracy > 95%', 'Complete data']
        }

        mock_ai_service.review_task_quality.return_value = {
            'quality_score': 0.92,
            'meets_requirements': True,
            'issues': [],
            'recommendations': ['Consider adding more detail to summary']
        }

        validation = await task_processor.validate_task_completion(task_result, requirements)

        assert validation is not None
        assert validation['is_valid'] == True
        assert validation['quality_score'] == 0.92
        assert len(validation['issues']) == 0

    @pytest.mark.asyncio
    async def test_validate_task_completion_failure(self, task_processor, mock_ai_service):
        """Test task completion validation failure"""
        task_result = {
            'output_files': ['result.xlsx'],  # Missing summary.txt
            'summary': 'Incomplete task',
            'solution': 'Partial solution'
        }

        requirements = {
            'deliverables': ['result.xlsx', 'summary.txt'],
            'quality_criteria': ['Accuracy > 95%']
        }

        mock_ai_service.review_task_quality.return_value = {
            'quality_score': 0.65,
            'meets_requirements': False,
            'issues': ['Missing summary.txt file', 'Low accuracy score'],
            'recommendations': ['Complete all deliverables', 'Improve data accuracy']
        }

        validation = await task_processor.validate_task_completion(task_result, requirements)

        assert validation is not None
        assert validation['is_valid'] == False
        assert len(validation['issues']) == 2
        assert 'Missing summary.txt' in validation['issues'][0]

    @pytest.mark.asyncio
    async def test_estimate_task_duration(self, task_processor, mock_ai_service, sample_task):
        """Test task duration estimation"""
        mock_ai_service.analyze_task_requirements.return_value = {
            'estimated_time': 3.5,
            'complexity': 'medium',
            'factors': {
                'file_count': 2,
                'data_volume': 'medium',
                'language_complexity': 'japanese'
            }
        }

        duration = await task_processor.estimate_task_duration(sample_task)

        assert duration == 3.5
        mock_ai_service.analyze_task_requirements.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_task_progress(self, task_processor):
        """Test task progress tracking"""
        task_id = 'task123'

        # Start tracking
        task_processor.start_task_tracking(task_id)

        # Update progress
        await task_processor.update_task_progress(task_id, 25, 'Downloaded files')
        await task_processor.update_task_progress(task_id, 50, 'Processing data')
        await task_processor.update_task_progress(task_id, 100, 'Task completed')

        # Get progress
        progress = task_processor.get_task_progress(task_id)

        assert progress is not None
        assert progress['percentage'] == 100
        assert progress['status'] == 'Task completed'
        assert len(progress['history']) == 3


class TestDeliverySubmitter:
    """Test cases for DeliverySubmitter"""

    @pytest.fixture
    def mock_http_client(self):
        """Mock HTTP client"""
        client = Mock(spec=HTTPClient)
        client.post = AsyncMock()
        client.put = AsyncMock()
        client.upload_file = AsyncMock()
        return client

    @pytest.fixture
    def mock_ai_service(self):
        """Mock AI service"""
        service = Mock(spec=AIService)
        service.generate_delivery_message = AsyncMock()
        service.translate_text = AsyncMock()
        return service

    @pytest.fixture
    def delivery_submitter(self, mock_http_client, mock_ai_service):
        """Create delivery submitter with mocked dependencies"""
        with patch('modules.delivery.submission.HTTPClient', return_value=mock_http_client), \
                patch('modules.delivery.submission.AIService', return_value=mock_ai_service):
            return DeliverySubmitter()

    @pytest.fixture
    def sample_delivery(self):
        """Sample delivery data for testing"""
        return {
            'task_id': 'task123',
            'job_id': 'job456',
            'files': [
                {'path': '/tmp/result.xlsx', 'name': 'completed_data.xlsx'},
                {'path': '/tmp/summary.txt', 'name': 'task_summary.txt'}
            ],
            'message': 'Task completed as requested. Please find attached files.',
            'completion_notes': 'All data has been validated and cross-checked for accuracy.'
        }

    @pytest.mark.asyncio
    async def test_prepare_delivery_package_success(self, delivery_submitter, mock_ai_service, sample_delivery):
        """Test successful delivery package preparation"""
        mock_ai_service.generate_delivery_message.return_value = {
            'message': 'Dear client, I have completed the task as requested...',
            'subject': 'Task Completion - Data Entry Project',
            'summary': 'Completed data entry for 100+ customer records with validation'
        }

        package = await delivery_submitter.prepare_delivery_package(sample_delivery)

        assert package is not None
        assert 'message' in package
        assert 'subject' in package
        assert 'files' in package
        assert len(package['files']) == 2
        mock_ai_service.generate_delivery_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_delivery_files_success(self, delivery_submitter, mock_http_client, sample_delivery):
        """Test successful file uploads"""
        mock_http_client.upload_file.side_effect = [
            {'success': True, 'file_url': 'https://shufti.jp/files/result.xlsx', 'file_id': 'file1'},
            {'success': True, 'file_url': 'https://shufti.jp/files/summary.txt', 'file_id': 'file2'}
        ]

        uploads = await delivery_submitter.upload_delivery_files(sample_delivery['files'])

        assert len(uploads) == 2
        assert all(u['success'] for u in uploads)
        assert uploads[0]['file_id'] == 'file1'
        assert uploads[1]['file_url'] == 'https://shufti.jp/files/summary.txt'

    @pytest.mark.asyncio
    async def test_upload_delivery_files_partial_failure(self, delivery_submitter, mock_http_client, sample_delivery):
        """Test file uploads with partial failure"""
        mock_http_client.upload_file.side_effect = [
            {'success': True, 'file_url': 'https://shufti.jp/files/result.xlsx'},
            {'success': False, 'error': 'File too large'}
        ]

        uploads = await delivery_submitter.upload_delivery_files(sample_delivery['files'])

        assert len(uploads) == 2
        assert uploads[0]['success'] == True
        assert uploads[1]['success'] == False
        assert 'error' in uploads[1]

    @pytest.mark.asyncio
    async def test_submit_delivery_success(self, delivery_submitter, mock_http_client, mock_ai_service,
                                           sample_delivery):
        """Test successful delivery submission"""
        # Mock file uploads
        mock_http_client.upload_file.return_value = {
            'success': True,
            'file_url': 'https://shufti.jp/files/result.xlsx'
        }

        # Mock delivery message generation
        mock_ai_service.generate_delivery_message.return_value = {
            'message': 'Task completed successfully',
            'subject': 'Delivery Complete'
        }

        # Mock submission response
        mock_http_client.post.return_value = {
            'status': 200,
            'content': '{"success": true, "delivery_id": "del123", "status": "submitted"}'
        }

        result = await delivery_submitter.submit_delivery(sample_delivery)

        assert result is not None
        assert result['success'] == True
        assert result['delivery_id'] == 'del123'
        assert result['status'] == 'submitted'

    @pytest.mark.asyncio
    async def test_submit_delivery_upload_failure(self, delivery_submitter, mock_http_client, mock_ai_service,
                                                  sample_delivery):
        """Test delivery submission with upload failure"""
        # Mock failed file upload
        mock_http_client.upload_file.return_value = {
            'success': False,
            'error': 'Upload failed'
        }

        mock_ai_service.generate_delivery_message.return_value = {
            'message': 'Test message',
            'subject': 'Test'
        }

        result = await delivery_submitter.submit_delivery(sample_delivery)

        assert result is not None
        assert result['success'] == False
        assert 'error' in result

    @pytest.mark.asyncio
    async def test_check_delivery_status_success(self, delivery_submitter, mock_http_client):
        """Test checking delivery status"""
        delivery_id = 'del123'
        mock_http_client.post.return_value = {
            'status': 200,
            'content': '''
            <div class="delivery-status">
                <span class="status">Accepted</span>
                <div class="client-feedback">Great work! Payment will be processed.</div>
                <div class="rating">5 stars</div>
                <div class="payment-status">Processing</div>
            </div>
            '''
        }

        status = await delivery_submitter.check_delivery_status(delivery_id)

        assert status is not None
        assert status['status'] == 'Accepted'
        assert 'client_feedback' in status
        assert status['rating'] == '5 stars'

    @pytest.mark.asyncio
    async def test_handle_delivery_feedback_positive(self, delivery_submitter, mock_ai_service):
        """Test handling positive delivery feedback"""
        feedback = {
            'delivery_id': 'del123',
            'rating': 5,
            'comment': 'Excellent work, exactly what we needed!',
            'status': 'accepted'
        }

        mock_ai_service.translate_text.return_value = 'Excellent work, exactly what we needed!'

        response = await delivery_submitter.handle_delivery_feedback(feedback)

        assert response is not None
        assert response['acknowledgment'] is not None
        assert 'thank' in response['acknowledgment'].lower()

    @pytest.mark.asyncio
    async def test_handle_delivery_feedback_revision_request(self, delivery_submitter, mock_ai_service):
        """Test handling revision request feedback"""
        feedback = {
            'delivery_id': 'del123',
            'rating': 3,
            'comment': 'Please add more detail to the summary section',
            'status': 'revision_requested',
            'revision_notes': 'Summary needs more technical details'
        }

        response = await delivery_submitter.handle_delivery_feedback(feedback)

        assert response is not None
        assert response['needs_revision'] == True
        assert 'revision_notes' in response

    @pytest.mark.asyncio
    async def test_generate_delivery_report(self, delivery_submitter):
        """Test delivery report generation"""
        delivery_data = {
            'task_id': 'task123',
            'job_id': 'job456',
            'start_time': '2024-01-15T10:00:00',
            'completion_time': '2024-01-15T14:30:00',
            'files_delivered': 2,
            'status': 'completed'
        }

        report = delivery_submitter.generate_delivery_report(delivery_data)

        assert report is not None
        assert 'task_id' in report
        assert 'duration_hours' in report
        assert report['duration_hours'] == 4.5
        assert report['files_count'] == 2

    @pytest.mark.asyncio
    async def test_validate_delivery_files(self, delivery_submitter):
        """Test delivery file validation"""
        files = [
            {'path': '/tmp/existing.txt', 'name': 'test.txt'},
            {'path': '/tmp/nonexistent.txt', 'name': 'missing.txt'}
        ]

        # Create temporary file for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write('test content')
            files[0]['path'] = tmp.name

        try:
            validation = delivery_submitter.validate_delivery_files(files)

            assert validation is not None
            assert len(validation['valid_files']) == 1
            assert len(validation['invalid_files']) == 1
            assert validation['valid_files'][0]['name'] == 'test.txt'
        finally:
            # Clean up
            os.unlink(tmp.name)


# Integration tests
class TestDeliveryIntegration:
    """Integration tests for task processing and delivery workflow"""

    @pytest.mark.asyncio
    async def test_complete_delivery_workflow(self):
        """Test complete workflow from task processing to delivery"""
        with patch('modules.delivery.task_processor.AIService') as mock_ai_processor, \
                patch('modules.delivery.submission.AIService') as mock_ai_submitter, \
                patch('modules.delivery.task_processor.HTTPClient') as mock_http_processor, \
                patch('modules.delivery.submission.HTTPClient') as mock_http_submitter:
            # Setup mocks for task processing
            mock_ai_processor.return_value.analyze_task_requirements = AsyncMock(return_value={
                'task_type': 'data_entry',
                'estimated_time': 2.0
            })

            mock_ai_processor.return_value.generate_task_solution = AsyncMock(return_value={
                'solution': 'Task completed',
                'output_files': ['result.xlsx'],
                'summary': 'Data entry completed successfully'
            })

            mock_http_processor.return_value.download_file = AsyncMock(return_value={
                'success': True,
                'file_path': '/tmp/input.pdf'
            })

            # Setup mocks for delivery
            mock_ai_submitter.return_value.generate_delivery_message = AsyncMock(return_value={
                'message': 'Task completed as requested',
                'subject': 'Delivery Complete'
            })

            mock_http_submitter.return_value.upload_file = AsyncMock(return_value={
                'success': True,
                'file_url': 'https://shufti.jp/files/result.xlsx'
            })

            mock_http_submitter.return_value.post = AsyncMock(return_value={
                'status': 200,
                'content': '{"success": true, "delivery_id": "del123"}'
            })

            # Test complete workflow
            processor = TaskProcessor()
            submitter = DeliverySubmitter()

            task = {
                'id': 'task123',
                'type': 'data_entry',
                'description': 'Process customer data',
                'files': [{'url': 'https://example.com/input.pdf', 'name': 'input.pdf'}]
            }

            # Step 1: Process task
            task_result = await processor.process_task(task)
            assert task_result['success'] == True

            # Step 2: Prepare delivery
            delivery_data = {
                'task_id': task['id'],
                'files': [{'path': '/tmp/result.xlsx', 'name': 'result.xlsx'}],
                'message': 'Task completed'
            }

            # Step 3: Submit delivery
            delivery_result = await submitter.submit_delivery(delivery_data)
            assert delivery_result['success'] == True
            assert 'delivery_id' in delivery_result


# Performance and stress tests
class TestDeliveryPerformance:
    """Performance tests for delivery components"""

    @pytest.mark.asyncio
    async def test_concurrent_task_processing(self):
        """Test processing multiple tasks concurrently"""
        with patch('modules.delivery.task_processor.AIService') as mock_ai:
            mock_ai.return_value.analyze_task_requirements = AsyncMock(return_value={
                'task_type': 'simple',
                'estimated_time': 1.0
            })
            mock_ai.return_value.generate_task_solution = AsyncMock(return_value={
                'solution': 'Completed',
                'output_files': ['result.txt']
            })

            processor = TaskProcessor()

            # Create multiple tasks
            tasks = [
                {'id': f'task{i}', 'type': 'simple', 'description': f'Task {i}'}
                for i in range(5)
            ]

            # Process concurrently
            results = await asyncio.gather(*[
                processor.process_task(task) for task in tasks
            ])

            assert len(results) == 5
            assert all(result['success'] for result in results)


# Pytest configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_delivery.py -v
    pytest.main([__file__, "-v"])