import logging
import re
from pathlib import Path

from logger_setup import get_log
from scraper import XiaoheimiScraper
from youtube import YouTube

logger = logging.getLogger(__name__)


def filter_anime_list(anime_list: list, xh_anime_list: list) -> list:
    """
    Prevent anime from being in two lists at the same time
    """
    for anime in xh_anime_list:
        if anime in anime_list:
            anime_list.remove(anime)
    return anime_list


def main() -> None:
    get_log()
    logger.debug("Logging Started")

    # Variables
    playlist_download_dir = Path(r"\\192.168.0.111\General File Sharing\From YouTube\Chinese Anime For Subbing")
    destination_dir = playlist_download_dir / "##Currently Airing"
    playlist_id = "PLdUiOF8vZ51jW1w84E01SGY2KNeOEPZBn"
    anime_list = [keyword for folder in destination_dir.iterdir() for keyword in re.findall(r'\((.*?)\)', folder.name)]

    youtube_channel_ids = ["UC80ztI40QAXzWL94eoRzWow", "UCBIiQ5Hlsadi1HQl8dufZag", "UC8r57bRU8OrpXnLFNC0ym7Q"]

    xh_anime_list = ["徒弟个个是大佬", "徒弟都是女魔头", "被迫成为反派赘婿", "异皇重生", "妖道至尊", "祖师出山",
                     "仙武帝尊", "龙城争霸", "九霄帝神"]
    yt_anime_list = filter_anime_list(anime_list, xh_anime_list)

    # Arguments
    youtube = YouTube(playlist_id)
    youtube.clear_playlist()
    youtube.match_to_youtube_videos(youtube_channel_ids, yt_anime_list)
    youtube.match_to_youtube_videos(["UCJS5PJXcAIpXkBOjPNvK7Uw"], ["大主宰"])
    youtube.playlist_downloader(playlist_download_dir)

    xiaoheimi = XiaoheimiScraper()
    matched_urls = xiaoheimi.match_to_recent_videos(xh_anime_list)
    xiaoheimi.download_all_videos(matched_urls, playlist_download_dir)

    logger.debug("Logging Ended\n")


if __name__ == '__main__':
    main()
