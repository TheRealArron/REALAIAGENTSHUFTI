"""
Logging utilities for the Shufti agent
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Any


class ShuftiLogger:
    """Custom logger for the Shufti agent"""

    def __init__(self, name: str = "shufti_agent"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Prevent duplicate handlers
        if not self.logger.handlers:
            self.setup_handlers()

    def setup_handlers(self):
        """Setup logging handlers"""
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # File handler
        log_file = Path("logs") / "shufti_agent.log"
        log_file.parent.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def info(self, message: str, extra: Optional[dict] = None):
        """Log info message"""
        self.logger.info(message, extra=extra)

    def error(self, message: str, extra: Optional[dict] = None):
        """Log error message"""
        self.logger.error(message, extra=extra)

    def warning(self, message: str, extra: Optional[dict] = None):
        """Log warning message"""
        self.logger.warning(message, extra=extra)

    def debug(self, message: str, extra: Optional[dict] = None):
        """Log debug message"""
        self.logger.debug(message, extra=extra)

    def workflow_state(self, state: str, details: Optional[dict] = None):
        """Log workflow state changes"""
        message = f"Workflow State: {state}"
        if details:
            message += f" - Details: {details}"
        self.logger.info(message)


# Global logger instance
_logger = ShuftiLogger()


def get_logger() -> ShuftiLogger:
    """Get the global logger instance"""
    return _logger


# Convenience functions
def log_info(message: str, extra: Optional[dict] = None):
    """Log info message"""
    _logger.info(message, extra)


def log_error(message: str, extra: Optional[dict] = None):
    """Log error message"""
    _logger.error(message, extra)


def log_warning(message: str, extra: Optional[dict] = None):
    """Log warning message"""
    _logger.warning(message, extra)


def log_debug(message: str, extra: Optional[dict] = None):
    """Log debug message"""
    _logger.debug(message, extra)


def log_workflow_state(state: str, details: Optional[dict] = None):
    """Log workflow state changes"""
    _logger.workflow_state(state, details)


def log_job_application(job_id: str, status: str, details: Optional[dict] = None):
    """Log job application events"""
    message = f"Job Application {job_id}: {status}"
    if details:
        message += f" - {details}"
    _logger.info(message)


def log_web_request(url: str, method: str = "GET", status_code: Optional[int] = None):
    """Log web requests"""
    message = f"Web Request: {method} {url}"
    if status_code:
        message += f" - Status: {status_code}"
    _logger.debug(message)


def log_ai_interaction(prompt: str, response: Optional[str] = None, model: Optional[str] = None):
    """Log AI model interactions"""
    message = f"AI Interaction"
    if model:
        message += f" ({model})"
    message += f" - Prompt length: {len(prompt)}"
    if response:
        message += f" - Response length: {len(response)}"
    _logger.debug(message)


def log_job_discovery(job_count: int, source: str = "shufti"):
    """Log job discovery events"""
    message = f"Job Discovery: Found {job_count} jobs from {source}"
    _logger.info(message)


def log_authentication(success: bool, details: Optional[str] = None):
    """Log authentication events"""
    status = "SUCCESS" if success else "FAILED"
    message = f"Authentication: {status}"
    if details:
        message += f" - {details}"
    _logger.info(message)