import logging
import re
import time
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import requests
from bs4 import BeautifulSoup

import scrapers as sps
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
        ffmpeg_bin_dir = ffmpeg_folder_name / "bin"
    else:
        ffmpeg_link = "https://github.com/yt-dlp/FFmpeg-Builds/releases/" \
                      "download/latest/ffmpeg-master-latest-win64-gpl.zip"
        zip_data = requests.get(ffmpeg_link)
        with ZipFile(BytesIO(zip_data.content)) as zip_file:
            zip_file.extractall(ffmpeg_dir)
            namelist = zip_file.namelist()  # Get the names of all the files and directories in the zip.
            ffmpeg_folder_name = namelist[0]
        ffmpeg_bin_dir = ffmpeg_dir / ffmpeg_folder_name / "bin"
    logger.info(f"Ffmpeg bin directory: {ffmpeg_bin_dir}, Exists: {ffmpeg_bin_dir.exists()}")
    return ffmpeg_bin_dir


def download_time() -> int:
    """
    Determine the download time for the program depending on the time of the day.
    """
    current_hr = time.localtime().tm_hour
    return 3600 if current_hr < 18 else 1200


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
    youtube_channel_ids = [
        "UC80ztI40QAXzWL94eoRzWow",  # No. 7 Animation Hall
        "UCBIiQ5Hlsadi1HQl8dufZag",  # 云朵屋互娱
        "UCDsfSnYAzLAG8233lSfVC3g",  # Chinese animation
        "UCJSAZ5pbDi8StbSbJI1riEg",  # Qixiang-Animation
        "UCnQ4raNnLXrXy9ZzOzC2Tcw",  # 七七动漫
        "UC87Bjy1d5lSiDthuq1mNtqg",  # 大熊说漫 Big Bear Animation
        "UCJS5PJXcAIpXkBOjPNvK7Uw",  # Vita Animation Groups
        "UCh4STTSfZURHIs3CpsYeIjA",  # Animation Factory
        "UCXmOpN9pg1hJBRkHODL00EA",  # 三福动漫 Sanfu
        "UC5FQ3sxZsjxD9Bej9PsPt9Q",  # Mythology Animation
        "UCNIKva6iDURgVxf44pMZlKA",  # Animal Family
        "UCl4cPgwEFz31KRyybXKRN_A",  # 小狗动漫
        "UCOC-FcGSep0BFx7XCzBdQ-g",  # D-TV Channel
        "UC_JsHod-IAlWFWi7kDhb03Q",  # 阅文漫画
        "UCQKq8mAjHXFRd6CsdDrCB1w",  # Ziyue Animation
        "UC_grnC_fPff0bSbk9V-R3aQ",  # 幻月动漫 Moon Anime
        "UCQeGBZ2W56r-aRtMZOSooAg",  # Ake Video Official channel
        "UCYkn7e_zaRR_UxOrJR0RVdg",  # 次元动漫社 Animation Club
        "UCvkA0WKMLxk0vfI5Ck8EKKw",  # 趣漫社
    ]
    if len(youtube_channel_ids) != len(set(youtube_channel_ids)):
        logger.warning("Remove duplicate detected in youtube channel ids!")
        time.sleep(30)

    yd = YouTubeDownloader(yt_dl_archive_file)
    try:
        logger.info("Checking YouTube site for recent anime upload matches...")
        youtube = YouTube(playlist_id, resolved_names_file)
        youtube.clear_playlist()
        youtube.match_to_youtube_videos(list(dict.fromkeys(youtube_channel_ids)), anime_list)  # ids will be unique
        time.sleep(30)  # Prevents skipped downloads by giving YouTube time to added videos the playlist.
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
    scrappers = {
        "xiaobaotv.net": "XiaobaotvScraper",
        "yhdm.in": "YhdmScrapper",
        "agedm88.com": "AgeDm1Scrapper",
        "v.lq010.com": "LQ010Scrapper",
        "animebaby.top": "AnimeBabyScrapper",
    }

    for site_address, scrapper_class in scrappers.items():
        try:
            site_address = um.check_url(site_address)
            logger.info(f"Checking {site_address} site for recent anime upload matches...")
            scrapper = getattr(sps, scrapper_class)(site_address)
            site_posts = scrapper.get_anime_posts()
            site_posts.update(scrapper.get_anime_posts(page=2))
            site_posts.update(scrapper.get_anime_posts(page=3))
            matched_posts = scrapper.match_to_recent_videos(site_posts)
            matched_download_details = scrapper.get_recent_posts_videos_download_link(matched_posts)
            sd.batch_downloader(site_address, matched_download_details, 6)
        except Exception as error:
            error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
            logger.exception(error_message)
            tb.send_telegram_message(error_message)


def m3u8_video_downloader() -> None:
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
    download_dir = Path(r"\\192.168.31.111\General File Sharing\From YouTube\Chinese Anime For Subbing")
    destination_dir, project_files = download_dir / "##Currently Airing", download_dir / "Project Files"
    project_files.mkdir(exist_ok=True)
    ffmpeg_bin_dir, proxy_file = set_ffmpeg_bin(project_files / "ffmpeg"), project_files / "proxies.txt"
    resolved_names_file = project_files / "resolved_names_dl_archive.txt"
    yt_dl_archive_file = project_files / "yt_dlp_archive.txt"
    youtube_only_file, url_data_file = project_files / "youtube_only.txt", project_files / "url_data.json"

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/127.0.0.0 Safari/537.36"}
    anime_list = [keyword for folder in destination_dir.iterdir() for keyword in re.findall(r'\((.*?)\)', folder.name)]

    tb = TelegramBot()
    # Set url manager options.
    URLManager.headers, URLManager.url_data_file = headers, url_data_file
    # Set download options.
    DownloadOptions.tb, DownloadOptions.download_path, DownloadOptions.timeout_secs = tb, download_dir, download_time()
    DownloadOptions.ffmpeg_path, DownloadOptions.min_res_height = ffmpeg_bin_dir, 720  # Minimum resolution height.
    # Set scrapper options.
    scrapper_list = scrapper_anime_list(youtube_only_file, anime_list)
    sps.ScrapperTools.tb, sps.ScrapperTools.current_date = tb, datetime.now().date()  # .replace(day=) to change day.
    sps.ScrapperTools.headers, sps.ScrapperTools.anime_list, sps.ScrapperTools.video_num_per_post = headers, scrapper_list, 8
    sps.ScrapperTools.resolved_names_archive = set(resolved_names_file.read_text(encoding="utf-8").splitlines()) \
        if resolved_names_file.exists() else set()
    # Set options for proxy.
    RotatingProxiesRequest.headers, RotatingProxiesRequest.proxy_file = headers, proxy_file
    # Run code to download new anime.
    # get_yt_channel_id("")
    run_youtube_api(yt_dl_archive_file, resolved_names_file, anime_list, tb)
    run_scrappers(resolved_names_file, tb)
    sps.ScrapperTools.sel_driver.quit()
    # m3u8_video_downloader()

    logger.info(f"Total Runtime: {timedelta(seconds=round(time.perf_counter() - start))}")


if __name__ == '__main__':
    setup_logging()
    logger.debug("Logging Started")
    main()
    logger.debug("Logging Ended\n")
