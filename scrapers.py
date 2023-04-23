import logging
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser

from utilities.ch_title_gen import ChineseTitleGenerator

logger = logging.getLogger(__name__)


class ScrapperTools:
    parser = "html.parser"
    video_num_per_post = 3  # The number of recent videos that will downloaded per post.
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/106.0.0.0 Safari/537.36'
    }
    ch_gen = ChineseTitleGenerator()

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


class XiaobaotvScraper(ScrapperTools):
    def __init__(self) -> None:
        self.base_url = "https://xiaobaotv.net"

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post name as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/index.php/vod/show/id/51/page/{page}.html"
        try:
            page_response = requests.get(self.base_url + payload, headers=self.header)
            logger.info(f"Page Response = {page_response}")
            soup = BeautifulSoup(page_response.text, self.parser)
            posts = soup.find_all('li', class_='col-lg-8 col-md-6 col-sm-4 col-xs-3')
            for post in posts:
                post_name = post.find('h4', class_='title text-overflow').text
                post_url = self.base_url + post.find('a').get('href')
                logger.info(f"Post Title: {post_name}, Post URL: {post_url}")
                video_name_and_link[post_name] = post_url
            return video_name_and_link
        except Exception as error:
            logger.exception(error)
            logger.critical("Program failed to access website!\n")

    def get_recent_posts_videos_download_link(self, matched_posts: dict, download_archive: Path) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info("..........Checking for latest videos download links..........")
        all_download_details = {}
        current_date_without_time = datetime.now().date()
        start = time.perf_counter()
        archive_content = download_archive.read_text(encoding="utf-8").splitlines()
        for post_name, match_details in matched_posts.items():
            anime_name, url = match_details[0], match_details[1]
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.text, self.parser)
            post_update = soup.find('span', class_='text-red').text.split(' / ')
            last_updated_date_without_time = parser.parse(post_update[1]).date()
            if last_updated_date_without_time >= current_date_without_time:
                latest_video_number = int(post_update[0].strip('更新至集全'))
                if latest_video_number < self.video_num_per_post:  # Prevents asking for more videos than are available.
                    num_videos = latest_video_number  # This sets the number to download all videos of the post.
                else:
                    num_videos = self.video_num_per_post
                video_start_num = latest_video_number - num_videos + 1
                logger.info(f"Post named: {post_name} is new, last Updated: {last_updated_date_without_time}, "
                            f"latest video number: {latest_video_number}. "
                            f"Last {num_videos} video numbers: {video_start_num}-{latest_video_number}")
                for video_number in range(video_start_num, latest_video_number + 1):
                    video_post = soup.find('li', {"title": f"{video_number}"})
                    file_name = f"{post_name} 第{video_number}集"
                    resolved_name = self.ch_gen.generate_title(file_name, anime_name)
                    if resolved_name not in archive_content:
                        video_link = self.base_url + video_post.find('a').get('href')
                        download_link = self.get_video_download_link(video_link)
                        logger.info(f"File name: {file_name}, Video link: {video_link}, Download link: {download_link}")
                        all_download_details[download_link] = file_name, anime_name
                    else:
                        logger.warning(f"File name: {file_name}, Resolved name: {resolved_name} already in archive! ")
            else:
                logger.warning(f"Post named: {post_name} is not recent, Last Updated: {last_updated_date_without_time}")
        end = time.perf_counter()
        logger.info(f"Total time: {end - start}\n")
        return all_download_details

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        download_link = None
        page_response = requests.get(video_url, headers=self.header)
        soup = BeautifulSoup(page_response.text, self.parser)
        download_script = soup.find(class_='embed-responsive clearfix')
        download_match = re.finditer(r'"url":"(.*?)"', str(download_script))
        for match in download_match:
            download_link = match[1].replace("\\", '')
        return download_link


class AnimeBabyScrapper(ScrapperTools):
    def __init__(self) -> None:
        self.base_url = "https://www.animebaby.top"

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post name as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"/index.php/vod/show/id/20/page/{page}.html"
        try:
            page_response = requests.get(self.base_url + payload, headers=self.header)
            logger.info(f"Page Response = {page_response}")
            soup = BeautifulSoup(page_response.text, self.parser)
            posts = soup.find_all('a', class_="module-item-title")
            for post in posts:
                post_name = post.contents[0]
                post_url = self.base_url + post.get('href')
                logger.info(f"Post Title: {post_name}, Post URL: {post_url}")
                video_name_and_link[post_name] = post_url
            return video_name_and_link
        except Exception as error:
            logger.exception(error)
            logger.critical("Program failed to access website!\n")

    def get_recent_posts_videos_download_link(self, matched_posts: dict, download_archive: Path) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info("..........Checking for latest videos download links..........")
        all_download_details = {}
        current_date_without_time = datetime.now().date()
        start = time.perf_counter()
        archive_content = download_archive.read_text(encoding="utf-8").splitlines()
        for post_name, match_details in matched_posts.items():
            anime_name, url = match_details[0], match_details[1]
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.text, self.parser)
            post_update = soup.find(string="更新：").parent.next_sibling.text.split("，")[0]
            last_update_time = parser.parse(post_update).date()
            if last_update_time >= current_date_without_time:
                latest_video_number = int(soup.find(string="连载：").parent.next_sibling.text.strip("全更新至集第"))
                if latest_video_number < self.video_num_per_post:  # Prevents asking for more videos than are available.
                    num_videos = latest_video_number  # This sets the number to download all videos of the post.
                else:
                    num_videos = self.video_num_per_post
                video_start_num = latest_video_number - num_videos + 1
                logger.info(f"Post named: {post_name} is new, last Updated: {last_update_time}, "
                            f"latest video number: {latest_video_number}. "
                            f"Last {num_videos} video numbers: {video_start_num}-{latest_video_number}")
                for video_number in range(video_start_num, latest_video_number + 1):
                    video_post = soup.find('a', {"title": f"播放{post_name}第{video_number:02d}集"})
                    file_name = f"{post_name} 第{video_number}集"
                    resolved_name = self.ch_gen.generate_title(file_name, anime_name)
                    if resolved_name not in archive_content:
                        try:
                            video_link = self.base_url + video_post.get('href')
                        except Exception as error:
                            video_link = None
                            logger.error(f"Video link not found! Error: {error}")
                        download_link = self.get_video_download_link(video_link)
                        logger.info(f"File name: {file_name}, Video link: {video_link}, Download link: {download_link}")
                        all_download_details[download_link] = file_name, anime_name
                    else:
                        logger.warning(f"File name: {file_name}, Resolved name: {resolved_name} already in archive! ")
            else:
                logger.warning(f"Post named: {post_name} is not recent, Last Updated: {last_update_time}")
        end = time.perf_counter()
        logger.info(f"Total time: {end - start}\n")
        return all_download_details

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        if video_url:
            page_response = requests.get(video_url, headers=self.header)
            soup = BeautifulSoup(page_response.text, self.parser)
            download_link = soup.find(id="bfurl").get('href')
            return download_link


class TempScrapper(ScrapperTools):
    def __init__(self) -> None:
        self.base_url = ""

    def get_anime_posts(self, page: int = 1) -> dict:
        """
        This method returns all the anime's posted on the sites given page.
        :return: Post name as key and url as value.
        """
        logger.info(f"..........Site Page {page} Anime Posts..........")
        video_name_and_link = {}
        payload = f"{page}"
        try:
            page_response = requests.get(self.base_url + payload, headers=self.header)
            logger.info(f"Page Response = {page_response}")
            soup = BeautifulSoup(page_response.text, self.parser)
            posts = soup.find_all()
            for post in posts:
                post_name = ''
                post_url = ''
                logger.info(f"Post Title: {post_name}, Post URL: {post_url}")
                video_name_and_link[post_name] = post_url
            return video_name_and_link
        except Exception as error:
            logger.exception(error)
            logger.critical("Program failed to access website!\n")

    def get_recent_posts_videos_download_link(self, matched_posts: dict) -> dict:
        """
        Check if post's url latest video is recent and gets the videos download links of it and its other recent posts.
        How many of the other recent post videos are determined by video_num_per_post value.
        """
        logger.info("..........Checking for latest videos download links..........")
        all_download_details = {}
        current_date_without_time = datetime.now().date()
        start = time.perf_counter()
        for post_name, match_details in matched_posts.items():
            anime_name, url = match_details[0], match_details[1]
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.text, self.parser)
            post_update = soup.find()
            last_update_time = parser.parse(post_update).date()
            if last_update_time >= current_date_without_time:
                latest_video_number = int(soup.find())
                if latest_video_number < self.video_num_per_post:  # Prevents asking for more videos than are available.
                    num_videos = latest_video_number  # This sets the number to download all videos of the post.
                else:
                    num_videos = self.video_num_per_post
                video_start_num = latest_video_number - num_videos + 1
                logger.info(f"Post named: {post_name} is new, last Updated: {last_update_time}, "
                            f"latest video number: {latest_video_number}. "
                            f"Last {num_videos} video numbers: {video_start_num}-{latest_video_number}")
                for video_number in range(video_start_num, latest_video_number + 1):
                    video_post = soup.find()
                    file_name = f""
                    try:
                        video_link = ''
                    except Exception as error:
                        video_link = None
                        logger.error(f"Video link not found! Error: {error}")
                    download_link = self.get_video_download_link(video_link)
                    logger.info(f"File name: {file_name}, Video link: {video_link}, Download link: {download_link}")
                    all_download_details[download_link] = file_name, anime_name
            else:
                logger.warning(f"Post named: {post_name} is not recent, Last Updated: {last_update_time}")
        end = time.perf_counter()
        logger.info(f"Total time: {end - start}\n")
        return all_download_details

    def get_video_download_link(self, video_url: str) -> str:
        """
        This method uses the video url to find the video download link.
        """
        if video_url:
            page_response = requests.get(video_url, headers=self.header)
            soup = BeautifulSoup(page_response.text, self.parser)
            download_link = soup.find()
            return download_link
