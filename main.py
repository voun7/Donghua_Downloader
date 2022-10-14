import logging
import re
from pathlib import Path

from logger_setup import get_log
from youtube import YouTube

logger = logging.getLogger(__name__)


# This function returns a list of all the donghua chinese names enclosed in the brackets of their folders.
def get_donghua_chinese_name_list(destination_dir: Path) -> list:
    keywords = [keyword for folder in destination_dir.iterdir() for keyword in re.findall(r'\((.*?)\)', folder.name)]
    return keywords


def main():
    get_log()
    logger.debug("Logging Started")

    # Variables
    playlist_download_dir = Path(r"\\192.168.0.111\General File Sharing\From YouTube\Chinese Anime For Subbing")
    destination_dir = playlist_download_dir / "##Currently Airing"
    youtube_channel_ids = [
        "UC80ztI40QAXzWL94eoRzWow",
        "UCBIiQ5Hlsadi1HQl8dufZag",
        "UC8r57bRU8OrpXnLFNC0ym7Q",
        "UCJS5PJXcAIpXkBOjPNvK7Uw",
        "UCJSAZ5pbDi8StbSbJI1riEg"
    ]
    playlist_id = "PLdUiOF8vZ51jW1w84E01SGY2KNeOEPZBn"

    anime_list = get_donghua_chinese_name_list(destination_dir)
    youtube = YouTube(playlist_id)
    youtube.clear_playlist()
    youtube.match_to_youtube_videos(anime_list, youtube_channel_ids)
    youtube.playlist_downloader(playlist_download_dir)

    logger.debug("Logging Ended\n")


if __name__ == '__main__':
    main()
