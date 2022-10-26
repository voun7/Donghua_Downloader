import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dateutil import parser


class XiaoheimiScraper:
    def __init__(self):
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
        page_response = requests.get(self.base_url + payload, headers=self.header)
        soup = BeautifulSoup(page_response.text, 'lxml')
        posts = soup.find_all('li', class_='col-lg-8 col-md-6 col-sm-4 col-xs-3')
        print("..........Site Recent Anime Posts..........")
        for post in posts:
            post_name = post.find('h4', class_='title text-overflow').text
            post_url = self.base_url + post.find('a').get('href')
            # print(f"Post Title: {post_name}, Post URL: {post_url}")
            video_name_and_link[post_name] = post_url
        return video_name_and_link

    def video_downloader(self, video_url: str) -> None:
        print("Download Finished\n")

    # This method takes a post's url check if its recent and gets the latest video link.
    # It sends the video link to the video downloader.
    def get_latest_video_link(self, post_url: str) -> None:
        now = datetime.now()
        page_response = requests.get(post_url, headers=self.header)
        soup = BeautifulSoup(page_response.text, 'lxml')
        post_update = soup.find('span', class_='text-red').text.split(' / ')
        last_updated_date = parser.parse(post_update[1])
        latest_video_number = post_update[0].strip('更新至集全')
        if last_updated_date > now:
            print(f"Post is new, latest video number: {latest_video_number}")
            latest_video_post = soup.find('li', {"title": f"{latest_video_number}"})
            latest_video_link = self.base_url + latest_video_post.find('a').get('href')
            print(f"Latest Video link: {latest_video_link}")
            self.video_downloader(latest_video_link)
        else:
            print("Post is not recent")

    # This method starts running the class, it checks if anime matches
    # a recent post from the site and sends it to get its video link extracted.
    def match_to_site_videos(self, anime_list: list) -> None:
        posts = self.get_page_one_anime_posts()
        print("..........Matching Names to Site Recent Post..........")
        start = time.perf_counter()
        for name in anime_list:
            for post_name, post_url in posts.items():
                if name in post_name:
                    print(f"Anime: {name} matches Post Title: {post_name}, Post URL: {post_url}")
                    self.get_latest_video_link(post_url)
        end = time.perf_counter()
        total_time = end - start
        print(f"Total time matching and downloading recent videos from posts took: {total_time}")


def main():
    anime_list = ["徒弟个个是大佬", "徒弟都是女魔头", "被迫成为反派赘婿", "异皇重生", "万古神王", "绝世武", "靠你啦！战神系统"]
    xiaoheimi = XiaoheimiScraper()
    xiaoheimi.match_to_site_videos(anime_list)


if __name__ == '__main__':
    main()
