import logging
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dateutil import parser
from selenium import webdriver

from utilities.ch_title_gen import ChineseTitleGenerator
from utilities.telegram_bot import send_telegram_message

logger = logging.getLogger(__name__)
# Do not log this messages unless they are at least warnings
logging.getLogger("selenium").setLevel(logging.WARNING)


class ScrapperTools:
    parser = "html.parser"
    video_num_per_post = 3  # The number of recent videos that will downloaded per post.
    download_pattern = re.compile(r'"url":"(.*?)"')
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/113.0.0.0 Safari/537.36'
    }
    ch_gen = ChineseTitleGenerator()
    # Common texts used by scrappers are shared from here.
    check_downlink_message = "..........Checking for latest videos download links.........."
    time_message = "Time taken to retrieve recent posts download links: "
    # Selenium config
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)

    @staticmethod
    def match_to_recent_videos(posts: dict, anime_list: list) -> dict:
        """
        This method checks if anime matches a recent post from the site.
        :param posts: Posts should have name as key and url as value.
        :param anime_list: List of anime's to be matched with posts.
        :return: Anime names as key and post titles and urls as values.
        """
        matched_posts = {}
        logger.info("..........Matching names to site recent post..........")
        for anime_name in anime_list:
            for post_name, post_url in posts.items():
                if anime_name in post_name:
                    logger.info(f"Anime: {anime_name} matches Post Title: {post_name}, Post URL: {post_url}")
                    matched_posts[post_name] = anime_name, post_url
        if not matched_posts:
            logger.info("No post matches found!")
        return matched_posts

    def get_num_of_videos(self, latest_video_number: int) -> int:
        if latest_video_number < self.video_num_per_post:  # Prevents asking for more videos than are available.
            return latest_video_number  # This sets the number to download all videos of the post.
        else:
            return self.video_num_per_post


class XiaobaotvScraper(ScrapperTools):
    def __init__(self, site: str) -> None:
        self.base_url = f"https://{site}"

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post name as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/index.php/vod/show/id/51/page/{page}.html"
        page_response = requests.get(self.base_url + payload, headers=self.header)
        page_response.raise_for_status()
        soup = BeautifulSoup(page_response.text, self.parser)
        posts = soup.find_all('li', class_='col-lg-8 col-md-6 col-sm-4 col-xs-3')
        for post in posts:
            post_name = post.find('h4', class_='title text-overflow').text
            post_url = self.base_url + post.find('a').get('href')
            logger.info(f"Post Title: {post_name}, Post URL: {post_url}")
            video_name_and_link[post_name] = post_url
        return video_name_and_link

    def get_recent_posts_videos_download_link(self, matched_posts: dict, archive_content: set) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info(self.check_downlink_message)
        all_download_details, current_date_without_time, start = {}, datetime.now().date(), time.perf_counter()
        for post_name, match_details in matched_posts.items():
            anime_name, url = match_details[0], match_details[1]
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.text, self.parser)
            post_update = soup.find('span', class_='text-red').text.split(' / ')
            last_updated_date = parser.parse(post_update[1]).date()
            if not last_updated_date >= current_date_without_time:
                logger.warning(f"Post named: {post_name} is not recent, Last Updated: {last_updated_date}")
                continue
            latest_video_number = int(post_update[0].strip('更新至集全'))
            num_videos = self.get_num_of_videos(latest_video_number)
            video_start_num = latest_video_number - num_videos + 1
            logger.info(f"Post named: {post_name} is new, last Updated: {last_updated_date}, "
                        f"latest video number: {latest_video_number}. "
                        f"Last {num_videos} video numbers: {video_start_num}-{latest_video_number}")
            for video_number in range(video_start_num, latest_video_number + 1):
                file_name = f"{post_name} 第{video_number}集"
                resolved_name = self.ch_gen.generate_title(file_name, anime_name)
                if resolved_name in archive_content:
                    logger.warning(f"File name: {file_name}, Resolved name: {resolved_name} already in archive! ")
                    continue
                video_post = soup.find('li', {"title": f"{video_number}"})
                video_link = self.base_url + video_post.find('a').get('href')
                download_link = self.get_video_download_link(video_link)
                logger.info(f"File name: {file_name}, Video link: {video_link}, Download link: {download_link}")
                all_download_details[resolved_name] = file_name, anime_name, download_link
        end = time.perf_counter()
        logger.info(f"{self.time_message}{end - start}\n")
        return all_download_details

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        download_link = None
        page_response = requests.get(video_url, headers=self.header)
        soup = BeautifulSoup(page_response.text, self.parser)
        download_script = soup.find(class_='embed-responsive clearfix')
        download_match = self.download_pattern.finditer(str(download_script))
        for match in download_match:
            download_link = match[1].replace("\\", '')
        return download_link


class AnimeBabyScrapper(ScrapperTools):
    def __init__(self, site: str) -> None:
        self.base_url = f"https://{site}"
        self.cloudflare_detected = self.detect_cloudflare()
        self.chrome_driver = None
        if self.cloudflare_detected:
            self.initiate_driver()

    def detect_cloudflare(self) -> bool:
        page_response = requests.get(self.base_url, headers=self.header)
        if "cloudflare" in page_response:
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
        self.chrome_driver = Chrome(headless=True, version_main=113)
        self.chrome_driver.get(self.base_url)
        time.sleep(delay)  # Time to allow cloudflare checks to finish
        page_content = self.chrome_driver.page_source
        if "cloudflare" in page_content:
            logger.error("Cloudflare bypass failed!")
            message = f"Cloudflare bypass failed on {self.base_url} site!"
            send_telegram_message(message)
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
            page_response = requests.get(url, headers=self.header)
            page_response.raise_for_status()
            return BeautifulSoup(page_response.text, self.parser)
        else:
            self.chrome_driver.get(url)
            return BeautifulSoup(self.chrome_driver.page_source, self.parser)

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post name as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/index.php/vod/show/id/20/page/{page}.html"
        soup = self.get_page_response(self.base_url + payload)
        posts = soup.find_all('a', class_="module-item-title")
        for post in posts:
            post_name = post.contents[0]
            post_url = self.base_url + post.get('href')
            logger.info(f"Post Title: {post_name}, Post URL: {post_url}")
            video_name_and_link[post_name] = post_url
        return video_name_and_link

    def get_post_video_link(self, soup: BeautifulSoup, post_name: str, video_number: int) -> str | None:
        try:
            video_post = soup.find('a', {"title": f"播放{post_name}第{video_number:02d}集"})
            return self.base_url + video_post.get('href')
        except Exception as error:
            logger.error(f"Video link not found for Video Number:{post_name}{video_number}! Error: {error}")
            return

    def get_recent_posts_videos_download_link(self, matched_posts: dict, archive_content: set) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info(self.check_downlink_message)
        all_download_details, current_date_without_time, start = {}, datetime.now().date(), time.perf_counter()
        for post_name, match_details in matched_posts.items():
            anime_name, url = match_details[0], match_details[1]
            soup = self.get_page_response(url)
            post_update = soup.find(string="更新：").parent.next_sibling.text.split("，")[0]
            last_updated_date = parser.parse(post_update).date()
            if not last_updated_date >= current_date_without_time:
                logger.warning(f"Post named: {post_name} is not recent, Last Updated: {last_updated_date}")
                continue
            latest_video_post = soup.find(string="连载：").parent.next_sibling.text
            if "已完结" in latest_video_post or "完结" in latest_video_post:
                logger.info(f"Post named: {post_name} has finished airing! URL: {url}")
                continue
            latest_video_number = int(''.join(filter(str.isdigit, latest_video_post)))
            num_videos = self.get_num_of_videos(latest_video_number)
            video_start_num = latest_video_number - num_videos + 1
            logger.info(f"Post named: {post_name} is new, last Updated: {last_updated_date}, "
                        f"latest video number: {latest_video_number}. "
                        f"Last {num_videos} video numbers: {video_start_num}-{latest_video_number}")
            for video_number in range(video_start_num, latest_video_number + 1):
                file_name = f"{post_name} 第{video_number}集"
                resolved_name = self.ch_gen.generate_title(file_name, anime_name)
                if resolved_name in archive_content:
                    logger.warning(f"File name: {file_name}, Resolved name: {resolved_name} already in archive! ")
                    continue
                video_link = self.get_post_video_link(soup, post_name, video_number)
                download_link = self.get_video_download_link(video_link)
                logger.info(f"File name: {file_name}, Video link: {video_link}, Download link: {download_link}")
                all_download_details[resolved_name] = file_name, anime_name, download_link
        end = time.perf_counter()
        logger.info(f"{self.time_message}{end - start}\n")
        if self.cloudflare_detected:
            self.close_driver()
        return all_download_details

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        if video_url:
            soup = self.get_page_response(video_url)
            download_link = soup.find(id="bfurl").get('href')
            return download_link


class EightEightMVScrapper(ScrapperTools):
    def __init__(self, site: str) -> None:
        self.base_url = f"https://{site}"

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post name as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/vod-type-id-30-pg-{page}.html"
        page_response = requests.get(self.base_url + payload, headers=self.header)
        page_response.raise_for_status()
        soup = BeautifulSoup(page_response.content, self.parser)
        posts = soup.find_all('li', class_='p1 m1')
        for post in posts:
            post_name = post.find('p', class_='name').text
            post_url = self.base_url + post.find('a', class_='link-hover').get('href')
            logger.info(f"Post Title: {post_name}, Post URL: {post_url}")
            video_name_and_link[post_name] = post_url
        return video_name_and_link

    def get_post_video_link(self, soup: BeautifulSoup, video_number: int) -> str | None:
        try:
            video_post = soup.find('a', {"title": f"第{video_number:02d}集"})
            return self.base_url + video_post.get('href')
        except Exception as error:
            logger.error(f"Video link not found for Video Number:{video_number}! Error: {error}")
            return

    def get_recent_posts_videos_download_link(self, matched_posts: dict, archive_content: set) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info("..........Checking for latest videos download links..........")
        all_download_details, current_date_without_time, start = {}, datetime.now().date(), time.perf_counter()
        for post_name, match_details in matched_posts.items():
            anime_name, url = match_details[0], match_details[1]
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.content, self.parser)
            post_update = soup.find(string="更新：").parent.next_sibling.text
            last_updated_date = parser.parse(post_update).date()
            if not last_updated_date >= current_date_without_time:
                logger.warning(f"Post named: {post_name} is not recent, Last Updated: {last_updated_date}")
                continue
            latest_video_post = soup.find(string="状态：").parent.next_sibling.text
            latest_video_number = int(''.join(filter(str.isdigit, latest_video_post)))
            num_videos = self.get_num_of_videos(latest_video_number)
            video_start_num = latest_video_number - num_videos + 1
            logger.info(f"Post named: {post_name} is new, last Updated: {last_updated_date}, "
                        f"latest video number: {latest_video_number}. "
                        f"Last {num_videos} video numbers: {video_start_num}-{latest_video_number}")
            for video_number in range(video_start_num, latest_video_number + 1):
                file_name = f"{post_name} 第{video_number}集"
                resolved_name = self.ch_gen.generate_title(file_name, anime_name)
                if resolved_name in archive_content:
                    logger.warning(f"File name: {file_name}, Resolved name: {resolved_name} already in archive! ")
                    continue
                video_link = self.get_post_video_link(soup, video_number)
                download_link = self.get_video_download_link(video_link)
                logger.info(f"File name: {file_name}, Video link: {video_link}, Download link: {download_link}")
                all_download_details[resolved_name] = file_name, anime_name, download_link
        end = time.perf_counter()
        logger.info(f"{self.time_message}{end - start}\n")
        return all_download_details

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        if video_url:
            page_response = requests.get(video_url, headers=self.header)
            soup = BeautifulSoup(page_response.content, self.parser)
            download_link = soup.find()
            return ''


class AgeDm1Scrapper(ScrapperTools):
    def __init__(self, site: str) -> None:
        self.base_url = f"http://{site}"
        self.lst_ep_tag = " LST-EP:"

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post name as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/acg/china/{page}.html"
        self.driver.get(self.base_url + payload)
        soup = BeautifulSoup(self.driver.page_source, self.parser)
        posts = soup.find_all('li', class_='anime_icon2')
        for post in posts:
            post_name = post.find('h4', class_='anime_icon2_name').text.strip()
            post_url = self.base_url + post.find('a').get('href')
            latest_video_number = post.find('span').text
            logger.info(f"Post Title: {post_name}, Post URL: {post_url}")
            video_name_and_link[f"{post_name}{self.lst_ep_tag}{latest_video_number}"] = post_url
        return video_name_and_link

    def get_post_video_link(self, soup: BeautifulSoup, video_number: int) -> str | None:
        try:
            video_post = soup.find('a', string=f"第{video_number}集")
            return self.base_url + video_post.get('href')
        except Exception as error:
            logger.error(f"Video link not found for Video Number:{video_number}! Error: {error}")
            return

    def get_recent_posts_videos_download_link(self, matched_posts: dict, archive_content: set) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info("..........Checking for latest videos download links..........")
        all_download_details, start = {}, time.perf_counter()
        for post_name_and_last_ep, match_details in matched_posts.items():
            post_split = post_name_and_last_ep.split(self.lst_ep_tag)
            post_name, latest_video_post = post_split[0], post_split[1]
            anime_name, url = match_details[0], match_details[1]
            self.driver.get(url)
            soup = BeautifulSoup(self.driver.page_source, self.parser)
            latest_video_number = int(''.join(filter(str.isdigit, latest_video_post)))
            num_videos = self.get_num_of_videos(latest_video_number)
            video_start_num = latest_video_number - num_videos + 1
            logger.info(f"Post named: {post_name}, latest video number: {latest_video_number}. "
                        f"Last {num_videos} video numbers: {video_start_num}-{latest_video_number}")
            for video_number in range(video_start_num, latest_video_number + 1):
                file_name = f"{post_name} 第{video_number}集"
                resolved_name = self.ch_gen.generate_title(file_name, anime_name)
                if resolved_name in archive_content:
                    logger.warning(f"File name: {file_name}, Resolved name: {resolved_name} already in archive! ")
                    continue
                video_link = self.get_post_video_link(soup, video_number)
                download_link = self.get_video_download_link(video_link)
                logger.info(f"File name: {file_name}, Video link: {video_link}, Download link: {download_link}")
                all_download_details[resolved_name] = file_name, anime_name, download_link
        end = time.perf_counter()
        logger.info(f"{self.time_message}{end - start}\n")
        return all_download_details

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        if video_url:
            self.driver.get(video_url)
            soup = BeautifulSoup(self.driver.page_source, self.parser)
            download_match = soup.find(id="playiframe").get('src')
            download_link = re.search(r"https://[\w./]+.m3u8", download_match)
            if download_link:
                return download_link.group()
