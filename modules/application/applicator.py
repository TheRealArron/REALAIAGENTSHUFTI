"""
Job Applicator Module

This module handles the automated submission of job applications on Shufti.
It creates compelling proposals, handles form submissions, and manages application tracking.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime, timedelta
import random

from ..llm.ai_service import AIService
from ..auth.login import ShuftiAuth
from .job_matcher import JobMatch, MatchResult
from ...utils.http_client import RateLimitedHTTPClient
from ...utils.logger import get_logger
from ...utils.data_store import DataStore

logger = get_logger(__name__)


class ApplicationStatus(Enum):
    """Application submission status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    ERROR = "error"


@dataclass
class ApplicationTemplate:
    """Template for job applications"""
    greeting: str
    introduction: str
    experience_highlight: str
    approach_description: str
    timeline: str
    closing: str
    call_to_action: str


@dataclass
class ApplicationResult:
    """Result of job application submission"""
    job_id: str
    status: ApplicationStatus
    application_id: Optional[str] = None
    submission_time: Optional[datetime] = None
    proposal_text: Optional[str] = None
    bid_amount: Optional[int] = None
    error_message: Optional[str] = None


class JobApplicator:
    """Automated job application system"""

    def __init__(self, ai_service: AIService, auth: ShuftiAuth, http_client: RateLimitedHTTPClient,
                 data_store: DataStore):
        self.ai_service = ai_service
        self.auth = auth
        self.http_client = http_client
        self.data_store = data_store
        self.application_templates = self._load_templates()
        self.daily_application_limit = 10
        self.applications_today = 0

    def _load_templates(self) -> Dict[str, ApplicationTemplate]:
        """Load application templates for different job types"""
        return {
            "data_entry": ApplicationTemplate(
                greeting="こんにちは！",
                introduction="データ入力作業を専門とするAIアシスタントです。",
                experience_highlight="大量のデータ処理と高精度な入力作業を得意としており、",
                approach_description="効率的なワークフローを構築して品質を保証いたします。",
                timeline="お客様のスケジュールに合わせて迅速に対応可能です。",
                closing="ぜひお手伝いさせていただければと思います。",
                call_to_action="詳しい要件についてお聞かせください。"
            ),
            "translation": ApplicationTemplate(
                greeting="はじめまして！",
                introduction="多言語翻訳を専門とするAIアシスタントです。",
                experience_highlight="日本語、英語、中国語、韓国語の翻訳経験が豊富で、",
                approach_description="文脈を理解した自然で正確な翻訳を提供いたします。",
                timeline="お急ぎの案件にも対応可能です。",
                closing="高品質な翻訳サービスを提供いたします。",
                call_to_action="翻訳内容について詳しくお聞かせください。"
            ),
            "research": ApplicationTemplate(
                greeting="こんにちは！",
                introduction="リサーチ・調査作業を専門とするAIアシスタントです。",
                experience_highlight="インターネットリサーチから市場調査まで幅広く対応し、",
                approach_description="正確で詳細な情報収集と分析を行います。",
                timeline="効率的な調査プロセスで迅速に結果をお届けします。",
                closing="信頼性の高い調査結果を提供いたします。",
                call_to_action="調査の詳細についてお聞かせください。"
            ),
            "content_writing": ApplicationTemplate(
                greeting="はじめまして！",
                introduction="コンテンツライティングを専門とするAIアシスタントです。",
                experience_highlight="SEOを意識した記事作成からマーケティングコピーまで、",
                approach_description="読者の心に響く魅力的なコンテンツを作成いたします。",
                timeline="ご要望に応じて柔軟にスケジュール調整いたします。",
                closing="質の高いコンテンツ制作をお約束いたします。",
                call_to_action="コンテンツの方向性についてお聞かせください。"
            ),
            "general": ApplicationTemplate(
                greeting="こんにちは！",
                introduction="様々なタスクに対応可能なAIアシスタントです。",
                experience_highlight="データ処理、翻訳、リサーチ、コンテンツ作成など幅広いスキルを持ち、",
                approach_description="お客様のニーズに合わせて最適なソリューションを提供いたします。",
                timeline="柔軟なスケジュールで対応可能です。",
                closing="お客様の成功をサポートいたします。",
                call_to_action="プロジェクトの詳細についてお聞かせください。"
            )
        }

    async def apply_to_job(self, job_data: Dict, job_match: JobMatch) -> ApplicationResult:
        """
        Apply to a specific job

        Args:
            job_data: Job information
            job_match: Job match analysis result

        Returns:
            ApplicationResult with submission details
        """
        try:
            logger.info(f"Applying to job: {job_data.get('title', 'Unknown')}")

            # Check daily application limit
            if not self._can_apply_today():
                return ApplicationResult(
                    job_id=job_data.get("job_id", ""),
                    status=ApplicationStatus.ERROR,
                    error_message="Daily application limit reached"
                )

            # Check if already applied
            if self._already_applied(job_data.get("job_id", "")):
                return ApplicationResult(
                    job_id=job_data.get("job_id", ""),
                    status=ApplicationStatus.ERROR,
                    error_message="Already applied to this job"
                )

            # Generate proposal
            proposal = await self._generate_proposal(job_data, job_match)

            # Calculate bid amount
            bid_amount = self._calculate_bid_amount(job_data, job_match)

            # Submit application
            result = await self._submit_application(job_data, proposal, bid_amount)

            # Track application
            if result.status == ApplicationStatus.SUBMITTED:
                self._track_application(result)
                self.applications_today += 1

            return result

        except Exception as e:
            logger.error(f"Error applying to job {job_data.get('job_id', '')}: {str(e)}")
            return ApplicationResult(
                job_id=job_data.get("job_id", ""),
                status=ApplicationStatus.ERROR,
                error_message=str(e)
            )

    async def _generate_proposal(self, job_data: Dict, job_match: JobMatch) -> str:
        """Generate a compelling job proposal"""
        try:
            # Determine job category for template selection
            category = self._categorize_job(job_data, job_match)
            template = self.application_templates.get(category, self.application_templates["general"])

            # Use AI to customize the proposal
            customization_prompt = f"""
            Create a personalized job proposal in Japanese for this job:

            Job Title: {job_data.get('title', '')}
            Description: {job_data.get('description', '')}
            Budget: {job_data.get('budget', 0)} JPY
            Duration: {job_data.get('duration_days', 0)} days

            Matching Skills: {', '.join(job_match.matching_skills)}
            Confidence: {job_match.confidence_score:.2f}

            Base template structure:
            - Greeting: {template.greeting}
            - Introduction: {template.introduction}
            - Experience: {template.experience_highlight}
            - Approach: {template.approach_description}
            - Timeline: {template.timeline}
            - Closing: {template.closing}
            - Call to action: {template.call_to_action}

            Please create a natural, personalized proposal that:
            1. References specific job requirements
            2. Highlights relevant experience
            3. Shows understanding of the task
            4. Proposes a clear approach
            5. Remains professional and confident
            6. Is written in natural Japanese
            7. Is approximately 200-300 characters

            Do not use placeholder text or generic statements.
            """

            ai_proposal = await self.ai_service.generate_response(customization_prompt)

            # Clean and format the proposal
            proposal = self._format_proposal(ai_proposal, template)

            logger.info(f"Generated proposal for job {job_data.get('job_id', '')}")
            return proposal

        except Exception as e:
            logger.error(f"Error generating proposal: {str(e)}")
            # Fallback to template-based proposal
            return self._create_template_proposal(job_data, job_match)

    def _categorize_job(self, job_data: Dict, job_match: JobMatch) -> str:
        """Categorize job for template selection"""
        title = job_data.get("title", "").lower()
        description = job_data.get("description", "").lower()

        # Check for data entry keywords
        if any(keyword in title or keyword in description for keyword in
               ["データ入力", "data entry", "入力作業", "エクセル", "excel"]):
            return "data_entry"

        # Check for translation keywords
        if any(keyword in title or keyword in description for keyword in
               ["翻訳", "translation", "translate", "通訳", "多言語"]):
            return "translation"

        # Check for research keywords
        if any(keyword in title or keyword in description for keyword in
               ["リサーチ", "research", "調査", "情報収集", "市場調査"]):
            return "research"

        # Check for content writing keywords
        if any(keyword in title or keyword in description for keyword in
               ["ライティング", "writing", "記事", "コンテンツ", "ブログ"]):
            return "content_writing"

        return "general"

    def _format_proposal(self, ai_proposal: str, template: ApplicationTemplate) -> str:
        """Format and clean the AI-generated proposal"""
        # Remove any markdown formatting
        proposal = ai_proposal.replace("**", "").replace("*", "")

        # Ensure proper structure
        if not proposal.startswith(template.greeting):
            proposal = f"{template.greeting}\n\n{proposal}"

        if not proposal.endswith("。"):
            proposal += "。"

        # Add call to action if missing
        if template.call_to_action not in proposal:
            proposal += f"\n\n{template.call_to_action}"

        return proposal.strip()

    def _create_template_proposal(self, job_data: Dict, job_match: JobMatch) -> str:
        """Create a basic proposal using templates (fallback)"""
        category = self._categorize_job(job_data, job_match)
        template = self.application_templates.get(category, self.application_templates["general"])

        proposal_parts = [
            template.greeting,
            template.introduction,
            template.experience_highlight,
            template.approach_description,
            template.timeline,
            template.closing,
            template.call_to_action
        ]

        return "\n\n".join(proposal_parts)

    def _calculate_bid_amount(self, job_data: Dict, job_match: JobMatch) -> int:
        """Calculate appropriate bid amount"""
        try:
            job_budget = job_data.get("budget", 0)

            # If no budget specified, use estimated time
            if job_budget <= 0:
                estimated_hours = job_match.estimated_completion_time or 4
                hourly_rate = 2000  # Base rate in JPY
                return estimated_hours * hourly_rate

            # Bid slightly below budget but ensure minimum rate
            min_bid = 1000  # Minimum bid
            max_bid = int(job_budget * 0.9)  # 90% of budget

            # Consider match quality for pricing
            confidence_multiplier = 0.8 + (job_match.confidence_score * 0.2)
            calculated_bid = int(max_bid * confidence_multiplier)

            return max(min_bid, min(calculated_bid, max_bid))

        except Exception as e:
            logger.error(f"Error calculating bid: {str(e)}")
            return 2000  # Default bid

    async def _submit_application(self, job_data: Dict, proposal: str, bid_amount: int) -> ApplicationResult:
        """Submit the actual application"""
        try:
            job_id = job_data.get("job_id", "")

            # Ensure we're authenticated
            if not await self.auth.ensure_authenticated():
                return ApplicationResult(
                    job_id=job_id,
                    status=ApplicationStatus.ERROR,
                    error_message="Authentication failed"
                )

            # Prepare application data
            application_data = {
                "job_id": job_id,
                "proposal": proposal,
                "bid_amount": bid_amount,
                "estimated_delivery": self._calculate_delivery_date(job_data),
                "message": proposal
            }

            # Submit application via API
            headers = {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            }

            # Add random delay to appear more human
            await asyncio.sleep(random.uniform(2, 5))

            response = await self.http_client.post(
                f"https://app.shufti.jp/api/jobs/{job_id}/apply",
                json=application_data,
                headers=headers
            )

            if response.status_code == 200:
                response_data = response.json()
                application_id = response_data.get("application_id")

                logger.info(f"Successfully applied to job {job_id}")

                return ApplicationResult(
                    job_id=job_id,
                    status=ApplicationStatus.SUBMITTED,
                    application_id=application_id,
                    submission_time=datetime.now(),
                    proposal_text=proposal,
                    bid_amount=bid_amount
                )
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Application submission failed: {error_msg}")

                return ApplicationResult(
                    job_id=job_id,
                    status=ApplicationStatus.ERROR,
                    error_message=error_msg
                )

        except Exception as e:
            logger.error(f"Error submitting application: {str(e)}")
            return ApplicationResult(
                job_id=job_id,
                status=ApplicationStatus.ERROR,
                error_message=str(e)
            )

    def _calculate_delivery_date(self, job_data: Dict) -> str:
        """Calculate realistic delivery date"""
        duration_days = job_data.get("duration_days", 3)

        # Add buffer time
        buffer_days = max(1, duration_days // 4)
        total_days = duration_days + buffer_days

        delivery_date = datetime.now() + timedelta(days=total_days)
        return delivery_date.strftime("%Y-%m-%d")

    def _can_apply_today(self) -> bool:
        """Check if we can apply to more jobs today"""
        return self.applications_today < self.daily_application_limit

    def _already_applied(self, job_id: str) -> bool:
        """Check if we already applied to this job"""
        try:
            applications = self.data_store.get("applications", {})
            return job_id in applications
        except Exception:
            return False

    def _track_application(self, result: ApplicationResult):
        """Track submitted application"""
        try:
            applications = self.data_store.get("applications", {})
            applications[result.job_id] = {
                "application_id": result.application_id,
                "status": result.status.value,
                "submission_time": result.submission_time.isoformat() if result.submission_time else None,
                "bid_amount": result.bid_amount,
                "proposal": result.proposal_text[:100] + "..." if result.proposal_text else None
            }
            self.data_store.set("applications", applications)

            # Update daily counter
            today = datetime.now().strftime("%Y-%m-%d")
            daily_stats = self.data_store.get("daily_applications", {})
            daily_stats[today] = daily_stats.get(today, 0) + 1
            self.data_store.set("daily_applications", daily_stats)

            logger.info(f"Tracked application for job {result.job_id}")

        except Exception as e:
            logger.error(f"Error tracking application: {str(e)}")

    async def batch_apply(self, job_matches: List[Tuple[Dict, JobMatch]], max_applications: int = 5) -> List[
        ApplicationResult]:
        """
        Apply to multiple jobs in batch

        Args:
            job_matches: List of (job_data, job_match) tuples
            max_applications: Maximum number of applications to submit

        Returns:
            List of ApplicationResult objects
        """
        results = []
        applied_count = 0

        # Sort by match quality (best matches first)
        sorted_matches = sorted(job_matches, key=lambda x: x[1].confidence_score, reverse=True)

        for job_data, job_match in sorted_matches:
            if applied_count >= max_applications or not self._can_apply_today():
                break

            # Only apply to good matches
            if job_match.match_result in [MatchResult.PERFECT_MATCH, MatchResult.GOOD_MATCH]:
                result = await self.apply_to_job(job_data, job_match)
                results.append(result)

                if result.status == ApplicationStatus.SUBMITTED:
                    applied_count += 1

                # Add delay between applications
                await asyncio.sleep(random.uniform(10, 30))

        logger.info(f"Batch application completed: {applied_count} applications submitted")
        return results

    def get_application_stats(self) -> Dict:
        """Get application statistics"""
        try:
            applications = self.data_store.get("applications", {})
            daily_stats = self.data_store.get("daily_applications", {})

            total_applications = len(applications)
            today = datetime.now().strftime("%Y-%m-%d")
            today_applications = daily_stats.get(today, 0)

            # Count by status
            status_counts = {}
            for app_data in applications.values():
                status = app_data.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "total_applications": total_applications,
                "applications_today": today_applications,
                "daily_limit": self.daily_application_limit,
                "remaining_today": max(0, self.daily_application_limit - today_applications),
                "status_breakdown": status_counts,
                "success_rate": status_counts.get("submitted", 0) / max(total_applications, 1)
            }

        except Exception as e:
            logger.error(f"Error getting application stats: {str(e)}")
            return {}

    def update_daily_limit(self, new_limit: int):
        """Update daily application limit"""
        if new_limit > 0:
            self.daily_application_limit = new_limit
            logger.info(f"Updated daily application limit to {new_limit}")