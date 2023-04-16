import logging
import re
from pathlib import Path

from scrapers import XiaoheimiScraper, AnimeBabyScrapper
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
    if not download_archives_dir.exists():
        download_archives_dir.mkdir()
    playlist_id = "PLdUiOF8vZ51jW1w84E01SGY2KNeOEPZBn"
    anime_list = [keyword for folder in destination_dir.iterdir() for keyword in re.findall(r'\((.*?)\)', folder.name)]

    # To obtain the channel id you can view the source code of the channel page
    # and find either data-channel-external-id or "externalId"
    youtube_channel_ids = ["UC80ztI40QAXzWL94eoRzWow", "UCBIiQ5Hlsadi1HQl8dufZag", "UCXmOpN9pg1hJBRkHODL00EA",
                           "UCJSAZ5pbDi8StbSbJI1riEg", "UCJS5PJXcAIpXkBOjPNvK7Uw", "UCYkn7e_zaRR_UxOrJR0RVdg",
                           "UCpsQzjI6BLuxrH6XNUHSWCQ", "UCEY7zXcul32d1hvRCDlxLjQ", "UCNIKva6iDURgVxf44pMZlKA"]

    # Arguments
    try:
        logger.info("Checking YouTube site for recent anime upload matches...")
        youtube = YouTube(playlist_id, download_archive)
        youtube.clear_playlist()
        youtube.match_to_youtube_videos(youtube_channel_ids, anime_list)
        youtube.playlist_downloader(playlist_download_dir, youtube_download_archive)
    except Exception as error:
        logger.exception(f"An error occurred while running YouTube script! Error: {error}")

    sd = ScrapperDownloader(playlist_download_dir, download_archive)

    try:
        logger.info("Checking Xiaoheimi site for recent anime upload matches...")
        xiaoheimi = XiaoheimiScraper()
        xiaoheimi_posts = xiaoheimi.get_anime_posts()
        matched_posts = xiaoheimi.match_to_recent_videos(xiaoheimi_posts, anime_list)
        matched_download_details = xiaoheimi.get_recent_posts_videos_download_link(matched_posts)
        sd.batch_downloader(matched_download_details)
    except Exception as error:
        logger.exception(f"An error occurred while running Xiaoheimi script! Error: {error}")

    try:
        logger.info("Checking Anime baby site for recent anime upload matches...")
        anime_baby = AnimeBabyScrapper()
        anime_baby_posts = anime_baby.get_anime_posts()
        matched_posts = anime_baby.match_to_recent_videos(anime_baby_posts, anime_list)
        matched_download_details = anime_baby.get_recent_posts_videos_download_link(matched_posts)
        sd.batch_downloader(matched_download_details)
    except Exception as error:
        logger.exception(f"An error occurred while running Anime baby script! Error: {error}")


if __name__ == '__main__':
    get_log()
    logger.debug("Logging Started")
    main()
    logger.debug("Logging Ended\n")
