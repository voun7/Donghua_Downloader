import requests
from bs4 import BeautifulSoup

anime_list = ["徒弟个个是大佬", "徒弟都是女魔头", "被迫成为反派赘婿", "异皇重生"]

header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/106.0.0.0 Safari/537.36'}

url = 'https://xiaoheimi.net/index.php/vod/show/area/大陆/id/4.html'

page_response = requests.get(url, headers=header)

soup = BeautifulSoup(page_response.text, 'lxml')
posts = soup.find('li', class_='col-lg-8 col-md-6 col-sm-4 col-xs-3')
anime_name = posts.find('h4', class_='title text-overflow').text
print(anime_name)
anime_url = posts.find('h4', class_='title text-overflow')
print(anime_url)
