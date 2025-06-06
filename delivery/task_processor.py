"""
Task processor module for handling job task execution and delivery
"""
import logging
import json
import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import os
import re

from ..llm.ai_service import AIService
from ...config.constants import TaskType, JobStatus, TASK_TEMPLATES
from ...utils.logger import get_logger
from ...utils.data_store import DataStore

logger = get_logger(__name__)


class TaskProcessor:
    """Processes and executes various types of job tasks"""

    def __init__(self, ai_service: AIService, data_store: DataStore):
        self.ai_service = ai_service
        self.data_store = data_store
        self.temp_dir = Path(tempfile.gettempdir()) / "shufti_agent"
        self.temp_dir.mkdir(exist_ok=True)

        # Task processors for different job types
        self.task_processors = {
            TaskType.TRANSLATION: self._process_translation_task,
            TaskType.WRITING: self._process_writing_task,
            TaskType.DATA_ENTRY: self._process_data_entry_task,
            TaskType.RESEARCH: self._process_research_task,
            TaskType.CONTENT_CREATION: self._process_content_creation_task,
            TaskType.TRANSCRIPTION: self._process_transcription_task,
            TaskType.PROOFREADING: self._process_proofreading_task,
            TaskType.WEB_SCRAPING: self._process_web_scraping_task,
            TaskType.IMAGE_PROCESSING: self._process_image_processing_task,
            TaskType.OTHER: self._process_general_task
        }

    async def process_job_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a job task based on its type and requirements

        Args:
            job_data: Job information including task details

        Returns:
            Task processing result with deliverables
        """
        try:
            job_id = job_data.get('id')
            task_type = self._determine_task_type(job_data)

            logger.info(f"Processing job {job_id} with task type: {task_type}")

            # Update job status to in progress
            await self._update_job_status(job_id, JobStatus.IN_PROGRESS)

            # Get appropriate processor
            processor = self.task_processors.get(task_type, self._process_general_task)

            # Process the task
            result = await processor(job_data)

            # Validate result
            if self._validate_task_result(result, job_data):
                logger.info(f"Task processing completed successfully for job {job_id}")
                await self._update_job_status(job_id, JobStatus.COMPLETED)
                return result
            else:
                logger.error(f"Task result validation failed for job {job_id}")
                await self._update_job_status(job_id, JobStatus.FAILED)
                return {'success': False, 'error': 'Task validation failed'}

        except Exception as e:
            logger.error(f"Error processing task for job {job_data.get('id')}: {e}")
            await self._update_job_status(job_data.get('id'), JobStatus.FAILED)
            return {'success': False, 'error': str(e)}

    def _determine_task_type(self, job_data: Dict[str, Any]) -> str:
        """Determine the task type based on job description and title"""
        title = job_data.get('title', '').lower()
        description = job_data.get('description', '').lower()
        content = f"{title} {description}"

        # Keywords for different task types
        task_keywords = {
            TaskType.TRANSLATION: ['翻訳', 'translation', '英訳', '和訳', 'translate'],
            TaskType.WRITING: ['ライティング', 'writing', '記事', 'article', 'blog', 'コンテンツ'],
            TaskType.DATA_ENTRY: ['データ入力', 'data entry', '入力作業', 'typing', 'エクセル'],
            TaskType.RESEARCH: ['リサーチ', 'research', '調査', '情報収集', 'investigation'],
            TaskType.CONTENT_CREATION: ['コンテンツ作成', 'content creation', 'sns', 'marketing'],
            TaskType.TRANSCRIPTION: ['文字起こし', 'transcription', '音声', 'audio', 'テープ起こし'],
            TaskType.PROOFREADING: ['校正', 'proofreading', '添削', 'editing', '確認'],
            TaskType.WEB_SCRAPING: ['スクレイピング', 'scraping', 'データ収集', 'web data'],
            TaskType.IMAGE_PROCESSING: ['画像', 'image', '写真', 'photo', 'graphic']
        }

        for task_type, keywords in task_keywords.items():
            if any(keyword in content for keyword in keywords):
                return task_type

        return TaskType.OTHER

    async def _process_translation_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process translation tasks"""
        logger.info("Processing translation task")

        try:
            # Extract source text and language requirements
            source_text = self._extract_source_text(job_data)
            source_lang, target_lang = self._determine_languages(job_data)

            if not source_text:
                return {'success': False, 'error': 'No source text found'}

            # Perform translation using AI
            prompt = f"""
            Please translate the following text from {source_lang} to {target_lang}.
            Maintain the original meaning, tone, and style as much as possible.
            If there are technical terms, preserve their accuracy.

            Source text:
            {source_text}

            Provide only the translation without explanations.
            """

            translated_text = await self.ai_service.generate_text_async(prompt)

            # Create deliverable
            deliverable_path = await self._create_text_deliverable(
                translated_text,
                f"translation_{job_data.get('id', 'unknown')}.txt"
            )

            return {
                'success': True,
                'task_type': 'translation',
                'deliverable_path': deliverable_path,
                'deliverable_content': translated_text,
                'source_language': source_lang,
                'target_language': target_lang,
                'word_count': len(translated_text.split())
            }

        except Exception as e:
            logger.error(f"Translation task error: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_writing_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process writing and content creation tasks"""
        logger.info("Processing writing task")

        try:
            # Extract writing requirements
            topic = self._extract_writing_topic(job_data)
            word_count = self._extract_word_count(job_data)
            style = self._extract_writing_style(job_data)

            prompt = f"""
            Write an article in Japanese about: {topic}

            Requirements:
            - Target word count: approximately {word_count} words
            - Writing style: {style}
            - Make it engaging and informative
            - Use proper Japanese structure and grammar
            - Include relevant examples if appropriate

            Topic: {topic}
            """

            content = await self.ai_service.generate_text_async(prompt)

            # Create deliverable
            deliverable_path = await self._create_text_deliverable(
                content,
                f"article_{job_data.get('id', 'unknown')}.txt"
            )

            return {
                'success': True,
                'task_type': 'writing',
                'deliverable_path': deliverable_path,
                'deliverable_content': content,
                'topic': topic,
                'word_count': len(content.split()),
                'style': style
            }

        except Exception as e:
            logger.error(f"Writing task error: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_data_entry_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data entry tasks"""
        logger.info("Processing data entry task")

        try:
            # For data entry, we simulate the process since we can't access real data sources
            data_requirements = self._extract_data_requirements(job_data)

            # Generate sample data structure based on requirements
            sample_data = await self._generate_sample_data(data_requirements)

            # Create CSV or Excel deliverable
            deliverable_path = await self._create_data_deliverable(
                sample_data,
                f"data_entry_{job_data.get('id', 'unknown')}.csv"
            )

            return {
                'success': True,
                'task_type': 'data_entry',
                'deliverable_path': deliverable_path,
                'data_format': 'CSV',
                'record_count': len(sample_data),
                'note': 'Sample data structure created based on requirements'
            }

        except Exception as e:
            logger.error(f"Data entry task error: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_research_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process research tasks"""
        logger.info("Processing research task")

        try:
            research_topic = self._extract_research_topic(job_data)
            research_scope = self._extract_research_scope(job_data)

            prompt = f"""
            Conduct research on the following topic and provide a comprehensive report:

            Topic: {research_topic}
            Scope: {research_scope}

            Please provide:
            1. Executive summary
            2. Key findings
            3. Detailed analysis
            4. Conclusions and recommendations
            5. Sources and references (if applicable)

            Write the report in Japanese, maintaining professional tone.
            """

            research_report = await self.ai_service.generate_text_async(prompt)

            # Create deliverable
            deliverable_path = await self._create_text_deliverable(
                research_report,
                f"research_report_{job_data.get('id', 'unknown')}.txt"
            )

            return {
                'success': True,
                'task_type': 'research',
                'deliverable_path': deliverable_path,
                'deliverable_content': research_report,
                'topic': research_topic,
                'scope': research_scope
            }

        except Exception as e:
            logger.error(f"Research task error: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_content_creation_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process content creation tasks (SNS, marketing, etc.)"""
        logger.info("Processing content creation task")

        try:
            content_type = self._extract_content_type(job_data)
            target_audience = self._extract_target_audience(job_data)
            platform = self._extract_platform(job_data)

            prompt = f"""
            Create {content_type} content for {platform} targeting {target_audience}.

            Requirements from job description:
            {job_data.get('description', '')[:500]}

            Please create engaging, platform-appropriate content in Japanese.
            Consider the target audience and platform best practices.
            """

            content = await self.ai_service.generate_text_async(prompt)

            # Create deliverable
            deliverable_path = await self._create_text_deliverable(
                content,
                f"content_{job_data.get('id', 'unknown')}.txt"
            )

            return {
                'success': True,
                'task_type': 'content_creation',
                'deliverable_path': deliverable_path,
                'deliverable_content': content,
                'content_type': content_type,
                'platform': platform,
                'target_audience': target_audience
            }

        except Exception as e:
            logger.error(f"Content creation task error: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_transcription_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process transcription tasks"""
        logger.info("Processing transcription task")

        # Note: This is a simulation since we don't have access to actual audio files
        try:
            audio_info = self._extract_audio_info(job_data)

            # Simulate transcription result
            sample_transcription = f"""
            音声ファイルの書き起こし結果

            時間: 00:00:00 - 00:05:00
            話者A: こんにちは、今日はお忙しい中お時間をいただき、ありがとうございます。
            話者B: こちらこそ、よろしくお願いします。

            [注: 実際の音声ファイルが提供された場合、正確な書き起こしを行います]
            """

            # Create deliverable
            deliverable_path = await self._create_text_deliverable(
                sample_transcription,
                f"transcription_{job_data.get('id', 'unknown')}.txt"
            )

            return {
                'success': True,
                'task_type': 'transcription',
                'deliverable_path': deliverable_path,
                'deliverable_content': sample_transcription,
                'audio_info': audio_info,
                'note': 'Sample transcription format - actual transcription requires audio file'
            }

        except Exception as e:
            logger.error(f"Transcription task error: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_proofreading_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process proofreading and editing tasks"""
        logger.info("Processing proofreading task")

        try:
            source_text = self._extract_source_text(job_data)

            if not source_text:
                # Generate sample text for demonstration
                source_text = "校正対象のテキストがここに入ります。実際のファイルが提供された場合、詳細な校正を行います。"

            prompt = f"""
            Please proofread and edit the following Japanese text:

            {source_text}

            Please:
            1. Correct any grammatical errors
            2. Improve clarity and readability
            3. Maintain the original meaning and tone
            4. Provide a summary of changes made

            Provide both the corrected text and a summary of changes.
            """

            proofread_result = await self.ai_service.generate_text_async(prompt)

            # Create deliverable
            deliverable_path = await self._create_text_deliverable(
                proofread_result,
                f"proofread_{job_data.get('id', 'unknown')}.txt"
            )

            return {
                'success': True,
                'task_type': 'proofreading',
                'deliverable_path': deliverable_path,
                'deliverable_content': proofread_result,
                'original_length': len(source_text),
                'corrected_length': len(proofread_result)
            }

        except Exception as e:
            logger.error(f"Proofreading task error: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_web_scraping_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process web scraping tasks"""
        logger.info("Processing web scraping task")

        try:
            # Extract scraping requirements
            target_urls = self._extract_target_urls(job_data)
            data_fields = self._extract_data_fields(job_data)

            # Note: This is a simulation - actual implementation would use proper scraping
            sample_scraped_data = [
                {
                    'url': url,
                    'title': f'Sample Title from {url}',
                    'description': f'Sample description extracted from {url}',
                    'scraped_at': datetime.now().isoformat()
                }
                for url in target_urls[:5]  # Limit to 5 for demo
            ]

            # Create deliverable
            deliverable_path = await self._create_data_deliverable(
                sample_scraped_data,
                f"scraped_data_{job_data.get('id', 'unknown')}.json"
            )

            return {
                'success': True,
                'task_type': 'web_scraping',
                'deliverable_path': deliverable_path,
                'target_urls': target_urls,
                'data_fields': data_fields,
                'records_count': len(sample_scraped_data),
                'note': 'Sample data structure - actual scraping requires proper implementation'
            }

        except Exception as e:
            logger.error(f"Web scraping task error: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_image_processing_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process image processing tasks"""
        logger.info("Processing image processing task")

        try:
            # Extract image processing requirements
            processing_type = self._extract_image_processing_type(job_data)

            # Note: This is a simulation - actual implementation would process images
            result_info = {
                'processing_type': processing_type,
                'processed_images': 0,
                'output_format': 'Same as input',
                'note': 'Image processing requires actual image files and specialized libraries'
            }

            # Create a text report about the processing
            report = f"""
            画像処理タスクレポート

            処理タイプ: {processing_type}
            処理対象: {job_data.get('title', 'Unknown')}

            注意: 実際の画像ファイルが提供された場合、
            適切な画像処理ライブラリを使用して処理を行います。

            対応可能な処理:
            - リサイズ
            - フォーマット変換
            - 品質調整
            - 基本的な画像編集
            """

            deliverable_path = await self._create_text_deliverable(
                report,
                f"image_processing_report_{job_data.get('id', 'unknown')}.txt"
            )

            return {
                'success': True,
                'task_type': 'image_processing',
                'deliverable_path': deliverable_path,
                'processing_info': result_info
            }

        except Exception as e:
            logger.error(f"Image processing task error: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_general_task(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process general/unclassified tasks"""
        logger.info("Processing general task")

        try:
            # Analyze the job requirements
            title = job_data.get('title', '')
            description = job_data.get('description', '')

            prompt = f"""
            Analyze this job request and provide a detailed response:

            Job Title: {title}
            Job Description: {description}

            Please provide:
            1. Understanding of the requirements
            2. Proposed approach
            3. Expected deliverables
            4. Any clarifications needed

            Respond in Japanese with a professional tone.
            """

            analysis = await self.ai_service.generate_text_async(prompt)

            # Create deliverable
            deliverable_path = await self._create_text_deliverable(
                analysis,
                f"task_analysis_{job_data.get('id', 'unknown')}.txt"
            )

            return {
                'success': True,
                'task_type': 'general',
                'deliverable_path': deliverable_path,
                'deliverable_content': analysis,
                'requires_clarification': True
            }

        except Exception as e:
            logger.error(f"General task error: {e}")
            return {'success': False, 'error': str(e)}

    # Helper methods for extracting information from job data

    def _extract_source_text(self, job_data: Dict[str, Any]) -> str:
        """Extract source text from job data"""
        description = job_data.get('description', '')

        # Look for text patterns or file references
        if '翻訳' in description or 'translation' in description.lower():
            # Try to extract text between quotes or specific markers
            import re
            text_patterns = [
                r'"([^"]+)"',  # Text in quotes
                r'「([^」]+)」',  # Text in Japanese quotes
                r'以下.*?:(.*?)$',  # Text after "以下:"
            ]

            for pattern in text_patterns:
                matches = re.findall(pattern, description, re.MULTILINE | re.DOTALL)
                if matches:
                    return matches[0].strip()

        # If no specific text found, return part of description
        return description[:200] if len(description) > 50 else "サンプルテキスト"

    def _determine_languages(self, job_data: Dict[str, Any]) -> Tuple[str, str]:
        """Determine source and target languages"""
        description = job_data.get('description', '').lower() + job_data.get('title', '').lower()

        # Common language patterns
        if '英訳' in description or 'english' in description:
            return 'Japanese', 'English'
        elif '和訳' in description or 'japanese' in description:
            return 'English', 'Japanese'
        elif '中国語' in description or 'chinese' in description:
            if '→' in description or 'to' in description:
                return 'Chinese', 'Japanese'
            else:
                return 'Japanese', 'Chinese'
        else:
            return 'Japanese', 'English'  # Default

    def _extract_writing_topic(self, job_data: Dict[str, Any]) -> str:
        """Extract writing topic from job data"""
        title = job_data.get('title', '')
        description = job_data.get('description', '')

        # Look for topic indicators
        topic_patterns = [
            r'テーマ[：:]\s*([^\n]+)',
            r'について.*?書',
            r'topic[：:]\s*([^\n]+)',
        ]

        for pattern in topic_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            if matches:
                return matches[0].strip()

        return title if title else "指定されたテーマ"

    def _extract_word_count(self, job_data: Dict[str, Any]) -> int:
        """Extract target word count from job data"""
        description = job_data.get('description', '')

        # Look for word count patterns
        word_patterns = [
            r'(\d+)文字',
            r'(\d+)字',
            r'(\d+)\s*words?',
            r'約(\d+)',
        ]

        for pattern in word_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            if matches:
                return int(matches[0])

        return 500  # Default word count

    def _extract_writing_style(self, job_data: Dict[str, Any]) -> str:
        """Extract writing style requirements"""
        description = job_data.get('description', '').lower()

        style_keywords = {
            'formal': ['正式', 'フォーマル', 'formal', 'business'],
            'casual': ['カジュアル', 'casual', '親しみやす', 'friendly'],
            'professional': ['プロフェッショナル', 'professional', 'ビジネス'],
            'blog': ['ブログ', 'blog', 'personal'],
            'news': ['ニュース', 'news', '報道', 'journalistic']
        }

        for style, keywords in style_keywords.items():
            if any(keyword in description for keyword in keywords):
                return style

        return 'professional'  # Default style

    def _extract_data_requirements(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data entry requirements"""
        return {
            'format': 'CSV',
            'fields': ['Name', 'Email', 'Phone', 'Company'],
            'estimated_records': 100
        }

    def _extract_research_topic(self, job_data: Dict[str, Any]) -> str:
        """Extract research topic"""
        title = job_data.get('title', '')
        description = job_data.get('description', '')

        # Look for research topic indicators
        if 'について' in title:
            return title.split('について')[0].strip()

        return title if title else "指定されたトピック"

    def _extract_research_scope(self, job_data: Dict[str, Any]) -> str:
        """Extract research scope"""
        description = job_data.get('description', '')

        if '市場調査' in description:
            return 'market_research'
        elif '競合分析' in description:
            return 'competitive_analysis'
        elif '技術調査' in description:
            return 'technical_research'
        else:
            return 'general_research'

    def _extract_content_type(self, job_data: Dict[str, Any]) -> str:
        """Extract content type"""
        description = job_data.get('description', '').lower()

        if 'sns' in description or 'social media' in description:
            return 'social_media_post'
        elif 'ブログ' in description or 'blog' in description:
            return 'blog_post'
        elif 'marketing' in description or 'マーケティング' in description:
            return 'marketing_content'
        else:
            return 'general_content'

    def _extract_target_audience(self, job_data: Dict[str, Any]) -> str:
        """Extract target audience"""
        return job_data.get('target_audience', '一般ユーザー')

    def _extract_platform(self, job_data: Dict[str, Any]) -> str:
        """Extract target platform"""
        description = job_data.get('description', '').lower()

        platforms = ['twitter', 'facebook', 'instagram', 'linkedin', 'youtube', 'tiktok']
        for platform in platforms:
            if platform in description:
                return platform

        return 'general'

    def _extract_audio_info(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract audio information for transcription"""
        return {
            'duration': 'Unknown',
            'format': 'Unknown',
            'language': 'Japanese',
            'speakers': 'Multiple'
        }

    def _extract_target_urls(self, job_data: Dict[str, Any]) -> List[str]:
        """Extract target URLs for scraping"""
        description = job_data.get('description', '')

        # Simple URL extraction
        import re
        urls = re.findall(r'https?://[^\s]+', description)

        if not urls:
            # Return sample URLs for demonstration
            urls = ['https://example.com', 'https://sample.jp']

        return urls

    def _extract_data_fields(self, job_data: Dict[str, Any]) -> List[str]:
        """Extract data fields to scrape"""
        return ['title', 'description', 'price', 'date', 'url']

    def _extract_image_processing_type(self, job_data: Dict[str, Any]) -> str:
        """Extract image processing type"""
        description = job_data.get('description', '').lower()

        if 'リサイズ' in description or 'resize' in description:
            return 'resize'
        elif 'フォーマット' in description or 'format' in description:
            return 'format_conversion'
        elif '品質' in description or 'quality' in description:
            return 'quality_adjustment'
        else:
            return 'general_processing'

    # Deliverable creation methods

    async def _create_text_deliverable(self, content: str, filename: str) -> str:
        """Create a text deliverable file"""
        file_path = self.temp_dir / filename

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Created text deliverable: {file_path}")
        return str(file_path)

    async def _create_data_deliverable(self, data: List[Dict], filename: str) -> str:
        """Create a data deliverable file (CSV or JSON)"""
        file_path = self.temp_dir / filename

        if filename.endswith('.csv'):
            import csv
            if data:
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
        else:  # JSON
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Created data deliverable: {file_path}")
        return str(file_path)

    async def _generate_sample_data(self, requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate sample data based on requirements"""
        fields = requirements.get('fields', ['Name', 'Email', 'Phone'])
        count = min(requirements.get('estimated_records', 10), 50)  # Limit to 50 for demo

        sample_data = []
        for i in range(count):
            record = {}
            for field in fields:
                if field.lower() in ['name', '名前']:
                    record[field] = f"サンプル{i + 1}"
                elif field.lower() in ['email', 'メール']:
                    record[field] = f"sample{i + 1}@example.com"
                elif field.lower() in ['phone', '電話']:
                    record[field] = f"090-0000-{i + 1:04d}"
                elif field.lower() in ['company', '会社']:
                    record[field] = f"サンプル株式会社{i + 1}"
                else:
                    record[field] = f"データ{i + 1}"
            sample_data.append(record)

        return sample_data

    def _validate_task_result(self, result: Dict[str, Any], job_data: Dict[str, Any]) -> bool:
        """Validate task processing result"""
        if not result.get('success'):
            return False

        # Check if deliverable was created
        deliverable_path = result.get('deliverable_path')
        if deliverable_path and not os.path.exists(deliverable_path):
            logger.error(f"Deliverable file not found: {deliverable_path}")
            return False

        # Basic content validation
        deliverable_content = result.get('deliverable_content', '')
        if not deliverable_content or len(deliverable_content.strip()) < 10:
            logger.error("Deliverable content too short or empty")
            return False

        return True

    async def _update_job_status(self, job_id: str, status: str):
        """Update job status in data store"""
        try:
            job_data = self.data_store.get_job(job_id) or {}
            job_data['status'] = status
            job_data['updated_at'] = datetime.now().isoformat()

            if status == JobStatus.IN_PROGRESS:
                job_data['started_at'] = datetime.now().isoformat()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                job_data['completed_at'] = datetime.now().isoformat()

            self.data_store.save_job(job_id, job_data)
            logger.info(f"Updated job {job_id} status to {status}")

        except Exception as e:
            logger.error(f"Error updating job status: {e}")

    def get_task_progress(self, job_id: str) -> Dict[str, Any]:
        """Get current task progress"""
        try:
            job_data = self.data_store.get_job(job_id)
            if not job_data:
                return {'progress': 0, 'status': 'not_found'}

            status = job_data.get('status', JobStatus.PENDING)

            progress_map = {
                JobStatus.PENDING: 0,
                JobStatus.APPLIED: 10,
                JobStatus.ACCEPTED: 20,
                JobStatus.IN_PROGRESS: 50,
                JobStatus.COMPLETED: 100,
                JobStatus.FAILED: 0
            }

            return {
                'progress': progress_map.get(status, 0),
                'status': status,
                'started_at': job_data.get('started_at'),
                'estimated_completion': self._estimate_completion_time(job_data)
            }

        except Exception as e:
            logger.error(f"Error getting task progress: {e}")
            return {'progress': 0, 'status': 'error'}

    def _estimate_completion_time(self, job_data: Dict[str, Any]) -> Optional[str]:
        """Estimate task completion time"""
        try:
            if job_data.get('status') == JobStatus.COMPLETED:
                return job_data.get('completed_at')

            started_at = job_data.get('started_at')
            if not started_at:
                return None

            start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            estimated_duration = job_data.get('estimated_hours', 2) * 3600  # Convert to seconds
            estimated_completion = start_time + timedelta(seconds=estimated_duration)

            return estimated_completion.isoformat()

        except Exception as e:
            logger.error(f"Error estimating completion time: {e}")
            return None

    async def cleanup_temp_files(self, older_than_hours: int = 24):
        """Clean up temporary files older than specified hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=older_than_hours)

            for file_path in self.temp_dir.glob('*'):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_time:
                        file_path.unlink()
                        logger.info(f"Cleaned up temp file: {file_path}")

        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")

    def get_deliverable_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get information about job deliverables"""
        try:
            job_data = self.data_store.get_job(job_id)
            if not job_data:
                return None

            task_result = job_data.get('task_result', {})
            if not task_result:
                return None

            deliverable_path = task_result.get('deliverable_path')
            if not deliverable_path or not os.path.exists(deliverable_path):
                return None

            file_stat = os.stat(deliverable_path)

            return {
                'path': deliverable_path,
                'filename': os.path.basename(deliverable_path),
                'size': file_stat.st_size,
                'created_at': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                'modified_at': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                'task_type': task_result.get('task_type'),
                'content_preview': self._get_content_preview(deliverable_path)
            }

        except Exception as e:
            logger.error(f"Error getting deliverable info: {e}")
            return None

    def _get_content_preview(self, file_path: str) -> str:
        """Get preview of deliverable content"""
        try:
            if file_path.endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return content[:200] + '...' if len(content) > 200 else content
            elif file_path.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return f"JSON file with {len(data)} records"
            elif file_path.endswith('.csv'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    return f"CSV file with {len(lines) - 1} data rows"
            else:
                return "Binary file"

        except Exception as e:
            logger.error(f"Error getting content preview: {e}")
            return "Unable to preview"


class TaskQueue:
    """Manages task processing queue"""

    def __init__(self, max_concurrent_tasks: int = 3):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks = {}
        self.task_queue = []
        self.processing_lock = asyncio.Lock()

    async def add_task(self, job_id: str, job_data: Dict[str, Any], processor: TaskProcessor) -> bool:
        """Add task to processing queue"""
        async with self.processing_lock:
            if len(self.active_tasks) >= self.max_concurrent_tasks:
                self.task_queue.append((job_id, job_data, processor))
                logger.info(f"Task {job_id} added to queue (queue size: {len(self.task_queue)})")
                return False
            else:
                asyncio.create_task(self._process_task(job_id, job_data, processor))
                return True

    async def _process_task(self, job_id: str, job_data: Dict[str, Any], processor: TaskProcessor):
        """Process a single task"""
        try:
            self.active_tasks[job_id] = {
                'started_at': datetime.now(),
                'status': 'processing'
            }

            logger.info(f"Started processing task {job_id}")
            result = await processor.process_job_task(job_data)

            # Save result to job data
            job_data['task_result'] = result
            processor.data_store.save_job(job_id, job_data)

            logger.info(f"Completed processing task {job_id}")

        except Exception as e:
            logger.error(f"Error processing task {job_id}: {e}")

        finally:
            # Remove from active tasks and process next in queue
            if job_id in self.active_tasks:
                del self.active_tasks[job_id]

            await self._process_next_in_queue()

    async def _process_next_in_queue(self):
        """Process next task in queue if available"""
        async with self.processing_lock:
            if self.task_queue and len(self.active_tasks) < self.max_concurrent_tasks:
                job_id, job_data, processor = self.task_queue.pop(0)
                asyncio.create_task(self._process_task(job_id, job_data, processor))
                logger.info(f"Started queued task {job_id}")

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            'active_tasks': len(self.active_tasks),
            'queued_tasks': len(self.task_queue),
            'max_concurrent': self.max_concurrent_tasks,
            'active_task_ids': list(self.active_tasks.keys())
        }