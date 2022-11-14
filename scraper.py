import concurrent.futures
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser
from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)


class XiaoheimiScraper:
    def __init__(self) -> None:
        self.base_url = 'https://xiaoheimi.net'
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/106.0.0.0 Safari/537.36'
        }

    # This method returns all the anime's posted on the sites first page.
    def get_page_one_anime_posts(self) -> dict:
        video_name_and_link = {}
        payload = '/index.php/vod/show/area/大陆/id/4.html'
        try:
            page_response = requests.get(self.base_url + payload, headers=self.header)
            soup = BeautifulSoup(page_response.text, 'lxml')
            posts = soup.find_all('li', class_='col-lg-8 col-md-6 col-sm-4 col-xs-3')
            logger.info("..........Site Page one Anime Posts..........")
            for post in posts:
                post_name = post.find('h4', class_='title text-overflow').text
                post_url = self.base_url + post.find('a').get('href')
                logger.info(f"Post Title: {post_name}, Post URL: {post_url}")
                video_name_and_link[post_name] = post_url
            return video_name_and_link
        except Exception as error:
            logger.exception(error)
            logger.critical("Program failed to access website!\n")

    # This method takes a post's url check if its recent and gets the latest 3 video links.
    def get_latest_video_links(self, matched_posts: dict) -> list:
        logger.info("..........Checking for latest videos..........")
        latest_video_links = []
        default_num_videos = 3
        current_date_without_time = datetime.now().date()
        for name, url in matched_posts.items():
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.text, 'lxml')
            post_update = soup.find('span', class_='text-red').text.split(' / ')
            last_updated_date_without_time = parser.parse(post_update[1]).date()
            if last_updated_date_without_time >= current_date_without_time:
                latest_video_number = int(post_update[0].strip('更新至集全'))
                video_start_num = latest_video_number - default_num_videos + 1
                logger.info(f"Post named: {name} is new, latest video number: {latest_video_number}. "
                            f"Last {default_num_videos} video numbers: {video_start_num}-{latest_video_number}")
                for video_number in range(video_start_num, latest_video_number + 1):
                    video_post = soup.find('li', {"title": f"{video_number}"})
                    video_link = self.base_url + video_post.find('a').get('href')
                    logger.info(f"Video link: {video_link}")
                    latest_video_links.append(video_link)
            else:
                logger.warning(f"Post named: {name} is not recent, Last Updated: {last_updated_date_without_time}")
        return latest_video_links

    # This method checks if anime matches a recent post from the site.
    def match_to_recent_videos(self, anime_list: list) -> list:
        posts = self.get_page_one_anime_posts()
        matched_posts = {}
        logger.info("..........Matching names to site recent post..........")
        start = time.perf_counter()
        for name in anime_list:
            for post_name, post_url in posts.items():
                if name in post_name:
                    logger.info(f"Anime: {name} matches Post Title: {post_name}, Post URL: {post_url}")
                    matched_posts[post_name] = post_url
        checked_video_urls = self.get_latest_video_links(matched_posts)
        end = time.perf_counter()
        total_time = end - start
        logger.info(f"Done checking recent videos, Total time: {total_time}")
        return checked_video_urls

    @staticmethod
    def download_video(download_link: str, file_name: str, download_location: Path) -> None:
        def my_hook(d: dict) -> None:
            if d['status'] == 'error':
                logger.exception('An error has occurred ...')
            if d['status'] == 'finished':
                logger.info('Done downloading file, now post-processing ...')

        ydl_opts = {
            'logger': logger.getChild('yt_dlp'),
            'progress_hooks': [my_hook],
            'noprogress': True,
            'ignoreerrors': True,
            'socket_timeout': 120,
            'wait_for_video': (1, 600),
            'download_archive': 'logs/yt_dlp_downloads_archive.txt',
            'ffmpeg_location': 'ffmpeg/bin',
            'outtmpl': str(download_location) + '/' + file_name + '.%(ext)s'
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download(download_link)

    # This method uses the video url to find the video download link.
    # It uses yt-dlp to download the file from hls stream
    def video_downloader(self, video_url: str, download_location: Path) -> None:
        page_response = requests.get(video_url, headers=self.header)
        soup = BeautifulSoup(page_response.text, 'lxml')
        file_name = soup.title.string.strip(' 在线播放 - 小宝影院 - 在线视频')
        for match in re.finditer(r'(\d+)', file_name):
            number = match.group(0)
            file_name = file_name.replace(number, f"第{number}集")
        download_script = soup.find(class_='embed-responsive clearfix')
        download_match = re.finditer(r'"url":"(.*?)"', str(download_script))
        download_link = None
        for match in download_match:
            download_link = match[1].replace("\\", '')
        logger.info(f"Downloading Post: {video_url}, File name: {file_name}")
        logger.debug(f"Download link: {download_link}")
        self.download_video(download_link, file_name, download_location)

    def download_all_videos(self, video_urls: list, download_location: Path) -> None:
        logger.info("..........Downloading matched recent site videos..........")
        start = time.perf_counter()
        if not video_urls:
            logger.info("No Video(s) to Download")
        else:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                _ = [executor.submit(self.video_downloader, url, download_location) for url in video_urls]
            logger.info("Downloads finished!")
        end = time.perf_counter()
        total_time = end - start
        logger.info(f"Total time: {total_time}")
