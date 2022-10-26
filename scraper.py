import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser
from yt_dlp import YoutubeDL


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
        print("..........Site Page one Anime Posts..........")
        for post in posts:
            post_name = post.find('h4', class_='title text-overflow').text
            post_url = self.base_url + post.find('a').get('href')
            print(f"Post Title: {post_name}, Post URL: {post_url}")
            video_name_and_link[post_name] = post_url
        return video_name_and_link

    # This method takes a post's url check if its recent and gets the latest video link.
    def get_latest_video_links(self, matched_posts: dict) -> list:
        print("..........Checking for recent posts..........")
        latest_video_links = []
        now = datetime.now()
        for name, url in matched_posts.items():
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.text, 'lxml')
            post_update = soup.find('span', class_='text-red').text.split(' / ')
            last_updated_date = parser.parse(post_update[1])
            latest_video_number = post_update[0].strip('更新至集全')
            if last_updated_date > now:
                print(f"Post named: {name} is new, latest video number: {latest_video_number}")
                latest_video_post = soup.find('li', {"title": f"{latest_video_number}"})
                latest_video_link = self.base_url + latest_video_post.find('a').get('href')
                print(f"Latest Video link: {latest_video_link}")
                latest_video_links.append(latest_video_link)
            else:
                print(f"Post named: {name} is not recent")
        return latest_video_links

    # This method checks if anime matches a recent post from the site.
    def match_to_recent_videos(self, anime_list: list) -> list:
        posts = self.get_page_one_anime_posts()
        matched_posts = {}
        print("..........Matching names to site recent post..........")
        start = time.perf_counter()
        for name in anime_list:
            for post_name, post_url in posts.items():
                if name in post_name:
                    print(f"Anime: {name} matches Post Title: {post_name}, Post URL: {post_url}")
                    matched_posts[post_name] = post_url
        checked_video_urls = self.get_latest_video_links(matched_posts)
        end = time.perf_counter()
        total_time = end - start
        print(f"Done checking recent videos Total time: {total_time}")
        return checked_video_urls

    def video_downloader(self, video_urls: list) -> None:
        print("..........Downloading matched recent site videos..........")
        start = time.perf_counter()
        for url in video_urls:
            page_response = requests.get(url, headers=self.header)
            soup = BeautifulSoup(page_response.text, 'lxml')
            # print(soup.prettify())

        end = time.perf_counter()
        total_time = end - start
        print(f"Downloads finished Total time: {total_time}\n")


def main():
    anime_list = ["徒弟个个是大佬", "徒弟都是女魔头", "被迫成为反派赘婿", "异皇重生", "万古神王", "绝世武", "靠你啦！战神系统"]
    playlist_download_dir = Path(r"\\192.168.0.111\General File Sharing\From YouTube\Chinese Anime For Subbing")
    xiaoheimi = XiaoheimiScraper(playlist_download_dir)
    matched_urls = xiaoheimi.match_to_recent_videos(anime_list)
    xiaoheimi.video_downloader(matched_urls)


if __name__ == '__main__':
    main()
