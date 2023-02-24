import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import isodate
from dateutil import parser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pycnnum import cn2num
from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)


# This class makes calls to the YouTube API
class YouTube:
    def __init__(self, playlist_id: str) -> None:
        self.playlist_id = playlist_id
        self.youtube = None
        self.max_results = 50
        self.default_duration = timedelta(hours=12)
        try:
            self.get_authenticated_service()
        except Exception as error:
            logger.exception(error)
            logger.critical("Program failed to authenticate!\n")

    def get_authenticated_service(self) -> None:
        """
        This method authenticates the program.
        """
        scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        api_service_name = "youtube"
        api_version = "v3"
        client_secrets_file = "credentials/OAuth 2.0 Client ID.json"
        token_file = Path("credentials/token.json")
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), scopes)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes)
                creds = flow.run_local_server()
            # Save the credentials for the next run
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
        self.youtube = build(api_service_name, api_version, credentials=creds)

    def clear_playlist(self) -> None:
        """
        This method will remove videos in the playlist that where uploaded more than the default duration.
        """
        logger.info(f"..........Removing videos in playlist uploaded more than {self.default_duration}..........")
        request = self.youtube.playlistItems().list(
            part="snippet,contentDetails", maxResults=self.max_results, playlistId=self.playlist_id
        )
        response = request.execute()
        num_of_videos_in_playlist = response['pageInfo']['totalResults']
        if num_of_videos_in_playlist:
            logger.info(f"{num_of_videos_in_playlist} Video(s) in playlist.")
        else:
            logger.info("No videos in playlist!")
        current_time = datetime.now().astimezone()
        for item in response['items']:
            video_playlist_id = item['id']
            video_title = item['snippet']['title']
            if video_title != "Deleted video" and video_title != "Private video":
                iso_upload_time = item['contentDetails']['videoPublishedAt']
                upload_time = parser.parse(iso_upload_time).astimezone()
                time_diff = current_time - upload_time
                if time_diff < self.default_duration:
                    logger.info(f"Not Removing Video: {video_title}, Uploaded At: {upload_time}, "
                                f"Time since uploaded: {time_diff}")
                else:
                    logger.info(f"Removing Video: {video_title} from playlist, Uploaded At: {upload_time}, "
                                f"Time since uploaded: {time_diff}")
                    delete_request = self.youtube.playlistItems().delete(id=video_playlist_id)
                    delete_request.execute()
            else:
                logger.warning(f"Removing deleted or private video: {video_playlist_id} from playlist.")
                delete_request = self.youtube.playlistItems().delete(id=video_playlist_id)
                delete_request.execute()

    def get_channel_recent_video_uploads(self, channel_id: str) -> dict:
        """
        This method uses the channel id and finds the upload id then returns
        the video id and title for the videos uploaded less than the default time.
        """
        upload_id = None
        channel_request = self.youtube.channels().list(part="contentDetails", id=channel_id)
        channel_response = channel_request.execute()
        for item in channel_response['items']:
            upload_id = item['contentDetails']['relatedPlaylists']['uploads']
        request = self.youtube.playlistItems().list(part="snippet", maxResults=self.max_results, playlistId=upload_id)
        try:
            response = request.execute()
        except Exception as error:
            logger.error(f"Youtube Channel: {channel_id} request failed")
            logger.exception(error)
            return {}
        current_time = datetime.now().astimezone()
        video_id_and_title = {}
        for item in response['items']:
            channel_title = item['snippet']['channelTitle']
            video_id = item['snippet']['resourceId']['videoId']
            video_title = item['snippet']['title']
            # The time in snippet.publishedAt and contentDetails.videoPublishedAt are
            # always the same for the uploads playlist when accessed by non owner.
            iso_published_time = item['snippet']['publishedAt']
            upload_time = parser.parse(iso_published_time).astimezone()
            time_diff = current_time - upload_time
            if time_diff < self.default_duration:
                logger.info(f"Channel Title: {channel_title}, "
                            f"Video Title: {video_title}, "
                            f"Video ID: {video_id}, "
                            f"Uploaded At: {upload_time}")
                video_id_and_title[video_id] = video_title
        return video_id_and_title

    def check_video(self, matched_video_ids: list) -> dict:
        """
        This method will check if the videos are the correct duration and High Definition
        then returns video ids with no duplicates that meet the requirements.
        """
        logger.info("..........Checking matched videos for duration and quality..........")
        min_duration = timedelta(minutes=4)
        max_duration = timedelta(minutes=20)
        passed_check_videos = {}
        for video_id in matched_video_ids:
            request = self.youtube.videos().list(part="snippet,contentDetails", id=video_id)
            response = request.execute()
            for item in response['items']:
                video_title = item['snippet']['title']
                iso_content_duration = item['contentDetails']['duration']
                content_duration = isodate.parse_duration(iso_content_duration)
                definition = item['contentDetails']['definition']
                if min_duration < content_duration < max_duration and definition == "hd":
                    passed_check_videos[video_id] = video_title
                    logger.info(f"Video ID: {video_id} passed check. "
                                f"Duration: {content_duration}, Quality: {definition}, Video Title: {video_title}")
                else:
                    logger.warning(f"Video ID: {video_id} failed check. "
                                   f"Duration: {content_duration}, Quality: {definition}, Video Title: {video_title}")
        return passed_check_videos

    def get_videos_in_playlist(self) -> dict:
        request = self.youtube.playlistItems().list(
            part="snippet", maxResults=self.max_results, playlistId=self.playlist_id
        )
        response = request.execute()
        videos_in_playlist = {}
        for item in response['items']:
            video_id = item['snippet']['resourceId']['videoId']
            video_title = item['snippet']['title']
            videos_in_playlist[video_id] = video_title
        return videos_in_playlist

    def add_video_to_playlist(self, passed_videos: dict) -> None:
        """
        This method will check if videos is in playlist and add it otherwise.
        """
        logger.info("..........Adding videos to playlist..........")
        videos_in_playlist = self.get_videos_in_playlist()
        if not passed_videos:
            logger.warning("No videos to add to playlist!")
        for passed_video_id, passed_video_title in passed_videos.items():
            if passed_video_id not in list(videos_in_playlist.keys()):
                logger.info(f"Video ID: {passed_video_id} is being added to playlist, "
                            f"Video Title: {passed_video_title}")
                insert_request = self.youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": self.playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": passed_video_id
                            }
                        }
                    }
                )
                insert_request.execute()
            else:
                logger.warning(f"Video ID: {passed_video_id} already in playlist, Video Title: {passed_video_title}")

    @staticmethod
    def title_filter(name: str) -> str:
        """
        This function takes a name searches for the chinese number characters
        and replaces them all with numbers, then removes the keywords from the name.
        It converts the character it doesn't recognize to english with pycnnum.
        """
        filtered_name = name
        ch_num_pattern = re.compile(r'第([\u4e00-\u9fff]+)[集季话]')
        en_keyword_pattern = re.compile(r'[Ss](\d+)')
        ch_keyword = re.search(r'第(\d+)[集季话]', filtered_name)
        ch_key_and_num = re.search(r'季[-\d]', filtered_name)

        if ch_num_pattern.search(filtered_name):
            logger.debug("match in ch num")
            chinese_numbers = ch_num_pattern.finditer(filtered_name)
            for match in chinese_numbers:
                ch_num_match = match.group(0)
                ch_num_in_english = str(cn2num(match.group(1)))
                filtered_name = filtered_name.replace(ch_num_match, f"第{ch_num_in_english}集")
        if en_keyword_pattern.search(filtered_name) and ch_keyword:
            logger.debug("match in en key and ch key")
            en_keyword = en_keyword_pattern.finditer(filtered_name)
            for match in en_keyword:
                en_char_match = match.group(0)
                logger.debug(f"en_char_match: {en_char_match}")
                en_char_match_num = match.group(1)
                filtered_name = filtered_name.replace(en_char_match, f"第{en_char_match_num}集")
        if ch_key_and_num:
            logger.debug("match in ch key and num")
            filtered_name = filtered_name.replace('第', '')
        return filtered_name

    def resolved_title(self, name: str, title: str) -> str:
        """
        This function uses the name of the folder and appends it with the
        numbers in english or chinese that appear in the title name.
        The numbers that match keyword '第' at the start and ends with either keywords '集','季','话'
        are mostly used for determining the file name.
        """
        filtered_name = self.title_filter(title)
        logger.debug(f"Filtered name: {filtered_name}")
        symbol_finder = re.search(r'\d+\s?[-~]\s?\d+', filtered_name)
        keyword_number_list = re.findall(r'第(\d+)[集季话]', filtered_name)
        all_name_numbers = re.findall(r'(\d+)', filtered_name)

        if symbol_finder:
            symbol_number_list = re.findall(r'第(\d+)[-~](\d+)[集季话]', filtered_name)
            if symbol_number_list:
                logger.debug("symbol finder using symbol numbers")
                number_list = symbol_number_list[0]
                logger.debug(f"number list: {number_list}")
            else:
                logger.debug("symbol finder using all name numbers")
                number_list = all_name_numbers
                logger.debug(f"number list: {number_list}")
        elif keyword_number_list:
            logger.debug("using keyword numbers")
            number_list = keyword_number_list
            logger.debug(f"number list: {number_list}")
        else:
            logger.debug("using all name numbers")
            number_list = all_name_numbers
            logger.debug(f"number list: {number_list}")

        if symbol_finder:
            if len(number_list) == 2:
                first_ep_num = number_list[0]
                last_ep_num = number_list[1]
                new_name = name + " EP" + first_ep_num + '-' + last_ep_num
                return new_name
            else:
                season_num = number_list[0]
                first_ep_num = number_list[1]
                last_ep_num = number_list[2]
                new_name = name + " S" + season_num + " EP" + first_ep_num + '-' + last_ep_num
                return new_name
        else:
            if len(number_list) == 1:
                ep_num = number_list[0]
                new_name = name + " EP" + ep_num
                return new_name
            elif len(number_list) > 1:
                season_number = number_list[0]
                episode_number = number_list[1]
                new_name = name + " S" + season_number + " EP" + episode_number
                return new_name
            else:
                return filtered_name

    def match_to_youtube_videos(self, youtube_channel_ids: list, file_names: list) -> None:
        """
        This function matches the names in the list to recently uploaded YouTube videos
        from the channels and adds them to the playlist.
        """
        logger.info(f"..........Checking channel(s) for recent video uploads "
                    f"in the last {self.default_duration}..........")
        start = time.perf_counter()
        all_recent_uploads = {}
        for channel_id in youtube_channel_ids:
            uploads = self.get_channel_recent_video_uploads(channel_id)
            all_recent_uploads.update(uploads)
        if not all_recent_uploads:
            logger.info("No recent video uploads!")
        logger.info("..........Checking for video matches..........")
        matched_videos = {}
        for name in file_names:
            for video_id, video_title in all_recent_uploads.items():
                if name in video_title:
                    resolved_name = self.resolved_title(name, video_title)
                    logger.info(f"Folder name: {name} matches "
                                f"Video ID: {video_id}, Video Title: {video_title}")
                    if resolved_name not in list(matched_videos.values()):
                        logger.info(f"Resolved Name: {resolved_name} added to matches.")
                        matched_videos[video_id] = resolved_name
                    else:
                        logger.warning(f"Resolved Name: {resolved_name} already exists in matches, will not be added.")
        if matched_videos:
            passed_check_videos = self.check_video(list(matched_videos.keys()))
            self.add_video_to_playlist(passed_check_videos)
        else:
            logger.warning("No video matches!")
        end = time.perf_counter()
        total_time = end - start
        logger.info(f"Total time matching recent uploads and adding to playlist took: {total_time}")

    def playlist_downloader(self, download_location: Path, download_archives: Path) -> None:
        """
        This method uses yt_dlp to download videos from playlist.
        """
        logger.info("..........Downloading videos from playlist..........")
        start = time.perf_counter()

        def my_hook(d: dict) -> None:
            if d['status'] == 'error':
                logger.exception('An error has occurred ...')
            if d['status'] == 'finished':
                logger.info('Done downloading file, now post-processing ...')

        ydl_opts = {
            'logger': logger.setLevel(logging.INFO),
            'progress_hooks': [my_hook],
            # 'noprogress': True,
            'ignoreerrors': True,
            'socket_timeout': 120,
            'wait_for_video': (1, 600),
            'download_archive': download_archives / "youtube_downloads_archive.txt",
            'format': 'bestvideo[height>720][ext=mp4]+bestaudio[ext=m4a]',
            'ffmpeg_location': 'ffmpeg/bin',
            'outtmpl': str(download_location) + '/%(title)s.%(ext)s'
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download(self.playlist_id)
        end = time.perf_counter()
        total_time = end - start
        logger.info(f"Total time downloading playlist took: {total_time}\n")
