import logging
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dateutil import parser
from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)


class XiaoheimiScraper:
    def __init__(self, download_location):
        self.base_url = 'https://xiaoheimi.net'
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/106.0.0.0 Safari/537.36'
        }
        self.download_location = download_location

    # This method returns all the anime's posted on the sites first page.
    def get_page_one_anime_posts(self) -> dict:
        video_name_and_link = {}
        payload = '/index.php/vod/show/area/大陆/id/4.html'
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

    # This method takes a post's url check if its recent and gets the latest video link.
    def get_latest_video_links(self, matched_posts: dict) -> list:
        logger.info("..........Checking for recent posts..........")
        latest_video_links = []
        now = datetime.now()
        for name, url in matched_posts.items():
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.text, 'lxml')
            post_update = soup.find('span', class_='text-red').text.split(' / ')
            last_updated_date = parser.parse(post_update[1])
            latest_video_number = post_update[0].strip('更新至集全')
            if last_updated_date > now:
                logger.info(f"Post named: {name} is new, latest video number: {latest_video_number}")
                latest_video_post = soup.find('li', {"title": f"{latest_video_number}"})
                latest_video_link = self.base_url + latest_video_post.find('a').get('href')
                logger.info(f"Latest Video link: {latest_video_link}")
                latest_video_links.append(latest_video_link)
            else:
                logger.warning(f"Post named: {name} is not recent")
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
        logger.info(f"Done checking recent videos Total time: {total_time}")
        return checked_video_urls

    def video_downloader(self, video_urls: list) -> None:
        logger.info("..........Downloading matched recent site videos..........")
        start = time.perf_counter()
        for url in video_urls:
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.text, 'lxml')
            file_name = soup.title.string.replace(" 在线播放 - 小宝影院 - 在线视频", '')
            download_script = soup.find(class_='embed-responsive clearfix')
            download_match = re.finditer(r'"url":"(.*?)"', str(download_script))
            download_link = None
            for match in download_match:
                download_link = match[1].replace("\\", '')
                logger.debug(download_link)

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
                'wait_for_video': (1, 120),
                'download_archive': 'logs/yt_dlp_downloads_archive.txt',
                'ffmpeg_location': 'ffmpeg/bin',
                'outtmpl': str(self.download_location) + '/' + file_name + '.%(ext)s'
            }
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download(download_link)
        end = time.perf_counter()
        total_time = end - start
        logger.info(f"Downloads finished Total time: {total_time}")
