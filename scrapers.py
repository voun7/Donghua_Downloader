import logging
import re
import time

import requests
from bs4 import BeautifulSoup
from dateutil import parser
from selenium import webdriver

from utilities.ch_title_gen import ChineseTitleGenerator

logger = logging.getLogger(__name__)
# Do not log this messages unless they are at least warnings
logging.getLogger("selenium").setLevel(logging.WARNING)


class ScrapperTools:
    headers = anime_list = resolved_names_archive = tb = current_date = None
    video_num_per_post = None  # The number of recent videos that will downloaded per post.
    parser = "html.parser"
    ch_gen = ChineseTitleGenerator()
    # Common texts used by scrappers are shared from here.
    check_downlink_message = "..........Checking for latest videos download links.........."
    time_message = "Time taken to retrieve recent posts download links: "
    # Selenium config
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)

    def match_to_recent_videos(self, posts: dict) -> dict:
        """
        This method checks if a name from the anime list matches a recent post from the site.
        :param posts: Posts should have name as key and url as value.
        :return: Anime names as key and post titles and urls as values.
        """
        matched_posts = {}
        logger.info("..........Matching names to site recent post..........")
        for anime_name in self.anime_list:
            for post_title, post_url in posts.items():
                if anime_name in post_title:
                    logger.info(f"Anime Name: {anime_name} matches Post Title: {post_title}, Post URL: {post_url}")
                    matched_posts[post_title] = anime_name, post_url
        if not matched_posts:
            logger.info("No post matches found!")
        return matched_posts

    def get_num_of_videos(self, latest_video_number: int) -> int:
        if latest_video_number < self.video_num_per_post:  # Prevents asking for more videos than are available.
            return latest_video_number  # This sets the number to download all videos of the post.
        else:
            return self.video_num_per_post

    @staticmethod
    def video_post_num_extractor(video_post: str) -> int:
        post_num = [char for char in video_post if char.isdigit()]
        return int(''.join(post_num)) if post_num else 0


class XiaobaotvScraper(ScrapperTools):
    def __init__(self, site: str) -> None:
        self.base_url = f"https://{site}"
        self.session, self.request_type = requests.Session(), 1

    def get_page_response(self, url: str) -> BeautifulSoup:
        if self.request_type == 1:
            page_response = self.session.get(url, headers=self.headers)
            page_response.raise_for_status()
            return BeautifulSoup(page_response.text, self.parser)
        if self.request_type == 2:
            self.driver.get(url)
            return BeautifulSoup(self.driver.page_source, self.parser)

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post Title as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/index.php/vod/show/id/51/page/{page}.html"
        soup = self.get_page_response(self.base_url + payload)
        posts = soup.find_all('li', class_='col-lg-8 col-md-6 col-sm-4 col-xs-3')
        for post in posts:
            post_title = post.find('h4', class_='title text-overflow').text
            post_url = self.base_url + post.find('a').get('href')
            logger.info(f"Post Title: {post_title}, Post URL: {post_url}")
            video_name_and_link[post_title] = post_url
        return video_name_and_link

    def get_post_video_link(self, soup: BeautifulSoup, post_title: str, video_number: int) -> str | None:
        video_post1 = soup.find('li', {"title": f"{video_number}"})
        if video_post1:
            return self.base_url + video_post1.find('a').get('href')
        logger.error(f"Video Link not found for Video Number:{post_title} {video_number}!")

    def get_recent_posts_videos_download_link(self, matched_posts: dict) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info(self.check_downlink_message)
        all_download_details, start = {}, time.perf_counter()
        error_msgs = ""
        for post_title, match_details in matched_posts.items():
            try:
                anime_name, url = match_details[0], match_details[1]
                soup = self.get_page_response(url)
                post_update = soup.find('span', class_='text-red').text.split(' / ')
                last_updated_date = parser.parse(post_update[1]).date()
                if not last_updated_date >= self.current_date:
                    logger.warning(f"Post Title: {post_title} is not recent, Last Updated: {last_updated_date}")
                    continue
                latest_video_number = int(post_update[0].strip('更新至集全'))
                num_videos = self.get_num_of_videos(latest_video_number)
                video_start_num = latest_video_number - num_videos + 1
                logger.info(f"Post Title: {post_title} is new, Last Updated: {last_updated_date}, "
                            f"Latest Video Number: {latest_video_number}. "
                            f"Last {num_videos} Video Numbers: {video_start_num}-{latest_video_number}")
                for video_number in range(video_start_num, latest_video_number + 1):
                    post_video_name = f"{post_title} 第{video_number}集"
                    resolved_name = self.ch_gen.generate_title(post_video_name, anime_name)
                    if resolved_name in self.resolved_names_archive:
                        logger.warning(f"Post Video Name: {post_video_name}, "
                                       f"Resolved Name: {resolved_name} already in archive!")
                        continue
                    video_link = self.get_post_video_link(soup, post_title, video_number)
                    download_link = self.get_video_download_link(video_link)
                    logger.info(f"Post Video Name: {post_video_name}, Video Link: {video_link}, "
                                f"Download Link: {download_link}")
                    all_download_details[resolved_name] = post_video_name, download_link
            except Exception as error:
                self.request_type = 2  # change to selenium after error occurs.
                error_msg = f"An error occurred while scrapping {post_title}! \nError: {error}"
                logger.exception(error_msg)
                error_msgs = f"{error_msgs}\n{error_msg}\n"
        if error_msgs:
            self.tb.send_telegram_message(f"XiaobaotvScraper\n{error_msgs}")
        end = time.perf_counter()
        logger.info(f"{self.time_message}{end - start}")
        return all_download_details

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        if video_url:
            soup = self.get_page_response(video_url)
            download_script = soup.find(class_='embed-responsive clearfix')
            download_match = re.search(r'"url":"(.*?)"', str(download_script))
            download_link = download_match.group(1).replace("\\", '')
            return download_link


class AnimeBabyScrapper(ScrapperTools):
    def __init__(self, site: str) -> None:
        self.base_url = f"https://{site}"
        self.session = requests.Session()
        self.cloudflare_detected = self.detect_cloudflare()
        self.chrome_driver = None
        if self.cloudflare_detected:
            self.initiate_driver()

    def detect_cloudflare(self) -> bool:
        page_response = self.session.get(self.base_url, headers=self.headers)
        if "cloudflare" in page_response.text:
            logger.warning("Cloudflare detected in site!")
            return True
        else:
            logger.info("Cloudflare not detected in site.")
            return False

    def initiate_driver(self, delay: float = 12) -> None:
        """
        Initiate Chrome web driver that helps bypass cloudflare protection.
        :param delay: Time in seconds to spend waiting.
        """
        from undetected_chromedriver import Chrome
        self.chrome_driver = Chrome(headless=True)
        self.chrome_driver.get(self.base_url)
        time.sleep(delay)  # Time to allow cloudflare checks to finish
        page_content = self.chrome_driver.page_source
        if "cloudflare" in page_content:
            message = f"Cloudflare bypass failed on {self.base_url} site!"
            logger.error(message)
            self.tb.send_telegram_message(message)
        else:
            logger.info("Cloudflare bypass succeeded!")

    def close_driver(self, delay: float = 3) -> None:
        try:
            self.chrome_driver.close()
            time.sleep(delay)
        except Exception as error:
            logger.error(f"An error occurred while closing the driver! \nError: {error}")

    def get_page_response(self, url: str) -> BeautifulSoup:
        if not self.cloudflare_detected:
            page_response = self.session.get(url, headers=self.headers)
            page_response.raise_for_status()
            return BeautifulSoup(page_response.text, self.parser)
        else:
            self.chrome_driver.get(url)
            return BeautifulSoup(self.chrome_driver.page_source, self.parser)

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post Title as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/index.php/vod/show/id/20/page/{page}.html"
        soup = self.get_page_response(self.base_url + payload)
        posts = soup.find_all('a', class_="module-item-title")
        for post in posts:
            post_title = post.contents[0]
            post_url = self.base_url + post.get('href')
            logger.info(f"Post Title: {post_title}, Post URL: {post_url}")
            video_name_and_link[post_title] = post_url
        return video_name_and_link

    def get_post_video_link(self, soup: BeautifulSoup, post_title: str, video_number: int) -> str | None:
        video_post1 = soup.find('a', {"title": f"播放{post_title}第{video_number:02d}集"})
        if video_post1:
            return self.base_url + video_post1.get('href')
        video_post2 = soup.find('a', {"title": f"播放{post_title}第{video_number}集"})
        if video_post2:
            return self.base_url + video_post2.get('href')
        video_post3 = soup.find('a', {"title": f"播放{post_title}{video_number}"})
        if video_post3:
            return self.base_url + video_post3.get('href')
        logger.error(f"Video Link not found for Video Number:{post_title} {video_number}!")

    def get_recent_posts_videos_download_link(self, matched_posts: dict) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info(self.check_downlink_message)
        all_download_details, start = {}, time.perf_counter()
        for post_title, match_details in matched_posts.items():
            anime_name, url = match_details[0], match_details[1]
            soup = self.get_page_response(url)
            post_update = soup.find(string="更新：").parent.next_sibling.text.split("，")[0]
            last_updated_date = parser.parse(post_update).date()
            if not last_updated_date >= self.current_date:
                logger.warning(f"Post Title: {post_title} is not recent, Last Updated: {last_updated_date}")
                continue
            latest_video_post = soup.find(string="连载：").parent.next_sibling.text
            latest_video_number = self.video_post_num_extractor(latest_video_post)
            if not latest_video_number:
                logger.info(f"Post Title: {post_title} has finished airing! URL: {url}")
                continue
            num_videos = self.get_num_of_videos(latest_video_number)
            video_start_num = latest_video_number - num_videos + 1
            logger.info(f"Post Title: {post_title} is new, Last Updated: {last_updated_date}, "
                        f"Latest Video Number: {latest_video_number}. "
                        f"Last {num_videos} Video Numbers: {video_start_num}-{latest_video_number}")
            for video_number in range(video_start_num, latest_video_number + 1):
                post_video_name = f"{post_title} 第{video_number}集"
                resolved_name = self.ch_gen.generate_title(post_video_name, anime_name)
                if resolved_name in self.resolved_names_archive:
                    logger.warning(f"Post Video Name: {post_video_name}, "
                                   f"Resolved Name: {resolved_name} already in archive!")
                    continue
                video_link = self.get_post_video_link(soup, post_title, video_number)
                download_link = self.get_video_download_link(video_link)
                logger.info(f"Post Video Name: {post_video_name}, Video Link: {video_link}, "
                            f"Download Link: {download_link}")
                if download_link and resolved_name in all_download_details:
                    new_download_link = all_download_details[resolved_name][1]
                    download_link = self.test_download_links([download_link, new_download_link])

                all_download_details[resolved_name] = post_video_name, download_link
        end = time.perf_counter()
        logger.info(f"{self.time_message}{end - start}")
        if self.cloudflare_detected:
            self.close_driver()
        return all_download_details

    def test_download_links(self, download_links: list) -> str:
        """
        Use the classes request session to test for working download link.
        @return: Working download link
        """
        logger.debug(f"Testing download links: {download_links}")
        for link in download_links:
            try:
                page_response = self.session.get(link, headers=self.headers)
                page_response.raise_for_status()
                return link
            except requests.RequestException:
                logger.debug(f"download link: {link} failed test.")

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        if video_url:
            soup = self.get_page_response(video_url)
            download_link = soup.find(id="bfurl").get('href')
            return download_link


class AgeDm1Scrapper(ScrapperTools):
    def __init__(self, site: str) -> None:
        self.base_url = f"http://{site}"
        self.session = requests.Session()
        self.lst_ep_tag = " LST-EP:"

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post Title as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/acg/china/{page}.html"
        self.driver.get(self.base_url + payload)
        soup = BeautifulSoup(self.driver.page_source, self.parser)
        posts = soup.find_all('li', class_='anime_icon2')
        for post in posts:
            post_title = post.find('h4', class_='anime_icon2_name').text.strip()
            post_url = self.base_url + post.find('a').get('href')
            latest_video_number = post.find('span').text
            logger.info(f"Post Title: {post_title}, Post URL: {post_url}")
            video_name_and_link[f"{post_title}{self.lst_ep_tag}{latest_video_number}"] = post_url
        return video_name_and_link

    def get_post_video_link(self, soup: BeautifulSoup, video_number: int, url: str) -> str | None:
        video_post1 = soup.find('a', string=f"第{video_number}集")
        if video_post1:
            return self.base_url + video_post1.get('href')
        video_post2 = soup.find('a', class_="twidth", string=str(video_number))
        if video_post2:
            return self.base_url + video_post2.get('href')
        video_post3 = soup.find('a', string=str(video_number))
        if video_post3:
            return self.base_url + video_post3.get('href')
        video_link = f"{url}{video_number}.html"
        try:
            page_response = self.session.get(video_link, headers=self.headers)
            page_response.raise_for_status()
            return video_link
        except requests.RequestException:
            logger.error(f"Video Link: {video_link} failed test.")
        logger.error(f"Video Link not found for Video Number: {video_number}!")

    def get_recent_posts_videos_download_link(self, matched_posts: dict) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info(self.check_downlink_message)
        all_download_details, start = {}, time.perf_counter()
        for post_title_and_last_ep, match_details in matched_posts.items():
            post_split = post_title_and_last_ep.split(self.lst_ep_tag)
            post_title, latest_video_post = post_split[0], post_split[1]
            anime_name, url = match_details[0], match_details[1]
            self.driver.get(url)
            soup = BeautifulSoup(self.driver.page_source, self.parser)
            latest_video_number = self.video_post_num_extractor(latest_video_post)
            num_videos = self.get_num_of_videos(latest_video_number)
            video_start_num = latest_video_number - num_videos + 1
            logger.info(f"Post Title: {post_title}, Latest Video Number: {latest_video_number}. "
                        f"Last {num_videos} Video Numbers: {video_start_num}-{latest_video_number}")
            for video_number in range(video_start_num, latest_video_number + 1):
                post_video_name = f"{post_title} 第{video_number}集"
                resolved_name = self.ch_gen.generate_title(post_video_name, anime_name)
                if resolved_name in self.resolved_names_archive:
                    logger.warning(f"Post Video Name: {post_video_name}, "
                                   f"Resolved Name: {resolved_name} already in archive!")
                    continue
                video_link = self.get_post_video_link(soup, video_number, url)
                download_link = self.get_video_download_link(video_link)
                logger.info(f"Post Video Name: {post_video_name}, Video Link: {video_link}, "
                            f"Download Link: {download_link}")
                all_download_details[resolved_name] = post_video_name, download_link
        end = time.perf_counter()
        logger.info(f"{self.time_message}{end - start}")
        return all_download_details

    def test_download_links(self, download_links: list) -> str:
        logger.debug(f"Testing download links: {download_links}")
        for link in download_links:
            link = link.replace("497", "")
            try:
                page_response = self.session.get(link, headers=self.headers)
                page_response.raise_for_status()
                return link
            except requests.RequestException:
                logger.debug(f"download link: {link} failed test.")

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        if video_url:
            self.driver.get(video_url)
            soup = BeautifulSoup(self.driver.page_source, self.parser)
            download_match = soup.find(id="playiframe")
            if download_match:
                download_links = re.findall(r"https?://[\w\-./]+.m3u8", download_match.get('src'))
                download_link = self.test_download_links(download_links)
                if download_link:
                    return download_link


class ImyydsScrapper(ScrapperTools):
    def __init__(self, site: str) -> None:
        self.base_url = f"https://{site}"
        self.session = requests.Session()

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post Title as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/vodshow/4-国产-------{page}---.html"
        page_response = self.session.get(self.base_url + payload, headers=self.headers)
        page_response.raise_for_status()
        soup = BeautifulSoup(page_response.content, self.parser)
        posts = soup.find_all(class_='vodlist_title')
        for post in posts:
            post_title = post.text.strip()
            post_url = self.base_url + post.find('a').get('href')
            logger.info(f"Post Title: {post_title}, Post URL: {post_url}")
            video_name_and_link[post_title] = post_url
        return video_name_and_link

    def get_post_video_link(self, soup: BeautifulSoup, video_number: int) -> str | None:
        try:
            video_post = soup.find('a', string=f"第{video_number:02d}集")
            if video_post:
                video_post_link = self.base_url + video_post.get('href')
            else:
                video_post = soup.find('a', string=f"第{video_number}集")
                video_post_link = self.base_url + video_post.get('href')
            return video_post_link
        except Exception as error:
            logger.error(f"Video Link not found for Video Number:{video_number}! Error: {error}")
            return

    def get_recent_posts_videos_download_link(self, matched_posts: dict) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info(self.check_downlink_message)
        all_download_details, start = {}, time.perf_counter()
        for post_title, match_details in matched_posts.items():
            anime_name, url = match_details[0], match_details[1]
            page_response = self.session.get(url, headers=self.headers)
            soup = BeautifulSoup(page_response.content, self.parser)
            latest_video_post = soup.find(string="状态：")
            if not latest_video_post:
                logger.warning(f"Post Title: {post_title}. Latest Video Post not found! URL: {url}")
                continue
            else:
                latest_video_post = latest_video_post.parent.next_sibling.text
            if "已完结" in latest_video_post or "完结" in latest_video_post:
                logger.info(f"Post Title: {post_title} has finished airing! URL: {url}")
                continue
            latest_video_number = self.video_post_num_extractor(latest_video_post)
            num_videos = self.get_num_of_videos(latest_video_number)
            video_start_num = latest_video_number - num_videos + 1
            logger.info(f"Post Title: {post_title}, Latest Video Number: {latest_video_number}. "
                        f"Last {num_videos} Video Numbers: {video_start_num}-{latest_video_number}")
            for video_number in range(video_start_num, latest_video_number + 1):
                post_video_name = f"{post_title} 第{video_number}集"
                resolved_name = self.ch_gen.generate_title(post_video_name, anime_name)
                if resolved_name in self.resolved_names_archive:
                    logger.warning(f"Post Video Name: {post_video_name}, "
                                   f"Resolved Name: {resolved_name} already in archive!")
                    continue
                video_link = self.get_post_video_link(soup, video_number)
                download_link = self.get_video_download_link(video_link)
                logger.info(f"Post Video Name: {post_video_name}, Video Link: {video_link}, "
                            f"Download Link: {download_link}")
                all_download_details[resolved_name] = post_video_name, download_link
        end = time.perf_counter()
        logger.info(f"{self.time_message}{end - start}")
        return all_download_details

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        if video_url:
            page_response = self.session.get(video_url, headers=self.headers)
            soup = BeautifulSoup(page_response.text, self.parser)
            download_script = soup.find("script", attrs={'type': 'application/ld+json'})
            download_match = re.search(r'"contentUrl": "(.*?)"', download_script.text)
            download_link = download_match.group(1)
            return download_link


class TempScrapper(ScrapperTools):
    def __init__(self, site: str) -> None:
        self.base_url = f"https://{site}"
        self.session = requests.Session()

    def get_page_response(self, url: str, request_type: int = 1) -> BeautifulSoup:
        if request_type == 1:
            page_response = self.session.get(url, headers=self.headers)
            page_response.raise_for_status()
            return BeautifulSoup(page_response.text, self.parser)
        if request_type == 2:
            self.driver.get(url)
            return BeautifulSoup(self.driver.page_source, self.parser)

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post Title as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/{page}.html"
        soup = self.get_page_response(self.base_url + payload)
        posts = soup.find_all('a', class_="")
        for post in posts:
            post_title = post.contents[0]
            post_url = self.base_url + post.get('href')
            logger.info(f"Post Title: {post_title}, Post URL: {post_url}")
            video_name_and_link[post_title] = post_url
        return video_name_and_link

    def get_post_video_link(self, soup: BeautifulSoup, post_title: str, video_number: int) -> str | None:
        video_post1 = soup.find('a', {"title": f"播放{post_title}第{video_number:02d}集"})
        if video_post1:
            return self.base_url + video_post1.get('href')
        video_post2 = soup.find('a', {"title": f"播放{post_title}第{video_number}集"})
        if video_post2:
            return self.base_url + video_post2.get('href')
        video_post3 = soup.find('a', {"title": f"播放{post_title}{video_number}"})
        if video_post3:
            return self.base_url + video_post3.get('href')
        logger.error(f"Video Link not found for Video Number:{post_title} {video_number}!")

    def get_recent_posts_videos_download_link(self, matched_posts: dict) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info(self.check_downlink_message)
        all_download_details, start = {}, time.perf_counter()
        for post_title, match_details in matched_posts.items():
            anime_name, url = match_details[0], match_details[1]
            soup = self.get_page_response(url)
            post_update = soup.find(string="更新：").parent.next_sibling.text.split("，")[0]
            last_updated_date = parser.parse(post_update).date()
            if not last_updated_date >= self.current_date:
                logger.warning(f"Post Title: {post_title} is not recent, Last Updated: {last_updated_date}")
                continue
            latest_video_post = soup.find(string="连载：").parent.next_sibling.text
            latest_video_number = self.video_post_num_extractor(latest_video_post)
            num_videos = self.get_num_of_videos(latest_video_number)
            video_start_num = latest_video_number - num_videos + 1
            logger.info(f"Post Title: {post_title} is new, Last Updated: {last_updated_date}, "
                        f"Latest Video Number: {latest_video_number}. "
                        f"Last {num_videos} Video Numbers: {video_start_num}-{latest_video_number}")
            for video_number in range(video_start_num, latest_video_number + 1):
                post_video_name = f"{post_title} 第{video_number}集"
                resolved_name = self.ch_gen.generate_title(post_video_name, anime_name)
                if resolved_name in self.resolved_names_archive:
                    logger.warning(f"Post Video Name: {post_video_name}, "
                                   f"Resolved Name: {resolved_name} already in archive!")
                    continue
                video_link = self.get_post_video_link(soup, post_title, video_number)
                download_link = self.get_video_download_link(video_link)
                logger.info(f"Post Video Name: {post_video_name}, Video Link: {video_link}, "
                            f"Download Link: {download_link}")
                all_download_details[resolved_name] = post_video_name, download_link
        end = time.perf_counter()
        logger.info(f"{self.time_message}{end - start}")
        return all_download_details

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        if video_url:
            soup = self.get_page_response(video_url)
            download_link = soup.find(id="").get('href')
            return download_link
