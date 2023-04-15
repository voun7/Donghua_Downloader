import logging
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser

from utilities.downloader import ScrapperDownloader

logger = logging.getLogger(__name__)


class XiaoheimiScraper:
    def __init__(self) -> None:
        self.video_num_per_post = 3  # The number of recent videos that will downloaded per post.
        self.parser = "html.parser"
        self.base_url = 'https://xiaoheimi.net'
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/106.0.0.0 Safari/537.36'
        }

    def get_page_one_anime_posts(self) -> dict:
        """
        This method returns all the anime's posted on the sites first page.
        """
        logger.info("..........Site Page one Anime Posts..........")
        video_name_and_link = {}
        payload = '/index.php/vod/show/area/大陆/id/4.html'
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

    def get_latest_video_links(self, matched_posts: dict) -> dict:
        """
        This method takes a post's url check if its recent and gets the latest number of video links.
        """
        logger.info("..........Checking for latest videos..........")
        latest_video_links = {}
        current_date_without_time = datetime.now().date()
        for match_name, match_details in matched_posts.items():
            post_name, url = match_details[0], match_details[1]
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
                logger.info(f"Post named: {post_name} is new, latest video number: {latest_video_number}. "
                            f"Last {num_videos} video numbers: {video_start_num}-{latest_video_number}")
                for video_number in range(video_start_num, latest_video_number + 1):
                    video_post = soup.find('li', {"title": f"{video_number}"})
                    video_link = self.base_url + video_post.find('a').get('href')
                    logger.info(f"Video link: {video_link}")
                    latest_video_links[video_link] = match_name
            else:
                logger.warning(f"Post named: {post_name} is not recent, Last Updated: {last_updated_date_without_time}")
        return latest_video_links

    def match_to_recent_videos(self, anime_list: list) -> dict:
        """
        This method checks if anime matches a recent post from the site.
        """
        posts = self.get_page_one_anime_posts()
        matched_posts = {}
        logger.info("..........Matching names to site recent post..........")
        for name in anime_list:
            for post_name, post_url in posts.items():
                if name in post_name:
                    logger.info(f"Anime: {name} matches Post Title: {post_name}, Post URL: {post_url}")
                    matched_posts[name] = post_name, post_url
        if matched_posts:
            checked_video_urls = self.get_latest_video_links(matched_posts)
            return checked_video_urls
        else:
            logger.info("No post matches found!")
            return {}

    def get_video_download_link(self, video_url: str) -> tuple:
        """
        This method uses the video url to find the video download link.
        """
        download_link = None
        page_response = requests.get(video_url, headers=self.header)
        soup = BeautifulSoup(page_response.text, self.parser)
        file_name = soup.title.string.strip(' 在线播放 - 小宝影院 - 在线视频').replace('-', ' ')
        for match in re.finditer(r'(\d+)', file_name):
            number = match.group(0)
            file_name = file_name.replace(number, f"第{number}集")
        download_script = soup.find(class_='embed-responsive clearfix')
        download_match = re.finditer(r'"url":"(.*?)"', str(download_script))
        for match in download_match:
            download_link = match[1].replace("\\", '')
        return download_link, file_name

    def download_all_videos(self, video_matches: dict, download_location: Path, download_archives: Path) -> None:
        logger.info("..........Getting download links for video matches..........")
        if not video_matches:
            logger.info("No Video Matches!")
            return
        start = time.perf_counter()
        sd = ScrapperDownloader(download_location, download_archives)
        all_download_details = {}
        for video_link, match_name in video_matches.items():
            download_link, file_name = self.get_video_download_link(video_link)
            logger.info(f"File name: {file_name}, Download link: {download_link}")
            all_download_details[download_link] = file_name, match_name
        end = time.perf_counter()
        logger.info(f"Total time: {end - start}")
        sd.batch_downloader(all_download_details)
