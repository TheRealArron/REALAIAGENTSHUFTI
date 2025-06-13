"""
Constants used throughout the Shufti Agent application.
"""

# API and Web Configuration
SHUFTI_BASE_URL = "https://app.shufti.jp"
SHUFTI_JOBS_URL = f"{SHUFTI_BASE_URL}/jobs/search"
SHUFTI_LOGIN_URL = f"{SHUFTI_BASE_URL}/login"
SHUFTI_PROFILE_URL = f"{SHUFTI_BASE_URL}/profile"

# Rate Limiting
DEFAULT_RATE_LIMIT = 1.0  # seconds between requests
BURST_RATE_LIMIT = 0.5    # seconds for burst requests
MAX_CONCURRENT_REQUESTS = 3
REQUEST_TIMEOUT = 30      # seconds

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds
EXPONENTIAL_BACKOFF = True

# Memory Management
MAX_MEMORY_ENTRIES = 1000    # Maximum number of job entries to keep in memory
MEMORY_RETENTION_DAYS = 30   # Days to keep completed job data
SESSION_TIMEOUT = 3600       # Session timeout in seconds

# Job Processing
MAX_APPLICATIONS_PER_DAY = 10
MIN_JOB_PAYMENT = 500       # Minimum payment in yen
JOB_SEARCH_INTERVAL = 300   # seconds between job searches
MAX_JOBS_PER_SEARCH = 50

# Communication
MAX_MESSAGE_LENGTH = 1000
RESPONSE_TIMEOUT = 60       # seconds to wait for responses
MAX_COMMUNICATION_RETRIES = 3

# File Paths
DATA_DIR = "data"
LOGS_DIR = "logs"
MEMORY_FILE = "agent_memory.json"
SESSION_FILE = "session_data.json"




# Workflow States
WORKFLOW_STATES = [
    "IDLE",
    "SEARCHING_JOBS",
    "EVALUATING_JOB",
    "APPLYING_TO_JOB",
    "WAITING_FOR_RESPONSE",
    "WORKING_ON_TASK",
    "SUBMITTING_WORK",
    "COMPLETED",
    "ERROR"
]

# Job Categories
JOB_CATEGORIES = [
    "data_entry",
    "translation",
    "writing",
    "research",
    "design",
    "programming",
    "customer_service",
    "other"
]

# User Agent Strings
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
]

# Error Messages
ERROR_MESSAGES = {
    "LOGIN_FAILED": "Failed to login to Shufti platform",
    "RATE_LIMITED": "Rate limit exceeded, waiting before retry",
    "NETWORK_ERROR": "Network connection error",
    "PARSING_ERROR": "Failed to parse job data",
    "APPLICATION_ERROR": "Failed to submit job application",
    "TASK_ERROR": "Error processing job task",
    "SUBMISSION_ERROR": "Failed to submit completed work"
}

# Success Messages
SUCCESS_MESSAGES = {
    "LOGIN_SUCCESS": "Successfully logged into Shufti platform",
    "JOB_FOUND": "New job opportunity found",
    "APPLICATION_SENT": "Job application submitted successfully",
    "TASK_COMPLETED": "Job task completed successfully",
    "WORK_SUBMITTED": "Work submitted successfully"
}

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# AI Model Configuration
DEFAULT_AI_MODEL = "llama3.2:3b"  # Free Ollama model
AI_TEMPERATURE = 0.7
AI_MAX_TOKENS = 1000
AI_TIMEOUT = 30

# Job Matching Configuration
SIMILARITY_THRESHOLD = 0.7
KEYWORD_WEIGHT = 0.4
PAYMENT_WEIGHT = 0.3
COMPANY_WEIGHT = 0.3

# Application Templates
DEFAULT_APPLICATION_TEMPLATE = """
こんにちは、

この度は求人を拝見し、応募させていただきます。
私は経験豊富なフリーランサーとして、品質の高い作業をお約束いたします。

どうぞよろしくお願いいたします。
"""

# Task Processing
TASK_CHECK_INTERVAL = 60    # seconds
MAX_TASK_DURATION = 7200   # 2 hours in seconds
PROGRESS_REPORT_INTERVAL = 300  # 5 minutes

# Security
MAX_LOGIN_ATTEMPTS = 3
SESSION_RENEWAL_INTERVAL = 1800  # 30 minutes
CSRF_TOKEN_HEADER = "X-CSRF-Token"

# Browser Automation
SELENIUM_TIMEOUT = 10
PAGE_LOAD_TIMEOUT = 30
ELEMENT_WAIT_TIMEOUT = 10

# Cache Configuration
CACHE_DURATION = 300        # 5 minutes
MAX_CACHE_SIZE = 100        # Maximum cached items

# Monitoring
HEALTH_CHECK_INTERVAL = 300  # 5 minutes
PERFORMANCE_LOG_INTERVAL = 600  # 10 minutes