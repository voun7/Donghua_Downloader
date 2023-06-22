import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import requests
from selenium import webdriver

logger = logging.getLogger(__name__)
# Do not log this messages unless they are at least warnings
logging.getLogger("selenium").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)


class RotatingProxiesRequest:
    headers = proxy_file = None
    # Selenium config
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")

    def __init__(self) -> None:
        self.url = self.request_type = self._current_proxy = None
        self._working_proxies, self._forbidden_proxies = set(), set()
        self.no_proxies_recheck, self.max_proxies_recheck = 0, 8
        self.proxy_response = requests.Response
        self.success_flag = Event()  # Event to signal working proxy found success.
        if self.proxy_file.exists():
            self.proxies = set(self.proxy_file.read_text().splitlines())
        else:
            logger.error("Proxy file not found!")
            self.proxies = set()

    def request_proxy_check(self, proxy: str, timeout: float) -> None:
        try:
            response = requests.get(self.url, proxies={"http": proxy, "https": proxy}, headers=self.headers,
                                    timeout=timeout)
            response.raise_for_status()
            page_response = response.content
            if page_response:
                if self.success_flag.is_set():  # This is for the threads that have already made requests.
                    self._working_proxies.add(proxy)
                    logger.debug(f"Working proxy: {proxy} added to working proxy set.")
                    return
                self.success_flag.set()  # Set the flag to signal success.
                logger.debug(f"Request access successful using proxy: {proxy}")
                self._current_proxy = proxy
                self.proxy_response = page_response
        except requests.exceptions.RequestException as error:
            # logger.debug(f"Error occurred when using request with proxy: {proxy}. Error: {error}")
            if "403 Client" in str(error):
                self._forbidden_proxies.add(proxy)
                logger.debug(f"Forbidden proxy: {proxy} added to forbidden proxy set.")

    def selenium_proxy_check(self, proxy: str, timeout: float) -> None:
        try:
            self.options.add_argument(f'--proxy-server={proxy}')
            driver = webdriver.Chrome(options=self.options)
            driver.set_page_load_timeout(timeout)
            driver.get(self.url)
            page_response = driver.page_source
            if page_response and len(page_response) > 600:
                if self.success_flag.is_set():  # This is for the threads that have already made requests.
                    self._working_proxies.add(proxy)
                    logger.debug(f"Working proxy: {proxy} added to set. Working proxies: {self._working_proxies}")
                    return
                self.success_flag.set()  # Set the flag to signal success.
                logger.debug(f"Selenium access successful using proxy: {proxy}")
                self._current_proxy = proxy
                self.proxy_response = page_response
            else:
                logger.debug("Page response not long enough.")
        except Exception as error:
            error_msgs = ["ERR_CONNECTION_RESET", "ERR_TUNNEL_CONNECTION_FAILED", "Timed out receiving message"]
            if not any(msg in str(error) for msg in error_msgs):
                logger.debug(f"Error occurred when using selenium with proxy: {proxy}. Error: {error}")

    def check_and_set_proxy(self, proxy: str, timeout: float = 15) -> None:
        if self.success_flag.is_set():  # Check if success has been achieved.
            return
        if self._current_proxy:
            self._current_proxy = self.proxy_response = None  # Clear memory.
        if self.request_type == 1:
            self.request_proxy_check(proxy, timeout)
        if self.request_type == 2:
            self.selenium_proxy_check(proxy, timeout)

    def check_proxies(self) -> None:
        if self._forbidden_proxies & self.proxies:
            self.proxies = self.proxies - self._forbidden_proxies  # Remove forbidden proxies from proxies set.
            logger.debug(f"Forbidden proxies removed from proxies set. Forbidden proxies: {self._forbidden_proxies}")
        logger.debug(f"Checking all proxies. Proxies size: {len(self.proxies)}")
        max_workers = 200 if self.request_type == 1 else 5
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(self.check_and_set_proxy, self.proxies)
        if not self._current_proxy:
            self.no_proxies_recheck += 1
            logger.warning(f"No working proxy found! Recking proxies! Count: {self.no_proxies_recheck}")
            if self.no_proxies_recheck > self.max_proxies_recheck:
                raise Exception("Max number of check for proxies reached! Get new proxy file list!")
            else:
                self.check_proxies()  # Recursion is used until a working proxy is found.

    def check_working_proxies(self) -> None:
        logger.debug(f"Checking working proxies. Working proxies: {self._working_proxies}")
        self.success_flag.clear()
        max_workers = 50 if self.request_type == 1 else 5
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(self.check_and_set_proxy, self._working_proxies)
        if self._current_proxy:
            logger.debug(f"Working proxy: {self._current_proxy} from set worked!")
        else:
            self._working_proxies = set()  # Empty set.
            logger.debug("No working proxy in the set worked.")

    def get_proxy(self, url: str, request_type: int) -> str | None:
        self.url, self.request_type = url, request_type

        if self._current_proxy:  # Previously working proxy.
            self.success_flag.clear()
            self.check_and_set_proxy(self._current_proxy, 30)  # Check if the working proxy still works.
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
