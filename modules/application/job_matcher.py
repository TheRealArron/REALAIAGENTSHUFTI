"""
Job Matcher Module

This module handles intelligent matching of job requirements with agent capabilities.
It analyzes job descriptions, requirements, and determines if the agent can handle the task.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re

from ..llm.ai_service import AIService
from ...config.constants import JobCategories, SkillLevels
from ...utils.logger import get_logger

logger = get_logger(__name__)


class MatchResult(Enum):
    """Job matching results"""
    PERFECT_MATCH = "perfect_match"
    GOOD_MATCH = "good_match"
    PARTIAL_MATCH = "partial_match"
    NO_MATCH = "no_match"


@dataclass
class JobMatch:
    """Job matching result with confidence score"""
    job_id: str
    match_result: MatchResult
    confidence_score: float  # 0.0 to 1.0
    matching_skills: List[str]
    missing_skills: List[str]
    reasons: List[str]
    estimated_completion_time: Optional[int] = None  # in hours


@dataclass
class AgentCapabilities:
    """Agent's current capabilities and skills"""
    core_skills: List[str]
    languages: List[str]
    tools: List[str]
    experience_level: str
    hourly_capacity: int
    max_project_duration: int  # in days


class JobMatcher:
    """Intelligent job matching system"""

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        self.agent_capabilities = self._initialize_capabilities()

    def _initialize_capabilities(self) -> AgentCapabilities:
        """Initialize agent capabilities"""
        return AgentCapabilities(
            core_skills=[
                "data_entry", "web_scraping", "content_writing", "translation",
                "image_processing", "document_processing", "research",
                "social_media_management", "email_handling", "basic_coding",
                "excel_processing", "pdf_processing", "online_research"
            ],
            languages=["japanese", "english", "chinese", "korean"],
            tools=[
                "browser_automation", "api_integration", "file_processing",
                "image_editing", "document_conversion", "data_analysis"
            ],
            experience_level="intermediate",
            hourly_capacity=8,
            max_project_duration=30
        )

    async def analyze_job(self, job_data: Dict) -> JobMatch:
        """
        Analyze a job and determine match quality

        Args:
            job_data: Job information dictionary

        Returns:
            JobMatch object with analysis results
        """
        try:
            logger.info(f"Analyzing job: {job_data.get('title', 'Unknown')}")

            # Extract key information
            title = job_data.get("title", "")
            description = job_data.get("description", "")
            requirements = job_data.get("requirements", [])
            category = job_data.get("category", "")
            budget = job_data.get("budget", 0)
            duration = job_data.get("duration_days", 0)

            # Analyze with AI
            ai_analysis = await self._ai_analyze_job(title, description, requirements)

            # Basic compatibility checks
            basic_checks = self._basic_compatibility_check(job_data)

            # Skill matching
            skill_match = self._analyze_skills(ai_analysis["required_skills"])

            # Calculate overall match
            match_result, confidence = self._calculate_match_score(
                basic_checks, skill_match, ai_analysis
            )

            # Estimate completion time
            estimated_time = self._estimate_completion_time(
                ai_analysis["complexity"], duration
            )

            return JobMatch(
                job_id=job_data.get("job_id", ""),
                match_result=match_result,
                confidence_score=confidence,
                matching_skills=skill_match["matching"],
                missing_skills=skill_match["missing"],
                reasons=self._generate_match_reasons(basic_checks, skill_match, ai_analysis),
                estimated_completion_time=estimated_time
            )

        except Exception as e:
            logger.error(f"Error analyzing job: {str(e)}")
            return JobMatch(
                job_id=job_data.get("job_id", ""),
                match_result=MatchResult.NO_MATCH,
                confidence_score=0.0,
                matching_skills=[],
                missing_skills=[],
                reasons=[f"Analysis failed: {str(e)}"]
            )

    async def _ai_analyze_job(self, title: str, description: str, requirements: List[str]) -> Dict:
        """Use AI to analyze job requirements"""
        try:
            prompt = f"""
            Analyze this job posting and extract key information:

            Title: {title}
            Description: {description}
            Requirements: {', '.join(requirements) if requirements else 'None specified'}

            Please provide analysis in this format:
            - Required Skills: [list of specific skills needed]
            - Complexity Level: [beginner/intermediate/advanced]
            - Task Type: [data_entry/research/content/technical/creative/other]
            - Language Requirements: [languages needed]
            - Time Sensitivity: [urgent/normal/flexible]
            - Special Tools: [any specific tools or software needed]
            """

            response = await self.ai_service.generate_response(prompt)

            # Parse AI response (simplified parsing)
            analysis = {
                "required_skills": self._extract_skills_from_response(response),
                "complexity": self._extract_complexity_from_response(response),
                "task_type": self._extract_task_type_from_response(response),
                "languages": self._extract_languages_from_response(response),
                "time_sensitivity": self._extract_time_sensitivity_from_response(response),
                "special_tools": self._extract_tools_from_response(response)
            }

            return analysis

        except Exception as e:
            logger.error(f"AI analysis failed: {str(e)}")
            return {
                "required_skills": [],
                "complexity": "intermediate",
                "task_type": "general",
                "languages": ["japanese"],
                "time_sensitivity": "normal",
                "special_tools": []
            }

    def _basic_compatibility_check(self, job_data: Dict) -> Dict:
        """Perform basic compatibility checks"""
        checks = {
            "budget_acceptable": True,
            "duration_feasible": True,
            "category_supported": True,
            "location_compatible": True
        }

        # Budget check (assuming minimum acceptable rates)
        budget = job_data.get("budget", 0)
        if budget > 0 and budget < 1000:  # Very low budget jobs
            checks["budget_acceptable"] = False

        # Duration check
        duration = job_data.get("duration_days", 0)
        if duration > self.agent_capabilities.max_project_duration:
            checks["duration_feasible"] = False

        # Category check
        category = job_data.get("category", "").lower()
        unsupported_categories = ["adult", "gambling", "illegal", "medical_advice"]
        if any(cat in category for cat in unsupported_categories):
            checks["category_supported"] = False

        return checks

    def _analyze_skills(self, required_skills: List[str]) -> Dict:
        """Analyze skill matching"""
        required_skills_lower = [skill.lower() for skill in required_skills]
        agent_skills_lower = [skill.lower() for skill in self.agent_capabilities.core_skills]

        matching_skills = []
        missing_skills = []

        for skill in required_skills_lower:
            # Direct match
            if skill in agent_skills_lower:
                matching_skills.append(skill)
            # Partial/related match
            elif any(agent_skill in skill or skill in agent_skill for agent_skill in agent_skills_lower):
                matching_skills.append(skill)
            else:
                missing_skills.append(skill)

        return {
            "matching": matching_skills,
            "missing": missing_skills,
            "match_percentage": len(matching_skills) / max(len(required_skills), 1)
        }

    def _calculate_match_score(self, basic_checks: Dict, skill_match: Dict, ai_analysis: Dict) -> Tuple[
        MatchResult, float]:
        """Calculate overall match score and result"""
        # Base score from basic checks
        basic_score = sum(basic_checks.values()) / len(basic_checks)

        # Skill match score
        skill_score = skill_match["match_percentage"]

        # Complexity penalty/bonus
        complexity = ai_analysis.get("complexity", "intermediate")
        complexity_modifier = {
            "beginner": 0.1,
            "intermediate": 0.0,
            "advanced": -0.2
        }.get(complexity, 0.0)

        # Calculate final score
        final_score = (basic_score * 0.3 + skill_score * 0.7) + complexity_modifier
        final_score = max(0.0, min(1.0, final_score))

        # Determine match result
        if final_score >= 0.8:
            match_result = MatchResult.PERFECT_MATCH
        elif final_score >= 0.6:
            match_result = MatchResult.GOOD_MATCH
        elif final_score >= 0.4:
            match_result = MatchResult.PARTIAL_MATCH
        else:
            match_result = MatchResult.NO_MATCH

        return match_result, final_score

    def _estimate_completion_time(self, complexity: str, duration_days: int) -> int:
        """Estimate completion time in hours"""
        base_hours = {
            "beginner": 2,
            "intermediate": 4,
            "advanced": 8
        }.get(complexity, 4)

        # Factor in project duration
        if duration_days > 0:
            # For longer projects, estimate daily effort
            daily_hours = min(base_hours, self.agent_capabilities.hourly_capacity)
            return daily_hours * min(duration_days, 7)  # Cap at 1 week estimation

        return base_hours

    def _generate_match_reasons(self, basic_checks: Dict, skill_match: Dict, ai_analysis: Dict) -> List[str]:
        """Generate human-readable reasons for the match result"""
        reasons = []

        # Basic compatibility reasons
        if not basic_checks["budget_acceptable"]:
            reasons.append("Budget may be too low for quality work")
        if not basic_checks["duration_feasible"]:
            reasons.append("Project duration exceeds capacity")
        if not basic_checks["category_supported"]:
            reasons.append("Job category not supported")

        # Skill matching reasons
        match_percentage = skill_match["match_percentage"]
        if match_percentage >= 0.8:
            reasons.append("Excellent skill match")
        elif match_percentage >= 0.6:
            reasons.append("Good skill compatibility")
        elif match_percentage >= 0.4:
            reasons.append("Partial skill match - may require learning")
        else:
            reasons.append("Significant skill gaps identified")

        # Missing skills
        if skill_match["missing"]:
            reasons.append(f"Missing skills: {', '.join(skill_match['missing'][:3])}")

        # Complexity consideration
        complexity = ai_analysis.get("complexity", "intermediate")
        if complexity == "advanced":
            reasons.append("High complexity task - proceed with caution")
        elif complexity == "beginner":
            reasons.append("Simple task - good for quick completion")

        return reasons[:5]  # Limit to top 5 reasons

    # Helper methods for parsing AI responses
    def _extract_skills_from_response(self, response: str) -> List[str]:
        """Extract skills from AI response"""
        skills_match = re.search(r'Required Skills:\s*\[(.*?)\]', response, re.IGNORECASE)
        if skills_match:
            skills_text = skills_match.group(1)
            return [skill.strip().strip('"\'') for skill in skills_text.split(',')]
        return []

    def _extract_complexity_from_response(self, response: str) -> str:
        """Extract complexity level from AI response"""
        complexity_match = re.search(r'Complexity Level:\s*(\w+)', response, re.IGNORECASE)
        if complexity_match:
            return complexity_match.group(1).lower()
        return "intermediate"

    def _extract_task_type_from_response(self, response: str) -> str:
        """Extract task type from AI response"""
        task_match = re.search(r'Task Type:\s*(\w+)', response, re.IGNORECASE)
        if task_match:
            return task_match.group(1).lower()
        return "general"

    def _extract_languages_from_response(self, response: str) -> List[str]:
        """Extract language requirements from AI response"""
        lang_match = re.search(r'Language Requirements:\s*\[(.*?)\]', response, re.IGNORECASE)
        if lang_match:
            langs_text = lang_match.group(1)
            return [lang.strip().strip('"\'') for lang in langs_text.split(',')]
        return ["japanese"]

    def _extract_time_sensitivity_from_response(self, response: str) -> str:
        """Extract time sensitivity from AI response"""
        time_match = re.search(r'Time Sensitivity:\s*(\w+)', response, re.IGNORECASE)
        if time_match:
            return time_match.group(1).lower()
        return "normal"

    def _extract_tools_from_response(self, response: str) -> List[str]:
        """Extract special tools from AI response"""
        tools_match = re.search(r'Special Tools:\s*\[(.*?)\]', response, re.IGNORECASE)
        if tools_match:
            tools_text = tools_match.group(1)
            return [tool.strip().strip('"\'') for tool in tools_text.split(',')]
        return []

    async def get_recommended_jobs(self, jobs: List[Dict], max_results: int = 10) -> List[JobMatch]:
        """
        Get recommended jobs based on matching analysis

        Args:
            jobs: List of job dictionaries
            max_results: Maximum number of recommendations

        Returns:
            List of JobMatch objects sorted by match quality
        """
        try:
            job_matches = []

            for job in jobs:
                match = await self.analyze_job(job)
                if match.match_result != MatchResult.NO_MATCH:
                    job_matches.append(match)

            # Sort by confidence score (descending)
            job_matches.sort(key=lambda x: x.confidence_score, reverse=True)

            return job_matches[:max_results]

        except Exception as e:
            logger.error(f"Error getting job recommendations: {str(e)}")
            return []

    def update_capabilities(self, new_skills: List[str] = None, new_tools: List[str] = None):
        """Update agent capabilities dynamically"""
        if new_skills:
            self.agent_capabilities.core_skills.extend(new_skills)
            logger.info(f"Added new skills: {new_skills}")

        if new_tools:
            self.agent_capabilities.tools.extend(new_tools)
            logger.info(f"Added new tools: {new_tools}")