# core/constants.py

# Base URL for the job search site
BASE_URL = "https://app.shufti.jp/jobs/search"

# Login URL for the platform
LOGIN_URL = "https://app.shufti.jp/login"

# The model name for the transformer model (e.g., T5)
MODEL_NAME = "google/flan-t5-small"

# Configuration settings (e.g., max pages for scraping)
MAX_PAGES = 5  # Max pages to scrape per session
DELAY = 5      # Delay between page requests in seconds

# Logging settings
LOG_FILE_PATH = "session_log.txt"  # Path to log file

# You can add more constants based on your application's requirements.
