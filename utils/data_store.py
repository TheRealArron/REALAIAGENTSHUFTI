"""Simple data storage for job data and agent state."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

from config.settings import settings
from config.constants import JobStatus
from utils.logger import log_info, log_error, log_debug


@dataclass
class JobData:
    """Data structure for job information."""
    job_id: str
    title: str
    description: str
    url: str
    price: Optional[str] = None
    deadline: Optional[str] = None
    category: Optional[str] = None
    status: JobStatus = JobStatus.DISCOVERED
    discovered_at: str = None
    applied_at: Optional[str] = None
    client_name: Optional[str] = None
    requirements: List[str] = None
    tags: List[str] = None
    match_score: Optional[float] = None
    application_message: Optional[str] = None
    communication_history: List[Dict] = None
    work_progress: Optional[Dict] = None
    completed_at: Optional[str] = None

    def __post_init__(self):
        if self.discovered_at is None:
            self.discovered_at = datetime.now(timezone.utc).isoformat()
        if self.requirements is None:
            self.requirements = []
        if self.tags is None:
            self.tags = []
        if self.communication_history is None:
            self.communication_history = []

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'JobData':
        """Create from dictionary."""
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = JobStatus(data['status'])
        return cls(**data)

    def update_status(self, new_status: JobStatus):
        """Update job status with timestamp."""
        old_status = self.status
        self.status = new_status

        # Add status change to communication history
        self.communication_history.append({
            'type': 'status_change',
            'old_status': old_status.value,
            'new_status': new_status.value,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

        # Set specific timestamps
        if new_status == JobStatus.APPLIED:
            self.applied_at = datetime.now(timezone.utc).isoformat()
        elif new_status == JobStatus.COMPLETED:
            self.completed_at = datetime.now(timezone.utc).isoformat()

    def add_communication(self, message_type: str, content: str, sender: str = 'agent'):
        """Add communication record."""
        self.communication_history.append({
            'type': message_type,
            'sender': sender,
            'content': content,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })


class DataStore:
    """Thread-safe data storage for jobs and agent state."""

    def __init__(self, data_file: Path = None):
        self.data_file = data_file or settings.JOBS_DATA_FILE
        self.lock = threading.RLock()
        self._jobs: Dict[str, JobData] = {}
        self._metadata = {
            'last_updated': None,
            'total_jobs_discovered': 0,
            'total_jobs_applied': 0,
            'total_jobs_completed': 0,
            'agent_start_time': datetime.now(timezone.utc).isoformat()
        }
        self.load_data()

    def load_data(self):
        """Load data from file."""
        with self.lock:
            try:
                if self.data_file.exists():
                    with open(self.data_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Load jobs
                    jobs_data = data.get('jobs', {})
                    self._jobs = {
                        job_id: JobData.from_dict(job_data)
                        for job_id, job_data in jobs_data.items()
                    }

                    # Load metadata
                    self._metadata.update(data.get('metadata', {}))

                    log_info(f"Loaded {len(self._jobs)} jobs from storage")
                else:
                    log_info("No existing data file found, starting fresh")

            except Exception as e:
                log_error(f"Failed to load data from {self.data_file}", error=str(e))
                self._jobs = {}

    def save_data(self):
        """Save data to file."""
        with self.lock:
            try:
                # Ensure directory exists
                self.data_file.parent.mkdir(parents=True, exist_ok=True)

                # Prepare data for serialization
                data = {
                    'jobs': {
                        job_id: job.to_dict()
                        for job_id, job in self._jobs.items()
                    },
                    'metadata': self._metadata
                }

                # Update metadata
                data['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat()
                data['metadata']['total_jobs_discovered'] = len(self._jobs)
                data['metadata']['total_jobs_applied'] = len([
                    j for j in self._jobs.values()
                    if j.status.value in ['applied', 'in_progress', 'communicating', 'delivering', 'completed']
                ])
                data['metadata']['total_jobs_completed'] = len([
                    j for j in self._jobs.values()
                    if j.status == JobStatus.COMPLETED
                ])

                # Write to file
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                log_debug(f"Saved {len(self._jobs)} jobs to storage")

            except Exception as e:
                log_error(f"Failed to save data to {self.data_file}", error=str(e))

    def add_job(self, job: JobData) -> bool:
        """Add a new job."""
        with self.lock:
            if job.job_id in self._jobs:
                log_debug(f"Job {job.job_id} already exists, skipping")
                return False

            self._jobs[job.job_id] = job
            self.save_data()
            log_info(f"Added new job: {job.job_id} - {job.title}")
            return True

    def get_job(self, job_id: str) -> Optional[JobData]:
        """Get job by ID."""
        with self.lock:
            return self._jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs) -> bool:
        """Update job data."""
        with self.lock:
            if job_id not in self._jobs:
                log_error(f"Job {job_id} not found for update")
                return False

            job = self._jobs[job_id]
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)

            self.save_data()
            log_debug(f"Updated job {job_id}")
            return True

    def update_job_status(self, job_id: str, new_status: JobStatus) -> bool:
        """Update job status."""
        with self.lock:
            if job_id not in self._jobs:
                log_error(f"Job {job_id} not found for status update")
                return False

            old_status = self._jobs[job_id].status
            self._jobs[job_id].update_status(new_status)
            self.save_data()

            log_info(f"Job {job_id} status: {old_status.value} -> {new_status.value}")
            return True

    def get_jobs_by_status(self, status: JobStatus) -> List[JobData]:
        """Get all jobs with specific status."""
        with self.lock:
            return [job for job in self._jobs.values() if job.status == status]

    def get_jobs_by_statuses(self, statuses: List[JobStatus]) -> List[JobData]:
        """Get jobs with any of the specified statuses."""
        with self.lock:
            return [job for job in self._jobs.values() if job.status in statuses]

    def get_all_jobs(self) -> List[JobData]:
        """Get all jobs."""
        with self.lock:
            return list(self._jobs.values())

    def get_jobs_summary(self) -> Dict[str, int]:
        """Get summary of jobs by status."""
        with self.lock:
            summary = {}
            for status in JobStatus:
                summary[status.value] = len([
                    job for job in self._jobs.values()
                    if job.status == status
                ])
            return summary

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        with self.lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                self.save_data()
                log_info(f"Deleted job {job_id}")
                return True
            return False

    def cleanup_old_jobs(self, days: int = 30):
        """Remove jobs older than specified days."""
        with self.lock:
            cutoff_date = datetime.now(timezone.utc).timestamp() - (days * 24 * 3600)
            jobs_to_delete = []

            for job_id, job in self._jobs.items():
                try:
                    job_date = datetime.fromisoformat(job.discovered_at.replace('Z', '+00:00'))
                    if job_date.timestamp() < cutoff_date and job.status in [JobStatus.COMPLETED, JobStatus.REJECTED,
                                                                             JobStatus.FAILED]:
                        jobs_to_delete.append(job_id)
                except Exception as e:
                    log_error(f"Error parsing date for job {job_id}", error=str(e))

            for job_id in jobs_to_delete:
                del self._jobs[job_id]

            if jobs_to_delete:
                self.save_data()
                log_info(f"Cleaned up {len(jobs_to_delete)} old jobs")

    def export_data(self, export_file: Path) -> bool:
        """Export data to a different file."""
        with self.lock:
            try:
                data = {
                    'jobs': {
                        job_id: job.to_dict()
                        for job_id, job in self._jobs.items()
                    },
                    'metadata': self._metadata,
                    'export_timestamp': datetime.now(timezone.utc).isoformat()
                }

                with open(export_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                log_info(f"Exported data to {export_file}")
                return True

            except Exception as e:
                log_error(f"Failed to export data to {export_file}", error=str(e))
                return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics."""
        with self.lock:
            stats = {
                'total_jobs': len(self._jobs),
                'status_breakdown': self.get_jobs_summary(),
                'metadata': self._metadata.copy()
            }

            # Calculate additional metrics
            if self._jobs:
                completed_jobs = [j for j in self._jobs.values() if j.status == JobStatus.COMPLETED]
                applied_jobs = [j for j in self._jobs.values() if j.applied_at]

                stats['completion_rate'] = len(completed_jobs) / len(applied_jobs) if applied_jobs else 0
                stats['average_match_score'] = sum(j.match_score for j in self._jobs.values() if j.match_score) / len(
                    [j for j in self._jobs.values() if j.match_score]) if any(
                    j.match_score for j in self._jobs.values()) else 0
            else:
                stats['completion_rate'] = 0
                stats['average_match_score'] = 0

            return stats


# Global data store instance
data_store = DataStore()