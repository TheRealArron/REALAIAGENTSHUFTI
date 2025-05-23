"""Agent memory and state management."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field
from enum import Enum

from config.settings import settings
from config.constants import WorkflowState, JobStatus
from utils.logger import log_info, log_error, log_debug, log_workflow_state


@dataclass
class AgentCapabilities:
    """Agent's capabilities and skills."""
    skills: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=lambda: ['Japanese', 'English'])
    categories: List[str] = field(default_factory=list)
    experience_level: str = 'intermediate'
    max_concurrent_jobs: int = 3
    preferred_job_types: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.skills:
            self.skills = [
                'web_development', 'data_entry', 'translation',
                'writing', 'research', 'content_creation'
            ]
        if not self.categories:
            self.categories = [
                'web_development', 'data_entry', 'translation',
                'writing', 'design'
            ]
        if not self.preferred_job_types:
            self.preferred_job_types = [
                'short_term', 'fixed_price', 'remote'
            ]


@dataclass
class AgentPerformance:
    """Agent performance metrics."""
    jobs_discovered: int = 0
    jobs_applied: int = 0
    jobs_accepted: int = 0
    jobs_completed: int = 0
    jobs_rejected: int = 0
    average_completion_time: float = 0.0
    success_rate: float = 0.0
    client_satisfaction: float = 0.0
    earnings_total: float = 0.0
    last_activity: Optional[str] = None

    def update_metrics(self, job_data: Dict[str, Any]):
        """Update performance metrics based on job data."""
        self.last_activity = datetime.now(timezone.utc).isoformat()

        # Update counters based on job status changes
        if job_data.get('event') == 'job_discovered':
            self.jobs_discovered += 1
        elif job_data.get('event') == 'job_applied':
            self.jobs_applied += 1
        elif job_data.get('event') == 'job_accepted':
            self.jobs_accepted += 1
        elif job_data.get('event') == 'job_completed':
            self.jobs_completed += 1
            if 'earnings' in job_data:
                self.earnings_total += float(job_data['earnings'])
        elif job_data.get('event') == 'job_rejected':
            self.jobs_rejected += 1

        # Calculate success rate
        if self.jobs_applied > 0:
            self.success_rate = self.jobs_accepted / self.jobs_applied


@dataclass
class WorkflowContext:
    """Current workflow context and state."""
    current_state: WorkflowState = WorkflowState.IDLE
    previous_state: Optional[WorkflowState] = None
    state_changed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    current_job_id: Optional[str] = None
    active_jobs: List[str] = field(default_factory=list)
    pending_actions: List[Dict] = field(default_factory=list)
    error_count: int = 0
    last_error: Optional[str] = None
    session_start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def change_state(self, new_state: WorkflowState, reason: str = None):
        """Change workflow state with logging."""
        old_state = self.current_state
        self.previous_state = old_state
        self.current_state = new_state
        self.state_changed_at = datetime.now(timezone.utc).isoformat()

        log_workflow_state(old_state.value, new_state.value, reason)

    def add_pending_action(self, action_type: str, data: Dict[str, Any]):
        """Add a pending action to the queue."""
        self.pending_actions.append({
            'type': action_type,
            'data': data,
            'created_at': datetime.now(timezone.utc).isoformat()
        })

    def get_next_action(self) -> Optional[Dict]:
        """Get and remove the next pending action."""
        if self.pending_actions:
            return self.pending_actions.pop(0)
        return None

    def record_error(self, error_message: str):
        """Record an error occurrence."""
        self.error_count += 1
        self.last_error = error_message


class AgentMemory:
    """Centralized agent memory and state management."""

    def __init__(self, memory_file: Path = None):
        self.memory_file = memory_file or settings.MEMORY_FILE
        self.lock = threading.RLock()

        # Core components
        self.capabilities = AgentCapabilities()
        self.performance = AgentPerformance()
        self.workflow = WorkflowContext()

        # Session data
        self.session_data: Dict[str, Any] = {}
        self.learned_patterns: Dict[str, Any] = {}
        self.client_interactions: Dict[str, List[Dict]] = {}

        # Load existing memory
        self.load_memory()

    def load_memory(self):
        """Load memory from file."""
        with self.lock:
            try:
                if self.memory_file.exists():
                    with open(self.memory_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Load capabilities
                    if 'capabilities' in data:
                        cap_data = data['capabilities']
                        self.capabilities = AgentCapabilities(**cap_data)

                    # Load performance metrics
                    if 'performance' in data:
                        perf_data = data['performance']
                        self.performance = AgentPerformance(**perf_data)

                    # Load workflow context (but reset current state)
                    if 'workflow' in data:
                        workflow_data = data['workflow']
                        # Don't restore current state - start fresh
                        workflow_data['current_state'] = WorkflowState.IDLE.value
                        workflow_data['current_job_id'] = None
                        workflow_data['active_jobs'] = []
                        workflow_data['pending_actions'] = []
                        self.workflow = WorkflowContext(**workflow_data)

                    # Load other data
                    self.session_data = data.get('session_data', {})
                    self.learned_patterns = data.get('learned_patterns', {})
                    self.client_interactions = data.get('client_interactions', {})

                    log_info("Loaded agent memory from storage")
                else:
                    log_info("No existing memory file found, starting fresh")

            except Exception as e:
                log_error(f"Failed to load memory from {self.memory_file}", error=str(e))

    def save_memory(self):
        """Save memory to file."""
        with self.lock:
            try:
                # Ensure directory exists
                self.memory_file.parent.mkdir(parents=True, exist_ok=True)

                # Convert workflow state enum to string
                workflow_data = asdict(self.workflow)
                workflow_data['current_state'] = self.workflow.current_state.value
                if self.workflow.previous_state:
                    workflow_data['previous_state'] = self.workflow.previous_state.value

                data = {
                    'capabilities': asdict(self.capabilities),
                    'performance': asdict(self.performance),
                    'workflow': workflow_data,
                    'session_data': self.session_data,
                    'learned_patterns': self.learned_patterns,
                    'client_interactions': self.client_interactions,
                    'last_saved': datetime.now(timezone.utc).isoformat()
                }

                with open(self.memory_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                log_debug("Saved agent memory to storage")

            except Exception as e:
                log_error(f"Failed to save memory to {self.memory_file}", error=str(e))

    def update_capabilities(self, **kwargs):
        """Update agent capabilities."""
        with self.lock:
            for key, value in kwargs.items():
                if hasattr(self.capabilities, key):
                    setattr(self.capabilities, key, value)
            self.save_memory()
            log_debug("Updated agent capabilities")

    def record_performance_event(self, event_type: str, job_data: Dict[str, Any] = None):
        """Record a performance-related event."""
        with self.lock:
            event_data = {'event': event_type}
            if job_data:
                event_data.update(job_data)

            self.performance.update_metrics(event_data)
            self.save_memory()
            log_debug(f"Recorded performance event: {event_type}")

    def change_workflow_state(self, new_state: WorkflowState, reason: str = None):
        """Change workflow state."""
        with self.lock:
            self.workflow.change_state(new_state, reason)
            self.save_memory()

    def get_current_state(self) -> WorkflowState:
        """Get current workflow state."""
        return self.workflow.current_state

    def is_available_for_new_jobs(self) -> bool:
        """Check if agent can take on new jobs."""
        with self.lock:
            active_count = len(self.workflow.active_jobs)
            max_concurrent = self.capabilities.max_concurrent_jobs

            return (
                    active_count < max_concurrent and
                    self.workflow.current_state in [WorkflowState.IDLE, WorkflowState.CRAWLING]
            )

    def add_active_job(self, job_id: str):
        """Add a job to active jobs list."""
        with self.lock:
            if job_id not in self.workflow.active_jobs:
                self.workflow.active_jobs.append(job_id)
                self.save_memory()
                log_debug(f"Added active job: {job_id}")

    def remove_active_job(self, job_id: str):
        """Remove a job from active jobs list."""
        with self.lock:
            if job_id in self.workflow.active_jobs:
                self.workflow.active_jobs.remove(job_id)
                if self.workflow.current_job_id == job_id:
                    self.workflow.current_job_id = None
                self.save_memory()
                log_debug(f"Removed active job: {job_id}")

    def set_current_job(self, job_id: str):
        """Set the currently active job."""
        with self.lock:
            self.workflow.current_job_id = job_id
            if job_id not in self.workflow.active_jobs:
                self.add_active_job(job_id)
            self.save_memory()

    def learn_from_interaction(self, interaction_type: str, data: Dict[str, Any]):
        """Learn from client interactions."""
        with self.lock:
            if interaction_type not in self.learned_patterns:
                self.learned_patterns[interaction_type] = []

            learning_entry = {
                'data': data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            self.learned_patterns[interaction_type].append(learning_entry)

            # Keep only recent patterns (last 100 per type)
            if len(self.learned_patterns[interaction_type]) > 100:
                self.learned_patterns[interaction_type] = self.learned_patterns[interaction_type][-100:]

            self.save_memory()
            log_debug(f"Learned from interaction: {interaction_type}")

    def record_client_interaction(self, client_id: str, interaction: Dict[str, Any]):
        """Record interaction with a specific client."""
        with self.lock:
            if client_id not in self.client_interactions:
                self.client_interactions[client_id] = []

            interaction_record = {
                **interaction,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            self.client_interactions[client_id].append(interaction_record)

            # Keep only recent interactions per client (last 50)
            if len(self.client_interactions[client_id]) > 50:
                self.client_interactions[client_id] = self.client_interactions[client_id][-50:]

            self.save_memory()

    def get_client_history(self, client_id: str) -> List[Dict]:
        """Get interaction history with a specific client."""
        return self.client_interactions.get(client_id, [])

    def get_session_data(self, key: str, default=None):
        """Get session-specific data."""
        return self.session_data.get(key, default)

    def set_session_data(self, key: str, value: Any):
        """Set session-specific data."""
        with self.lock:
            self.session_data[key] = value
            # Don't save session data immediately (it's temporary)

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        with self.lock:
            return {
                'capabilities': asdict(self.capabilities),
                'performance': asdict(self.performance),
                'current_state': self.workflow.current_state.value,
                'active_jobs_count': len(self.workflow.active_jobs),
                'error_count': self.workflow.error_count,
                'session_duration': self._calculate_session_duration()
            }

    def _calculate_session_duration(self) -> str:
        """Calculate current session duration."""
        try:
            start_time = datetime.fromisoformat(self.workflow.session_start_time.replace('Z', '+00:00'))
            duration = datetime.now(timezone.utc) - start_time
            return str(duration).split('.')[0]  # Remove microseconds
        except:
            return "Unknown"

    def reset_session(self):
        """Reset session-specific data."""
        with self.lock:
            self.workflow.current_state = WorkflowState.IDLE
            self.workflow.current_job_id = None
            self.workflow.active_jobs = []
            self.workflow.pending_actions = []
            self.workflow.session_start_time = datetime.now(timezone.utc).isoformat()
            self.session_data = {}
            self.save_memory()
            log_info("Reset agent session")


# Global memory instance
agent_memory = AgentMemory()