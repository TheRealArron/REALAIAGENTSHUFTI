"""Logging configuration for the Shufti agent."""

import sys
from pathlib import Path
from loguru import logger
from config.settings import settings


class Logger:
    """Centralized logging configuration."""

    def __init__(self):
        self.setup_logger()

    def setup_logger(self):
        """Configure loguru logger with file and console output."""
        # Remove default logger
        logger.remove()

        # Console logger with colors
        logger.add(
            sys.stderr,
            level=settings.LOG_LEVEL,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )

        # File logger
        logger.add(
            settings.LOG_FILE,
            level=settings.LOG_LEVEL,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="7 days",
            compression="zip"
        )

        # Add structured logging for important events
        logger.add(
            settings.LOG_DIR / "structured.log",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {extra} | {message}",
            filter=lambda record: "structured" in record["extra"],
            rotation="1 day",
            retention="30 days"
        )

    def get_logger(self, name: str = None):
        """Get a logger instance with optional name."""
        if name:
            return logger.bind(name=name)
        return logger


# Create global logger instance
log_manager = Logger()
app_logger = log_manager.get_logger("shufti_agent")


# Convenience functions for different log levels
def log_info(message: str, **kwargs):
    """Log info message with optional structured data."""
    if kwargs:
        app_logger.bind(structured=True, **kwargs).info(message)
    else:
        app_logger.info(message)


def log_error(message: str, **kwargs):
    """Log error message with optional structured data."""
    if kwargs:
        app_logger.bind(structured=True, **kwargs).error(message)
    else:
        app_logger.error(message)


def log_warning(message: str, **kwargs):
    """Log warning message with optional structured data."""
    if kwargs:
        app_logger.bind(structured=True, **kwargs).warning(message)
    else:
        app_logger.warning(message)


def log_debug(message: str, **kwargs):
    """Log debug message with optional structured data."""
    if kwargs:
        app_logger.bind(structured=True, **kwargs).debug(message)
    else:
        app_logger.debug(message)


def log_job_event(event_type: str, job_id: str, details: dict = None):
    """Log job-related events with structured data."""
    log_data = {
        "event_type": event_type,
        "job_id": job_id,
        "structured": True
    }
    if details:
        log_data.update(details)

    app_logger.bind(**log_data).info(f"Job event: {event_type}")


def log_workflow_state(old_state: str, new_state: str, reason: str = None):
    """Log workflow state changes."""
    log_data = {
        "old_state": old_state,
        "new_state": new_state,
        "structured": True
    }
    if reason:
        log_data["reason"] = reason

    app_logger.bind(**log_data).info(f"Workflow state change: {old_state} -> {new_state}")


def log_rate_limit(endpoint: str, wait_time: float):
    """Log rate limiting events."""
    app_logger.bind(
        structured=True,
        endpoint=endpoint,
        wait_time=wait_time
    ).warning(f"Rate limited on {endpoint}, waiting {wait_time}s")


def log_api_call(service: str, method: str, success: bool, response_time: float = None):
    """Log API calls with performance metrics."""
    log_data = {
        "service": service,
        "method": method,
        "success": success,
        "structured": True
    }
    if response_time:
        log_data["response_time"] = response_time

    level = "info" if success else "error"
    message = f"API call {service}.{method} {'succeeded' if success else 'failed'}"

    getattr(app_logger.bind(**log_data), level)(message)