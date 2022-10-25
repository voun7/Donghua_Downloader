import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import isodate
from dateutil import parser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)


# This class makes calls to the YouTube API
class YouTube:
    def __init__(self, playlist_id: str) -> None:
        self.playlist_id = playlist_id
        self.youtube = None
        self.default_duration = timedelta(hours=12)
        try:
            self.get_authenticated_service()
        except Exception as error:
            logger.exception(error)
            logger.critical("Program failed to authenticate!\n")

    # This method authenticates the script
    def get_authenticated_service(self) -> None:
        scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        api_service_name = "youtube"
        api_version = "v3"
        client_secrets_file = "Credentials/OAuth 2.0 Client ID.json"
        token_file = Path("Credentials/token.json")
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

    # This method will remove videos in the playlist that where uploaded more than the default duration.
    def clear_playlist(self) -> None:
        logger.info(f"..........Removing videos in playlist uploaded more than {self.default_duration}..........")
        request = self.youtube.playlistItems().list(
            part="snippet,contentDetails", maxResults=50, playlistId=self.playlist_id
        )
        response = request.execute()
        now = datetime.now().astimezone()
        for keys in response['items']:
            video_playlist_id = keys['id']
            video_title = keys['snippet']['title']
            if video_title != "Deleted video":
                iso_upload_time = keys['contentDetails']['videoPublishedAt']
                upload_time = parser.parse(iso_upload_time).astimezone()
                time_diff = now - upload_time
                if time_diff < self.default_duration:
                    logger.info(f"Not Removing Video: {video_title}, "
                                f"Uploaded At: {upload_time}, "
                                f"Time since uploaded: {time_diff}")
                else:
                    logger.info(f"Removing Video: {video_title} from playlist, "
                                f"Uploaded At: {upload_time}, "
                                f"Time since uploaded: {time_diff}")
                    delete_request = self.youtube.playlistItems().delete(id=video_playlist_id)
                    delete_request.execute()
            else:
                logger.warning(f"Removing deleted video: {video_playlist_id} from playlist.")
                delete_request = self.youtube.playlistItems().delete(id=video_playlist_id)
                delete_request.execute()

    # This method uses the channel id and finds the upload id then returns
    # a dict of the video id and title for the videos uploaded less than the default time.
    def get_channel_recent_video_uploads(self, channel_id: str) -> dict:
        upload_id = None
        channel_request = self.youtube.channels().list(part="contentDetails", id=channel_id)
        channel_response = channel_request.execute()
        for key in channel_response['items']:
            upload_id = key['contentDetails']['relatedPlaylists']['uploads']
        request = self.youtube.playlistItems().list(part="snippet", maxResults=50, playlistId=upload_id)
        response = request.execute()
        now = datetime.now().astimezone()
        video_id_and_title = {}
        for keys in response['items']:
            channel_title = keys['snippet']['channelTitle']
            video_id = keys['snippet']['resourceId']['videoId']
            video_title = keys['snippet']['title']
            # The time in snippet.publishedAt and contentDetails.videoPublishedAt are
            # always the same for the uploads playlist when accessed by non owner.
            iso_published_time = keys['snippet']['publishedAt']
            upload_time = parser.parse(iso_published_time).astimezone()
            time_diff = now - upload_time
            if time_diff < self.default_duration:
                logger.info(f"Channel Title: {channel_title}, "
                            f"Video Title: {video_title}, "
                            f"Video ID: {video_id}, "
                            f"Uploaded At: {upload_time}")
                video_id_and_title[video_id] = video_title
        return video_id_and_title

    # This method will check if the videos are the correct duration and High Definition
    # then returns a set of video ids with no duplicates that meet the requirements.
    def check_video(self, matched_video_ids: list) -> set:
        min_duration = timedelta(minutes=5)
        max_duration = timedelta(minutes=20)
        logger.info("..........Checking matched videos for duration and quality..........")
        passed_check_video_ids = set()
        for video_id in matched_video_ids:
            request = self.youtube.videos().list(part="contentDetails", id=video_id)
            response = request.execute()
            for item in response['items']:
                iso_content_duration = item['contentDetails']['duration']
                content_duration = isodate.parse_duration(iso_content_duration)
                definition = item['contentDetails']['definition']
                if min_duration < content_duration < max_duration and definition == "hd":
                    passed_check_video_ids.add(video_id)
                    logger.info(f"Video ID: {video_id} passed check. "
                                f"Duration: {content_duration}, Quality: {definition}")
                else:
                    logger.warning(f"Video ID: {video_id} failed check. "
                                   f"Duration: {content_duration}, Quality: {definition}")
        return passed_check_video_ids

    # This method will check if videos is in playlist and add it otherwise.
    def add_video_to_playlist(self, passed_video_ids: set) -> None:
        logger.info("..........Adding videos to playlist..........")
        video_ids_in_playlist = []
        request = self.youtube.playlistItems().list(part="snippet", maxResults=50, playlistId=self.playlist_id)
        response = request.execute()
        for keys in response['items']:
            video_ids_in_playlist.append(keys['snippet']['resourceId']['videoId'])
        for passed_video_id in passed_video_ids:
            if passed_video_id not in video_ids_in_playlist:
                logger.info(f"Video ID: {passed_video_id} is being added to playlist.")
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
                logger.warning(f"Video ID: {passed_video_id} already in playlist.")

    # This function matches the names in the list to recently uploaded YouTube videos
    # from the channels and adds them to the playlist.
    def match_to_youtube_videos(self, file_names: list, youtube_channel_ids: list) -> None:
        start = time.perf_counter()
        all_recent_uploads = {}
        logger.info(f"..........Checking all channels for recent video uploads "
                    f"in the last {self.default_duration}..........")
        for channel_id in youtube_channel_ids:
            uploads = self.get_channel_recent_video_uploads(channel_id)
            all_recent_uploads.update(uploads)
        logger.info("..........Checking for video matches..........")
        matched_video_ids = []
        for name in file_names:
            for video_id, video_title in all_recent_uploads.items():
                if name in video_title:
                    logger.info(f"Folder name: {name} matches "
                                f"Video ID: {video_id}, "
                                f"Video Title: {video_title}")
                    matched_video_ids.append(video_id)
        passed_video_ids = self.check_video(matched_video_ids)
        self.add_video_to_playlist(passed_video_ids)
        end = time.perf_counter()
        total_time = end - start
        logger.info(f"Total time matching recent uploads and adding to playlist took: {total_time}")

    # This method uses yt_dlp to download videos from playlist
    def playlist_downloader(self, playlist_download_location: Path) -> None:
        start = time.perf_counter()
        logger.info("..........Downloading videos from playlist..........")

        def my_hook(d):
            if d['status'] == 'error':
                logger.exception('An error has occurred ...')
            if d['status'] == 'finished':
                logger.info('Done downloading file, now post-processing ...')

        ydl_opts = {
            'logger': logger.getChild('yt_dlp'),
            'progress_hooks': [my_hook],
            'noprogress': True,
            'ignoreerrors': True,
            'wait_for_video': (1, 120),
            'download_archive': 'logs/yt_dlp_downloads_archive.txt',
            'format': 'bestvideo[height>720][ext=mp4]+bestaudio[ext=m4a]',
            'ffmpeg_location': 'ffmpeg/bin',
            'outtmpl': str(playlist_download_location) + '/%(title)s.%(ext)s'
        }
        with YoutubeDL(ydl_opts) as ydl:
            logger.debug(ydl.download(self.playlist_id))
        end = time.perf_counter()
        total_time = end - start
        logger.info(f"Total time downloading playlist took: {total_time}")
