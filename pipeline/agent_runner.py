# pipeline/agent_runner.py

import asyncio
from components.job_scraper import JobScraper
from components.messaging_agent import MessagingAgent
from components.profile_loader import load_user_profile
from components.logger import append_log
from config.constants import BASE_URL, LOGIN_URL


async def run_agent(email, password, user_name, skills, bio):
    # Load user profile
    user_profile = load_user_profile(email, user_name, skills, bio)

    # Initialize JobScraper and MessagingAgent
    scraper = JobScraper(email, password)
    messaging_agent = MessagingAgent(user_name, user_profile)

    # Crawl jobs
    append_log(f"[INFO] Starting job crawl for {user_name}...")
    jobs = await scraper.crawl_jobs(user_profile)

    # Send messages for each job
    append_log(f"[INFO] Sending application messages for {len(jobs)} jobs...")
    for job in jobs:
        messaging_agent.send_message(
            job["id"],
            job["title"],
            job["description"],
            job["requirements"]
        )

    append_log("[INFO] Agent process finished.")


def run_agent_with_name(email, password, user_name, skills, bio, log_callback):
    # Set the log callback to write logs to the GUI or a file
    global append_log
    append_log = log_callback

    # Run the agent in an asyncio event loop
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_agent(email, password, user_name, skills, bio))
