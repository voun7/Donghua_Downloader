import concurrent.futures
import logging
import socket
import subprocess
import time
from pathlib import Path

import requests
from yt_dlp import YoutubeDL

from utilities.m3u8_adfilter import M3u8AdFilter

logger = logging.getLogger(__name__)


class DownloadOptions:
    tb = download_path = timeout_secs = ffmpeg_path = min_res_height = None
    host_name = socket.gethostname()


class YouTubeDownloader(DownloadOptions):
    def __init__(self, yt_dl_archive_file: Path) -> None:
        self.yt_dl_archive_file = yt_dl_archive_file

    def my_hook(self, d: dict) -> None:
        if d['status'] == 'error':
            error_message = f'An error has occurred when downloading: {d["filename"]}'
            logger.exception(error_message)
            self.tb.send_telegram_message(error_message)
        if d['status'] == 'finished':
            logger.info(f'Done downloading file. File location: {d["filename"]}')

    def get_yt_dlp_options(self) -> dict:
        ydl_opts = {
            'ignoreerrors': 'only_download',
            'socket_timeout': 120,
            'wait_for_video': (1, self.timeout_secs),
            'download_archive': self.yt_dl_archive_file,
            'format': f'bestvideo[height>={self.min_res_height}][ext=mp4]+bestaudio[ext=m4a]',
            'ffmpeg_location': self.ffmpeg_path,
            'outtmpl': str(self.download_path) + '/%(title)s.%(ext)s'
        }

        if "VOUN-SERVER" in self.host_name:
            extra_opts = {
                'logger': logger.getChild('yt_dlp'),
                'noprogress': True,
                'progress_hooks': [self.my_hook],
            }
            ydl_opts.update(extra_opts)
        return ydl_opts

    def playlist_downloader(self, playlist_id: str) -> None:
        """
        This method uses yt_dlp to download videos from playlist.
        """
        logger.info("..........Downloading videos from playlist..........")
        start = time.perf_counter()

        playlist_link = f"https://www.youtube.com/playlist?list={playlist_id}"

        with YoutubeDL(self.get_yt_dlp_options()) as ydl:
            ydl.download(playlist_link)
        end = time.perf_counter()
        logger.info(f"Time downloading playlist took: {end - start}\n")


class ScrapperDownloader(DownloadOptions):
    def __init__(self, resolved_names_file: Path) -> None:
        self.resolved_names_file = resolved_names_file
        self.dl_resolved_names_archive, self.new_dl_resolved_names = set(), []
        if self.resolved_names_file.exists():
            self.dl_resolved_names_archive = set(self.resolved_names_file.read_text(encoding="utf-8").splitlines())
        self.cmd_output = subprocess.DEVNULL if "VOUN-SERVER" in self.host_name else None
        self.error_msgs = ""

    def update_download_archive(self) -> None:
        """
        Updated the names download archive with the new names.
        """
        if self.new_dl_resolved_names:
            logger.info(f"Archive updated with new names. Names: {self.new_dl_resolved_names}")
            with open(self.resolved_names_file, 'a', encoding="utf-8") as text_file:
                text_file.writelines(self.new_dl_resolved_names)
            self.new_dl_resolved_names = []  # Empty list after every update to prevent duplicates.

    def send_error_messages(self, scrapper_name: str) -> None:
        if self.error_msgs:
            self.tb.send_telegram_message(f"Scrapper Name: {scrapper_name}\n{self.error_msgs}")
            self.error_msgs = ""

    def check_download_archive(self, resolved_name: str, file_name: str) -> bool:
        """
        Check if the resolved name is in archive.
        """
        if resolved_name in self.dl_resolved_names_archive:
            logger.warning(f"Resolved name: {resolved_name}, File: {file_name} exists in the archive. "
                           f"Skipping download!")
            return True
        else:
            logger.debug(f"Resolved name: {resolved_name}, File: {file_name} is not in archive.")
            return False

    def bad_video_res_check(self, resolved_name: str, file_name: str, download_link: str) -> bool:
        """
        Returns True if video's height resolution is lower than the allowed minimum and False otherwise.
        The first 10 seconds of the video are downloaded for testing.
        """
        temp_file = Path(f"{self.download_path}/{file_name}_res_check_temp.mp4")
        duration = "10"  # Set the duration of the first fragment to download (in seconds).
        ffmpeg_cmd = [f"{self.ffmpeg_path}/ffmpeg", '-t', duration, '-i', download_link, '-c', 'copy', str(temp_file)]
        try:
            subprocess.run(ffmpeg_cmd, stderr=self.cmd_output, timeout=self.timeout_secs / 6.0)
        except Exception as error:
            logger.debug(f"An error occurred while downloading {temp_file}, Error: {error}")
            temp_file.unlink(missing_ok=True)
        # Get the resolution of the downloaded video.
        ffprobe_cmd = [f"{self.ffmpeg_path}/ffprobe", '-show_entries', 'stream=width,height', '-of', 'csv=p=0',
                       str(temp_file)]
        if not temp_file.exists():
            error_msg = f"Resolution check temp file for {file_name} not found, download failed!"
            logger.error(error_msg)
            self.error_msgs = f"{self.error_msgs}\n{error_msg}"
            return True
        resolution = subprocess.check_output(ffprobe_cmd, stderr=self.cmd_output).decode().strip().split(',')
        width, height = int(resolution[0]), int(resolution[1])
        # Delete the downloaded file.
        temp_file.unlink()
        if not height >= self.min_res_height:
            error_msg = (f"Resolved name: {resolved_name}, File: {file_name} failed resolution test! "
                         f"Resolution: {width} x {height}. Skipping download!")
            logger.error(error_msg)
            self.error_msgs = f"{self.error_msgs}\n{error_msg}"
            return True
        else:
            return False

    def m3u8_downloader(self, m3u8_file: Path, file_path: Path) -> None:
        """
        Download file with m3u8 playlist.
        :param m3u8_file: The m3u8 playlist.
        :param file_path: The file path for the file to be downloaded.
        """
        ffmpeg_cmd = [f"{self.ffmpeg_path}/ffmpeg", '-protocol_whitelist', 'file,http,https,tcp,tls', '-i',
                      str(m3u8_file), '-c', 'copy', str(file_path)]
        try:
            subprocess.run(ffmpeg_cmd, stderr=self.cmd_output, timeout=self.timeout_secs)
        except Exception as error:
            logger.debug(f"An error occurred while downloading {file_path.name}, Error: {error}")
            file_path.unlink(missing_ok=True)
        # Clean up the m3u8 playlist file.
        m3u8_file.unlink()

    def ad_free_playlist_downloader(self, file_name: str, response_text: str) -> None:
        """
        Remove embedded advertisements from m3u8 playlist.
        """
        logger.debug(f"Advertisement detected in {file_name}!")
        file_path = Path(f"{self.download_path}/{file_name}.mp4")
        # Remove advertisement from text.
        af = M3u8AdFilter()
        try:
            ad_free_m3u8_text = af.run_filters(response_text)
        except Exception as error:
            ad_free_m3u8_text = response_text
            error_message = f"An error occurred while trying to remove ads Error:\n{error}\nFile name: {file_name}\n"
            logger.error(f"{error_message}Response text:\n{response_text}")
            self.error_msgs = f"{self.error_msgs}\n{error_message}"
        # Create temp ad filtered m3u8 playlist.
        temp_m3u8_file = Path(f"{self.download_path}/{file_name}_filtered_playlist.m3u8")
        temp_m3u8_file.write_text(ad_free_m3u8_text)
        # Use ffmpeg to download and convert the modified playlist.
        self.m3u8_downloader(temp_m3u8_file, file_path)

    def link_downloader(self, file_name: str, download_link: str) -> None:
        """
        Download file with link.
        """
        logger.debug(f"Link downloader being used for {file_name}.")
        file_path = Path(f"{self.download_path}/{file_name}.mp4")
        # Set the ffmpeg command as a list.
        ffmpeg_cmd = [f"{self.ffmpeg_path}/ffmpeg", '-i', download_link, '-c', 'copy', str(file_path)]
        try:
            # Run the command using subprocess.run().
            subprocess.run(ffmpeg_cmd, stderr=self.cmd_output, timeout=self.timeout_secs)
        except Exception as error:
            logger.debug(f"An error occurred while downloading {file_name}, Error: {error}")
            file_path.unlink(missing_ok=True)

    def video_downloader(self, resolved_name: str, download_details: tuple) -> None:
        """
        Use m3u8 link to download video and create mp4 file. Embedded advertisements links will be removed.
        """
        file_name, download_link = download_details[0], download_details[1]
        file_path = Path(f"{self.download_path}/{file_name}.mp4")
        if file_path.exists():
            logger.warning(f"Resolved name: {resolved_name}, File: {file_name} exists in directory. Skipping download!")
            return
        if self.check_download_archive(resolved_name, file_name):
            return
        if download_link is None:
            error_msg = f"Resolved name: {resolved_name}, File: {file_name} has no download link. Skipping download!"
            logger.warning(error_msg)
            self.error_msgs = f"{self.error_msgs}\n{error_msg}"
            return
        if self.bad_video_res_check(resolved_name, file_name, download_link):
            return
        # Make a request to the m3u8 file link.
        response = requests.get(download_link)
        response_text, advert_tag = response.text, "#EXT-X-DISCONTINUITY\n"
        if advert_tag in response_text:
            self.ad_free_playlist_downloader(file_name, response_text)
        else:
            self.link_downloader(file_name, download_link)

        if file_path.exists():
            logger.info(f"Resolved name: {resolved_name}, File: {file_path.name}, downloaded successfully!")
            self.dl_resolved_names_archive.add(resolved_name)  # Prevent download of existing resolved names.
            self.new_dl_resolved_names.append(resolved_name + "\n")
        else:
            error_message = f"Resolved name: {resolved_name}, File: {file_path.name}, download failed!"
            logger.warning(error_message)
            self.error_msgs = f"{self.error_msgs}\n{error_message}"

    def batch_downloader(self, scrapper_name: str, all_download_details: dict) -> None:
        """
        Use multithreading to download multiple videos at the same time.
        @param scrapper_name: Name of scrapper using downloader.
        @param all_download_details: Should contain download link, file name and match name, in order.
        """
        logger.info(f"..........{scrapper_name} Using multithreading to download videos..........")
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
        self.send_error_messages(scrapper_name)
        logger.info("Downloads finished!")
        end = time.perf_counter()
        logger.info(f"Download time: {round(end - start, 4)}\n")
