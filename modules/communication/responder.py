"""
Communication responder module for generating appropriate responses
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import re

from ..llm.ai_service import AIService
from ...config.constants import RESPONSE_TEMPLATES, JobStatus
from ...utils.logger import get_logger

logger = get_logger(__name__)


class MessageResponder:
    """Generates appropriate responses to various types of messages"""

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        self.response_templates = RESPONSE_TEMPLATES

    def generate_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        """
        Generate appropriate response based on message type and context

        Args:
            message_data: Parsed message information
            context: Job and conversation context

        Returns:
            Generated response string or None if no response needed
        """
        try:
            message_type = self._classify_message(message_data, context)
            logger.info(f"Classified message as: {message_type}")

            response_generators = {
                'question': self._generate_question_response,
                'negotiation': self._generate_negotiation_response,
                'task_clarification': self._generate_task_clarification_response,
                'deadline_inquiry': self._generate_deadline_response,
                'price_negotiation': self._generate_price_response,
                'acceptance': self._generate_acceptance_response,
                'rejection': self._generate_rejection_response,
                'progress_update': self._generate_progress_response,
                'completion_notification': self._generate_completion_response,
                'revision_request': self._generate_revision_response,
                'general_inquiry': self._generate_general_response
            }

            generator = response_generators.get(message_type, self._generate_general_response)
            response = generator(message_data, context)

            if response:
                logger.info("Successfully generated response")
                return self._post_process_response(response, context)
            else:
                logger.warning("No response generated")
                return None

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._generate_fallback_response(message_data, context)

    def _classify_message(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Classify the type of message to determine appropriate response"""
        content = message_data.get('content', '').lower()

        # Keywords for different message types
        question_keywords = ['?', '質問', 'question', 'どう', 'how', 'what', 'when', 'where', 'why']
        negotiation_keywords = ['価格', '料金', 'price', 'cost', '安く', 'discount', '交渉']
        deadline_keywords = ['いつ', '期限', 'deadline', 'when', '納期', 'delivery']
        acceptance_keywords = ['採用', 'accept', '決定', 'hire', '選択', 'choose']
        rejection_keywords = ['不採用', 'reject', '見送り', 'decline', 'cancel']
        progress_keywords = ['進捗', 'progress', '状況', 'status', '途中']
        completion_keywords = ['完了', 'complete', '終了', 'finish', '納品', 'delivery']
        revision_keywords = ['修正', 'revision', '変更', 'change', '直し', 'fix']

        # Check for specific patterns
        if any(keyword in content for keyword in question_keywords):
            return 'question'
        elif any(keyword in content for keyword in negotiation_keywords):
            return 'price_negotiation'
        elif any(keyword in content for keyword in deadline_keywords):
            return 'deadline_inquiry'
        elif any(keyword in content for keyword in acceptance_keywords):
            return 'acceptance'
        elif any(keyword in content for keyword in rejection_keywords):
            return 'rejection'
        elif any(keyword in content for keyword in progress_keywords):
            return 'progress_update'
        elif any(keyword in content for keyword in completion_keywords):
            return 'completion_notification'
        elif any(keyword in content for keyword in revision_keywords):
            return 'revision_request'
        else:
            return 'general_inquiry'

    def _generate_question_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response to questions about the job or capabilities"""
        prompt = f"""
        You are a professional freelancer responding to a client's question about a job.

        Job Details:
        - Title: {context.get('job_title', 'N/A')}
        - Description: {context.get('job_description', 'N/A')[:500]}
        - Budget: {context.get('budget', 'N/A')}

        Client's Question: {message_data.get('content', '')}

        Generate a helpful, professional response in Japanese that:
        1. Directly answers their question
        2. Demonstrates your expertise
        3. Shows enthusiasm for the project
        4. Keeps the tone polite and professional

        Response should be 2-3 sentences maximum.
        """

        return self.ai_service.generate_text(prompt)

    def _generate_negotiation_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response for price or terms negotiation"""
        current_budget = context.get('budget', 0)

        prompt = f"""
        You are negotiating project terms with a client.

        Current Budget: {current_budget} yen
        Client Message: {message_data.get('content', '')}

        Generate a professional negotiation response in Japanese that:
        1. Shows flexibility while maintaining value
        2. Explains the reasoning for your pricing
        3. Offers alternatives if needed
        4. Maintains a collaborative tone

        Keep response concise and professional.
        """

        return self.ai_service.generate_text(prompt)

    def _generate_task_clarification_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response asking for task clarification"""
        template = self.response_templates.get('task_clarification', {}).get('ja',
                                                                             "ご質問いただきありがとうございます。詳細について確認させていただきたい点がございます。")

        prompt = f"""
        A client has sent this message about task details: {message_data.get('content', '')}

        Generate a polite response in Japanese asking for specific clarification about:
        1. Task requirements
        2. Expected deliverables
        3. Timeline expectations

        Base response on this template: {template}
        Keep it professional and concise.
        """

        return self.ai_service.generate_text(prompt)

    def _generate_deadline_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response about deadlines and delivery times"""
        estimated_hours = context.get('estimated_hours', 24)

        prompt = f"""
        Client is asking about deadlines. The estimated work time is {estimated_hours} hours.
        Client message: {message_data.get('content', '')}

        Generate a response in Japanese that:
        1. Provides a realistic timeline
        2. Shows commitment to quality
        3. Offers to discuss if timeline needs adjustment

        Be specific but flexible.
        """

        return self.ai_service.generate_text(prompt)

    def _generate_price_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response to price-related inquiries"""
        budget = context.get('budget', '未定')

        prompt = f"""
        Client is discussing price. Current budget: {budget}
        Client message: {message_data.get('content', '')}

        Generate a professional response in Japanese that:
        1. Explains your pricing rationale
        2. Shows value proposition
        3. Maintains flexibility for negotiation

        Be confident but open to discussion.
        """

        return self.ai_service.generate_text(prompt)

    def _generate_acceptance_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response when job is accepted"""
        template = self.response_templates.get('acceptance', {}).get('ja',
                                                                     "この度はお選びいただき、誠にありがとうございます。責任を持って取り組ませていただきます。")

        return template

    def _generate_rejection_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response when job is rejected"""
        template = self.response_templates.get('rejection', {}).get('ja',
                                                                    "ご検討いただき、ありがとうございました。またの機会がございましたら、よろしくお願いいたします。")

        return template

    def _generate_progress_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response about project progress"""
        job_status = context.get('status', JobStatus.IN_PROGRESS)

        prompt = f"""
        Client is asking about project progress. Current status: {job_status}
        Client message: {message_data.get('content', '')}

        Generate a progress update response in Japanese that:
        1. Provides specific progress information
        2. Mentions next steps
        3. Reassures about timeline

        Be transparent and professional.
        """

        return self.ai_service.generate_text(prompt)

    def _generate_completion_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response when notifying about completion"""
        template = self.response_templates.get('completion', {}).get('ja',
                                                                     "作業が完了いたしました。ご確認のほど、よろしくお願いいたします。")

        return template

    def _generate_revision_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate response to revision requests"""
        prompt = f"""
        Client is requesting revisions: {message_data.get('content', '')}

        Generate a response in Japanese that:
        1. Acknowledges the revision request
        2. Shows willingness to make changes
        3. Asks for specific clarification if needed

        Be accommodating and professional.
        """

        return self.ai_service.generate_text(prompt)

    def _generate_general_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate general response for unclassified messages"""
        prompt = f"""
        Generate a polite, professional response in Japanese to this client message:
        {message_data.get('content', '')}

        The response should:
        1. Acknowledge their message
        2. Be helpful and engaging
        3. Show professionalism
        4. Be appropriate for a freelance context

        Keep it concise and natural.
        """

        return self.ai_service.generate_text(prompt)

    def _generate_fallback_response(self, message_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate fallback response when other methods fail"""
        return self.response_templates.get('general', {}).get('ja',
                                                              "メッセージをありがとうございます。内容を確認して、適切にご対応させていただきます。")

    def _post_process_response(self, response: str, context: Dict[str, Any]) -> str:
        """Post-process the generated response"""
        if not response:
            return ""

        # Clean up the response
        response = response.strip()

        # Remove any unwanted characters or formatting
        response = re.sub(r'\n+', '\n', response)
        response = re.sub(r'\s+', ' ', response)

        # Ensure appropriate length (not too long for messages)
        if len(response) > 500:
            sentences = response.split('。')
            response = '。'.join(sentences[:3]) + '。' if len(sentences) > 3 else response

        return response

    def generate_proactive_message(self, job_data: Dict[str, Any], message_type: str) -> Optional[str]:
        """
        Generate proactive messages (like progress updates or delivery notifications)

        Args:
            job_data: Job information
            message_type: Type of proactive message to send

        Returns:
            Generated message string
        """
        try:
            if message_type == 'progress_update':
                return self._generate_proactive_progress_update(job_data)
            elif message_type == 'delivery_notification':
                return self._generate_delivery_notification(job_data)
            elif message_type == 'deadline_reminder':
                return self._generate_deadline_reminder(job_data)
            else:
                logger.warning(f"Unknown proactive message type: {message_type}")
                return None

        except Exception as e:
            logger.error(f"Error generating proactive message: {e}")
            return None

    def _generate_proactive_progress_update(self, job_data: Dict[str, Any]) -> str:
        """Generate proactive progress update message"""
        progress_percentage = job_data.get('progress_percentage', 0)

        prompt = f"""
        Generate a proactive progress update message in Japanese for a freelance job.
        Current progress: {progress_percentage}%
        Job title: {job_data.get('title', '')}

        The message should:
        1. Inform about current progress
        2. Mention what's been completed
        3. Indicate next steps
        4. Reassure about timeline

        Keep it professional and concise.
        """

        return self.ai_service.generate_text(prompt)

    def _generate_delivery_notification(self, job_data: Dict[str, Any]) -> str:
        """Generate delivery notification message"""
        template = self.response_templates.get('delivery', {}).get('ja',
                                                                   "作業が完了し、成果物をお送りいたします。ご確認をお願いいたします。")

        return template

    def _generate_deadline_reminder(self, job_data: Dict[str, Any]) -> str:
        """Generate deadline reminder message"""
        deadline = job_data.get('deadline', '')

        prompt = f"""
        Generate a polite reminder message in Japanese about an upcoming deadline.
        Deadline: {deadline}
        Job title: {job_data.get('title', '')}

        The message should:
        1. Politely remind about the deadline
        2. Confirm current progress
        3. Assure timely completion

        Be professional and reassuring.
        """

        return self.ai_service.generate_text(prompt)


class ResponseValidator:
    """Validates generated responses before sending"""

    @staticmethod
    def validate_response(response: str, context: Dict[str, Any]) -> bool:
        """
        Validate that a response is appropriate before sending

        Args:
            response: Generated response text
            context: Message context

        Returns:
            True if response is valid, False otherwise
        """
        if not response or not response.strip():
            return False

        # Check length constraints
        if len(response) > 1000:  # Too long
            return False

        if len(response) < 5:  # Too short
            return False

        # Check for inappropriate content (basic check)
        inappropriate_patterns = [
            r'個人情報',  # Personal information
            r'連絡先',  # Contact information
            r'電話番号',  # Phone number
            r'メール',  # Email
        ]

        for pattern in inappropriate_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                logger.warning(f"Response contains inappropriate content: {pattern}")
                return False

        return True

    @staticmethod
    def sanitize_response(response: str) -> str:
        """Sanitize response content"""
        # Remove potential personal information patterns
        sanitized = re.sub(r'\b\d{3}-\d{4}-\d{4}\b', '[電話番号]', response)  # Phone numbers
        sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[メールアドレス]',
                           sanitized)  # Email

        return sanitized