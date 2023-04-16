import concurrent.futures
import logging
import re
import subprocess
import time
from pathlib import Path

import requests

from utilities.ch_title_gen import ChineseTitleGenerator

logger = logging.getLogger(__name__)


class ScrapperDownloader:
    def __init__(self, download_location: Path, download_archive: Path) -> None:
        self.download_archive = download_archive
        self.download_location = download_location
        self.archive_content = self.new_archive_names = []
        if self.download_archive.exists():
            self.archive_content = self.download_archive.read_text(encoding="utf-8").splitlines()

    def update_download_archive(self) -> None:
        """
        Updated the names download archive with the new names.
        """
        if self.new_archive_names:
            logger.info("Archive updated with new names.")
            logger.debug(f"new_archive_names: {self.new_archive_names}")
            with open(self.download_archive, 'a', encoding="utf-8") as text_file:
                text_file.writelines(self.new_archive_names)

    def check_download_archive(self, file_name: str) -> bool:
        """
        Check if file name is in archive.
        :param file_name: name of file.
        """
        name_no_s1 = None
        if "S1 " in file_name:  # For cases were the first season indicator is included.
            logger.debug("s1 tag in file name")
            name_no_s1 = file_name.replace("S1 ", "")

        if any(name in self.archive_content for name in [file_name, name_no_s1]):
            logger.debug(f"File: {file_name} is in archive.")
            return True
        else:
            logger.debug(f"File: {file_name} is not in archive.")
            return False

    def m3u8_video_download(self, download_link: str, download_details) -> None:
        """
        Use m3u8 link to download video and create mp4 file. Embedded advertisements links will be removed.
        """
        file_name, video_match_name = download_details[0], download_details[1]
        file_path = Path(f"{self.download_location}/{file_name}.mp4")
        gen = ChineseTitleGenerator()
        resolved_name = gen.generate_title(file_name, video_match_name)
        if file_path.exists():
            logger.warning(f"Resolved name: {resolved_name}, File: {file_name} exists in directory. Skipping download!")
            return
        if self.check_download_archive(resolved_name):
            logger.warning(f"Resolved name: {resolved_name}, File: {file_name} exists in the archive. "
                           f"Skipping download!")
            return
        # Make a request to the m3u8 file link.
        response = requests.get(download_link)
        # Remove embedded advertisement fragments from the response text if any.
        advert_tag = "#EXT-X-DISCONTINUITY\n"
        advert_pattern = re.compile(re.escape(advert_tag) + "(.*?)" + re.escape(advert_tag), re.DOTALL)
        ad_free_m3u8_text = advert_pattern.sub("", response.text)
        # Create temp ad filtered m3u8 playlist.
        temp_m3u8_file = Path(f"{self.download_location}/{file_name}_filtered_playlist.m3u8")
        temp_m3u8_file.write_text(ad_free_m3u8_text)
        # Use ffmpeg to download and convert the modified playlist.
        command = ['ffmpeg/bin/ffmpeg', '-protocol_whitelist', 'file,http,https,tcp,tls', '-i', str(temp_m3u8_file),
                   '-c', 'copy', str(file_path)]
        subprocess.run(command, stderr=subprocess.DEVNULL)
        # Clean up the temp filtered playlist file.
        temp_m3u8_file.unlink()

        if file_path.exists():
            logger.info(f"Resolved name: {resolved_name}, File: {file_path.name}, downloaded successfully!")
            self.new_archive_names.append(resolved_name + "\n")

    def batch_downloader(self, all_download_details: dict) -> None:
        """
        Use multithreading to download multiple videos at the same time.
        :param all_download_details: Should contain download link, file name and match name, in order.
        """
        logger.info("..........Using multithreading to download videos..........")
        if not all_download_details:
            logger.info("No Video Matches!")
            return
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            _ = [executor.submit(self.m3u8_video_download, download_link, download_details)
                 for download_link, download_details in all_download_details.items()]
        self.update_download_archive()
        logger.info("Downloads finished!")
        end = time.perf_counter()
        logger.info(f"Total download time: {end - start}\n")
