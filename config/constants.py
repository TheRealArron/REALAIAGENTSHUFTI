"""Constants used across the Shufti agent application."""

from enum import Enum
from typing import Dict, List

class JobStatus(Enum):
    """Job processing status."""
    DISCOVERED = "discovered"
    ANALYZING = "analyzing"
    MATCHED = "matched"
    APPLYING = "applying"
    APPLIED = "applied"
    IN_PROGRESS = "in_progress"
    COMMUNICATING = "communicating"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"

class WorkflowState(Enum):
    """Agent workflow states."""
    IDLE = "idle"
    CRAWLING = "crawling"
    ANALYZING = "analyzing"
    APPLYING = "applying"
    COMMUNICATING = "communicating"
    WORKING = "working"
    ERROR = "error"

# Job categories and keywords (in Japanese and English)
JOB_CATEGORIES = {
    "web_development": {
        "keywords_jp": ["ウェブ開発", "Web開発", "ホームページ作成", "サイト制作", "HTML", "CSS", "JavaScript"],
        "keywords_en": ["web development", "website creation", "html", "css", "javascript", "frontend", "backend"]
    },
    "data_entry": {
        "keywords_jp": ["データ入力", "入力作業", "エクセル", "Excel", "スプレッドシート"],
        "keywords_en": ["data entry", "excel", "spreadsheet", "typing", "input"]
    },
    "translation": {
        "keywords_jp": ["翻訳", "通訳", "英語", "日本語", "多言語"],
        "keywords_en": ["translation", "english", "japanese", "multilingual", "interpreter"]
    },
    "writing": {
        "keywords_jp": ["ライティング", "執筆", "記事作成", "コンテンツ", "ブログ"],
        "keywords_en": ["writing", "content creation", "blog", "article", "copywriting"]
    },
    "design": {
        "keywords_jp": ["デザイン", "グラフィック", "ロゴ", "画像編集", "Photoshop"],
        "keywords_en": ["design", "graphic", "logo", "photoshop", "illustration"]
    }
}

# Common Japanese phrases for communication
JAPANESE_PHRASES = {
    "greeting": "初めまして。お仕事の件でご連絡いたします。",
    "interest": "こちらのお仕事に興味があります。",
    "experience": "類似の経験があり、質の高い作業をお約束いたします。",
    "timeline": "ご指定の期日までに完了可能です。",
    "questions": "ご質問がございましたらお気軽にお聞かせください。",
    "closing": "よろしくお願いいたします。",
    "completion": "作業が完了いたしました。ご確認をお願いいたします。",
    "revision": "修正が必要でしたらお知らせください。"
}

# Browser selectors for Shufti.jp
SELECTORS = {
    "login": {
        "email_input": "input[name='email'], input[type='email']",
        "password_input": "input[name='password'], input[type='password']",
        "login_button": "button[type='submit'], input[type='submit']"
    },
    "jobs": {
        "job_list": ".job-item, .job-card, [data-job-id]",
        "job_title": ".job-title, h2, h3",
        "job_description": ".job-description, .description",
        "job_price": ".price, .budget, .reward",
        "job_deadline": ".deadline, .due-date",
        "apply_button": ".apply-btn, button[data-action='apply']"
    },
    "application": {
        "message_textarea": "textarea[name='message'], textarea.message",
        "submit_button": "button[type='submit'], .submit-btn"
    },
    "communication": {
        "message_list": ".messages, .chat-messages",
        "message_input": "textarea.message-input, input.message",
        "send_button": ".send-btn, button.send"
    }
}

# Headers for HTTP requests
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0"
}

# Rate limiting settings
RATE_LIMITS = {
    "requests_per_minute": 10,
    "requests_per_hour": 100,
    "burst_limit": 3,
    "backoff_factor": 2.0,
    "max_backoff": 300  # 5 minutes
}

# Retry configuration
RETRY_CONFIG = {
    "max_retries": 3,
    "backoff_factor": 1.5,
    "status_codes_to_retry": [429, 500, 502, 503, 504],
    "timeout": 30
}

# AI model prompts
AI_PROMPTS = {
    "job_analysis": """
    Analyze this job posting and extract key information:
    - Required skills
    - Budget/payment
    - Deadline
    - Difficulty level
    - Whether it matches our capabilities
    
    Job posting: {job_text}
    
    Respond in JSON format with the extracted information.
    """,

    "application_message": """
    Write a professional application message in Japanese for this job:
    
    Job: {job_title}
    Description: {job_description}
    
    The message should be polite, show relevant experience, and express genuine interest.
    Keep it concise but professional.
    """,

    "communication_response": """
    Generate an appropriate response to this client message in Japanese:
    
    Client message: {client_message}
    Context: {context}
    
    The response should be professional, helpful, and address their concerns.
    """
}