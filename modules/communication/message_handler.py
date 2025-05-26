"""
Message Handler Module

This module processes incoming messages from clients on Shufti platform.
It analyzes message content, determines appropriate responses, and manages conversation flow.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import re
import asyncio

from ..llm.ai_service import AIService
from ..auth.login import ShuftiAuth
from ...utils.http_client import RateLimitedHTTPClient
from ...utils.logger import get_logger
from ...utils.data_store import DataStore
from ...config.constants import MessageTypes, ResponsePriority

logger = get_logger(__name__)


class MessageType(Enum):
    """Types of incoming messages"""
    PROJECT_INQUIRY = "project_inquiry"
    PROJECT_DETAILS = "project_details"
    CLARIFICATION = "clarification"
    FEEDBACK = "feedback"
    PROGRESS_UPDATE = "progress_update"
    PAYMENT_RELATED = "payment_related"
    COMPLAINT = "complaint"
    GENERAL = "general"
    SPAM = "spam"
    URGENT = "urgent"


class MessagePriority(Enum):
    """Message priority levels"""
    CRITICAL = 1  # Respond within 15 minutes
    HIGH = 2  # Respond within 1 hour
    NORMAL = 3  # Respond within 4 hours
    LOW = 4  # Respond within 24 hours


@dataclass
class IncomingMessage:
    """Represents an incoming message from a client"""
    message_id: str
    job_id: str
    client_id: str
    client_name: str
    subject: Optional[str]
    content: str
    timestamp: datetime
    message_type: MessageType
    priority: MessagePriority
    requires_immediate_response: bool = False
    attachments: List[str] = None
    conversation_thread_id: Optional[str] = None


@dataclass
class MessageAnalysis:
    """Analysis result of a message"""
    sentiment: str  # positive, negative, neutral
    intent: str
    key_topics: List[str]
    questions: List[str]
    action_items: List[str]
    urgency_indicators: List[str]
    requires_clarification: bool
    contains_new_requirements: bool


@dataclass
class ProcessedMessage:
    """Processed message ready for response"""
    original_message: IncomingMessage
    analysis: MessageAnalysis
    suggested_response: str
    response_priority: MessagePriority
    follow_up_actions: List[str]
    estimated_response_time: int  # minutes


class MessageHandler:
    """Handles incoming client messages and communication"""

    def __init__(self, ai_service: AIService, auth: ShuftiAuth, http_client: RateLimitedHTTPClient,
                 data_store: DataStore):
        self.ai_service = ai_service
        self.auth = auth
        self.http_client = http_client
        self.data_store = data_store
        self.response_templates = self._load_response_templates()
        self.processed_messages = {}
        self.conversation_contexts = {}

    def _load_response_templates(self) -> Dict[str, Dict[str, str]]:
        """Load response templates for different message types"""
        return {
            "project_inquiry": {
                "greeting": "お問い合わせいただき、ありがとうございます。",
                "confirmation": "プロジェクトの詳細について確認させていただきます。",
                "next_steps": "詳細な要件をお聞かせいただければ、適切な提案をさせていただきます。",
                "closing": "何かご不明な点がございましたら、お気軽にお声かけください。"
            },
            "project_details": {
                "acknowledgment": "プロジェクトの詳細をご共有いただき、ありがとうございます。",
                "understanding": "要件について理解いたしました。",
                "proposal": "以下のアプローチで進めさせていただければと思います：",
                "timeline": "スケジュールについてご確認させていただきます。"
            },
            "clarification": {
                "thanks": "ご質問いただき、ありがとうございます。",
                "explanation": "詳しくご説明させていただきます。",
                "additional_info": "追加でご不明な点がございましたら、お聞かせください。",
                "availability": "いつでもサポートいたします。"
            },
            "feedback": {
                "appreciation": "貴重なフィードバックをいただき、ありがとうございます。",
                "response": "ご指摘の点について対応いたします。",
                "improvement": "より良いサービス提供に努めます。",
                "follow_up": "改善状況については随時ご報告いたします。"
            },
            "progress_update": {
                "status": "プロジェクトの進捗状況をご報告いたします。",
                "completed": "完了した作業：",
                "in_progress": "現在進行中の作業：",
                "next_steps": "次のステップ：",
                "timeline": "予定スケジュール：",
                "questions": "ご確認いただきたい点："
            },
            "urgent": {
                "immediate": "緊急のご連絡をいただき、承知いたしました。",
                "priority": "最優先で対応させていただきます。",
                "eta": "対応予定時刻をお知らせいたします。",
                "contact": "緊急時は直接ご連絡ください。"
            }
        }

    async def fetch_new_messages(self) -> List[IncomingMessage]:
        """Fetch new messages from Shufti platform"""
        try:
            if not await self.auth.ensure_authenticated():
                logger.error("Authentication failed, cannot fetch messages")
                return []

            # Fetch messages from API
            response = await self.http_client.get(
                "https://app.shufti.jp/api/messages/inbox",
                params={"status": "unread", "limit": 50}
            )

            if response.status_code != 200:
                logger.error(f"Failed to fetch messages: HTTP {response.status_code}")
                return []

            messages_data = response.json().get("messages", [])
            messages = []

            for msg_data in messages_data:
                try:
                    message = self._parse_message(msg_data)
                    messages.append(message)
                except Exception as e:
                    logger.error(f"Error parsing message {msg_data.get('id', 'unknown')}: {str(e)}")
                    continue

            logger.info(f"Fetched {len(messages)} new messages")
            return messages

        except Exception as e:
            logger.error(f"Error fetching messages: {str(e)}")
            return []

    def _parse_message(self, msg_data: Dict) -> IncomingMessage:
        """Parse raw message data into IncomingMessage object"""
        message_id = msg_data.get("id", "")
        content = msg_data.get("content", "")

        # Analyze message type and priority
        message_type = self._classify_message_type(content, msg_data.get("subject", ""))
        priority = self._determine_priority(content, message_type)

        return IncomingMessage(
            message_id=message_id,
            job_id=msg_data.get("job_id", ""),
            client_id=msg_data.get("client_id", ""),
            client_name=msg_data.get("client_name", "Unknown"),
            subject=msg_data.get("subject"),
            content=content,
            timestamp=datetime.fromisoformat(msg_data.get("timestamp", datetime.now().isoformat())),
            message_type=message_type,
            priority=priority,
            requires_immediate_response=self._requires_immediate_response(content),
            attachments=msg_data.get("attachments", []),
            conversation_thread_id=msg_data.get("thread_id")
        )

    def _classify_message_type(self, content: str, subject: str = "") -> MessageType:
        """Classify the type of message based on content analysis"""
        content_lower = content.lower()
        subject_lower = (subject or "").lower()
        combined_text = f"{subject_lower} {content_lower}"

        # Check for urgent indicators
        urgent_keywords = ["緊急", "急ぎ", "至急", "urgent", "asap", "immediately", "今すぐ"]
        if any(keyword in combined_text for keyword in urgent_keywords):
            return MessageType.URGENT

        # Check for project inquiry
        inquiry_keywords = ["見積", "依頼", "相談", "inquiry", "quote", "proposal", "興味", "検討"]
        if any(keyword in combined_text for keyword in inquiry_keywords):
            return MessageType.PROJECT_INQUIRY

        # Check for project details
        details_keywords = ["詳細", "要件", "仕様", "requirement", "specification", "detail", "具体的"]
        if any(keyword in combined_text for keyword in details_keywords):
            return MessageType.PROJECT_DETAILS

        # Check for clarification requests
        clarification_keywords = ["質問", "確認", "不明", "question", "clarify", "unclear", "わからない"]
        if any(keyword in combined_text for keyword in clarification_keywords):
            return MessageType.CLARIFICATION

        # Check for feedback
        feedback_keywords = ["フィードバック", "修正", "変更", "feedback", "revision", "change", "改善"]
        if any(keyword in combined_text for keyword in feedback_keywords):
            return MessageType.FEEDBACK

        # Check for progress updates requests
        progress_keywords = ["進捗", "状況", "progress", "status", "update", "どうですか", "いかがですか"]
        if any(keyword in combined_text for keyword in progress_keywords):
            return MessageType.PROGRESS_UPDATE

        # Check for payment related
        payment_keywords = ["支払", "料金", "請求", "payment", "invoice", "billing", "cost", "price"]
        if any(keyword in combined_text for keyword in payment_keywords):
            return MessageType.PAYMENT_RELATED

        # Check for complaints
        complaint_keywords = ["不満", "問題", "complaint", "issue", "problem", "困る", "トラブル"]
        if any(keyword in combined_text for keyword in complaint_keywords):
            return MessageType.COMPLAINT

        # Check for spam indicators
        spam_keywords = ["spam", "広告", "宣伝", "marketing", "promotion", "無料", "free", "win", "prize"]
        if any(keyword in combined_text for keyword in spam_keywords):
            return MessageType.SPAM

        return MessageType.GENERAL

    def _determine_priority(self, content: str, message_type: MessageType) -> MessagePriority:
        """Determine message priority based on content and type"""
        content_lower = content.lower()

        # Critical priority indicators
        critical_indicators = ["緊急", "至急", "urgent", "critical", "emergency", "immediately", "asap"]
        if any(indicator in content_lower for indicator in critical_indicators):
            return MessagePriority.CRITICAL

        # High priority message types
        if message_type in [MessageType.URGENT, MessageType.COMPLAINT, MessageType.PAYMENT_RELATED]:
            return MessagePriority.HIGH

        # High priority indicators
        high_indicators = ["急ぎ", "早め", "soon", "quickly", "deadline", "締切"]
        if any(indicator in content_lower for indicator in high_indicators):
            return MessagePriority.HIGH

        # Normal priority for most project-related messages
        if message_type in [MessageType.PROJECT_INQUIRY, MessageType.PROJECT_DETAILS, MessageType.CLARIFICATION]:
            return MessagePriority.NORMAL

        return MessagePriority.LOW

    def _requires_immediate_response(self, content: str) -> bool:
        """Check if message requires immediate response"""
        immediate_indicators = [
            "緊急", "至急", "今すぐ", "急ぎ", "urgent", "immediately", "asap",
            "critical", "emergency", "deadline today", "今日中"
        ]
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in immediate_indicators)

    async def analyze_message(self, message: IncomingMessage) -> MessageAnalysis:
        """Analyze message content using AI"""
        try:
            analysis_prompt = f"""
            Analyze this message from a client:

            Subject: {message.subject or 'No subject'}
            Content: {message.content}
            Message Type: {message.message_type.value}

            Please provide analysis in this format:
            Sentiment: [positive/negative/neutral]
            Intent: [brief description of what the client wants]
            Key Topics: [comma-separated list of main topics]
            Questions: [list any direct questions asked]
            Action Items: [list any tasks or actions requested]
            Urgency Indicators: [any words/phrases indicating urgency]
            Requires Clarification: [yes/no - if message is unclear]
            Contains New Requirements: [yes/no - if new project requirements mentioned]
            """

            ai_response = await self.ai_service.generate_response(analysis_prompt)

            # Parse AI response
            analysis = self._parse_analysis_response(ai_response)

            # Update conversation context
            if message.conversation_thread_id:
                self._update_conversation_context(message.conversation_thread_id, message, analysis)

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing message: {str(e)}")
            return MessageAnalysis(
                sentiment="neutral",
                intent="general inquiry",
                key_topics=[],
                questions=[],
                action_items=[],
                urgency_indicators=[],
                requires_clarification=False,
                contains_new_requirements=False
            )

    def _parse_analysis_response(self, ai_response: str) -> MessageAnalysis:
        """Parse AI analysis response into MessageAnalysis object"""
        try:
            # Extract information using regex patterns
            sentiment_match = re.search(r'Sentiment:\s*(\w+)', ai_response, re.IGNORECASE)
            intent_match = re.search(r'Intent:\s*([^\n]+)', ai_response, re.IGNORECASE)
            topics_match = re.search(r'Key Topics:\s*([^\n]+)', ai_response, re.IGNORECASE)
            questions_match = re.search(r'Questions:\s*([^\n]+)', ai_response, re.IGNORECASE)
            actions_match = re.search(r'Action Items:\s*([^\n]+)', ai_response, re.IGNORECASE)
            urgency_match = re.search(r'Urgency Indicators:\s*([^\n]+)', ai_response, re.IGNORECASE)
            clarification_match = re.search(r'Requires Clarification:\s*(\w+)', ai_response, re.IGNORECASE)
            requirements_match = re.search(r'Contains New Requirements:\s*(\w+)', ai_response, re.IGNORECASE)

            return MessageAnalysis(
                sentiment=sentiment_match.group(1).lower() if sentiment_match else "neutral",
                intent=intent_match.group(1).strip() if intent_match else "general inquiry",
                key_topics=[topic.strip() for topic in topics_match.group(1).split(',') if topics_match else []],
            questions = [q.strip() for q in questions_match.group(1).split(',') if
                         questions_match and questions_match.group(1).strip() != 'None'],
            action_items = [a.strip() for a in actions_match.group(1).split(',') if
                            actions_match and actions_match.group(1).strip() != 'None'],
            urgency_indicators = [u.strip() for u in urgency_match.group(1).split(',') if
                                  urgency_match and urgency_match.group(1).strip() != 'None'],
            requires_clarification = clarification_match.group(1).lower() == 'yes' if clarification_match else False,
            contains_new_requirements = requirements_match.group(1).lower() == 'yes' if requirements_match else False
            )

            except Exception as e:
            logger.error(f"Error parsing analysis response: {str(e)}")
            return MessageAnalysis(
                sentiment="neutral",
                intent="general inquiry",
                key_topics=[],
                questions=[],
                action_items=[],
                urgency_indicators=[],
                requires_clarification=False,
                contains_new_requirements=False
            )

    def _update_conversation_context(self, thread_id: str, message: IncomingMessage, analysis: MessageAnalysis):
        """Update conversation context for thread continuity"""
        if thread_id not in self.conversation_contexts:
            self.conversation_contexts[thread_id] = {
                "messages": [],
                "project_status": "initial",
                "key_requirements": [],
                "client_preferences": [],
                "last_update": datetime.now()
            }

        context = self.conversation_contexts[thread_id]
        context["messages"].append({
            "message_id": message.message_id,
            "timestamp": message.timestamp,
            "content_summary": analysis.intent,
            "key_topics": analysis.key_topics
        })

        # Update project information
        if analysis.contains_new_requirements:
            context["key_requirements"].extend(analysis.key_topics)

        context["last_update"] = datetime.now()

        # Keep only recent messages (last 10)
        context["messages"] = context["messages"][-10:]

    async def process_message(self, message: IncomingMessage) -> ProcessedMessage:
        """Process a message and prepare response"""
        try:
            logger.info(f"Processing message {message.message_id} from {message.client_name}")

            # Analyze message content
            analysis = await self.analyze_message(message)

            # Generate suggested response
            suggested_response = await self._generate_response(message, analysis)

            # Determine response priority and timing
            response_priority = self._adjust_response_priority(message.priority, analysis)
            estimated_time = self._calculate_response_time(response_priority)

            # Identify follow-up actions
            follow_up_actions = self._identify_follow_up_actions(message, analysis)

            processed = ProcessedMessage(
                original_message=message,
                analysis=analysis,
                suggested_response=suggested_response,
                response_priority=response_priority,
                follow_up_actions=follow_up_actions,
                estimated_response_time=estimated_time
            )

            # Store processed message
            self.processed_messages[message.message_id] = processed

            logger.info(f"Processed message {message.message_id}, priority: {response_priority.name}")
            return processed

        except Exception as e:
            logger.error(f"Error processing message {message.message_id}: {str(e)}")
            raise

    async def _generate_response(self, message: IncomingMessage, analysis: MessageAnalysis) -> str:
        """Generate appropriate response based on message analysis"""
        try:
            # Get conversation context if available
            context_info = ""
            if message.conversation_thread_id and message.conversation_thread_id in self.conversation_contexts:
                context = self.conversation_contexts[message.conversation_thread_id]
                recent_topics = [msg["key_topics"] for msg in context["messages"][-3:]]
                context_info = f"Previous conversation topics: {recent_topics}"

            # Generate response using AI
            response_prompt = f"""
            Generate a professional response in Japanese for this client message:

            Client Message: {message.content}
            Message Type: {message.message_type.value}
            Client Sentiment: {analysis.sentiment}
            Client Intent: {analysis.intent}
            Key Topics: {', '.join(analysis.key_topics)}
            Questions Asked: {', '.join(analysis.questions)}
            Action Items: {', '.join(analysis.action_items)}
            {context_info}

            Response Requirements:
            1. Professional and friendly tone
            2. Address all questions and concerns
            3. Provide clear next steps
            4. Written in natural Japanese
            5. Length: 100-200 characters
            6. Include appropriate business expressions

            Template structure to consider:
            - Greeting/Acknowledgment
            - Address main points
            - Provide information/answers
            - Next steps or call to action
            - Professional closing
            """

            ai_response = await self.ai_service.generate_response(response_prompt)

            # Clean and format response
            response = self._format_response(ai_response, message.message_type)

            return response

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            # Fallback to template response
            return self._generate_template_response(message, analysis)

    def _format_response(self, ai_response: str, message_type: MessageType) -> str:
        """Format and clean AI-generated response"""
        # Remove markdown formatting
        response = ai_response.replace("**", "").replace("*", "")

        # Ensure proper Japanese formatting
        response = response.strip()

        # Add appropriate closing if missing
        if not response.endswith(("。", "！", "？", "です", "ます")):
            response += "。"

        # Ensure professional greeting for new conversations
        greetings = ["こんにちは", "いつもお世話になっております", "ご連絡いただき"]
        if not any(greeting in response for greeting in greetings):
            if message_type == MessageType.PROJECT_INQUIRY:
                response = f"お問い合わせいただき、ありがとうございます。\n\n{response}"

        return response

    def _generate_template_response(self, message: IncomingMessage, analysis: MessageAnalysis) -> str:
        """Generate response using templates (fallback method)"""
        message_type_key = message.message_type.value
        templates = self.response_templates.get(message_type_key, self.response_templates["general"])

        response_parts = []

        # Add greeting/acknowledgment
        if "greeting" in templates:
            response_parts.append(templates["greeting"])
        elif "acknowledgment" in templates:
            response_parts.append(templates["acknowledgment"])

        # Add main response based on analysis
        if analysis.questions:
            response_parts.append("ご質問にお答えいたします。")

        if analysis.action_items:
            response_parts.append("ご依頼の件について対応いたします。")

        # Add next steps
        if "next_steps" in templates:
            response_parts.append(templates["next_steps"])

        # Add closing
        if "closing" in templates:
            response_parts.append(templates["closing"])

        return "\n\n".join(response_parts)

    def _adjust_response_priority(self, original_priority: MessagePriority,
                                  analysis: MessageAnalysis) -> MessagePriority:
        """Adjust response priority based on analysis"""
        # Increase priority for negative sentiment
        if analysis.sentiment == "negative":
            if original_priority.value > MessagePriority.HIGH.value:
                return MessagePriority.HIGH

        # Increase priority if many questions or urgent indicators
        if len(analysis.questions) > 2 or len(analysis.urgency_indicators) > 0:
            if original_priority.value > MessagePriority.NORMAL.value:
                return MessagePriority.NORMAL

        return original_priority

    def _calculate_response_time(self, priority: MessagePriority) -> int:
        """Calculate estimated response time in minutes"""
        time_mapping = {
            MessagePriority.CRITICAL: 15,
            MessagePriority.HIGH: 60,
            MessagePriority.NORMAL: 240,
            MessagePriority.LOW: 1440
        }
        return time_mapping.get(priority, 240)

    def _identify_follow_up_actions(self, message: IncomingMessage, analysis: MessageAnalysis) -> List[str]:
        """Identify required follow-up actions"""
        actions = []

        # Project-related actions
        if message.message_type == MessageType.PROJECT_INQUIRY:
            actions.append("send_detailed_quote")
            actions.append("schedule_clarification_call")

        if message.message_type == MessageType.PROJECT_DETAILS:
            actions.append("update_project_scope")
            actions.append("revise_timeline")

        # Analysis-based actions
        if analysis.requires_clarification:
            actions.append("request_clarification")

        if analysis.contains_new_requirements:
            actions.append("update_requirements_document")
            actions.append("recalculate_timeline")

        if analysis.questions:
            actions.append("prepare_detailed_answers")

        # Priority-based actions
        if message.requires_immediate_response:
            actions.append("send_immediate_acknowledgment")

        return actions

    async def batch_process_messages(self, messages: List[IncomingMessage]) -> List[ProcessedMessage]:
        """Process multiple messages in batch"""
        processed_messages = []

        # Sort by priority (critical first)
        sorted_messages = sorted(messages, key=lambda m: m.priority.value)

        for message in sorted_messages:
            try:
                processed = await self.process_message(message)
                processed_messages.append(processed)

                # Add small delay between processing
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error processing message {message.message_id}: {str(e)}")
                continue

        logger.info(f"Batch processed {len(processed_messages)} messages")
        return processed_messages

    def get_message_statistics(self) -> Dict:
        """Get message handling statistics"""
        try:
            total_messages = len(self.processed_messages)

            # Count by type
            type_counts = {}
            priority_counts = {}

            for processed in self.processed_messages.values():
                msg_type = processed.original_message.message_type.value
                priority = processed.response_priority.name

                type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
                priority_counts[priority] = priority_counts.get(priority, 0) + 1

            # Calculate average response time
            avg_response_time = sum(p.estimated_response_time for p in self.processed_messages.values()) / max(
                total_messages, 1)

            return {
                "total_processed": total_messages,
                "message_types": type_counts,
                "priority_distribution": priority_counts,
                "average_response_time_minutes": avg_response_time,
                "active_conversations": len(self.conversation_contexts)
            }

        except Exception as e:
            logger.error(f"Error getting message statistics: {str(e)}")
            return {}

    def mark_message_as_read(self, message_id: str):
        """Mark a message as read on the platform"""
        # This would typically make an API call to mark the message as read
        # For now, we'll just log it
        logger.info(f"Marked message {message_id} as read")