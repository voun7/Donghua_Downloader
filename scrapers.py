import concurrent.futures
import logging
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser

from ch_title_gen import ChineseTitleGenerator

logger = logging.getLogger(__name__)


class XiaoheimiScraper:
    def __init__(self, download_archives) -> None:
        self.download_archives = download_archives / "resolved_names_download_archive.txt"
        self.archive_content = []
        self.new_archive_names = []
        if self.download_archives.exists():
            self.archive_content = self.download_archives.read_text(encoding="utf-8").splitlines()
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

    def get_latest_video_links(self, matched_posts: dict, default_num_videos: int = 3) -> dict:
        """
        This method takes a post's url check if its recent and gets
        the latest default number of video links.
        """
        logger.info("..........Checking for latest videos..........")
        latest_video_links = {}
        current_date_without_time = datetime.now().date()
        for match_name, match_details in matched_posts.items():
            post_name = match_details[0]
            url = match_details[1]
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.text, self.parser)
            post_update = soup.find('span', class_='text-red').text.split(' / ')
            last_updated_date_without_time = parser.parse(post_update[1]).date()
            if last_updated_date_without_time >= current_date_without_time:
                latest_video_number = int(post_update[0].strip('更新至集全'))
                if latest_video_number < default_num_videos:
                    num_videos = latest_video_number
                else:
                    num_videos = default_num_videos
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

    def update_download_archive(self) -> None:
        """
        Updated the names download archive with the new names.
        """
        if self.new_archive_names:
            with open(self.download_archives, 'a', encoding="utf-8") as text_file:
                text_file.writelines(self.new_archive_names)

    def check_download_archive(self, file_name: str) -> bool:
        """
        Check if file name is in archive.
        :param file_name: name of file.
        """
        name_no_s1 = None
        if "S1 " in file_name:  # For cases were the first season indicator is included.
            name_no_s1 = file_name.replace("S1 ", "")

        if any(name in self.archive_content for name in [file_name, name_no_s1]):
            logger.debug(f"File: {file_name} is in archive.")
            return True
        else:
            logger.debug(f"File: {file_name} is not in archive.")
            return False

    def m3u8_video_download(self, file_name: str, video_match_name: str, download_link: str,
                            download_location: Path) -> None:
        """
        Use m3u8 link to download video and create mp4 file.
        Embedded advertisements links will be removed.
        """
        file_path = Path(f"{download_location}/{file_name}.mp4")
        gen = ChineseTitleGenerator()
        resolved_name = gen.generate_title(file_name, video_match_name)
        if file_path.exists():
            logger.info(f"Resolved name: {resolved_name}, File: {file_name} exists in directory. Skipping download!")
            return
        if self.check_download_archive(resolved_name):
            logger.info(f"Resolved name: {resolved_name}, File: {file_name} exists in the archive. Skipping download!")
            return

        # Make a request to the m3u8 file link.
        response = requests.get(download_link)
        # Remove embedded advertisement fragments from the response text if any.
        advert_tag = "#EXT-X-DISCONTINUITY\n"
        advert_pattern = re.compile(re.escape(advert_tag) + "(.*?)" + re.escape(advert_tag), re.DOTALL)
        ad_free_m3u8_text = advert_pattern.sub("", response.text)

        temp_m3u8_file = Path(f"{download_location}/{file_name}_filtered_playlist.m3u8")
        temp_m3u8_file.write_text(ad_free_m3u8_text)

        # Use ffmpeg to download and convert the modified playlist.
        command = ['ffmpeg/bin/ffmpeg', '-protocol_whitelist', 'file,http,https,tcp,tls', '-i', str(temp_m3u8_file),
                   '-c', 'copy', str(file_path)]
        subprocess.run(command, stderr=subprocess.DEVNULL)
        # Clean up the filtered playlist file.
        temp_m3u8_file.unlink()

        if file_path.exists():
            logger.info(f"Resolved name: {resolved_name}, File: {file_path.name}, downloaded successfully!")
            self.new_archive_names.append(resolved_name + "\n")

    def video_downloader(self, video_match: tuple, download_location: Path) -> None:
        """
        This method uses the video url to find the video download link.
        It uses yt-dlp to download the file from hls stream.
        """
        video_url = video_match[0]
        video_match_name = video_match[1]
        page_response = requests.get(video_url, headers=self.header)
        soup = BeautifulSoup(page_response.text, self.parser)
        file_name = soup.title.string.strip(' 在线播放 - 小宝影院 - 在线视频').replace('-', ' ')
        for match in re.finditer(r'(\d+)', file_name):
            number = match.group(0)
            file_name = file_name.replace(number, f"第{number}集")
        download_script = soup.find(class_='embed-responsive clearfix')
        download_match = re.finditer(r'"url":"(.*?)"', str(download_script))
        download_link = None
        for match in download_match:
            download_link = match[1].replace("\\", '')
        logger.debug(f"Downloading Post: {video_url}, File name: {file_name}, Download link: {download_link}")
        self.m3u8_video_download(file_name, video_match_name, download_link, download_location)

    def download_all_videos(self, video_matches: dict, download_location: Path) -> None:
        logger.info("..........Downloading matched recent site videos..........")
        start = time.perf_counter()
        if not video_matches:
            logger.info("No Video(s) to Download!")
        else:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                _ = [executor.submit(self.video_downloader, video, download_location)
                     for video in video_matches.items()]
            self.update_download_archive()
            logger.info("Downloads finished!")
        end = time.perf_counter()
        total_time = end - start
        logger.info(f"Total download time: {total_time}\n")
