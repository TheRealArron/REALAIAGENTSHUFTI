import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""

    def __init__(self):
        # Shufti credentials
        self.SHUFTI_EMAIL: str = os.getenv('SHUFTI_EMAIL', '')
        self.SHUFTI_PASSWORD: str = os.getenv('SHUFTI_PASSWORD', '')

        # AI Service settings
        self.AI_MODEL: str = os.getenv('AI_MODEL', 'gpt-3.5-turbo')
        self.AI_API_KEY: str = os.getenv('AI_API_KEY', '')
        self.AI_BASE_URL: str = os.getenv('AI_BASE_URL', 'https://api.openai.com/v1')

        # Application settings
        self.MAX_JOBS_PER_RUN: int = int(os.getenv('MAX_JOBS_PER_RUN', '5'))
        self.JOB_CHECK_INTERVAL: int = int(os.getenv('JOB_CHECK_INTERVAL', '300'))
        self.AUTO_APPLY: bool = os.getenv('AUTO_APPLY', 'false').lower() == 'true'

        # Rate limiting
        self.REQUEST_DELAY: float = float(os.getenv('REQUEST_DELAY', '2.0'))
        self.MAX_RETRIES: int = int(os.getenv('MAX_RETRIES', '3'))

        # Storage
        self.DATA_DIR: str = os.getenv('DATA_DIR', 'data')
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FILE: str = os.getenv('LOG_FILE', 'logs/shufti_agent.log')
        self.LOG_MAX_SIZE: int = int(os.getenv('LOG_MAX_SIZE', '10485760'))  # 10MB
        self.LOG_BACKUP_COUNT: int = int(os.getenv('LOG_BACKUP_COUNT', '5'))

        # Data storage files
        self.JOBS_DATA_FILE: str = os.getenv('JOBS_DATA_FILE', 'data/jobs.json')
        self.APPLICATIONS_DATA_FILE: str = os.getenv('APPLICATIONS_DATA_FILE', 'data/applications.json')
        self.MESSAGES_DATA_FILE: str = os.getenv('MESSAGES_DATA_FILE', 'data/messages.json')
        self.TASKS_DATA_FILE: str = os.getenv('TASKS_DATA_FILE', 'data/tasks.json')
        self.USER_DATA_FILE: str = os.getenv('USER_DATA_FILE', 'data/user_profile.json')
        self.SESSION_DATA_FILE: str = os.getenv('SESSION_DATA_FILE', 'data/session.json')

        # Memory file (ADDED - this was missing)
        self.MEMORY_FILE: str = os.getenv('MEMORY_FILE', 'data/agent_memory.json')

        # User profile for job matching
        self.USER_SKILLS: str = os.getenv('USER_SKILLS', '')
        self.USER_EXPERIENCE: str = os.getenv('USER_EXPERIENCE', '')
        self.USER_LANGUAGES: str = os.getenv('USER_LANGUAGES', 'Japanese,English')

        # Communication settings
        self.AUTO_RESPOND: bool = os.getenv('AUTO_RESPOND', 'true').lower() == 'true'
        self.RESPONSE_DELAY: int = int(os.getenv('RESPONSE_DELAY', '60'))

    def validate(self) -> bool:
        """Validate that required settings are present"""
        required_settings = [
            'SHUFTI_EMAIL',
            'SHUFTI_PASSWORD'
        ]

        missing = []
        for setting in required_settings:
            if not getattr(self, setting):
                missing.append(setting)

        if missing:
            print(f"Missing required environment variables: {', '.join(missing)}")
            return False

        return True

    def get_ai_config(self) -> dict:
        """Get AI service configuration"""
        return {
            'model': self.AI_MODEL,
            'api_key': self.AI_API_KEY,
            'base_url': self.AI_BASE_URL
        }

    def get_user_profile(self) -> dict:
        """Get user profile for job matching"""
        return {
            'skills': [skill.strip() for skill in self.USER_SKILLS.split(',') if skill.strip()],
            'experience': self.USER_EXPERIENCE,
            'languages': [lang.strip() for lang in self.USER_LANGUAGES.split(',') if lang.strip()]
        }


# Global settings instance
settings = Settings()