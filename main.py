import logging
import re
import time
from pathlib import Path

from scrapers import ScrapperTools, XiaobaotvScraper, AnimeBabyScrapper, AgeDm1Scrapper, ImyydsScrapper
from utilities.downloader import ScrapperDownloader
from utilities.logger_setup import get_log
from utilities.proxy_request import RotatingProxiesRequest
from utilities.telegram_bot import send_telegram_message
from youtube import YouTube

logger = logging.getLogger(__name__)


def main() -> None:
    # Variables
    start = time.perf_counter()
    playlist_download_dir = Path(r"\\192.168.0.111\General File Sharing\From YouTube\Chinese Anime For Subbing")
    destination_dir = playlist_download_dir / "##Currently Airing"
    download_archives_dir = playlist_download_dir / "Download Archives"
    download_archive = download_archives_dir / "resolved_names_download_archive.txt"
    youtube_download_archive = download_archives_dir / "youtube_downloads_archive.txt"
    proxy_file = download_archives_dir / "proxy list.txt"
    ffmpeg_path = "ffmpeg/bin"
    min_res_height = 720  # Minimum resolution height.
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                             'Chrome/113.0.0.0 Safari/537.36'}
    if not download_archives_dir.exists():
        download_archives_dir.mkdir()
    playlist_id = "PLdUiOF8vZ51jW1w84E01SGY2KNeOEPZBn"
    anime_list = [keyword for folder in destination_dir.iterdir() for keyword in re.findall(r'\((.*?)\)', folder.name)]
    # YouTube Channel IDs ordering determines priority when matching videos.
    # To obtain the channel id check the source code of the channel page search for "externalId".
    ch_id_1 = "UC80ztI40QAXzWL94eoRzWow"  # No. 7 Animation Hall
    ch_id_2 = "UCYkn7e_zaRR_UxOrJR0RVdg"  # 次元动漫社 Animation Club
    ch_id_3 = "UCBIiQ5Hlsadi1HQl8dufZag"  # 云朵屋互娱
    ch_id_4 = "UCJSAZ5pbDi8StbSbJI1riEg"  # Qixiang-Animation
    ch_id_5 = "UCJS5PJXcAIpXkBOjPNvK7Uw"  # Vita Animation Groups
    ch_id_6 = "UCXmOpN9pg1hJBRkHODL00EA"  # 三福动漫 Sanfu
    ch_id_7 = "UCNIKva6iDURgVxf44pMZlKA"  # Animal Family
    youtube_channel_ids = [ch_id_1, ch_id_2, ch_id_3, ch_id_4, ch_id_5, ch_id_6, ch_id_7]

    # Arguments
    try:
        logger.info("Checking YouTube site for recent anime upload matches...")
        youtube = YouTube(playlist_id, download_archive)
        youtube.clear_playlist()
        youtube.match_to_youtube_videos(youtube_channel_ids, anime_list)
        youtube.playlist_downloader(playlist_download_dir, youtube_download_archive, ffmpeg_path, min_res_height)
    except Exception as error:
        error_message = f"An error occurred while running YouTube scrapper! Error: {error}"
        logger.exception(error_message)
        send_telegram_message(error_message)

    sd = ScrapperDownloader(playlist_download_dir, download_archive, ffmpeg_path, min_res_height)

    ScrapperTools.headers, ScrapperTools.anime_list = headers, anime_list
    ScrapperTools.archive_content = set(download_archive.read_text(encoding="utf-8").splitlines())

    RotatingProxiesRequest.headers, RotatingProxiesRequest.proxy_file = headers, proxy_file

    site_address = "xiaobaotv.net"
    try:
        logger.info(f"Checking {site_address} site for recent anime upload matches...")
        xiaobaotv = XiaobaotvScraper(site_address)
        site_posts = xiaobaotv.get_anime_posts()
        matched_posts = xiaobaotv.match_to_recent_videos(site_posts)
        matched_download_details = xiaobaotv.get_recent_posts_videos_download_link(matched_posts)
        sd.batch_downloader(matched_download_details)
    except Exception as error:
        error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
        logger.exception(error_message)
        send_telegram_message(error_message)

    site_address = "animebaby.top"
    try:
        logger.info(f"Checking {site_address} site for recent anime upload matches...")
        anime_baby = AnimeBabyScrapper(site_address)
        site_posts = anime_baby.get_anime_posts()
        site_posts.update(anime_baby.get_anime_posts(page=2))
        matched_posts = anime_baby.match_to_recent_videos(site_posts)
        matched_download_details = anime_baby.get_recent_posts_videos_download_link(matched_posts)
        sd.batch_downloader(matched_download_details)
    except Exception as error:
        error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
        logger.exception(error_message)
        send_telegram_message(error_message)

    site_address = "agedm1.com"
    try:
        logger.info(f"Checking {site_address} site for recent anime upload matches...")
        agedm1 = AgeDm1Scrapper(site_address)
        site_posts = agedm1.get_anime_posts()
        site_posts.update(agedm1.get_anime_posts(page=2))
        matched_posts = agedm1.match_to_recent_videos(site_posts)
        matched_download_details = agedm1.get_recent_posts_videos_download_link(matched_posts)
        agedm1.driver.quit()  # Close headless browser
        sd.batch_downloader(matched_download_details)
    except Exception as error:
        error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
        logger.exception(error_message)
        send_telegram_message(error_message)

    site_address = "imyyds.com"
    try:
        logger.info(f"Checking {site_address} site for recent anime upload matches...")
        imyyds = ImyydsScrapper(site_address)
        site_posts = imyyds.get_anime_posts()
        matched_posts = imyyds.match_to_recent_videos(site_posts)
        matched_download_details = imyyds.get_recent_posts_videos_download_link(matched_posts)
        sd.batch_downloader(matched_download_details)
    except Exception as error:
        error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
        logger.exception(error_message)
        send_telegram_message(error_message)

    # site_address = ".com"
    # try:
    #     logger.info(f"Checking {site_address} site for recent anime upload matches...")
    #     temp_scrapper = TempScrapper(site_address)
    #     site_posts = temp_scrapper.get_anime_posts()
    #     matched_posts = temp_scrapper.match_to_recent_videos(site_posts)
    #     matched_download_details = temp_scrapper.get_recent_posts_videos_download_link(matched_posts)
    #     sd.batch_downloader(matched_download_details)
    # except Exception as error:
    #     error_message = f"An error occurred while running {site_address} site scrapper! \nError: {error}"
    #     logger.exception(error_message)
    #     send_telegram_message(error_message)

    end = time.perf_counter()
    logger.info(f"Total Runtime: {end - start}")


if __name__ == '__main__':
    get_log()
    logger.debug("Logging Started")
    main()
    logger.debug("Logging Ended\n")
