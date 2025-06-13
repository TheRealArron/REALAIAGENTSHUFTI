"""
Agent Memory Management System

This module handles the persistent memory and state management for the Shufti agent,
including job history, user preferences, and workflow states.
"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum

from utils.logger import log_info, log_error, log_warning
from config.constants import MAX_MEMORY_ENTRIES, MEMORY_RETENTION_DAYS


class JobStatus(Enum):
    """Job application and processing status"""
    DISCOVERED = "discovered"
    MATCHED = "matched"
    APPLIED = "applied"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class JobMemory:
    """Memory entry for a specific job"""
    job_id: str
    title: str
    company: str
    url: str
    status: JobStatus
    applied_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    payment_amount: Optional[float] = None
    notes: str = ""
    communication_history: List[Dict] = None
    task_details: Dict = None

    def __post_init__(self):
        if self.communication_history is None:
            self.communication_history = []
        if self.task_details is None:
            self.task_details = {}


@dataclass
class UserPreferences:
    """User preferences and settings"""
    preferred_job_types: List[str] = None
    minimum_payment: float = 0.0
    maximum_daily_applications: int = 10
    working_hours: Dict[str, str] = None
    blacklisted_companies: Set[str] = None
    keywords_to_avoid: Set[str] = None
    preferred_keywords: Set[str] = None

    def __post_init__(self):
        if self.preferred_job_types is None:
            self.preferred_job_types = []
        if self.working_hours is None:
            self.working_hours = {"start": "09:00", "end": "18:00"}
        if self.blacklisted_companies is None:
            self.blacklisted_companies = set()
        if self.keywords_to_avoid is None:
            self.keywords_to_avoid = set()
        if self.preferred_keywords is None:
            self.preferred_keywords = set()


@dataclass
class SessionStats:
    """Statistics for current session"""
    jobs_discovered: int = 0
    jobs_applied: int = 0
    jobs_completed: int = 0
    total_earnings: float = 0.0
    session_start: datetime = None
    last_activity: datetime = None

    def __post_init__(self):
        if self.session_start is None:
            self.session_start = datetime.now()
        if self.last_activity is None:
            self.last_activity = datetime.now()


class AgentMemory:
    """
    Centralized memory management for the Shufti agent

    Handles:
    - Job application history
    - User preferences
    - Session statistics
    - Workflow states
    - Communication history
    """

    def __init__(self, memory_file: str = "agent_memory.json"):
        self.memory_file = Path(memory_file)  # Convert to Path object
        self.lock = threading.RLock()

        # Initialize memory components
        self.jobs: Dict[str, JobMemory] = {}
        self.preferences = UserPreferences()
        self.session_stats = SessionStats()
        self.workflow_states: Dict[str, Any] = {}
        self.communication_log: List[Dict] = []

        # Load existing memory
        self.load_memory()

        log_info(f"Agent memory initialized with {len(self.jobs)} job records")

    def load_memory(self):
        """Load memory from persistent storage"""
        try:
            if self.memory_file.exists():
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Load jobs
                if 'jobs' in data:
                    for job_id, job_data in data['jobs'].items():
                        # Convert datetime strings back to datetime objects
                        if job_data.get('applied_at'):
                            job_data['applied_at'] = datetime.fromisoformat(job_data['applied_at'])
                        if job_data.get('completed_at'):
                            job_data['completed_at'] = datetime.fromisoformat(job_data['completed_at'])

                        # Convert status string to enum
                        if 'status' in job_data:
                            job_data['status'] = JobStatus(job_data['status'])

                        self.jobs[job_id] = JobMemory(**job_data)

                # Load preferences
                if 'preferences' in data:
                    pref_data = data['preferences']
                    # Convert sets stored as lists back to sets
                    for key in ['blacklisted_companies', 'keywords_to_avoid', 'preferred_keywords']:
                        if key in pref_data and isinstance(pref_data[key], list):
                            pref_data[key] = set(pref_data[key])
                    self.preferences = UserPreferences(**pref_data)

                # Load session stats
                if 'session_stats' in data:
                    stats_data = data['session_stats']
                    if stats_data.get('session_start'):
                        stats_data['session_start'] = datetime.fromisoformat(stats_data['session_start'])
                    if stats_data.get('last_activity'):
                        stats_data['last_activity'] = datetime.fromisoformat(stats_data['last_activity'])
                    self.session_stats = SessionStats(**stats_data)

                # Load other data
                self.workflow_states = data.get('workflow_states', {})
                self.communication_log = data.get('communication_log', [])

                log_info("Memory loaded successfully")
            else:
                log_info("No existing memory file found, starting fresh")

        except Exception as e:
            log_error(f"Failed to load memory from {self.memory_file}: {str(e)}")
            log_warning("Starting with empty memory")

    def save_memory(self):
        """Save memory to persistent storage"""
        with self.lock:
            try:
                # Prepare data for JSON serialization
                data = {
                    'jobs': {},
                    'preferences': asdict(self.preferences),
                    'session_stats': asdict(self.session_stats),
                    'workflow_states': self.workflow_states,
                    'communication_log': self.communication_log[-1000:],  # Keep last 1000 messages
                    'saved_at': datetime.now().isoformat()
                }

                # Convert jobs to serializable format
                for job_id, job in self.jobs.items():
                    job_dict = asdict(job)
                    # Convert datetime objects to ISO format strings
                    if job_dict.get('applied_at'):
                        job_dict['applied_at'] = job_dict['applied_at'].isoformat()
                    if job_dict.get('completed_at'):
                        job_dict['completed_at'] = job_dict['completed_at'].isoformat()
                    # Convert enum to string
                    if 'status' in job_dict:
                        job_dict['status'] = job_dict['status'].value
                    data['jobs'][job_id] = job_dict

                # Convert sets to lists for JSON serialization
                pref_data = data['preferences']
                for key in ['blacklisted_companies', 'keywords_to_avoid', 'preferred_keywords']:
                    if key in pref_data and isinstance(pref_data[key], set):
                        pref_data[key] = list(pref_data[key])

                # Convert session stats datetime objects
                stats_data = data['session_stats']
                if stats_data.get('session_start'):
                    stats_data['session_start'] = stats_data['session_start'].isoformat()
                if stats_data.get('last_activity'):
                    stats_data['last_activity'] = stats_data['last_activity'].isoformat()

                # Write to file
                with open(self.memory_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                log_info(f"Memory saved to {self.memory_file}")

            except Exception as e:
                log_error(f"Failed to save memory: {str(e)}")

    def add_job(self, job_memory: JobMemory):
        """Add or update a job in memory"""
        with self.lock:
            self.jobs[job_memory.job_id] = job_memory
            self.session_stats.last_activity = datetime.now()

            if job_memory.status == JobStatus.DISCOVERED:
                self.session_stats.jobs_discovered += 1
            elif job_memory.status == JobStatus.APPLIED:
                self.session_stats.jobs_applied += 1
            elif job_memory.status == JobStatus.COMPLETED:
                self.session_stats.jobs_completed += 1
                if job_memory.payment_amount:
                    self.session_stats.total_earnings += job_memory.payment_amount

            self.save_memory()

    def get_job(self, job_id: str) -> Optional[JobMemory]:
        """Retrieve a job from memory"""
        return self.jobs.get(job_id)

    def update_job_status(self, job_id: str, status: JobStatus, notes: str = ""):
        """Update job status"""
        with self.lock:
            if job_id in self.jobs:
                old_status = self.jobs[job_id].status
                self.jobs[job_id].status = status
                self.jobs[job_id].notes = notes
                self.session_stats.last_activity = datetime.now()

                if status == JobStatus.APPLIED and old_status != JobStatus.APPLIED:
                    self.jobs[job_id].applied_at = datetime.now()
                    self.session_stats.jobs_applied += 1
                elif status == JobStatus.COMPLETED and old_status != JobStatus.COMPLETED:
                    self.jobs[job_id].completed_at = datetime.now()
                    self.session_stats.jobs_completed += 1

                self.save_memory()
                log_info(f"Updated job {job_id} status: {old_status.value} -> {status.value}")

    def get_jobs_by_status(self, status: JobStatus) -> List[JobMemory]:
        """Get all jobs with a specific status"""
        return [job for job in self.jobs.values() if job.status == status]

    def get_recent_jobs(self, days: int = 7) -> List[JobMemory]:
        """Get jobs from the last N days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        return [
            job for job in self.jobs.values()
            if job.applied_at and job.applied_at > cutoff_date
        ]

    def is_job_blacklisted(self, company: str, title: str) -> bool:
        """Check if a job should be avoided"""
        # Check company blacklist
        if company.lower() in {c.lower() for c in self.preferences.blacklisted_companies}:
            return True

        # Check keywords to avoid
        title_lower = title.lower()
        for keyword in self.preferences.keywords_to_avoid:
            if keyword.lower() in title_lower:
                return True

        return False

    def should_apply_to_job(self, job_details: Dict) -> bool:
        """Determine if agent should apply to a job based on preferences"""
        # Check payment threshold
        payment = job_details.get('payment', 0)
        if payment < self.preferences.minimum_payment:
            return False

        # Check daily application limit
        today_applications = len([
            job for job in self.jobs.values()
            if job.applied_at and job.applied_at.date() == datetime.now().date()
        ])
        if today_applications >= self.preferences.maximum_daily_applications:
            return False

        # Check if already applied
        job_id = job_details.get('id')
        if job_id and job_id in self.jobs:
            return False

        # Check blacklist
        company = job_details.get('company', '')
        title = job_details.get('title', '')
        if self.is_job_blacklisted(company, title):
            return False

        return True

    def add_communication(self, job_id: str, message_type: str, content: str, timestamp: datetime = None):
        """Add communication entry for a job"""
        if timestamp is None:
            timestamp = datetime.now()

        with self.lock:
            communication_entry = {
                'job_id': job_id,
                'type': message_type,
                'content': content,
                'timestamp': timestamp.isoformat()
            }

            self.communication_log.append(communication_entry)

            # Also add to specific job's communication history
            if job_id in self.jobs:
                self.jobs[job_id].communication_history.append(communication_entry)

            self.save_memory()

    def get_job_communications(self, job_id: str) -> List[Dict]:
        """Get all communications for a specific job"""
        return [
            comm for comm in self.communication_log
            if comm.get('job_id') == job_id
        ]

    def cleanup_old_data(self):
        """Remove old data to prevent memory bloat"""
        with self.lock:
            cutoff_date = datetime.now() - timedelta(days=MEMORY_RETENTION_DAYS)

            # Remove old jobs
            old_job_ids = [
                job_id for job_id, job in self.jobs.items()
                if job.completed_at and job.completed_at < cutoff_date
            ]

            for job_id in old_job_ids:
                del self.jobs[job_id]

            # Clean up communication log
            self.communication_log = [
                comm for comm in self.communication_log
                if datetime.fromisoformat(comm['timestamp']) > cutoff_date
            ]

            if old_job_ids:
                log_info(f"Cleaned up {len(old_job_ids)} old job records")
                self.save_memory()

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory statistics"""
        return {
            'total_jobs': len(self.jobs),
            'jobs_by_status': {
                status.value: len(self.get_jobs_by_status(status))
                for status in JobStatus
            },
            'session_stats': asdict(self.session_stats),
            'total_communications': len(self.communication_log),
            'memory_file_size': self.memory_file.stat().st_size if self.memory_file.exists() else 0
        }


# Global memory instance
agent_memory = AgentMemory()


def get_memory() -> AgentMemory:
    """Get the global agent memory instance"""
    return agent_memory


# Convenience functions for external modules
def remember_job(job_memory: JobMemory):
    """Add a job to memory"""
    agent_memory.add_job(job_memory)


def recall_job(job_id: str) -> Optional[JobMemory]:
    """Retrieve a job from memory"""
    return agent_memory.get_job(job_id)


def update_job_memory(job_id: str, status: JobStatus, notes: str = ""):
    """Update job status in memory"""
    agent_memory.update_job_status(job_id, status, notes)


def log_communication(job_id: str, message_type: str, content: str):
    """Log a communication entry"""
    agent_memory.add_communication(job_id, message_type, content)


def should_apply(job_details: Dict) -> bool:
    """Check if we should apply to a job"""
    return agent_memory.should_apply_to_job(job_details)