"""
AI Service Module for Shufti Agent
Provides interface to free AI models for translation, text processing, and job analysis
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """Interface with free AI models for various text processing tasks"""

    def __init__(self):
        self.settings = get_settings()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Using Hugging Face Inference API (free tier)
        self.hf_api_url = "https://api-inference.huggingface.co/models"
        self.translation_model = "Helsinki-NLP/opus-mt-ja-en"  # Japanese to English
        self.text_generation_model = "microsoft/DialoGPT-medium"

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests

    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_hf_request(self, model_name: str, payload: Dict[str, Any]) -> Optional[Dict]:
        """Make request to Hugging Face Inference API"""
        try:
            self._wait_for_rate_limit()

            url = f"{self.hf_api_url}/{model_name}"
            headers = {
                "Content-Type": "application/json"
            }

            response = self.session.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 503:
                # Model is loading, wait and retry
                logger.info(f"Model {model_name} is loading, waiting...")
                time.sleep(20)
                response = self.session.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"HF API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error making HF request: {e}")
            return None

    def translate_japanese_to_english(self, japanese_text: str) -> str:
        """Translate Japanese text to English"""
        try:
            if not japanese_text or not japanese_text.strip():
                return ""

            # Fallback simple translation for common job-related terms
            simple_translations = {
                "仕事": "job",
                "募集": "recruitment",
                "応募": "application",
                "給料": "salary",
                "時給": "hourly wage",
                "経験": "experience",
                "スキル": "skill",
                "必要": "required",
                "詳細": "details",
                "条件": "conditions",
                "勤務": "work",
                "時間": "time",
                "場所": "location",
                "連絡": "contact",
                "メッセージ": "message",
                "完了": "completed",
                "提出": "submit",
                "確認": "confirm"
            }

            # Try simple keyword replacement first
            english_text = japanese_text
            for jp, en in simple_translations.items():
                english_text = english_text.replace(jp, en)

            # If text is mostly translated or short, return as is
            if len([c for c in english_text if ord(c) < 128]) / len(english_text) > 0.7:
                return english_text

            # Try HF translation API
            payload = {"inputs": japanese_text}
            result = self._make_hf_request(self.translation_model, payload)

            if result and isinstance(result, list) and len(result) > 0:
                translation = result[0].get('translation_text', english_text)
                logger.info(f"Translated: {japanese_text[:50]}... -> {translation[:50]}...")
                return translation

            # Fallback to simple replacement
            return english_text

        except Exception as e:
            logger.error(f"Translation error: {e}")
            return japanese_text  # Return original if translation fails

    def analyze_job_requirements(self, job_description: str) -> Dict[str, Any]:
        """Analyze job description to extract key requirements"""
        try:
            # Translate if Japanese
            if any(ord(c) > 127 for c in job_description):
                english_desc = self.translate_japanese_to_english(job_description)
            else:
                english_desc = job_description

            # Simple keyword-based analysis
            skills_keywords = [
                'python', 'javascript', 'java', 'html', 'css', 'react', 'vue', 'angular',
                'sql', 'database', 'mysql', 'postgresql', 'mongodb', 'redis',
                'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'git',
                'machine learning', 'ai', 'data analysis', 'excel', 'powerpoint',
                'communication', 'teamwork', 'leadership', 'project management'
            ]

            experience_keywords = [
                'entry level', 'junior', 'senior', 'lead', 'manager',
                'beginner', 'experienced', 'expert', 'years experience'
            ]

            requirements_keywords = [
                'required', 'must have', 'essential', 'mandatory',
                'preferred', 'nice to have', 'bonus', 'plus'
            ]

            desc_lower = english_desc.lower()

            found_skills = [skill for skill in skills_keywords if skill in desc_lower]
            found_experience = [exp for exp in experience_keywords if exp in desc_lower]
            found_requirements = [req for req in requirements_keywords if req in desc_lower]

            # Extract salary information
            salary_info = self._extract_salary_info(english_desc)

            analysis = {
                'skills_required': found_skills,
                'experience_level': found_experience,
                'requirement_type': found_requirements,
                'salary_info': salary_info,
                'complexity_score': len(found_skills) + len(found_requirements),
                'is_suitable': len(found_skills) <= 5,  # Simple suitability check
                'original_text': job_description,
                'translated_text': english_desc if english_desc != job_description else None
            }

            logger.info(
                f"Job analysis completed: {len(found_skills)} skills, complexity: {analysis['complexity_score']}")
            return analysis

        except Exception as e:
            logger.error(f"Job analysis error: {e}")
            return {
                'skills_required': [],
                'experience_level': [],
                'requirement_type': [],
                'salary_info': {},
                'complexity_score': 0,
                'is_suitable': True,
                'original_text': job_description,
                'translated_text': None,
                'error': str(e)
            }

    def _extract_salary_info(self, text: str) -> Dict[str, Any]:
        """Extract salary information from job description"""
        import re

        salary_info = {}
        text_lower = text.lower()

        # Look for currency amounts
        yen_pattern = r'¥[\d,]+|[\d,]+円'
        dollar_pattern = r'\$[\d,]+|[\d,]+\s*(?:usd|dollars?)'
        hourly_pattern = r'[\d,]+\s*(?:per hour|/hour|時給)'

        yen_matches = re.findall(yen_pattern, text_lower)
        dollar_matches = re.findall(dollar_pattern, text_lower)
        hourly_matches = re.findall(hourly_pattern, text_lower)

        if yen_matches:
            salary_info['currency'] = 'JPY'
            salary_info['amounts'] = yen_matches

        if dollar_matches:
            salary_info['currency'] = 'USD'
            salary_info['amounts'] = dollar_matches

        if hourly_matches:
            salary_info['type'] = 'hourly'
            salary_info['hourly_rates'] = hourly_matches

        # Check for salary keywords
        if any(word in text_lower for word in ['salary', 'wage', 'pay', 'compensation']):
            salary_info['has_salary_info'] = True

        return salary_info

    def generate_application_message(self, job_info: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
        """Generate personalized application message"""
        try:
            # Simple template-based message generation
            templates = [
                "Hello, I am interested in the {job_title} position. I have experience with {skills} and believe I would be a good fit for this role. Please let me know if you need any additional information.",
                "Hi, I would like to apply for the {job_title} position. My background includes {skills} and I am excited about this opportunity. Thank you for your consideration.",
                "Dear hiring manager, I am writing to express my interest in the {job_title} role. With my experience in {skills}, I am confident I can contribute effectively to your team."
            ]

            job_title = job_info.get('title', 'this position')
            skills = ", ".join(user_profile.get('skills', ['various technical skills'])[:3])

            import random
            template = random.choice(templates)
            message = template.format(job_title=job_title, skills=skills)

            # Translate to Japanese if needed
            if job_info.get('language') == 'japanese':
                # Simple Japanese template
                japanese_templates = [
                    f"こんにちは。{job_title}の求人に興味があります。{skills}の経験があり、この役職に適していると思います。追加情報が必要でしたらお知らせください。",
                    f"はじめまして。{job_title}に応募したいと思います。{skills}の経験があり、この機会に興味があります。ご検討よろしくお願いします。"
                ]
                message = random.choice(japanese_templates)

            logger.info(f"Generated application message: {len(message)} characters")
            return message

        except Exception as e:
            logger.error(f"Message generation error: {e}")
            return "Hello, I am interested in this position and would like to apply. Thank you for your consideration."

    def generate_task_response(self, task_description: str, context: Dict[str, Any] = None) -> str:
        """Generate response for task completion"""
        try:
            # Translate task if needed
            if any(ord(c) > 127 for c in task_description):
                english_task = self.translate_japanese_to_english(task_description)
            else:
                english_task = task_description

            # Simple task response generation
            task_lower = english_task.lower()

            if any(word in task_lower for word in ['write', 'create', 'draft']):
                response = "I have completed the writing task as requested. Please find the content above."
            elif any(word in task_lower for word in ['research', 'find', 'search']):
                response = "I have conducted the research and compiled the findings as requested."
            elif any(word in task_lower for word in ['analyze', 'review', 'check']):
                response = "I have completed the analysis and provided my findings above."
            elif any(word in task_lower for word in ['translate', 'convert']):
                response = "I have completed the translation/conversion as requested."
            else:
                response = "I have completed the requested task. Please let me know if you need any clarification."

            # Add Japanese version if original was Japanese
            if english_task != task_description:
                japanese_responses = {
                    "I have completed the writing task as requested. Please find the content above.": "ご依頼いただいた執筆作業が完了しました。上記をご確認ください。",
                    "I have conducted the research and compiled the findings as requested.": "調査を実施し、結果をまとめました。",
                    "I have completed the analysis and provided my findings above.": "分析を完了し、結果を上記に示しました。",
                    "I have completed the translation/conversion as requested.": "翻訳・変換作業が完了しました。",
                    "I have completed the requested task. Please let me know if you need any clarification.": "ご依頼いただいた作業が完了しました。ご不明な点がございましたらお知らせください。"
                }
                response = japanese_responses.get(response, "作業が完了しました。")

            return response

        except Exception as e:
            logger.error(f"Task response generation error: {e}")
            return "Task completed. Thank you."

    def extract_key_information(self, text: str, info_type: str = "general") -> Dict[str, Any]:
        """Extract key information from text based on type"""
        try:
            # Translate if Japanese
            if any(ord(c) > 127 for c in text):
                english_text = self.translate_japanese_to_english(text)
            else:
                english_text = text

            extracted = {
                'original_text': text,
                'translated_text': english_text if english_text != text else None,
                'info_type': info_type
            }

            if info_type == "contact":
                # Extract contact information
                import re
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                phone_pattern = r'[\d\-\(\)\+\s]{10,}'

                emails = re.findall(email_pattern, english_text)
                phones = re.findall(phone_pattern, english_text)

                extracted['emails'] = emails
                extracted['phones'] = phones

            elif info_type == "deadline":
                # Extract deadline information
                import re
                date_patterns = [
                    r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
                    r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',
                    r'by \w+ \d{1,2}',
                    r'until \w+ \d{1,2}'
                ]

                dates = []
                for pattern in date_patterns:
                    matches = re.findall(pattern, english_text.lower())
                    dates.extend(matches)

                extracted['deadlines'] = dates

            elif info_type == "requirements":
                # Extract requirements
                req_keywords = ['must', 'required', 'need', 'should', 'expect']
                requirements = []

                sentences = english_text.split('.')
                for sentence in sentences:
                    if any(keyword in sentence.lower() for keyword in req_keywords):
                        requirements.append(sentence.strip())

                extracted['requirements'] = requirements

            return extracted

        except Exception as e:
            logger.error(f"Information extraction error: {e}")
            return {
                'original_text': text,
                'translated_text': None,
                'info_type': info_type,
                'error': str(e)
            }


# Singleton instance
_ai_service = None


def get_ai_service() -> AIService:
    """Get singleton AI service instance"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service