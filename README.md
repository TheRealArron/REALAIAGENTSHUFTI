# Shufti Agent

An intelligent AI agent that automates the entire job workflow on Shufti.jp - from job discovery and application to communication and delivery.

## Overview

The Shufti Agent is a comprehensive automation solution that:
- Scrapes and monitors job listings from Shufti.jp
- Intelligently matches jobs based on your capabilities
- Automatically applies to suitable positions
- Handles client communication throughout the project
- Processes tasks and delivers completed work
- Maintains conversation context and project state

## Features

### 🔍 Job Discovery
- Automated job listing scraping with rate limiting
- Intelligent job parsing and categorization
- Real-time monitoring for new opportunities

### 🎯 Smart Matching
- AI-powered job requirement analysis
- Capability-based job filtering
- Customizable matching criteria

### 📝 Automated Application
- Dynamic application generation
- Portfolio and experience highlighting
- Professional proposal creation

### 💬 Communication Management
- Automated message handling
- Context-aware response generation
- Multi-language support (Japanese/English)

### 🚀 Task Processing & Delivery
- Intelligent task breakdown
- Automated work processing
- Quality assurance and submission

## Architecture

```
shufti_agent/
├── config/          # Configuration and settings
├── core/           # Main orchestration logic
├── modules/        # Feature-specific modules
│   ├── crawler/    # Job scraping and parsing
│   ├── auth/       # Authentication handling
│   ├── application/# Job matching and application
│   ├── communication/ # Message handling
│   ├── delivery/   # Task processing and submission
│   └── llm/        # AI service integration
├── utils/          # Shared utilities
└── tests/          # Test suite
```

## Quick Start

### Prerequisites
- Python 3.8+
- Chrome/Chromium browser
- Valid Shufti.jp account

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd shufti_agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Configure your settings in `config/settings.py`:
```python
# Update with your Shufti credentials and preferences
SHUFTI_EMAIL = "your-email@example.com"
SHUFTI_PASSWORD = "your-password"
```

### Running the Agent

```bash
python main.py
```

The agent will start monitoring jobs and automatically handle the complete workflow.

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Shufti Account
SHUFTI_EMAIL=your-email@example.com
SHUFTI_PASSWORD=your-secure-password

# AI Service (using free/local models)
AI_MODEL_NAME=gpt2
AI_MAX_TOKENS=1000

# Rate Limiting
RATE_LIMIT_DELAY=2
MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/agent.log

# Job Preferences
AUTO_APPLY=true
MIN_BUDGET=1000
MAX_APPLICATIONS_PER_DAY=5
```

### Job Matching Criteria

Customize job matching in `modules/application/job_matcher.py`:

```python
MATCHING_CRITERIA = {
    'skills': ['Python', 'AI', 'Web Development'],
    'min_budget': 1000,
    'max_duration': 30,  # days
    'categories': ['IT', 'Programming', 'AI/ML']
}
```

## Usage Examples

### Basic Monitoring
```python
from core.agent import ShuftiAgent

agent = ShuftiAgent()
agent.start_monitoring()  # Continuous job monitoring
```

### Manual Job Processing
```python
# Process specific job
job_id = "12345"
agent.process_job(job_id)

# Apply to job manually
agent.apply_to_job(job_id, custom_proposal="Custom proposal text")
```

### Communication Handling
```python
# Process new messages
agent.handle_messages()

# Respond to specific message
message_id = "msg_123"
agent.respond_to_message(message_id)
```

## Module Details

### Crawler Module
- **scraper.py**: Handles job listing extraction with rate limiting
- **parser.py**: Parses HTML content and extracts job details

### Authentication Module
- **login.py**: Manages Shufti.jp authentication and session handling

### Application Module
- **job_matcher.py**: AI-powered job matching based on criteria
- **applicator.py**: Generates and submits job applications

### Communication Module
- **message_handler.py**: Processes incoming messages and notifications
- **responder.py**: Generates contextually appropriate responses

### Delivery Module
- **task_processor.py**: Handles task analysis and processing
- **submission.py**: Manages final deliverable submission

### LLM Module
- **ai_service.py**: Interface with AI models for text generation and analysis

## AI Models

The agent uses free/open-source AI models:
- **Text Generation**: GPT-2 (local)
- **Translation**: MarianMT models
- **Classification**: DistilBERT

These models run locally without API costs while providing good performance for the required tasks.

## Rate Limiting & Ethics

The agent implements responsible scraping practices:
- Configurable delays between requests (default: 2 seconds)
- Exponential backoff on errors
- Respect for robots.txt
- Session management to avoid excessive logins

## Logging & Monitoring

### Log Levels
- **DEBUG**: Detailed execution information
- **INFO**: General operational messages
- **WARNING**: Potential issues or rate limiting
- **ERROR**: Error conditions and failures

### Log Files
- `logs/agent.log`: Main application log
- `logs/requests.log`: HTTP request/response log
- `logs/jobs.log`: Job processing activities

## Testing

Run the test suite:
```bash
# Run all tests
python -m pytest tests/

# Run specific test module
python -m pytest tests/test_crawler.py

# Run with coverage
python -m pytest tests/ --cov=shufti_agent
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify credentials in `.env`
   - Check for CAPTCHA requirements
   - Ensure account is not locked

2. **Rate Limiting**
   - Increase `RATE_LIMIT_DELAY` in settings
   - Reduce concurrent operations
   - Check for IP blocking

3. **Job Matching Issues**
   - Review matching criteria
   - Check skill keywords
   - Verify budget ranges

4. **Memory Issues**
   - Clear old job data periodically
   - Adjust memory retention settings
   - Monitor log file sizes

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Legal & Ethical Considerations

- Use responsibly and within Shufti.jp's terms of service
- Respect rate limits and server resources
- Maintain professional communication standards
- Ensure quality of delivered work
- Monitor agent behavior regularly

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review logs for error details
3. Create an issue with detailed information
4. Include relevant log excerpts

## Roadmap

### Planned Features
- [ ] Advanced job filtering with ML
- [ ] Portfolio management integration
- [ ] Performance analytics dashboard
- [ ] Multi-platform support
- [ ] Enhanced communication templates
- [ ] Automated testing framework

### Version History
- **v1.0.0**: Initial release with core functionality
- **v1.1.0**: Enhanced AI integration and error handling
- **v1.2.0**: Improved rate limiting and logging

## Disclaimer

This tool is for educational and automation purposes. Users are responsible for:
- Complying with platform terms of service
- Ensuring quality of work delivered
- Maintaining professional standards
- Monitoring automated activities

Always review and test the agent's behavior before deploying in production environments.