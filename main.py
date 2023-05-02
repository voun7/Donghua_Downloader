import logging
import re
import time
from pathlib import Path

from scrapers import XiaobaotvScraper, AnimeBabyScrapper, Yhdm6Scrapper
from utilities.downloader import ScrapperDownloader
from utilities.logger_setup import get_log
from youtube import YouTube

logger = logging.getLogger(__name__)


def main() -> None:
    # Variables
    playlist_download_dir = Path(r"\\192.168.0.111\General File Sharing\From YouTube\Chinese Anime For Subbing")
    destination_dir = playlist_download_dir / "##Currently Airing"
    download_archives_dir = playlist_download_dir / "Download Archives"
    download_archive = download_archives_dir / "resolved_names_download_archive.txt"
    youtube_download_archive = download_archives_dir / "youtube_downloads_archive.txt"
    ffmpeg_path = "ffmpeg/bin"
    min_res_height = 720  # Minimum resolution height.
    if not download_archives_dir.exists():
        download_archives_dir.mkdir()
    if download_archive.exists():
        archive_content = download_archive.read_text(encoding="utf-8").splitlines()
    else:
        archive_content = []
    playlist_id = "PLdUiOF8vZ51jW1w84E01SGY2KNeOEPZBn"
    anime_list = [keyword for folder in destination_dir.iterdir() for keyword in re.findall(r'\((.*?)\)', folder.name)]
    # YouTube Channel IDs ordering determines priority when matching videos.
    # To obtain the channel id check the source code of the channel page search for "externalId".
    ch_id_1 = "UC80ztI40QAXzWL94eoRzWow"  # No. 7 Animation Hall
    ch_id_2 = "UCYkn7e_zaRR_UxOrJR0RVdg"  # 次元动漫社 Animation Club
    ch_id_3 = "UCBIiQ5Hlsadi1HQl8dufZag"  # 云朵屋互娱
    ch_id_4 = "UCJSAZ5pbDi8StbSbJI1riEg"  # Qixiang-Animation
    ch_id_5 = "UCJS5PJXcAIpXkBOjPNvK7Uw"  # Vita Animation Groups
    ch_id_6 = "UCpsQzjI6BLuxrH6XNUHSWCQ"  # 小帅动漫 Xiaoshuai Animation
    ch_id_7 = "UCXmOpN9pg1hJBRkHODL00EA"  # 三福动漫 Sanfu
    ch_id_8 = "UCNIKva6iDURgVxf44pMZlKA"  # Animal Family
    youtube_channel_ids = [ch_id_1, ch_id_2, ch_id_3, ch_id_4, ch_id_5, ch_id_6, ch_id_7, ch_id_8]

    # Arguments
    try:
        logger.info("Checking YouTube site for recent anime upload matches...")
        youtube = YouTube(playlist_id, download_archive)
        youtube.clear_playlist()
        youtube.match_to_youtube_videos(youtube_channel_ids, anime_list)
        youtube.playlist_downloader(playlist_download_dir, youtube_download_archive, ffmpeg_path, min_res_height)
    except Exception as error:
        logger.exception(f"An error occurred while running YouTube scrapper! Error: {error}")

    sd = ScrapperDownloader(playlist_download_dir, download_archive, ffmpeg_path, min_res_height)

    site_name = "Xiaobaotv"
    try:
        logger.info(f"Checking {site_name} site for recent anime upload matches...")
        xiaobaotv = XiaobaotvScraper()
        site_posts = xiaobaotv.get_anime_posts()
        matched_posts = xiaobaotv.match_to_recent_videos(site_posts, anime_list)
        matched_download_details = xiaobaotv.get_recent_posts_videos_download_link(matched_posts, archive_content)
        sd.batch_downloader(matched_download_details)
    except Exception as error:
        logger.exception(f"An error occurred while running {site_name} site scrapper! Error: {error}")

    site_name = "Anime baby"
    try:
        logger.info(f"Checking {site_name} site for recent anime upload matches...")
        anime_baby = AnimeBabyScrapper()
        site_posts = anime_baby.get_anime_posts()
        matched_posts = anime_baby.match_to_recent_videos(site_posts, anime_list)
        matched_download_details = anime_baby.get_recent_posts_videos_download_link(matched_posts, archive_content)
        sd.batch_downloader(matched_download_details)
    except Exception as error:
        logger.exception(f"An error occurred while running {site_name} site scrapper! Error: {error}")

    site_name = "Yhdm6"
    try:
        logger.info(f"Checking {site_name} site for recent anime upload matches...")
        yhdm6 = Yhdm6Scrapper()
        site_posts = yhdm6.get_anime_posts()
        matched_posts = yhdm6.match_to_recent_videos(site_posts, anime_list)
        matched_download_details = yhdm6.get_recent_posts_videos_download_link(matched_posts, archive_content)
        sd.batch_downloader(matched_download_details)
    except Exception as error:
        logger.exception(f"An error occurred while running {site_name} site scrapper! Error: {error}")


if __name__ == '__main__':
    get_log()
    logger.debug("Logging Started")
    start = time.perf_counter()
    main()
    end = time.perf_counter()
    logger.info(f"Total Runtime: {end - start}")
    logger.debug("Logging Ended\n")
