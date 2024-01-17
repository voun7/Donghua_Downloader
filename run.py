import logging
import subprocess
import sys

from utilities.logger_setup import setup_logging

logger = logging.getLogger(__name__)


def update_and_run():
    logger.debug("Checking main git repository for updates...")

    result = subprocess.run(["git", "pull", "origin", "master"], capture_output=True)

    if "Already up to date" in str(result.stdout):
        logger.info(f"Local repository is up to date. \n{result}\n")
    else:
        logger.warning(f"Local repository is not up to date. \n{result}\n")
        req = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], capture_output=True)
        logger.info(f"Updating requirements...\n {req}")

    from main import main
    main()


if __name__ == '__main__':
    setup_logging()
    logger.debug("Logging Started")
    update_and_run()
    logger.debug("Logging Ended\n")
