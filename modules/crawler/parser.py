"""
HTML parser for Shufti job listings and details.
Extracts structured data from scraped HTML content.
"""

import re
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from utils.logger import logger
from config.constants import SHUFTI_SELECTORS


class ShuftiParser:
    """
    Parser for extracting structured job data from Shufti HTML pages.
    """

    def __init__(self):
        self.base_url = "https://app.shufti.jp"

    def parse_job_listings(self, html_content: str) -> List[Dict]:
        """
        Parse job listings from search results page.

        Args:
            html_content: HTML content from job listings page

        Returns:
            List of job dictionaries with basic information
        """
        jobs = []

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find job cards - adjust selectors based on actual Shufti structure
            job_cards = soup.find_all(['div', 'article'], class_=re.compile(r'job.*card|card.*job', re.I))

            if not job_cards:
                # Try alternative selectors
                job_cards = soup.find_all('div', attrs={'data-job-id': True})

            if not job_cards:
                # Try finding by common patterns
                job_cards = soup.find_all('div', class_=re.compile(r'list.*item|item.*list', re.I))

            logger.info(f"Found {len(job_cards)} job cards")

            for card in job_cards:
                job_data = self._parse_job_card(card)
                if job_data:
                    jobs.append(job_data)

            return jobs

        except Exception as e:
            logger.error(f"Error parsing job listings: {e}")
            return []

    def _parse_job_card(self, card: Tag) -> Optional[Dict]:
        """
        Parse individual job card from listings page.

        Args:
            card: BeautifulSoup Tag representing a job card

        Returns:
            Dictionary with job basic information
        """
        try:
            job_data = {}

            # Extract job title
            title_elem = (card.find(['h2', 'h3', 'h4'], class_=re.compile(r'title|name', re.I)) or
                          card.find('a', class_=re.compile(r'title|link', re.I)) or
                          card.find(['h2', 'h3', 'h4']) or
                          card.find('a'))

            if title_elem:
                job_data['title'] = self._clean_text(title_elem.get_text())

                # Extract job URL from title link
                if title_elem.name == 'a' and title_elem.get('href'):
                    job_data['url'] = urljoin(self.base_url, title_elem['href'])
                else:
                    # Look for link within the card
                    link_elem = card.find('a', href=True)
                    if link_elem:
                        job_data['url'] = urljoin(self.base_url, link_elem['href'])

            # Extract company name
            company_elem = (card.find(class_=re.compile(r'company|employer', re.I)) or
                            card.find('span', string=re.compile(r'株式会社|有限会社|合同会社', re.I)))

            if company_elem:
                job_data['company'] = self._clean_text(company_elem.get_text())

            # Extract location
            location_elem = (card.find(class_=re.compile(r'location|place|address', re.I)) or
                             card.find(
                                 string=re.compile(r'東京|大阪|名古屋|福岡|札幌|仙台|広島|remote|リモート', re.I)))

            if location_elem:
                if hasattr(location_elem, 'get_text'):
                    job_data['location'] = self._clean_text(location_elem.get_text())
                else:
                    job_data['location'] = self._clean_text(str(location_elem))

            # Extract salary/compensation
            salary_elem = (card.find(class_=re.compile(r'salary|pay|price|amount', re.I)) or
                           card.find(string=re.compile(r'円|¥|\$|USD|JPY', re.I)))

            if salary_elem:
                if hasattr(salary_elem, 'get_text'):
                    job_data['salary'] = self._clean_text(salary_elem.get_text())
                else:
                    job_data['salary'] = self._clean_text(str(salary_elem))

            # Extract job type/category
            category_elem = (card.find(class_=re.compile(r'category|type|tag', re.I)) or
                             card.find('span', class_=re.compile(r'badge|label', re.I)))

            if category_elem:
                job_data['category'] = self._clean_text(category_elem.get_text())

            # Extract posting date
            date_elem = (card.find(class_=re.compile(r'date|time|posted', re.I)) or
                         card.find('time') or
                         card.find(string=re.compile(r'\d+日前|\d+時間前|yesterday|today', re.I)))

            if date_elem:
                if hasattr(date_elem, 'get_text'):
                    date_text = date_elem.get_text()
                else:
                    date_text = str(date_elem)
                job_data['posted_date'] = self._parse_date(date_text)

            # Extract job ID if available
            job_id = (card.get('data-job-id') or
                      card.get('id') or
                      self._extract_id_from_url(job_data.get('url', '')))

            if job_id:
                job_data['job_id'] = job_id

            # Add scraped timestamp
            job_data['scraped_at'] = datetime.now().isoformat()

            # Only return if we have essential information
            if job_data.get('title') or job_data.get('url'):
                return job_data
            else:
                return None

        except Exception as e:
            logger.error(f"Error parsing job card: {e}")
            return None

    def parse_job_details(self, html_content: str) -> Dict:
        """
        Parse detailed job information from job detail page.

        Args:
            html_content: HTML content from job detail page

        Returns:
            Dictionary with detailed job information
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            details = {}

            # Extract job description
            desc_elem = (soup.find(class_=re.compile(r'description|detail|content|body', re.I)) or
                         soup.find('div', id=re.compile(r'description|detail', re.I)))

            if desc_elem:
                details['description'] = self._clean_text(desc_elem.get_text())

            # Extract requirements
            req_elem = (soup.find(class_=re.compile(r'requirement|skill|qualification', re.I)) or
                        soup.find(string=re.compile(r'必要なスキル|要件|資格', re.I)))

            if req_elem:
                if hasattr(req_elem, 'get_text'):
                    details['requirements'] = self._clean_text(req_elem.get_text())
                else:
                    # Find parent element
                    parent = req_elem.parent if req_elem.parent else None
                    if parent:
                        details['requirements'] = self._clean_text(parent.get_text())

            # Extract benefits
            benefits_elem = (soup.find(class_=re.compile(r'benefit|perk|welfare', re.I)) or
                             soup.find(string=re.compile(r'福利厚生|待遇|手当', re.I)))

            if benefits_elem:
                if hasattr(benefits_elem, 'get_text'):
                    details['benefits'] = self._clean_text(benefits_elem.get_text())
                else:
                    parent = benefits_elem.parent if benefits_elem.parent else None
                    if parent:
                        details['benefits'] = self._clean_text(parent.get_text())

            # Extract work schedule/hours
            schedule_elem = (soup.find(class_=re.compile(r'schedule|hour|time', re.I)) or
                             soup.find(string=re.compile(r'勤務時間|労働時間|シフト', re.I)))

            if schedule_elem:
                if hasattr(schedule_elem, 'get_text'):
                    details['schedule'] = self._clean_text(schedule_elem.get_text())
                else:
                    parent = schedule_elem.parent if schedule_elem.parent else None
                    if parent:
                        details['schedule'] = self._clean_text(parent.get_text())

            # Extract application deadline
            deadline_elem = (soup.find(class_=re.compile(r'deadline|expire|close', re.I)) or
                             soup.find(string=re.compile(r'締切|応募期限|募集終了', re.I)))

            if deadline_elem:
                if hasattr(deadline_elem, 'get_text'):
                    deadline_text = deadline_elem.get_text()
                else:
                    deadline_text = str(deadline_elem)
                details['application_deadline'] = self._parse_date(deadline_text)

            # Extract contact information
            contact_elem = soup.find(class_=re.compile(r'contact|email|phone', re.I))
            if contact_elem:
                details['contact_info'] = self._clean_text(contact_elem.get_text())

            # Extract application instructions
            apply_elem = (soup.find(class_=re.compile(r'apply|application|instruction', re.I)) or
                          soup.find(string=re.compile(r'応募方法|申込み方法', re.I)))

            if apply_elem:
                if hasattr(apply_elem, 'get_text'):
                    details['application_instructions'] = self._clean_text(apply_elem.get_text())
                else:
                    parent = apply_elem.parent if apply_elem.parent else None
                    if parent:
                        details['application_instructions'] = self._clean_text(parent.get_text())

            # Look for application form or button
            apply_button = soup.find(['button', 'a'], class_=re.compile(r'apply|submit|応募', re.I))
            if apply_button:
                details['apply_url'] = apply_button.get('href') or apply_button.get('data-url')
                details['has_apply_button'] = True

            return details

        except Exception as e:
            logger.error(f"Error parsing job details: {e}")
            return {}

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""

        # Remove extra whitespace and newlines
        text = re.sub(r'\s+', ' ', text.strip())

        # Remove common unwanted characters
        text = re.sub(r'[^\w\s\-.,!?()/@#$%&*+=:;「」【】『』]', '', text)

        return text

    def _parse_date(self, date_text: str) -> Optional[str]:
        """
        Parse date from various Japanese and English formats.

        Args:
            date_text: Text containing date information

        Returns:
            ISO format date string or None
        """
        try:
            date_text = date_text.strip()

            # Handle relative dates (Japanese)
            if '日前' in date_text:
                days_match = re.search(r'(\d+)日前', date_text)
                if days_match:
                    days_ago = int(days_match.group(1))
                    date = datetime.now() - timedelta(days=days_ago)
                    return date.isoformat()

            if '時間前' in date_text:
                hours_match = re.search(r'(\d+)時間前', date_text)
                if hours_match:
                    hours_ago = int(hours_match.group(1))
                    date = datetime.now() - timedelta(hours=hours_ago)
                    return date.isoformat()

            # Handle relative dates (English)
            if 'yesterday' in date_text.lower():
                date = datetime.now() - timedelta(days=1)
                return date.isoformat()

            if 'today' in date_text.lower():
                return datetime.now().isoformat()

            # Handle absolute dates
            # Try various date formats
            date_patterns = [
                r'(\d{4})/(\d{1,2})/(\d{1,2})',  # YYYY/MM/DD
                r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
                r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
                r'(\d{1,2})-(\d{1,2})-(\d{4})',  # MM-DD-YYYY
            ]

            for pattern in date_patterns:
                match = re.search(pattern, date_text)
                if match:
                    try:
                        if len(match.group(1)) == 4:  # Year first
                            year, month, day = match.groups()
                        else:  # Year last
                            month, day, year = match.groups()

                        date = datetime(int(year), int(month), int(day))
                        return date.isoformat()
                    except ValueError:
                        continue

            return None

        except Exception as e:
            logger.error(f"Error parsing date '{date_text}': {e}")
            return None

    def _extract_id_from_url(self, url: str) -> Optional[str]:
        """Extract job ID from URL."""
        try:
            if not url:
                return None

            # Look for numeric ID in URL
            id_match = re.search(r'/jobs?/(\d+)', url)
            if id_match:
                return id_match.group(1)

            # Look for any ID parameter
            id_match = re.search(r'[?&]id=([^&]+)', url)
            if id_match:
                return id_match.group(1)

            return None

        except Exception:
            return None

    def extract_skills_from_text(self, text: str) -> List[str]:
        """
        Extract technical skills and keywords from text.

        Args:
            text: Text to analyze

        Returns:
            List of identified skills
        """
        if not text:
            return []

        # Common technical skills - extend as needed
        skill_patterns = [
            r'\b(Python|Java|JavaScript|TypeScript|React|Vue|Angular|Node\.js)\b',
            r'\b(HTML|CSS|SQL|MongoDB|PostgreSQL|MySQL|Redis)\b',
            r'\b(AWS|Azure|GCP|Docker|Kubernetes|Git|Linux)\b',
            r'\b(機械学習|AI|人工知能|データサイエンス|ビッグデータ)\b',
            r'\b(フロントエンド|バックエンド|フルスタック|API|REST)\b',
        ]

        found_skills = []
        text_lower = text.lower()

        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found_skills.extend(matches)

        # Remove duplicates and return
        return list(set(found_skills))

    def categorize_job(self, job_data: Dict) -> str:
        """
        Automatically categorize job based on title and description.

        Args:
            job_data: Job data dictionary

        Returns:
            Job category string
        """
        title = job_data.get('title', '').lower()
        description = job_data.get('description', '').lower()
        text = f"{title} {description}"

        # Category patterns
        categories = {
            'engineering': [
                'engineer', 'developer', 'programmer', 'architect',
                'エンジニア', '開発者', 'プログラマー'
            ],
            'design': [
                'designer', 'ui', 'ux', 'graphic', 'web design',
                'デザイナー', 'デザイン'
            ],
            'marketing': [
                'marketing', 'sales', 'business development',
                'マーケティング', '営業', '販売'
            ],
            'management': [
                'manager', 'director', 'lead', 'head',
                'マネージャー', '管理', '責任者'
            ],
            'data': [
                'data scientist', 'analyst', 'data engineer',
                'データサイエンティスト', 'アナリスト'
            ]
        }

        for category, keywords in categories.items():
            if any(keyword in text for keyword in keywords):
                return category

        return 'other'


# Utility functions for testing and validation
def validate_job_data(job_data: Dict) -> bool:
    """
    Validate that job data contains required fields.

    Args:
        job_data: Job data dictionary

    Returns:
        True if valid, False otherwise
    """
    required_fields = ['title']
    recommended_fields = ['company', 'url', 'location']

    # Check required fields
    for field in required_fields:
        if not job_data.get(field):
            logger.warning(f"Missing required field: {field}")
            return False

    # Warn about missing recommended fields
    for field in recommended_fields:
        if not job_data.get(field):
            logger.info(f"Missing recommended field: {field}")

    return True


def clean_job_data(job_data: Dict) -> Dict:
    """
    Clean and standardize job data.

    Args:
        job_data: Raw job data dictionary

    Returns:
        Cleaned job data dictionary
    """
    cleaned = {}

    for key, value in job_data.items():
        if isinstance(value, str):
            # Clean string values
            cleaned[key] = re.sub(r'\s+', ' ', value.strip())
        else:
            cleaned[key] = value

    return cleaned


# Example usage
if __name__ == "__main__":
    # Test parsing with sample HTML
    sample_html = """
    <div class="job-card">
        <h3 class="job-title"><a href="/jobs/123">Python Developer</a></h3>
        <div class="company-name">Tech Corp</div>
        <div class="location">Tokyo, Japan</div>
        <div class="salary">¥5,000,000 - ¥7,000,000</div>
        <div class="posted-date">2日前</div>
    </div>
    """

    parser = ShuftiParser()
    jobs = parser.parse_job_listings(sample_html)

    for job in jobs:
        print(f"Found job: {job}")
        if validate_job_data(job):
            print("✓ Valid job data")
        else:
            print("✗ Invalid job data")