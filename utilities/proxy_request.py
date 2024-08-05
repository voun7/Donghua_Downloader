import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import requests

logger = logging.getLogger(__name__)
# Do not log this messages unless they are at least warnings
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)


class RotatingProxiesRequest:
    headers = proxy_file = None

    def __init__(self) -> None:
        """
        A class that uses the provided url to search for working proxies.
        Some free proxy sites:
        https://proxyscrape.com/free-proxy-list
        https://github.com/TheSpeedX/PROXY-List
        https://free-proxy-list.net/
        """
        self.all_proxies = self.url = self.current_proxy = self.proxy_response = None
        self.working_proxies, self.forbidden_proxies = set(), set()
        self.no_proxies_recheck, self.max_proxies_recheck = 0, 4
        self.success_flag = Event()  # Event to signal working proxy found success.
        if self.proxy_file.exists():
            self.all_proxies = set(self.proxy_file.read_text().splitlines())
        else:
            logger.error("Proxy file not found!")

    def clear_success_flag(self) -> None:
        self.success_flag.clear()
        logger.debug("Success flag cleared")

    @staticmethod
    def parse_proxy(proxy: str) -> str:
        """
        Check the proxy and process it as needed. Proxy with username and password will be reconstructed.
        """
        p_spl = proxy.split(":")
        if p_spl[-1].isdigit():
            return proxy
        return f"http://{p_spl[2]}:{p_spl[3]}@{p_spl[0]}:{p_spl[1]}"

    def proxy_check(self, proxy: str) -> None:
        """
        Check if a single proxy is working or is blocked.
        """
        original_proxy, proxy = proxy, self.parse_proxy(proxy)
        response = requests.get(self.url, proxies={"http": proxy}, headers=self.headers, timeout=5)
        if response.status_code == 403:
            self.forbidden_proxies.add(original_proxy)
            logger.debug(f"Forbidden proxy: {proxy} added to forbidden proxies.")
        else:
            self.working_proxies.add(proxy)
            logger.debug(f"Working proxy: {proxy} added to working proxies.")
            if self.success_flag.is_set():  # This is for the threads that have already made requests.
                return
            self.success_flag.set()  # Set the flag to signal success.
            logger.debug(f"Success flag set. Current proxy set to: {proxy}")
            self.current_proxy, self.proxy_response = proxy, response.content

    def check_and_set_proxy(self, proxy: str) -> None:
        """
        Check if event flag is set and stop other threads from making new proxy checks.
        This helps quickly stop new threads after the current proxy and success flags have been set.
        """
        if self.success_flag.is_set():
            return
        if self.current_proxy:
            self.current_proxy = self.proxy_response = None  # Clear memory.
        self.proxy_check(proxy)

    def check_working_proxies(self) -> None:
        """
        Recheck all previously discovered working proxies.
        """
        logger.debug(f"Checking working proxies. Working proxies: {self.working_proxies}")
        self.clear_success_flag()
        with ThreadPoolExecutor(50) as executor:
            executor.map(self.check_and_set_proxy, self.working_proxies)
        if self.current_proxy:
            logger.debug(f"Working proxy: {self.current_proxy} from set worked!")
        else:
            self.working_proxies = set()  # Empty set.
            logger.debug("No working proxy in the set worked. Set has been emptied.")

    def check_all_proxies(self) -> None:
        """
        Check all proxies from proxy file for a working proxy. Check stops when max recheck value exceeded.
        """
        if self.forbidden_proxies:
            self.all_proxies = self.all_proxies - self.forbidden_proxies
            logger.debug(f"Forbidden proxies removed from all proxies. {len(self.forbidden_proxies)=}")
        logger.debug(f"Checking all proxies. Proxies size: {len(self.all_proxies)}")
        self.clear_success_flag()
        with ThreadPoolExecutor(200) as executor:
            executor.map(self.check_and_set_proxy, self.all_proxies)
        if not self.current_proxy:
            self.no_proxies_recheck += 1
            logger.warning(f"No working proxy found! Recking proxies! Count: {self.no_proxies_recheck}")
            if self.no_proxies_recheck > self.max_proxies_recheck:
                logger.critical("Max number of check for proxies reached! Get new proxies!")
            else:
                self.check_all_proxies()  # Recursion is used until a working proxy is found.

    def get_proxy(self, url: str) -> str | None:
        """
        Entry point of program.
        :param url: url used to test proxies.
        :return: A working proxy or None if no working proxy is found for given url.
        """
        self.url = url

        if self.current_proxy:  # Previously working proxy.
            self.clear_success_flag()
            self.check_and_set_proxy(self.current_proxy)  # Check if the working proxy still works.
            if self.current_proxy:  # Double check if a proxy was given.
                logger.debug("Current proxy worked!")
                return self.current_proxy
            else:
                logger.debug("Current proxy did not work!")

        if self.working_proxies:
            self.check_working_proxies()
            if self.current_proxy:
                return self.current_proxy

        if not self.current_proxy:
            self.check_all_proxies()
            return self.current_proxy
