"""
Workflow Manager for the Shufti Agent.
Manages job workflow states and orchestrates the entire process.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
import json

from utils.data_store import DataStore
from utils.logger import get_logger
from core.memory import AgentMemory

logger = get_logger(__name__)


class WorkflowState(Enum):
    """Job workflow states."""
    IDLE = "idle"
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    APPLYING = "applying"
    WAITING_RESPONSE = "waiting_response"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMMUNICATING = "communicating"
    DELIVERING = "delivering"
    SUBMITTED = "submitted"
    REVISION_REQUESTED = "revision_requested"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowTransition:
    """Represents a workflow state transition."""

    def __init__(self, from_state: WorkflowState, to_state: WorkflowState,
                 condition: Optional[Callable] = None, action: Optional[Callable] = None):
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition
        self.action = action


class WorkflowManager:
    """Manages the workflow states and transitions for jobs."""

    def __init__(self, data_store: DataStore, memory: AgentMemory):
        self.data_store = data_store
        self.memory = memory
        self.logger = logging.getLogger(__name__)

        # Active jobs and their states
        self.active_jobs: Dict[str, WorkflowState] = {}
        self.job_contexts: Dict[str, Dict[str, Any]] = {}

        # Workflow transitions
        self.transitions = self._setup_transitions()

        # Event handlers
        self.state_handlers: Dict[WorkflowState, List[Callable]] = {}
        self.transition_handlers: List[Callable] = []

        # Monitoring
        self.max_concurrent_jobs = 5
        self.job_timeout_hours = 24

    def _setup_transitions(self) -> List[WorkflowTransition]:
        """Setup valid workflow transitions."""
        return [
            # From IDLE
            WorkflowTransition(WorkflowState.IDLE, WorkflowState.SEARCHING),

            # From SEARCHING
            WorkflowTransition(WorkflowState.SEARCHING, WorkflowState.ANALYZING),
            WorkflowTransition(WorkflowState.SEARCHING, WorkflowState.IDLE),

            # From ANALYZING
            WorkflowTransition(WorkflowState.ANALYZING, WorkflowState.APPLYING),
            WorkflowTransition(WorkflowState.ANALYZING, WorkflowState.SEARCHING),
            WorkflowTransition(WorkflowState.ANALYZING, WorkflowState.IDLE),

            # From APPLYING
            WorkflowTransition(WorkflowState.APPLYING, WorkflowState.WAITING_RESPONSE),
            WorkflowTransition(WorkflowState.APPLYING, WorkflowState.FAILED),

            # From WAITING_RESPONSE
            WorkflowTransition(WorkflowState.WAITING_RESPONSE, WorkflowState.ACCEPTED),
            WorkflowTransition(WorkflowState.WAITING_RESPONSE, WorkflowState.FAILED),
            WorkflowTransition(WorkflowState.WAITING_RESPONSE, WorkflowState.CANCELLED),

            # From ACCEPTED
            WorkflowTransition(WorkflowState.ACCEPTED, WorkflowState.IN_PROGRESS),

            # From IN_PROGRESS
            WorkflowTransition(WorkflowState.IN_PROGRESS, WorkflowState.COMMUNICATING),
            WorkflowTransition(WorkflowState.IN_PROGRESS, WorkflowState.DELIVERING),
            WorkflowTransition(WorkflowState.IN_PROGRESS, WorkflowState.FAILED),

            # From COMMUNICATING
            WorkflowTransition(WorkflowState.COMMUNICATING, WorkflowState.IN_PROGRESS),
            WorkflowTransition(WorkflowState.COMMUNICATING, WorkflowState.DELIVERING),

            # From DELIVERING
            WorkflowTransition(WorkflowState.DELIVERING, WorkflowState.SUBMITTED),
            WorkflowTransition(WorkflowState.DELIVERING, WorkflowState.FAILED),

            # From SUBMITTED
            WorkflowTransition(WorkflowState.SUBMITTED, WorkflowState.REVISION_REQUESTED),
            WorkflowTransition(WorkflowState.SUBMITTED, WorkflowState.COMPLETED),
            WorkflowTransition(WorkflowState.SUBMITTED, WorkflowState.FAILED),

            # From REVISION_REQUESTED
            WorkflowTransition(WorkflowState.REVISION_REQUESTED, WorkflowState.IN_PROGRESS),
            WorkflowTransition(WorkflowState.REVISION_REQUESTED, WorkflowState.FAILED),

            # Terminal states can transition to IDLE for cleanup
            WorkflowTransition(WorkflowState.COMPLETED, WorkflowState.IDLE),
            WorkflowTransition(WorkflowState.FAILED, WorkflowState.IDLE),
            WorkflowTransition(WorkflowState.CANCELLED, WorkflowState.IDLE),
        ]

    async def start_job_workflow(self, job_data: Dict[str, Any]) -> str:
        """Start a new job workflow."""
        job_id = job_data.get("id") or f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if len(self.active_jobs) >= self.max_concurrent_jobs:
            raise Exception(f"Maximum concurrent jobs ({self.max_concurrent_jobs}) reached")

        # Initialize job state
        self.active_jobs[job_id] = WorkflowState.IDLE
        self.job_contexts[job_id] = {
            "job_data": job_data,
            "start_time": datetime.now(),
            "last_update": datetime.now(),
            "history": [],
            "error_count": 0,
            "retry_count": 0
        }

        # Store in data store
        await self.data_store.store_job(job_id, {
            **job_data,
            "workflow_state": WorkflowState.IDLE.value,
            "start_time": datetime.now().isoformat()
        })

        self.logger.info(f"Started workflow for job {job_id}")
        return job_id

    async def transition_job(self, job_id: str, new_state: WorkflowState,
                             context: Optional[Dict[str, Any]] = None) -> bool:
        """Transition a job to a new state."""
        if job_id not in self.active_jobs:
            self.logger.error(f"Job {job_id} not found in active jobs")
            return False

        current_state = self.active_jobs[job_id]

        # Check if transition is valid
        if not self._is_valid_transition(current_state, new_state):
            self.logger.error(f"Invalid transition from {current_state} to {new_state} for job {job_id}")
            return False

        # Execute transition
        try:
            # Update state
            old_state = self.active_jobs[job_id]
            self.active_jobs[job_id] = new_state

            # Update context
            if context:
                self.job_contexts[job_id].update(context)

            self.job_contexts[job_id]["last_update"] = datetime.now()
            self.job_contexts[job_id]["history"].append({
                "from_state": old_state.value,
                "to_state": new_state.value,
                "timestamp": datetime.now().isoformat(),
                "context": context or {}
            })

            # Update data store
            await self.data_store.update_job(job_id, {
                "workflow_state": new_state.value,
                "last_update": datetime.now().isoformat(),
                "workflow_history": self.job_contexts[job_id]["history"]
            })

            # Execute state handlers
            await self._execute_state_handlers(job_id, new_state)

            # Execute transition handlers
            await self._execute_transition_handlers(job_id, old_state, new_state)

            self.logger.info(f"Job {job_id} transitioned from {old_state} to {new_state}")
            return True

        except Exception as e:
            self.logger.error(f"Error transitioning job {job_id}: {str(e)}")
            return False

    def _is_valid_transition(self, from_state: WorkflowState, to_state: WorkflowState) -> bool:
        """Check if a state transition is valid."""
        for transition in self.transitions:
            if transition.from_state == from_state and transition.to_state == to_state:
                return True
        return False

    async def _execute_state_handlers(self, job_id: str, state: WorkflowState):
        """Execute handlers for entering a state."""
        if state in self.state_handlers:
            for handler in self.state_handlers[state]:
                try:
                    await handler(job_id, self.job_contexts[job_id])
                except Exception as e:
                    self.logger.error(f"Error in state handler for {state}: {str(e)}")

    async def _execute_transition_handlers(self, job_id: str, from_state: WorkflowState, to_state: WorkflowState):
        """Execute transition handlers."""
        for handler in self.transition_handlers:
            try:
                await handler(job_id, from_state, to_state, self.job_contexts[job_id])
            except Exception as e:
                self.logger.error(f"Error in transition handler: {str(e)}")

    def register_state_handler(self, state: WorkflowState, handler: Callable):
        """Register a handler for a specific state."""
        if state not in self.state_handlers:
            self.state_handlers[state] = []
        self.state_handlers[state].append(handler)

    def register_transition_handler(self, handler: Callable):
        """Register a handler for state transitions."""
        self.transition_handlers.append(handler)

    async def get_job_state(self, job_id: str) -> Optional[WorkflowState]:
        """Get current state of a job."""
        return self.active_jobs.get(job_id)

    async def get_job_context(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job context."""
        return self.job_contexts.get(job_id)

    async def get_active_jobs(self) -> Dict[str, WorkflowState]:
        """Get all active jobs and their states."""
        return self.active_jobs.copy()

    async def complete_job(self, job_id: str, result: Dict[str, Any]):
        """Mark a job as completed."""
        await self.transition_job(job_id, WorkflowState.COMPLETED, {
            "completion_result": result,
            "completion_time": datetime.now()
        })

        # Clean up after a delay
        asyncio.create_task(self._cleanup_job_after_delay(job_id, 3600))  # 1 hour

    async def fail_job(self, job_id: str, error: str, retry: bool = True):
        """Mark a job as failed."""
        context = self.job_contexts.get(job_id, {})
        context["error_count"] = context.get("error_count", 0) + 1
        context["last_error"] = error
        context["last_error_time"] = datetime.now()

        if retry and context["error_count"] < 3:
            # Retry logic
            context["retry_count"] = context.get("retry_count", 0) + 1
            retry_delay = min(300 * (2 ** context["retry_count"]), 3600)  # Exponential backoff, max 1 hour

            self.logger.info(f"Scheduling retry for job {job_id} in {retry_delay} seconds")
            asyncio.create_task(self._retry_job_after_delay(job_id, retry_delay))
        else:
            await self.transition_job(job_id, WorkflowState.FAILED, context)
            asyncio.create_task(self._cleanup_job_after_delay(job_id, 7200))  # 2 hours

    async def cancel_job(self, job_id: str, reason: str):
        """Cancel a job."""
        await self.transition_job(job_id, WorkflowState.CANCELLED, {
            "cancellation_reason": reason,
            "cancellation_time": datetime.now()
        })

        asyncio.create_task(self._cleanup_job_after_delay(job_id, 1800))  # 30 minutes

    async def _retry_job_after_delay(self, job_id: str, delay: int):
        """Retry a job after a delay."""
        await asyncio.sleep(delay)

        if job_id in self.active_jobs:
            # Reset to appropriate state for retry
            current_state = self.active_jobs[job_id]
            if current_state == WorkflowState.FAILED:
                # Determine appropriate retry state based on where it failed
                context = self.job_contexts.get(job_id, {})
                history = context.get("history", [])

                if history:
                    # Go back to the state before the failure
                    last_successful_state = WorkflowState.SEARCHING  # Default fallback
                    for entry in reversed(history[:-1]):  # Exclude the failed transition
                        try:
                            last_successful_state = WorkflowState(entry["to_state"])
                            break
                        except ValueError:
                            continue

                    await self.transition_job(job_id, last_successful_state, {
                        "retry_attempt": True,
                        "retry_time": datetime.now()
                    })

    async def _cleanup_job_after_delay(self, job_id: str, delay: int):
        """Clean up a job after a delay."""
        await asyncio.sleep(delay)
        await self._cleanup_job(job_id)

    async def _cleanup_job(self, job_id: str):
        """Clean up a completed/failed/cancelled job."""
        if job_id in self.active_jobs:
            # Archive job data
            context = self.job_contexts.get(job_id, {})
            await self.data_store.update_job(job_id, {
                "archived": True,
                "archive_time": datetime.now().isoformat(),
                "final_context": context
            })

            # Remove from active tracking
            del self.active_jobs[job_id]
            if job_id in self.job_contexts:
                del self.job_contexts[job_id]

            self.logger.info(f"Cleaned up job {job_id}")

    async def monitor_jobs(self):
        """Monitor active jobs for timeouts and issues."""
        current_time = datetime.now()
        timeout_threshold = timedelta(hours=self.job_timeout_hours)

        jobs_to_timeout = []

        for job_id, context in self.job_contexts.items():
            job_age = current_time - context["start_time"]
            last_update_age = current_time - context["last_update"]

            # Check for timeout
            if job_age > timeout_threshold:
                jobs_to_timeout.append((job_id, "Job timeout"))
                continue

            # Check for stale jobs (no updates for 30 minutes)
            if last_update_age > timedelta(minutes=30):
                state = self.active_jobs[job_id]
                if state not in [WorkflowState.WAITING_RESPONSE, WorkflowState.SUBMITTED]:
                    jobs_to_timeout.append((job_id, "Stale job - no updates"))

        # Handle timeouts
        for job_id, reason in jobs_to_timeout:
            self.logger.warning(f"Timing out job {job_id}: {reason}")
            await self.fail_job(job_id, reason, retry=False)

    async def get_workflow_stats(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        stats = {
            "active_jobs": len(self.active_jobs),
            "max_concurrent": self.max_concurrent_jobs,
            "states": {}
        }

        # Count jobs by state
        for state in self.active_jobs.values():
            state_name = state.value
            stats["states"][state_name] = stats["states"].get(state_name, 0) + 1

        # Get historical data from data store
        try:
            all_jobs = await self.data_store.get_all_jobs()
            stats["total_jobs"] = len(all_jobs)

            completed_jobs = [j for j in all_jobs if j.get("workflow_state") == "completed"]
            failed_jobs = [j for j in all_jobs if j.get("workflow_state") == "failed"]

            stats["completed_jobs"] = len(completed_jobs)
            stats["failed_jobs"] = len(failed_jobs)
            stats["success_rate"] = len(completed_jobs) / len(all_jobs) if all_jobs else 0

        except Exception as e:
            self.logger.error(f"Error getting workflow stats: {str(e)}")

        return stats

    async def pause_workflow(self, job_id: str):
        """Pause a job workflow."""
        if job_id in self.job_contexts:
            self.job_contexts[job_id]["paused"] = True
            self.job_contexts[job_id]["pause_time"] = datetime.now()
            self.logger.info(f"Paused workflow for job {job_id}")

    async def resume_workflow(self, job_id: str):
        """Resume a paused job workflow."""
        if job_id in self.job_contexts:
            self.job_contexts[job_id]["paused"] = False
            self.job_contexts[job_id]["resume_time"] = datetime.now()
            self.logger.info(f"Resumed workflow for job {job_id}")

    def is_job_paused(self, job_id: str) -> bool:
        """Check if a job is paused."""
        context = self.job_contexts.get(job_id, {})
        return context.get("paused", False)


class WorkflowOrchestrator:
    """Orchestrates multiple workflow managers and provides high-level control."""

    def __init__(self, workflow_manager: WorkflowManager):
        self.workflow_manager = workflow_manager
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.monitor_task = None

    async def start(self):
        """Start the workflow orchestrator."""
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Workflow orchestrator started")

    async def stop(self):
        """Stop the workflow orchestrator."""
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Workflow orchestrator stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                await self.workflow_manager.monitor_jobs()
                await asyncio.sleep(60)  # Monitor every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {str(e)}")
                await asyncio.sleep(60)

    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        stats = await self.workflow_manager.get_workflow_stats()
        return {
            "orchestrator_running": self.running,
            "workflow_stats": stats,
            "timestamp": datetime.now().isoformat()
        }