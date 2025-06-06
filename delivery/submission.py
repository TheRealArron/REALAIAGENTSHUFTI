"""
Job submission handling module.
Manages the final submission of completed work to clients.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import mimetypes

from utils.http_client import HTTPClient
from utils.logger import get_logger
from utils.data_store import DataStore

logger = get_logger(__name__)


class JobSubmission:
    """Handles final job submission and delivery."""

    def __init__(self, http_client: HTTPClient, data_store: DataStore):
        self.http_client = http_client
        self.data_store = data_store
        self.logger = logging.getLogger(__name__)

    async def submit_job(self, job_id: str, submission_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit completed job to client.

        Args:
            job_id: The job identifier
            submission_data: Data to submit including files and message

        Returns:
            Submission result
        """
        try:
            self.logger.info(f"Starting job submission for job {job_id}")

            # Get job details
            job_details = await self.data_store.get_job(job_id)
            if not job_details:
                raise ValueError(f"Job {job_id} not found")

            # Prepare submission
            submission_payload = await self._prepare_submission_payload(
                job_details, submission_data
            )

            # Submit to Shufti
            submission_result = await self._submit_to_shufti(
                job_id, submission_payload
            )

            # Update job status
            await self._update_job_status(job_id, "submitted", submission_result)

            self.logger.info(f"Successfully submitted job {job_id}")
            return submission_result

        except Exception as e:
            self.logger.error(f"Error submitting job {job_id}: {str(e)}")
            await self._update_job_status(job_id, "submission_failed", {"error": str(e)})
            raise

    async def _prepare_submission_payload(
            self,
            job_details: Dict[str, Any],
            submission_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare the payload for job submission."""
        payload = {
            "job_id": job_details["id"],
            "message": submission_data.get("message", "Job completed successfully."),
            "completion_time": datetime.now().isoformat(),
            "deliverables": []
        }

        # Add files if any
        if "files" in submission_data:
            for file_info in submission_data["files"]:
                deliverable = await self._prepare_file_deliverable(file_info)
                payload["deliverables"].append(deliverable)

        # Add text deliverables
        if "text_deliverables" in submission_data:
            for text_item in submission_data["text_deliverables"]:
                payload["deliverables"].append({
                    "type": "text",
                    "content": text_item["content"],
                    "title": text_item.get("title", "Text Deliverable")
                })

        return payload

    async def _prepare_file_deliverable(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare file deliverable for submission."""
        file_path = file_info["path"]

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get file info
        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)

        deliverable = {
            "type": "file",
            "filename": os.path.basename(file_path),
            "size": file_size,
            "mime_type": mime_type or "application/octet-stream",
            "description": file_info.get("description", "")
        }

        # Read file content for upload
        with open(file_path, 'rb') as f:
            deliverable["content"] = f.read()

        return deliverable

    async def _submit_to_shufti(
            self,
            job_id: str,
            payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit the job to Shufti platform."""

        # For file uploads, we need to use multipart form data
        if any(d["type"] == "file" for d in payload.get("deliverables", [])):
            return await self._submit_with_files(job_id, payload)
        else:
            return await self._submit_text_only(job_id, payload)

    async def _submit_text_only(
            self,
            job_id: str,
            payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit text-only deliverables."""
        submission_url = f"https://app.shufti.jp/api/jobs/{job_id}/submit"

        # Prepare text payload
        text_payload = {
            "message": payload["message"],
            "completion_time": payload["completion_time"],
            "deliverables": [
                d for d in payload["deliverables"]
                if d["type"] == "text"
            ]
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = await self.http_client.post(
            submission_url,
            json=text_payload,
            headers=headers
        )

        if response.status_code != 200:
            raise Exception(f"Submission failed: {response.status_code} - {response.text}")

        return response.json()

    async def _submit_with_files(
            self,
            job_id: str,
            payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit job with file attachments."""
        submission_url = f"https://app.shufti.jp/api/jobs/{job_id}/submit"

        # Prepare multipart form data
        files = {}
        data = {
            "message": payload["message"],
            "completion_time": payload["completion_time"]
        }

        file_index = 0
        for deliverable in payload["deliverables"]:
            if deliverable["type"] == "file":
                file_key = f"file_{file_index}"
                files[file_key] = (
                    deliverable["filename"],
                    deliverable["content"],
                    deliverable["mime_type"]
                )
                data[f"{file_key}_description"] = deliverable["description"]
                file_index += 1
            elif deliverable["type"] == "text":
                data[f"text_deliverable_{len([k for k in data.keys() if k.startswith('text_deliverable')])}"] = \
                deliverable["content"]

        response = await self.http_client.post_multipart(
            submission_url,
            data=data,
            files=files
        )

        if response.status_code != 200:
            raise Exception(f"File submission failed: {response.status_code} - {response.text}")

        return response.json()

    async def _update_job_status(
            self,
            job_id: str,
            status: str,
            result_data: Dict[str, Any]
    ):
        """Update job status after submission."""
        update_data = {
            "status": status,
            "submission_time": datetime.now().isoformat(),
            "submission_result": result_data
        }

        await self.data_store.update_job(job_id, update_data)

    async def check_submission_status(self, job_id: str) -> Dict[str, Any]:
        """Check the status of a submitted job."""
        try:
            status_url = f"https://app.shufti.jp/api/jobs/{job_id}/status"

            response = await self.http_client.get(status_url)

            if response.status_code != 200:
                raise Exception(f"Status check failed: {response.status_code}")

            return response.json()

        except Exception as e:
            self.logger.error(f"Error checking submission status for job {job_id}: {str(e)}")
            return {"error": str(e)}

    async def handle_submission_feedback(
            self,
            job_id: str,
            feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle feedback from client after submission."""
        try:
            self.logger.info(f"Processing feedback for job {job_id}")

            feedback_type = feedback_data.get("type", "general")

            if feedback_type == "revision_request":
                return await self._handle_revision_request(job_id, feedback_data)
            elif feedback_type == "acceptance":
                return await self._handle_job_acceptance(job_id, feedback_data)
            elif feedback_type == "rejection":
                return await self._handle_job_rejection(job_id, feedback_data)
            else:
                return await self._handle_general_feedback(job_id, feedback_data)

        except Exception as e:
            self.logger.error(f"Error handling feedback for job {job_id}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_revision_request(
            self,
            job_id: str,
            feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle revision requests from client."""
        revision_notes = feedback_data.get("revision_notes", "")

        # Update job status to require revision
        await self._update_job_status(job_id, "revision_requested", {
            "revision_notes": revision_notes,
            "request_time": datetime.now().isoformat()
        })

        self.logger.info(f"Job {job_id} marked for revision")

        return {
            "success": True,
            "action": "revision_requested",
            "message": "Job marked for revision based on client feedback"
        }

    async def _handle_job_acceptance(
            self,
            job_id: str,
            feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle job acceptance from client."""
        await self._update_job_status(job_id, "accepted", {
            "acceptance_time": datetime.now().isoformat(),
            "client_rating": feedback_data.get("rating"),
            "client_comment": feedback_data.get("comment", "")
        })

        self.logger.info(f"Job {job_id} accepted by client")

        return {
            "success": True,
            "action": "job_accepted",
            "message": "Job successfully accepted by client"
        }

    async def _handle_job_rejection(
            self,
            job_id: str,
            feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle job rejection from client."""
        rejection_reason = feedback_data.get("reason", "No reason provided")

        await self._update_job_status(job_id, "rejected", {
            "rejection_time": datetime.now().isoformat(),
            "rejection_reason": rejection_reason
        })

        self.logger.info(f"Job {job_id} rejected by client: {rejection_reason}")

        return {
            "success": True,
            "action": "job_rejected",
            "message": f"Job rejected: {rejection_reason}"
        }

    async def _handle_general_feedback(
            self,
            job_id: str,
            feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle general feedback from client."""
        # Store feedback for future reference
        job_data = await self.data_store.get_job(job_id)
        if not job_data:
            raise ValueError(f"Job {job_id} not found")

        if "feedback_history" not in job_data:
            job_data["feedback_history"] = []

        job_data["feedback_history"].append({
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback_data.get("message", ""),
            "rating": feedback_data.get("rating")
        })

        await self.data_store.update_job(job_id, {"feedback_history": job_data["feedback_history"]})

        return {
            "success": True,
            "action": "feedback_recorded",
            "message": "Feedback recorded successfully"
        }

    async def get_submission_history(self, job_id: str) -> List[Dict[str, Any]]:
        """Get submission history for a job."""
        try:
            job_data = await self.data_store.get_job(job_id)
            if not job_data:
                return []

            history = []

            # Add submission record
            if job_data.get("status") in ["submitted", "accepted", "rejected"]:
                history.append({
                    "type": "submission",
                    "timestamp": job_data.get("submission_time"),
                    "status": job_data.get("status"),
                    "result": job_data.get("submission_result", {})
                })

            # Add feedback history
            for feedback in job_data.get("feedback_history", []):
                history.append({
                    "type": "feedback",
                    "timestamp": feedback["timestamp"],
                    "content": feedback["feedback"],
                    "rating": feedback.get("rating")
                })

            # Sort by timestamp
            history.sort(key=lambda x: x["timestamp"] or "")

            return history

        except Exception as e:
            self.logger.error(f"Error getting submission history for job {job_id}: {str(e)}")
            return []


class DeliveryManager:
    """Manages the entire delivery process."""

    def __init__(self, http_client: HTTPClient, data_store: DataStore):
        self.submission = JobSubmission(http_client, data_store)
        self.data_store = data_store
        self.logger = logging.getLogger(__name__)

    async def complete_job_delivery(
            self,
            job_id: str,
            deliverables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Complete the entire job delivery process."""
        try:
            self.logger.info(f"Starting complete delivery process for job {job_id}")

            # Submit the job
            submission_result = await self.submission.submit_job(job_id, deliverables)

            # Monitor submission status
            status_result = await self.submission.check_submission_status(job_id)

            return {
                "success": True,
                "submission_result": submission_result,
                "current_status": status_result
            }

        except Exception as e:
            self.logger.error(f"Error in complete delivery for job {job_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }