import logging
import subprocess

from logger_setup import get_log

logger = logging.getLogger(__name__)


def update_and_run():
    logger.debug("Checking main git repository for updates...")

    result = subprocess.run(["git", "pull"], capture_output=True)

    if "Already up to date" in str(result.stdout):
        logger.info(f"Local repository is up to date. \n{result}\n")
    else:
        logger.warning(f"Local repository is not up to date. \n{result}\n")

    from main import main
    main()


if __name__ == '__main__':
    get_log()
    logger.debug("Logging Started")
    update_and_run()
    logger.debug("Logging Ended\n")
