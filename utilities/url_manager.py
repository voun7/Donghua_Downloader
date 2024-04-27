import json
import logging
import re

import requests

logger = logging.getLogger(__name__)


class URLManager:
    headers = url_data_file = None

    def __init__(self) -> None:
        self.url_data = self.load_url_data()
        logger.debug(f"Url Data: {self.url_data}")
        self.site_name_pattern = re.compile(r"https*://w{0,3}\.?(.+?)[/?]")

    def load_url_data(self) -> dict:
        if self.url_data_file and self.url_data_file.exists():
            try:
                url_data = json.loads(self.url_data_file.read_text())
            except json.decoder.JSONDecodeError:
                return {}
            return url_data
        else:
            return {}

    def update_url_data(self) -> None:
        """
        Update the url data file.
        """
        with open(self.url_data_file, "w") as outfile:
            json.dump(self.url_data, outfile)

    def error_check_url(self, url: str) -> str | None:
        """
        Check if the url works and catch any error that may occur when testing url.
        """
        try:
            response = requests.get(f"http://{url}", headers=self.headers)
            site_name = self.site_name_pattern.search(response.url).group(1)
            return site_name
        except requests.exceptions.ConnectionError:
            logger.error(f"Site: {url} failed to connect.")
            return

    def last_working_url(self, url: str) -> str:
        """
        Use the given website as a key to find the most recent updated url that worked in the data dict.
        """
        for value in reversed(self.url_data[url]):
            url_test = self.error_check_url(value)
            if url_test:
                return url_test

    def check_url(self, url: str) -> str:
        """
        Check site url to see if it has been updated.
        """
        site_name = self.error_check_url(url)
        if url == site_name:
            logger.debug(f"Original Site url: {url} has not changed.")
            return site_name
        if site_name and url not in self.url_data:  # Original url changed but not in data file.
            logger.debug(f"Original Site url: {url} has changed to {site_name}, url key is not in data file.")
            self.url_data[url] = [site_name]
            self.update_url_data()
        elif site_name and url in self.url_data:  # Original url changed and in data file.
            logger.debug(f"Original Site url: {url} has changed to {site_name}, url key is in data file.")
            if site_name not in self.url_data[url]:
                logger.debug(f"New site url: {site_name} being added as value.")
                self.url_data[url].append(site_name)
                self.update_url_data()
        elif site_name is None and url in self.url_data:  # Original url failed to load.
            site_name = self.last_working_url(url)
            if site_name:
                logger.warning(f"Site: {url} link has changed to {site_name}. Update site link to new link.")
            else:
                raise ConnectionError(f"Site: {url} does not work and no alternatives in data file!")
        return site_name
