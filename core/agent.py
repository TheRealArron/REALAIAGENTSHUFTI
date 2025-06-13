"""
Main Shufti Agent - Orchestrates the entire job application and completion process.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

from config.settings import settings
from config.constants import JOB_SEARCH_INTERVAL, MAX_APPLICATIONS_PER_DAY
from core.workflow_manager import WorkflowManager, WorkflowOrchestrator, WorkflowState
from core.memory import AgentMemory
from utils.http_client import HTTPClient
from utils.data_store import DataStore
from utils.logger import get_logger

# Import all modules
from modules.auth.login import ShuftiAuth
from modules.crawler.scraper import JobScraper
from modules.crawler.parser import JobParser
from modules.application.job_matcher import JobMatcher
from modules.application.applicator import JobApplicator
from modules.communication.message_handler import MessageHandler
from modules.communication.responder import MessageResponder
from modules.delivery.task_processor import TaskProcessor
from modules.delivery.submission import DeliveryManager
from modules.llm.ai_service import AIService

logger = get_logger(__name__)


class ShuftiAgent:
    """Main Shufti Agent that orchestrates all job-related activities."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.running = False

        # Core components
        self.http_client = HTTPClient()
        self.data_store = DataStore()
        self.memory = AgentMemory()
        self.ai_service = AIService()

        # Workflow management
        self.workflow_manager = WorkflowManager(self.data_store, self.memory)
        self.orchestrator = WorkflowOrchestrator(self.workflow_manager)

        # Authentication
        self.auth = ShuftiAuth(self.http_client, self.data_store)

        # Job processing modules
        self.scraper = JobScraper(self.http_client, self.data_store)
        self.parser = JobParser()
        self.matcher = JobMatcher(self.ai_service, self.data_store)
        self.applicator = JobApplicator(self.http_client, self.data_store, self.ai_service)

        # Communication modules
        self.message_handler = MessageHandler(self.http_client, self.data_store, self.ai_service)
        self.responder = MessageResponder(self.ai_service, self.data_store)

        # Delivery modules
        self.task_processor = TaskProcessor(self.ai_service, self.data_store)
        self.delivery_manager = DeliveryManager(self.http_client, self.data_store)

        # Agent state
        self.daily_applications = 0
        self.last_search_time = None
        self.authenticated = False

        # Setup workflow handlers
        self._setup_workflow_handlers()

        # Background tasks
        self.background_tasks: List[asyncio.Task] = []

    def _setup_workflow_handlers(self):
        """Setup workflow state handlers."""

        # State handlers
        self.workflow_manager.register_state_handler(
            WorkflowState.SEARCHING, self._handle_searching_state
        )
        self.workflow_manager.register_state_handler(
            WorkflowState.ANALYZING, self._handle_analyzing_state
        )
        self.workflow_manager.register_state_handler(
            WorkflowState.APPLYING, self._handle_applying_state
        )
        self.workflow_manager.register_state_handler(
            WorkflowState.WAITING_RESPONSE, self._handle_waiting_response_state
        )
        self.workflow_manager.register_state_handler(
            WorkflowState.ACCEPTED, self._handle_accepted_state
        )
        self.workflow_manager.register_state_handler(
            WorkflowState.IN_PROGRESS, self._handle_in_progress_state
        )
        self.workflow_manager.register_state_handler(
            WorkflowState.COMMUNICATING, self._handle_communicating_state
        )
        self.workflow_manager.register_state_handler(
            WorkflowState.DELIVERING, self._handle_delivering_state
        )
        self.workflow_manager.register_state_handler(
            WorkflowState.REVISION_REQUESTED, self._handle_revision_requested_state
        )

        # Transition handler
        self.workflow_manager.register_transition_handler(self._handle_state_transition)

    async def start(self):
        """Start the Shufti Agent."""
        try:
            self.logger.info("Starting Shufti Agent...")

            # Initialize components
            await self._initialize_components()

            # Authenticate
            await self._authenticate()

            # Start workflow orchestrator
            await self.orchestrator.start()

            # Start background tasks
            await self._start_background_tasks()

            self.running = True
            self.logger.info("Shufti Agent started successfully")

        except Exception as e:
            self.logger.error(f"Error starting Shufti Agent: {str(e)}")
            await self.stop()
            raise

    async def stop(self):
        """Stop the Shufti Agent."""
        self.logger.info("Stopping Shufti Agent...")

        self.running = False

        # Stop orchestrator
        await self.orchestrator.stop()

        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()

        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        # Cleanup components
        await self.http_client.close()

        self.logger.info("Shufti Agent stopped")

    async def _initialize_components(self):
        """Initialize all components."""
        # Load agent memory
        await self.memory.load_from_storage()

        # Initialize data store
        # Data store initialization is handled internally

        self.logger.info("Components initialized")

    async def _authenticate(self):
        """Authenticate with Shufti platform."""
        try:
            if not settings.SHUFTI_EMAIL or not settings.SHUFTI_PASSWORD:
                raise ValueError("Shufti credentials not configured")

            result = await self.auth.login(settings.SHUFTI_EMAIL, settings.SHUFTI_PASSWORD)

            if result["success"]:
                self.authenticated = True
                self.logger.info("Successfully authenticated with Shufti")
            else:
                raise Exception(f"Authentication failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            raise

    async def _start_background_tasks(self):
        """Start background tasks."""
        # Job search task
        search_task = asyncio.create_task(self._job_search_loop())
        self.background_tasks.append(search_task)

        # Message monitoring task
        message_task = asyncio.create_task(self._message_monitoring_loop())
        self.background_tasks.append(message_task)

        # Daily reset task
        reset_task = asyncio.create_task(self._daily_reset_loop())
        self.background_tasks.append(reset_task)

        self.logger.info("Background tasks started")

    async def _job_search_loop(self):
        """Main job search loop."""
        while self.running:
            try:
                current_time = datetime.now()

                # Check if it's time to search
                if (self.last_search_time is None or
                        current_time - self.last_search_time >= timedelta(seconds=JOB_SEARCH_INTERVAL)):

                    # Check daily application limit
                    if self.daily_applications < MAX_APPLICATIONS_PER_DAY:
                        await self._search_and_apply_jobs()
                        self.last_search_time = current_time
                    else:
                        self.logger.info(f"Daily application limit ({MAX_APPLICATIONS_PER_DAY}) reached")

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in job search loop: {str(e)}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _message_monitoring_loop(self):
        """Monitor for new messages."""
        while self.running:
            try:
                # Check for new messages
                await self._check_and_handle_messages()
                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in message monitoring loop: {str(e)}")
                await asyncio.sleep(60)

    async def _daily_reset_loop(self):
        """Reset daily counters."""
        while self.running:
            try:
                now = datetime.now()
                next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                sleep_seconds = (next_midnight - now).total_seconds()

                await asyncio.sleep(sleep_seconds)

                # Reset daily counters
                self.daily_applications = 0
                self.logger.info("Daily application counter reset")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in daily reset loop: {str(e)}")
                await asyncio.sleep(3600)  # Retry in an hour

    async def _search_and_apply_jobs(self):
        """Search for jobs and start application workflow."""
        try:
            self.logger.info("Starting job search...")

            # Search for jobs
            jobs = await self.scraper.search_jobs()

            if not jobs:
                self.logger.info("No jobs found in search")
                return

            self.logger.info(f"Found {len(jobs)} jobs")

            # Process each job
            for job_data in jobs[:5]:  # Limit to first 5 jobs
                try:
                    # Start workflow
                    job_id = await self.workflow_manager.start_job_workflow(job_data)

                    # Transition to searching state
                    await self.workflow_manager.transition_job(job_id, WorkflowState.SEARCHING)

                except Exception as e:
                    self.logger.error(f"Error starting workflow for job {job_data.get('id', 'unknown')}: {str(e)}")

        except Exception as e:
            self.logger.error(f"Error in job search: {str(e)}")

    async def _check_and_handle_messages(self):
        """Check for and handle new messages."""
        try:
            # Get active jobs that might have messages
            active_jobs = await self.workflow_manager.get_active_jobs()

            for job_id, state in active_jobs.items():
                # Only check messages for jobs in relevant states
                if state in [WorkflowState.WAITING_RESPONSE, WorkflowState.ACCEPTED,
                             WorkflowState.IN_PROGRESS, WorkflowState.SUBMITTED]:

                    messages = await self.message_handler.get_new_messages(job_id)

                    if messages:
                        await self._process_job_messages(job_id, messages)

        except Exception as e:
            self.logger.error(f"Error checking messages: {str(e)}")

    async def _process_job_messages(self, job_id: str, messages: List[Dict[str, Any]]):
        """Process messages for a specific job."""
        for message in messages:
            try:
                # Handle the message
                response = await self.message_handler.handle_message(job_id, message)

                # Update workflow state if needed
                if response.get("state_change"):
                    new_state = WorkflowState(response["state_change"])
                    await self.workflow_manager.transition_job(job_id, new_state)

                # Trigger communication state if response needed
                if response.get("needs_response"):
                    current_state = await self.workflow_manager.get_job_state(job_id)
                    if current_state == WorkflowState.IN_PROGRESS:
                        await self.workflow_manager.transition_job(job_id, WorkflowState.COMMUNICATING)

            except Exception as e:
                self.logger.error(f"Error processing message for job {job_id}: {str(e)}")

    # Workflow state handlers
    async def _handle_searching_state(self, job_id: str, context: Dict[str, Any]):
        """Handle SEARCHING state."""
        try:
            # This state is already handled by the search loop
            # Transition to analyzing
            await self.workflow_manager.transition_job(job_id, WorkflowState.ANALYZING)

        except Exception as e:
            await self.workflow_manager.fail_job(job_id, f"Searching failed: {str(e)}")

    async def _handle_analyzing_state(self, job_id: str, context: Dict[str, Any]):
        """Handle ANALYZING state."""
        try:
            job_data = context["job_data"]

            # Parse job details
            parsed_job = await self.parser.parse_job_details(job_data)

            # Match job requirements
            match_result = await self.matcher.analyze_job_match(parsed_job)

            if match_result["should_apply"]:
                # Update context with match result
                await self.workflow_manager.transition_job(job_id, WorkflowState.APPLYING, {
                    "parsed_job": parsed_job,
                    "match_result": match_result
                })
            else:
                # Skip this job
                self.logger.info(f"Skipping job {job_id}: {match_result.get('reason', 'No match')}")
                await self.workflow_manager.transition_job(job_id, WorkflowState.CANCELLED, {
                    "reason": "Job requirements not matched"
                })

        except Exception as e:
            await self.workflow_manager.fail_job(job_id, f"Analysis failed: {str(e)}")

    async def _handle_applying_state(self, job_id: str, context: Dict[str, Any]):
        """Handle APPLYING state."""
        try:
            parsed_job = context["parsed_job"]
            match_result = context["match_result"]

            # Apply for the job
            application_result = await self.applicator.apply_for_job(parsed_job, match_result)

            if application_result["success"]:
                self.daily_applications += 1
                await self.workflow_manager.transition_job(job_id, WorkflowState.WAITING_RESPONSE, {
                    "application_result": application_result,
                    "application_time": datetime.now()
                })
            else:
                await self.workflow_manager.fail_job(job_id,
                                                     f"Application failed: {application_result.get('error', 'Unknown error')}")

        except Exception as e:
            await self.workflow_manager.fail_job(job_id, f"Application failed: {str(e)}")

    async def _handle_waiting_response_state(self, job_id: str, context: Dict[str, Any]):
        """Handle WAITING_RESPONSE state."""
        # This state is passive - we wait for messages
        # The message handler will transition the state when we get a response
        pass

    async def _handle_accepted_state(self, job_id: str, context: Dict[str, Any]):
        """Handle ACCEPTED state."""
        try:
            # Job was accepted, start work
            await self.workflow_manager.transition_job(job_id, WorkflowState.IN_PROGRESS, {
                "work_start_time": datetime.now()
            })

        except Exception as e:
            await self.workflow_manager.fail_job(job_id, f"Failed to start work: {str(e)}")

    async def _handle_in_progress_state(self, job_id: str, context: Dict[str, Any]):
        """Handle IN_PROGRESS state."""
        try:
            parsed_job = context["parsed_job"]

            # Process the job task
            task_result = await self.task_processor.process_job_task(job_id, parsed_job)

            if task_result["success"]:
                # Prepare for delivery
                await self.workflow_manager.transition_job(job_id, WorkflowState.DELIVERING, {
                    "task_result": task_result,
                    "work_completion_time": datetime.now()
                })
            else:
                await self.workflow_manager.fail_job(job_id,
                                                     f"Task processing failed: {task_result.get('error', 'Unknown error')}")

        except Exception as e:
            await self.workflow_manager.fail_job(job_id, f"Work processing failed: {str(e)}")

    async def _handle_communicating_state(self, job_id: str, context: Dict[str, Any]):
        """Handle COMMUNICATING state."""
        try:
            # Generate and send response to recent messages
            messages = context.get("recent_messages", [])

            if messages:
                latest_message = messages[-1]
                response = await self.responder.generate_response(job_id, latest_message)

                # Send the response
                await self.message_handler.send_message(job_id, response["message"])

            # Return to in progress state
            await self.workflow_manager.transition_job(job_id, WorkflowState.IN_PROGRESS)

        except Exception as e:
            await self.workflow_manager.fail_job(job_id, f"Communication failed: {str(e)}")

    async def _handle_delivering_state(self, job_id: str, context: Dict[str, Any]):
        """Handle DELIVERING state."""
        try:
            task_result = context["task_result"]

            # Submit the completed work
            delivery_result = await self.delivery_manager.complete_job_delivery(job_id, task_result)

            if delivery_result["success"]:
                await self.workflow_manager.transition_job(job_id, WorkflowState.SUBMITTED, {
                    "delivery_result": delivery_result,
                    "submission_time": datetime.now()
                })
            else:
                await self.workflow_manager.fail_job(job_id,
                                                     f"Delivery failed: {delivery_result.get('error', 'Unknown error')}")

        except Exception as e:
            await self.workflow_manager.fail_job(job_id, f"Delivery failed: {str(e)}")

    async def _handle_revision_requested_state(self, job_id: str, context: Dict[str, Any]):
        """Handle REVISION_REQUESTED state."""
        try:
            # Get revision feedback
            revision_notes = context.get("revision_notes", "")

            # Update memory with revision feedback
            await self.memory.store_experience("revision_request", {
                "job_id": job_id,
                "notes": revision_notes,
                "timestamp": datetime.now()
            })

            # Go back to in progress to handle revisions
            await self.workflow_manager.transition_job(job_id, WorkflowState.IN_PROGRESS, {
                "revision_mode": True,
                "revision_notes": revision_notes
            })

        except Exception as e:
            await self.workflow_manager.fail_job(job_id, f"Revision handling failed: {str(e)}")

    async def _handle_state_transition(self, job_id: str, from_state: WorkflowState,
                                       to_state: WorkflowState, context: Dict[str, Any]):
        """Handle state transitions."""
        # Store experience in memory
        await self.memory.store_experience("state_transition", {
            "job_id": job_id,
            "from_state": from_state.value,
            "to_state": to_state.value,
            "timestamp": datetime.now(),
            "context_keys": list(context.keys())
        })

        # Log transition
        self.logger.info(f"Job {job_id} transitioned: {from_state.value} -> {to_state.value}")

    # Public methods for manual control
    async def pause_job(self, job_id: str):
        """Pause a specific job."""
        await self.workflow_manager.pause_workflow(job_id)
        self.logger.info(f"Paused job {job_id}")

    async def resume_job(self, job_id: str):
        """Resume a paused job."""
        await self.workflow_manager.resume_workflow(job_id)
        self.logger.info(f"Resumed job {job_id}")

    async def cancel_job(self, job_id: str, reason: str = "Manual cancellation"):
        """Cancel a specific job."""
        await self.workflow_manager.cancel_job(job_id, reason)
        self.logger.info(f"Cancelled job {job_id}: {reason}")

    async def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        system_status = await self.orchestrator.get_system_status()

        return {
            "running": self.running,
            "authenticated": self.authenticated,
            "daily_applications": self.daily_applications,
            "max_daily_applications": MAX_APPLICATIONS_PER_DAY,
            "last_search": self.last_search_time.isoformat() if self.last_search_time else None,
            "system_status": system_status
        }

    async def get_active_jobs(self) -> Dict[str, Any]:
        """Get information about active jobs."""
        active_jobs = await self.workflow_manager.get_active_jobs()

        job_details = {}
        for job_id, state in active_jobs.items():
            context = await self.workflow_manager.get_job_context(job_id)
            job_details[job_id] = {
                "state": state.value,
                "start_time": context["start_time"].isoformat() if context.get("start_time") else None,
                "last_update": context["last_update"].isoformat() if context.get("last_update") else None,
                "error_count": context.get("error_count", 0),
                "paused": context.get("paused", False)
            }

        return job_details

    async def force_job_search(self):
        """Force an immediate job search."""
        if self.daily_applications < MAX_APPLICATIONS_PER_DAY:
            await self._search_and_apply_jobs()
            self.last_search_time = datetime.now()
            return {"success": True, "message": "Job search initiated"}
        else:
            return {"success": False, "message": "Daily application limit reached"}


# Singleton instance
_agent_instance: Optional[ShuftiAgent] = None


def get_agent() -> ShuftiAgent:
    """Get the singleton agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ShuftiAgent()
    return _agent_instance