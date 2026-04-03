"""
Python-based scheduler (Option B).

This is an alternative to cron for users who prefer a long-running
Python process. Cron is preferred for most setups because:
- It's built into macOS and Linux
- It handles restarts and failures independently
- It doesn't consume memory when not running

Use this only if you cannot use cron (e.g., on Windows without WSL).

Usage:
    python -m rsaf_monitor.scheduler          # Runs at 6:00 AM daily
    python -m rsaf_monitor.scheduler --time 07:00  # Custom time
"""

import argparse
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def run_scheduler(run_time: str = "06:00"):
    """
    Run the monitor on a daily schedule.

    Args:
        run_time: Time to run in HH:MM format (24-hour)
    """
    try:
        import schedule
    except ImportError:
        print("Install the schedule package: pip install schedule")
        return

    from .main import main as run_monitor

    def job():
        logger.info(f"Scheduled run triggered at {datetime.now()}")
        try:
            run_monitor()
        except Exception as e:
            logger.error(f"Scheduled run failed: {e}", exc_info=True)

    schedule.every().day.at(run_time).do(job)

    print(f"RSAF Monitor scheduler started. Will run daily at {run_time}.")
    print("Press Ctrl+C to stop.")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RSAF Monitor Scheduler")
    parser.add_argument("--time", default="06:00",
                        help="Daily run time in HH:MM format (default: 06:00)")
    args = parser.parse_args()
    run_scheduler(args.time)
