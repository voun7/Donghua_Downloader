import concurrent.futures
import logging
import re
import subprocess
import time
from pathlib import Path

import requests

from utilities.telegram_bot import send_telegram_message

logger = logging.getLogger(__name__)


class ScrapperDownloader:
    def __init__(self, download_location: Path, download_archive: Path, ffmpeg_path: str, min_res_height: int) -> None:
        self.timeout_secs = 900.0
        self.download_location = download_location
        self.download_archive = download_archive
        self.ffmpeg_path = ffmpeg_path
        self.min_res_height = min_res_height  # Minimum allowed height of video resolution.
        self.downloaded_resolved_names_archive, self.new_downloaded_resolved_names = set(), []
        if self.download_archive.exists():
            self.downloaded_resolved_names_archive = set(self.download_archive.read_text(encoding="utf-8").splitlines())

    def update_download_archive(self) -> None:
        """
        Updated the names download archive with the new names.
        """
        if self.new_downloaded_resolved_names:
            logger.info(f"Archive updated with new names. Names: {self.new_downloaded_resolved_names}")
            with open(self.download_archive, 'a', encoding="utf-8") as text_file:
                text_file.writelines(self.new_downloaded_resolved_names)
            self.new_downloaded_resolved_names = []  # Empty list after every update to prevent duplicates.

    def check_download_archive(self, resolved_name: str, file_name: str) -> bool:
        """
        Check if the resolved name is in archive.
        """
        if resolved_name in self.downloaded_resolved_names_archive:
            logger.warning(f"Resolved name: {resolved_name}, File: {file_name} exists in the archive. "
                           f"Skipping download!")
            return True
        else:
            logger.debug(f"Resolved name: {resolved_name}, File: {file_name} is not in archive.")
            return False

    def check_video_resolution(self, resolved_name: str, file_name: str, download_link: str) -> bool:
        """
        Returns True if video's height resolution is lower than the allowed minimum and False otherwise.
        The first 10 seconds of the video are downloaded for testing.
        """
        temp_file = Path(f"{self.download_location}/{file_name}_res_check_temp.mp4")
        duration = "10"  # Set the duration of the first fragment to download (in seconds).
        ffmpeg_cmd = [f"{self.ffmpeg_path}/ffmpeg", '-t', duration, '-i', download_link, '-c', 'copy', str(temp_file)]
        try:
            subprocess.run(ffmpeg_cmd, stderr=subprocess.DEVNULL, timeout=self.timeout_secs / 6.0)
        except Exception as error:
            logger.debug(f"An error occurred while downloading {temp_file}, Error: {error}")
            temp_file.unlink(missing_ok=True)
        # Get the resolution of the downloaded video.
        ffprobe_cmd = [f"{self.ffmpeg_path}/ffprobe", '-show_entries', 'stream=width,height', '-of', 'csv=p=0',
                       str(temp_file)]
        if not temp_file.exists():
            error_message = f"Resolution check temp file for {file_name} not found, download failed!"
            logger.error(error_message)
            send_telegram_message(error_message)
            return True
        resolution = subprocess.check_output(ffprobe_cmd, stderr=subprocess.DEVNULL).decode().strip().split(',')
        width, height = int(resolution[0]), int(resolution[1])
        # Delete the downloaded file.
        temp_file.unlink()
        if not height >= self.min_res_height:
            logger.warning(f"Resolved name: {resolved_name}, File: {file_name} failed resolution test! "
                           f"Resolution: {width} x {height}. Skipping download!")
            return True
        else:
            return False

    @staticmethod
    def ad_remover(text: str, advert_tag_start: str, advert_tag_end: str) -> str:
        """
        Remove embedded advertisement fragments from the response text if any
        :param text: Text containing embedded advertisement.
        :param advert_tag_start: Start of the advertisement.
        :param advert_tag_end: End of the advertisement.
        :return: Advertisement free text.
        """
        advert_pattern = re.compile(advert_tag_start + "(.*?)" + advert_tag_end, re.DOTALL)
        ad_free_m3u8_text = advert_pattern.sub("", text)
        ad_tag_txt = advert_pattern.search(text)
        if ad_tag_txt:
            logger.info(f"Ad tag found using pattern: {advert_pattern}, Ad tag: \n{ad_tag_txt.group(0)}")
        return ad_free_m3u8_text

    def m3u8_downloader(self, m3u8_file: Path, file_path: Path) -> None:
        """
        Download file with m3u8 playlist.
        :param m3u8_file: The m3u8 playlist.
        :param file_path: The file path for the file to be downloaded.
        """
        ffmpeg_cmd = [f"{self.ffmpeg_path}/ffmpeg", '-protocol_whitelist', 'file,http,https,tcp,tls', '-i',
                      str(m3u8_file), '-c', 'copy', str(file_path)]
        try:
            subprocess.run(ffmpeg_cmd, stderr=subprocess.DEVNULL, timeout=self.timeout_secs)
        except Exception as error:
            logger.debug(f"An error occurred while downloading {file_path.name}, Error: {error}")
            file_path.unlink(missing_ok=True)
        # Clean up the m3u8 playlist file.
        m3u8_file.unlink()

    def ad_free_playlist_downloader(self, file_name: str, response_text: str, advert_tag) -> None:
        """
        Remove embedded advertisements from m3u8 playlist.
        """
        logger.debug(f"Advertisement detected in {file_name} and are being removed!")
        file_path = Path(f"{self.download_location}/{file_name}.mp4")
        ad_tag_start1, ad_tag_start2 = f"{advert_tag}#EXTINF:9", f"{advert_tag}#EXTINF:8.208200"
        ad_tag_start3, ad_tag_start4 = f"{advert_tag}#EXT-X-DISCONTINUITY", f"{advert_tag}{advert_tag}#EXTINF:8"
        ad_tag_start5 = f"{advert_tag}#EXTINF:8"
        # Remove advertisement from text.
        ad_free_m3u8_text = self.ad_remover(response_text, ad_tag_start1, advert_tag)
        ad_free_m3u8_text = self.ad_remover(ad_free_m3u8_text, ad_tag_start2, advert_tag)
        ad_free_m3u8_text = self.ad_remover(ad_free_m3u8_text, ad_tag_start3, advert_tag)
        ad_free_m3u8_text = self.ad_remover(ad_free_m3u8_text, ad_tag_start4, advert_tag)
        ad_free_m3u8_text = self.ad_remover(ad_free_m3u8_text, ad_tag_start5, advert_tag)
        # Create temp ad filtered m3u8 playlist.
        temp_m3u8_file = Path(f"{self.download_location}/{file_name}_filtered_playlist.m3u8")
        temp_m3u8_file.write_text(ad_free_m3u8_text)
        # Use ffmpeg to download and convert the modified playlist.
        self.m3u8_downloader(temp_m3u8_file, file_path)

    def link_downloader(self, file_name: str, download_link: str) -> None:
        """
        Download file with link.
        """
        logger.debug(f"Link downloader being used for {file_name}.")
        file_path = Path(f"{self.download_location}/{file_name}.mp4")
        # Set the ffmpeg command as a list.
        ffmpeg_cmd = [f"{self.ffmpeg_path}/ffmpeg", '-i', download_link, '-c', 'copy', str(file_path)]
        try:
            # Run the command using subprocess.run().
            subprocess.run(ffmpeg_cmd, stderr=subprocess.DEVNULL, timeout=self.timeout_secs)
        except Exception as error:
            logger.debug(f"An error occurred while downloading {file_name}, Error: {error}")
            file_path.unlink(missing_ok=True)

    def video_downloader(self, resolved_name: str, download_details: tuple) -> None:
        """
        Use m3u8 link to download video and create mp4 file. Embedded advertisements links will be removed.
        """
        file_name, download_link = download_details[0], download_details[1]
        file_path = Path(f"{self.download_location}/{file_name}.mp4")
        if file_path.exists():
            logger.warning(f"Resolved name: {resolved_name}, File: {file_name} exists in directory. Skipping download!")
            return
        if self.check_download_archive(resolved_name, file_name):
            return
        if download_link is None:
            logger.warning(f"Resolved name: {resolved_name}, "
                           f"File: {file_name} has no download link. Skipping download!")
            return
        if self.check_video_resolution(resolved_name, file_name, download_link):
            return
        # Make a request to the m3u8 file link.
        response = requests.get(download_link)
        response_text, advert_tag = response.text, "#EXT-X-DISCONTINUITY\n"
        if advert_tag in response_text:
            self.ad_free_playlist_downloader(file_name, response_text, advert_tag)
        else:
            self.link_downloader(file_name, download_link)

        if file_path.exists():
            logger.info(f"Resolved name: {resolved_name}, File: {file_path.name}, downloaded successfully!")
            self.downloaded_resolved_names_archive.add(resolved_name)  # Prevent download of exising resolved names.
            self.new_downloaded_resolved_names.append(resolved_name + "\n")
        else:
            error_message = f"Resolved name: {resolved_name}, File: {file_path.name}, download failed!"
            logger.warning(error_message)
            send_telegram_message(error_message)

    def batch_downloader(self, all_download_details: dict) -> None:
        """
        Use multithreading to download multiple videos at the same time.
        :param all_download_details: Should contain download link, file name and match name, in order.
        """
        logger.info("..........Using multithreading to download videos..........")
        if not all_download_details:
            logger.info("No Videos to download!\n")
            return
        logger.debug(f"all_download_details: {all_download_details}")
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.video_downloader, resolved_name, download_details)
                       for resolved_name, download_details in all_download_details.items()]
            for i, f in enumerate(concurrent.futures.as_completed(futures)):  # as each  process completes
                error = f.exception()
                if error:
                    logger.exception(f.result())
                    logger.exception(error)
        self.update_download_archive()
        logger.info("Downloads finished!")
        end = time.perf_counter()
        logger.info(f"Download time: {end - start}\n")
