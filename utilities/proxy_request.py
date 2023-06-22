import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import requests
from selenium import webdriver

logger = logging.getLogger(__name__)
# Do not log this messages unless they are at least warnings
logging.getLogger("selenium").setLevel(logging.WARNING)


class RotatingProxiesRequest:
    headers = proxy_file = None
    # Selenium config
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")

    def __init__(self) -> None:
        self.url = self.request_type = self._current_proxy = None
        self._working_proxies = set()
        self.timeout, self.no_proxies_recheck, self.max_proxies_recheck = 15, 0, 8
        self.proxy_response = requests.Response
        self.success_flag = Event()  # Event to signal working proxy found success.
        if self.proxy_file.exists():
            self.proxies = self.proxy_file.read_text().splitlines()
        else:
            logger.error("Proxy file not found!")
            self.proxies = []

    def request_proxy_check(self, proxy: str) -> None:
        try:
            response = requests.get(self.url, proxies={"http": proxy, "https": proxy}, headers=self.headers,
                                    timeout=self.timeout)
            response.raise_for_status()
            page_response = response.content
            if page_response:
                if self.success_flag.is_set():  # This is for the threads that have already made requests.
                    logger.debug(f"Working proxy: {proxy} added to set.")
                    self._working_proxies.add(proxy)
                    return
                self.success_flag.set()  # Set the flag to signal success.
                logger.info(f"Access successful using proxy: {proxy}")
                self._current_proxy = proxy
                self.proxy_response = page_response
        except requests.exceptions.RequestException as error:
            logger.debug(f"Error occurred when using request with proxy: {proxy}. Error: {error}")

    def selenium_proxy_check(self, proxy: str) -> None:
        try:
            self.options.add_argument(f'--proxy-server={proxy}')
            driver = webdriver.Chrome(options=self.options)
            driver.set_page_load_timeout(self.timeout)
            driver.get(self.url)
            page_response = driver.page_source
            if page_response:
                if self.success_flag.is_set():  # This is for the threads that have already made requests.
                    logger.debug(f"Working proxy: {proxy} added to set.")
                    self._working_proxies.add(proxy)
                    return
                self.success_flag.set()  # Set the flag to signal success.
                logger.info(f"Access successful using proxy: {proxy}")
                self._current_proxy = proxy
                self.proxy_response = page_response
        except Exception as error:
            logger.debug(f"Error occurred when using selenium with proxy: {proxy}. Error: {error}")

    def check_and_set_proxy(self, proxy: str) -> None:
        if self.success_flag.is_set():  # Check if success has been achieved.
            return
        if self._current_proxy:
            self._current_proxy = self.proxy_response = None  # Clear memory.
        if self.request_type == 1:
            self.request_proxy_check(proxy)
        if self.request_type == 2:
            self.selenium_proxy_check(proxy)

    def check_proxies(self) -> None:
        logger.debug("Checking all proxies.")
        max_workers = 200 if self.request_type == 1 else 20
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(self.check_and_set_proxy, self.proxies)
        if not self._current_proxy:
            self.no_proxies_recheck += 1
            logger.warning(f"No working proxy found! Recking proxies! Count:{self.no_proxies_recheck}")
            if self.no_proxies_recheck > self.max_proxies_recheck:
                raise Exception("Max number of check for proxies reached! Get new proxy file list!")
            else:
                self.check_proxies()  # Recursion is used until a working proxy is found.

    def check_working_proxies(self) -> None:
        logger.debug("Checking working proxies.")
        self.success_flag.clear()
        for proxy in self._working_proxies:
            self.check_and_set_proxy(proxy)
            if self._current_proxy:
                break
        if not self._current_proxy:
            self._working_proxies = set()  # Empty set.
            logger.debug("No working proxy in the set worked.")

    def get_proxy(self, url: str, request_type: float) -> str | None:
        self.url, self.request_type = url, request_type

        if self._current_proxy:  # Previously working proxy.
            self.success_flag.clear()
            self.check_and_set_proxy(self._current_proxy)  # Check if the working proxy still works.
            if self._current_proxy:  # Double check if a proxy was given.
                logger.debug("Current proxy worked!")
                return self._current_proxy
            else:
                logger.debug("Current proxy did not work!")

        if self._working_proxies:
            self.check_working_proxies()
            if self._current_proxy:
                return self._current_proxy

        if not self._current_proxy:
            self.check_proxies()
            return self._current_proxy
