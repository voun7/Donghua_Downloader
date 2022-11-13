import logging
import re
from pathlib import Path

from logger_setup import get_log
from youtube import YouTube
from scraper import XiaoheimiScraper

logger = logging.getLogger(__name__)


def main() -> None:
    get_log()
    logger.debug("Logging Started")

    # Variables
    playlist_download_dir = Path(r"\\192.168.0.111\General File Sharing\From YouTube\Chinese Anime For Subbing")
    destination_dir = playlist_download_dir / "##Currently Airing"
    youtube_channel_ids = ["UC80ztI40QAXzWL94eoRzWow", "UCBIiQ5Hlsadi1HQl8dufZag", "UC8r57bRU8OrpXnLFNC0ym7Q"]
    playlist_id = "PLdUiOF8vZ51jW1w84E01SGY2KNeOEPZBn"
    anime_list = [keyword for folder in destination_dir.iterdir() for keyword in re.findall(r'\((.*?)\)', folder.name)]
    anime_list_two = ["徒弟个个是大佬", "徒弟都是女魔头", "被迫成为反派赘婿", "异皇重生", "妖道至尊", "祖师出山"]

    # Arguments
    youtube = YouTube(playlist_id)
    youtube.clear_playlist()
    youtube.match_to_youtube_videos(youtube_channel_ids, anime_list)
    youtube.match_to_youtube_videos(["UCJSAZ5pbDi8StbSbJI1riEg"], ["史上第一祖师爷", "从姑获鸟开始", "掌门低调点"])
    youtube.match_to_youtube_videos(["UCJS5PJXcAIpXkBOjPNvK7Uw"], ["大主宰"])
    youtube.playlist_downloader(playlist_download_dir)

    xiaoheimi = XiaoheimiScraper()
    matched_urls = xiaoheimi.match_to_recent_videos(anime_list_two)
    xiaoheimi.download_all_videos(matched_urls, playlist_download_dir)

    logger.debug("Logging Ended\n")


if __name__ == '__main__':
    main()
