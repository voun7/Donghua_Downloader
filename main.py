import logging
import re
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import requests
from bs4 import BeautifulSoup

from scrapers import ScrapperTools, XiaobaotvScraper, AnimeBabyScrapper, EightEightMVScrapper, AgeDm1Scrapper, \
    ImyydsScrapper
from utilities.downloader import DownloadOptions, YouTubeDownloader, ScrapperDownloader
from utilities.logger_setup import setup_logging
from utilities.proxy_request import RotatingProxiesRequest
from utilities.telegram_bot import TelegramBot
from utilities.url_manager import URLManager
from youtube import YouTube

logger = logging.getLogger(__name__)


def set_credentials() -> None:
    """
    Set locations for credentials files.
    """
    cred_dir = Path("credentials")
    logger.info(f"Credential files location being set. Path: {cred_dir.absolute()}")
    TelegramBot.credential_file = cred_dir / "telegram auth.json"
    YouTube.credential_file = cred_dir / "OAuth 2.0 Client ID.json"
    YouTube.token_file = cred_dir / "token.json"


def set_ffmpeg_bin(ffmpeg_dir: Path) -> Path:
    """
    Return path to ffmpeg bin folder. Ffmpeg will be downloaded and setup if it does not exist.
    """
    if ffmpeg_dir.exists():
        ffmpeg_folder_name = list(ffmpeg_dir.iterdir())[0]
        return ffmpeg_folder_name / "bin"
    else:
        ffmpeg_link = "https://github.com/yt-dlp/FFmpeg-Builds/releases/" \
                      "download/latest/ffmpeg-master-latest-win64-gpl.zip"
        zip_data = requests.get(ffmpeg_link)
        with ZipFile(BytesIO(zip_data.content)) as zip_file:
            zip_file.extractall(ffmpeg_dir)
            namelist = zip_file.namelist()  # Get the names of all the files and directories in the zip.
            ffmpeg_folder_name = namelist[0]
        return ffmpeg_dir / ffmpeg_folder_name / "bin"


def download_time() -> int:
    """
    Determine the download time for the program depending on the time of the day.
    """
    current_hr = time.localtime().tm_hour
    return 7200 if current_hr < 13 else 1200


def get_yt_channel_id(url: str) -> None:
    """
    Use link from YouTube channel page to get the channel id.
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    # print(soup.prettify())
    channel_id_link = soup.find('link', {"title": "RSS"})
    if channel_id_link:
        channel_id_link = channel_id_link.get('href')
        channel_id = re.search("channel_id=(.+)", channel_id_link).group(1)
        print(f"Channel URL: {url}, Channel ID: {channel_id}")
    else:
        print("Could not find channel id link. URL must be from the channel page!")


def run_youtube_api(yt_dl_archive_file: Path, resolved_names_file: Path, anime_list: list, tb: TelegramBot) -> None:
    # Variables
    playlist_id = "PLdUiOF8vZ51jW1w84E01SGY2KNeOEPZBn"
    # YouTube Channel IDs ordering determines priority when matching videos.
    ch_id_1 = "UC80ztI40QAXzWL94eoRzWow"  # No. 7 Animation Hall
    ch_id_2 = "UCYkn7e_zaRR_UxOrJR0RVdg"  # 次元动漫社 Animation Club
    ch_id_3 = "UCBIiQ5Hlsadi1HQl8dufZag"  # 云朵屋互娱
    ch_id_4 = "UCJSAZ5pbDi8StbSbJI1riEg"  # Qixiang-Animation
    ch_id_5 = "UCJS5PJXcAIpXkBOjPNvK7Uw"  # Vita Animation Groups
    ch_id_6 = "UCXmOpN9pg1hJBRkHODL00EA"  # 三福动漫 Sanfu
    ch_id_7 = "UCNIKva6iDURgVxf44pMZlKA"  # Animal Family
    ch_id_8 = "UCgVZKHiJrIHomPGMD8KYTzw"  # D-ANIME
    ch_id_9 = "UC_JsHod-IAlWFWi7kDhb03Q"  # 阅文漫画
    ch_id_10 = "UCQKq8mAjHXFRd6CsdDrCB1w"  # Ziyue Animation
    ch_id_11 = "UC_grnC_fPff0bSbk9V-R3aQ"  # 幻月动漫 Moon Anime
    ch_id_12 = "UCQeGBZ2W56r-aRtMZOSooAg"  # Ake Video Official channel
    youtube_channel_ids = [ch_id_1, ch_id_2, ch_id_3, ch_id_4, ch_id_5, ch_id_6, ch_id_7, ch_id_8, ch_id_9, ch_id_10,
                           ch_id_11, ch_id_12]
    yd = YouTubeDownloader(yt_dl_archive_file)

    try:
        logger.info("Checking YouTube site for recent anime upload matches...")
        youtube = YouTube(playlist_id, resolved_names_file, tb)
        youtube.clear_playlist()
        youtube.match_to_youtube_videos(youtube_channel_ids, anime_list)
        # time.sleep(5)  # Prevents skipped downloads by giving YouTube time to added videos the playlist.
        yd.playlist_downloader(playlist_id)
    except Exception as error:
        error_message = f"An error occurred while running YouTube scrapper! Error: {error}"
        logger.exception(error_message)
        tb.send_telegram_message(error_message)


def scrapper_anime_list(youtube_only_file: Path, anime_list: list) -> list:
    """
    An anime list that only has anime that is allowed to be used by scrapper will be returned.
    This method is used to prevent scrapers from scrapping anime that is preferred to be found on YouTube.
    :param youtube_only_file: The file contains a list of anime that are not allowed to be scrapped.
    :param anime_list: The unfiltered anime used list used by YouTube.
    """
    if youtube_only_file.exists():
        logger.debug("Creating filtered anime list for scrappers.")
        yt_only_anime = youtube_only_file.read_text(encoding="utf-8").splitlines()
        scrapper_list = [anime for anime in anime_list if anime not in yt_only_anime]
        return scrapper_list
    else:
        return anime_list


def run_scrappers(resolved_names_file: Path, tb: TelegramBot) -> None:
    um, sd = URLManager(), ScrapperDownloader(resolved_names_file)

    site_address = um.check_url("xiaobaotv.net")
    try:
        logger.info(f"Checking {site_address} site for recent anime upload matches...")
        xiaobaotv = XiaobaotvScraper(site_address)
        site_posts = xiaobaotv.get_anime_posts()
        matched_posts = xiaobaotv.match_to_recent_videos(site_posts)
        matched_download_details = xiaobaotv.get_recent_posts_videos_download_link(matched_posts)
        sd.batch_downloader(site_address, matched_download_details)
    except Exception as error:
        error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
        logger.exception(error_message)
        tb.send_telegram_message(error_message)

    site_address = um.check_url("animebaby.top")
    try:
        logger.info(f"Checking {site_address} site for recent anime upload matches...")
        anime_baby = AnimeBabyScrapper(site_address)
        site_posts = anime_baby.get_anime_posts()
        site_posts.update(anime_baby.get_anime_posts(page=2))
        site_posts.update(anime_baby.get_anime_posts(page=3))
        matched_posts = anime_baby.match_to_recent_videos(site_posts)
        matched_download_details = anime_baby.get_recent_posts_videos_download_link(matched_posts)
        sd.batch_downloader(site_address, matched_download_details)
    except Exception as error:
        error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
        logger.exception(error_message)
        tb.send_telegram_message(error_message)

    site_address = um.check_url("88mv.tv")
    try:
        logger.info(f"Checking {site_address} site for recent anime upload matches...")
        eight_eight_mv = EightEightMVScrapper(site_address)
        site_posts = eight_eight_mv.get_anime_posts()
        site_posts.update(eight_eight_mv.get_anime_posts(page=2))
        matched_posts = eight_eight_mv.match_to_recent_videos(site_posts)
        matched_download_details = eight_eight_mv.get_recent_posts_videos_download_link(matched_posts)
        sd.batch_downloader(site_address, matched_download_details)
    except Exception as error:
        error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
        logger.exception(error_message)
        tb.send_telegram_message(error_message)

    site_address = um.check_url("imyyds.com")
    try:
        logger.info(f"Checking {site_address} site for recent anime upload matches...")
        imyyds = ImyydsScrapper(site_address)
        site_posts = imyyds.get_anime_posts()
        site_posts.update(imyyds.get_anime_posts(page=2))
        site_posts.update(imyyds.get_anime_posts(page=3))
        matched_posts = imyyds.match_to_recent_videos(site_posts)
        matched_download_details = imyyds.get_recent_posts_videos_download_link(matched_posts)
        sd.batch_downloader(site_address, matched_download_details)
    except Exception as error:
        error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
        logger.exception(error_message)
        tb.send_telegram_message(error_message)

    site_address = um.check_url("agedm1.com")
    try:
        logger.info(f"Checking {site_address} site for recent anime upload matches...")
        agedm1 = AgeDm1Scrapper(site_address)
        site_posts = agedm1.get_anime_posts()
        site_posts.update(agedm1.get_anime_posts(page=2))
        matched_posts = agedm1.match_to_recent_videos(site_posts)
        matched_download_details = agedm1.get_recent_posts_videos_download_link(matched_posts)
        agedm1.driver.quit()  # Close headless browser
        sd.batch_downloader(site_address, matched_download_details)
    except Exception as error:
        error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
        logger.exception(error_message)
        tb.send_telegram_message(error_message)


def m3u8_video_downloader() -> None:
    # DownloadOptions.download_path = Path.home() / "Downloads"
    sd = ScrapperDownloader(Path("none"))
    video_name = ""
    video_link = ""
    sd.video_downloader("", (video_name, video_link))


def main() -> None:
    # Set credentials first.
    set_credentials()
    # Variables
    start = time.perf_counter()
    # Set directory files.
    playlist_download_dir = Path(r"\\192.168.31.111\General File Sharing\From YouTube\Chinese Anime For Subbing")
    destination_dir = playlist_download_dir / "##Currently Airing"
    dfsd_files_dir = playlist_download_dir / "DFSD Project Files"
    dfsd_files_dir.mkdir(exist_ok=True)
    ffmpeg_dir, proxy_file = dfsd_files_dir / "ffmpeg", dfsd_files_dir / "proxy list.txt"
    ffmpeg_bin_dir = set_ffmpeg_bin(ffmpeg_dir)
    logger.info(f"Ffmpeg bin directory: {ffmpeg_bin_dir}, Exists: {ffmpeg_bin_dir.exists()}")
    resolved_names_file = dfsd_files_dir / "resolved_names_download_archive.txt"
    yt_dl_archive_file = dfsd_files_dir / "youtube_downloads_archive.txt"
    youtube_only_file = dfsd_files_dir / "youtube_only.txt"
    url_data_file = dfsd_files_dir / "url_data.json"

    min_res_height = 720  # Minimum resolution height.
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                             'Chrome/113.0.0.0 Safari/537.36'}
    anime_list = [keyword for folder in destination_dir.iterdir() for keyword in re.findall(r'\((.*?)\)', folder.name)]

    tb = TelegramBot()
    # Set url manager options.
    URLManager.tb, URLManager.headers, URLManager.url_data_file = tb, headers, url_data_file
    # Set download options.
    dl_time = download_time()
    DownloadOptions.tb, DownloadOptions.download_path, DownloadOptions.timeout_secs = tb, playlist_download_dir, dl_time
    DownloadOptions.ffmpeg_path, DownloadOptions.min_res_height = ffmpeg_bin_dir, min_res_height
    # Set scrapper options.
    scrapper_list = scrapper_anime_list(youtube_only_file, anime_list)
    ScrapperTools.tb, ScrapperTools.current_date = tb, datetime.now().date()  # .replace(day=) to change day.
    ScrapperTools.headers, ScrapperTools.anime_list, ScrapperTools.video_num_per_post = headers, scrapper_list, 3
    ScrapperTools.resolved_names_archive = set(resolved_names_file.read_text(encoding="utf-8").splitlines()) \
        if resolved_names_file.exists() else set()
    # Set options for proxy.
    RotatingProxiesRequest.headers, RotatingProxiesRequest.proxy_file = headers, proxy_file
    # Run code to download new anime.
    # get_yt_channel_id("")
    run_youtube_api(yt_dl_archive_file, resolved_names_file, anime_list, tb)
    run_scrappers(resolved_names_file, tb)
    # m3u8_video_downloader()

    end = time.perf_counter()
    logger.info(f"Total Runtime: {end - start}")


if __name__ == '__main__':
    setup_logging()
    logger.debug("Logging Started")
    main()
    logger.debug("Logging Ended\n")
