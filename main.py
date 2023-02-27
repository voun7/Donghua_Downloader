import logging
import re
from pathlib import Path

from logger_setup import get_log
from scrapers import XiaoheimiScraper
from youtube import YouTube

logger = logging.getLogger(__name__)


def filter_anime_list(anime_list: list, *name_lists: list) -> list:
    """
    Prevent anime from being in two lists at the same time
    """
    for an_list in name_lists:
        for anime in an_list:
            if anime in anime_list:
                anime_list.remove(anime)
    return anime_list


def main() -> None:
    # Variables
    playlist_download_dir = Path(r"\\192.168.0.111\General File Sharing\From YouTube\Chinese Anime For Subbing")
    destination_dir = playlist_download_dir / "##Currently Airing"
    download_archives = playlist_download_dir / "Download Archives"
    if not download_archives.exists():
        download_archives.mkdir()
    playlist_id = "PLdUiOF8vZ51jW1w84E01SGY2KNeOEPZBn"
    anime_list = [keyword for folder in destination_dir.iterdir() for keyword in re.findall(r'\((.*?)\)', folder.name)]

    # To obtain the channel id you can view the source code of the channel page
    # and find either data-channel-external-id or "externalId"
    youtube_channel_ids = ["UC80ztI40QAXzWL94eoRzWow", "UCBIiQ5Hlsadi1HQl8dufZag", "UCXmOpN9pg1hJBRkHODL00EA",
                           "UCJSAZ5pbDi8StbSbJI1riEg", "UCJS5PJXcAIpXkBOjPNvK7Uw", "UCYkn7e_zaRR_UxOrJR0RVdg"]

    xh_anime_list = ["徒弟个个是大佬", "徒弟都是女魔头", "被迫成为反派赘婿", "妖道至尊", "绝世战魂", "诸天纪动态动画",
                     "混沌金乌", "一人之下"]
    yt_anime_list = filter_anime_list(anime_list, xh_anime_list)

    # Arguments
    logger.info("Checking youtube for recent anime upload matches...")
    youtube = YouTube(playlist_id, download_archives)
    youtube.clear_playlist()
    youtube.match_to_youtube_videos(youtube_channel_ids, yt_anime_list)
    youtube.playlist_downloader(playlist_download_dir)

    logger.info("Checking xiaoheimi for recent anime upload matches...")
    xiaoheimi = XiaoheimiScraper(download_archives)
    matched_urls = xiaoheimi.match_to_recent_videos(xh_anime_list)
    xiaoheimi.download_all_videos(matched_urls, playlist_download_dir)


if __name__ == '__main__':
    get_log()
    logger.debug("Logging Started")
    main()
    logger.debug("Logging Ended\n")
