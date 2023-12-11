import logging
import re

import requests

logger = logging.getLogger(__name__)


class URLManager:
    tb = headers = None

    def check_url(self, url: str) -> str:
        """
        Check site url to see if it has been updated.
        """
        try:
            response = requests.get(f"https://{url}")
        except requests.exceptions.ConnectionError:
            response = requests.get(f"http://{url}")
        site_url = re.search(r"https*://(.+?)/", response.url).group(1)
        if url != site_url:
            error_message = f"Site: {url} link has changed to {site_url}. Update site link soon to new link."
            logger.warning(error_message)
            self.tb.send_telegram_message(error_message)
        return site_url
