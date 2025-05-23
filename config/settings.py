"""
Settings configuration for the Shufti.jp job automation agent.

This module loads settings from environment variables and provides
default values for the agent's operation.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
dotenv_path = Path(__file__).parent.parent / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path)

# Base URLs
SHUFTI_BASE_URL = "https://app.shufti.jp"
SHUFTI_API_URL = f"{SHUFTI_BASE_URL}/api"
SHUFTI_JOBS_URL = f"{SHUFTI_BASE_URL}/jobs/search"

# API and request settings
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))  # seconds
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "2.0"))  # seconds between requests
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
CONCURRENT_REQUESTS = int(os.getenv("CONCURRENT_REQUESTS", "1"))  # Default to sequential

# Authentication
USERNAME = os.getenv("SHUFTI_USERNAME", "")
PASSWORD = os.getenv("SHUFTI_PASSWORD", "")
AUTH_TOKEN_PATH = os.getenv("AUTH_TOKEN_PATH", "data/auth_token.json")

# AI Service Configuration
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4000"))

# Job processing settings
MAX_JOBS_TO_PROCESS = int(os.getenv("MAX_JOBS_TO_PROCESS", "10"))
MIN_JOB_CONFIDENCE = float(os.getenv("MIN_JOB_CONFIDENCE", "0.7"))  # Minimum confidence to apply
AUTO_APPLY = os.getenv("AUTO_APPLY", "False").lower() in ("true", "1", "yes")

# Data storage
DATA_DIR = os.getenv("DATA_DIR", "data")
JOB_HISTORY_FILE = os.path.join(DATA_DIR, "job_history.json")
MESSAGE_HISTORY_FILE = os.path.join(DATA_DIR, "message_history.json")

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "logs/shufti_agent.log")

# User agent settings
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)

# Create necessary directories
for directory in [DATA_DIR, os.path.dirname(LOG_FILE)]:
    os.makedirs(directory, exist_ok=True)