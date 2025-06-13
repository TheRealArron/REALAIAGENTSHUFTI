#!/usr/bin/env python3
"""
Shufti Agent - Main Entry Point
Automated job application agent for Shufti platform
"""

import asyncio
import sys
import signal
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from core.agent import ShuftiAgent
from utils.logger import get_logger

logger = get_logger(__name__)


class ShuftiAgentRunner:
    """Main runner for the Shufti Agent"""

    def __init__(self):
        self.agent = None
        self.running = False

    async def start(self):
        """Start the agent"""
        try:
            # Validate settings
            if not settings.validate():
                logger.error("Invalid configuration. Please check your .env file.")
                return False

            logger.info("Starting Shufti Agent...")
            logger.info(f"Configuration: Max jobs per run: {settings.MAX_JOBS_PER_RUN}")
            logger.info(f"Job check interval: {settings.JOB_CHECK_INTERVAL} seconds")
            logger.info(f"Auto apply: {settings.AUTO_APPLY}")

            # Initialize agent
            self.agent = ShuftiAgent()
            await self.agent.initialize()

            self.running = True

            # Main loop
            while self.running:
                try:
                    logger.info("Starting job search and application cycle...")
                    await self.agent.run_cycle()

                    if not self.running:
                        break

                    logger.info(f"Cycle complete. Waiting {settings.JOB_CHECK_INTERVAL} seconds...")
                    await asyncio.sleep(settings.JOB_CHECK_INTERVAL)

                except KeyboardInterrupt:
                    logger.info("Received interrupt signal, shutting down...")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {str(e)}")
                    await asyncio.sleep(30)  # Wait before retrying

            return True

        except Exception as e:
            logger.error(f"Failed to start agent: {str(e)}")
            return False
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up resources"""
        if self.agent:
            await self.agent.cleanup()
        logger.info("Agent shutdown complete")

    def stop(self):
        """Stop the agent"""
        self.running = False


async def main():
    """Main entry point"""
    runner = ShuftiAgentRunner()

    # Handle shutdown signals
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        runner.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        success = await runner.start()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        sys.exit(1)

    # Run the agent
    asyncio.run(main())