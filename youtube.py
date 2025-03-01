import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import isodate
from ch_title_gen import ChineseTitleGenerator
from dateutil import parser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


# This class makes calls to the YouTube API.
class YouTube:
    credential_file = token_file = Path()

    def __init__(self, playlist_id: str, resolved_names_file: Path) -> None:
        self.playlist_id = playlist_id
        self.resolved_names_file = resolved_names_file
        self.youtube = None
        self.max_results = 50
        self.default_duration = timedelta(hours=12)
        self.ch_name_gen = ChineseTitleGenerator()
        self.get_authenticated_service()

    def get_authenticated_service(self) -> None:
        """
        This method authenticates the program.
        """
        scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        api_service_name, api_version, creds = "youtube", "v3", None
        # The file token_file stores the user's access and refresh tokens, and is created
        # automatically when the authorization flow completes for the first time.
        if self.token_file.exists():
            logger.debug("Token file exists and is being used.")
            creds = Credentials.from_authorized_user_file(str(self.token_file), scopes)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            logger.debug("Issue with token detected. Credentials validity are being rechecked!")
            try:
                if creds and creds.expired and creds.refresh_token:
                    logger.debug("Token Credentials are being refreshed.")
                    creds.refresh(Request())
                else:
                    logger.critical("Credentials did not work! Local login in is required!")
                    flow = InstalledAppFlow.from_client_secrets_file(str(self.credential_file), scopes)
                    creds = flow.run_local_server()
                # Save the credentials for the next run.
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            except Exception as error:
                raise RuntimeError(f"Youtube program failed to authenticate! \nError: {error}") from error
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
            return
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
        channel_request = self.youtube.channels().list(part="contentDetails", id=channel_id)
        try:
            channel_response = channel_request.execute()
            upload_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            request = self.youtube.playlistItems().list(part="snippet", maxResults=self.max_results,
                                                        playlistId=upload_id)
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

    def quality_check_videos(self, matched_videos: dict) -> dict:
        """
        This method will check if the videos are the correct duration and High Definition
        then returns video ids with no duplicates that meet the requirements.
        :param matched_videos: Dictionary containing the video id as key and resolved name as value.
        :return: Dictionary containing video id as key, resolved name and video title as values.
        """
        logger.info("..........Checking matched videos for duration and quality..........")
        min_duration, max_duration = timedelta(minutes=2), timedelta(minutes=40)
        passed_check_videos = {}
        for video_id, resolved_name in matched_videos.items():
            request = self.youtube.videos().list(part="snippet,contentDetails", id=video_id)
            response = request.execute()
            for item in response['items']:
                video_title = item['snippet']['title']
                iso_content_duration = item['contentDetails'].get('duration')
                if iso_content_duration:
                    content_duration = isodate.parse_duration(iso_content_duration)
                else:
                    content_duration = timedelta()  # Premieres are given 0 duration.
                definition = item['contentDetails']['definition']
                if min_duration < content_duration < max_duration and definition == "hd":
                    passed_check_videos[video_id] = resolved_name, video_title
                    logger.info(f"Video ID: {video_id} passed check. Duration: {content_duration}, "
                                f"Quality: {definition}, Resolved name: {resolved_name}, Video Title: {video_title}")
                else:
                    logger.warning(f"Video ID: {video_id} failed check. Duration: {content_duration}, "
                                   f"Quality: {definition}, Resolved name: {resolved_name}, Video Title: {video_title}")
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
        :param passed_videos: Dictionary containing the video id as key and video title as value.
        """
        logger.info("..........Adding videos to playlist..........")
        if not passed_videos:
            logger.warning("No videos to add to playlist!")
            return
        videos_in_playlist = self.get_videos_in_playlist()
        for passed_video_id, passed_video_title in passed_videos.items():
            if passed_video_id not in list(videos_in_playlist):
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

    def archive_check(self, quality_checked_videos: dict) -> dict:
        """
        Check if videos have been archived previously and archive new videos.
        This method will use the resolved name to prevent previously archived
        resolved names from being added to playlist.
        :param quality_checked_videos: Dictionary containing video id as key, resolved name and video title as values.
        :return: Dictionary containing the video id as key and video title as value.
        """
        logger.info("..........Checking archive for resolved name matches..........")
        resolved_names_archive = set(self.resolved_names_file.read_text(encoding="utf-8").splitlines())
        archive_checked_videos, new_resolved_names = {}, []
        for video_id, video_details in quality_checked_videos.items():
            resolved_name, video_title = video_details[0], video_details[1]
            if resolved_name in resolved_names_archive:
                logger.warning(f"Video ID: {video_id}, Resolved name: {resolved_name} is already in the archive.")
            elif self.ch_name_gen.episode_range_pattern.search(video_title):
                resolved_name_range = resolved_name.split("EP")
                resolved_name_episodes = resolved_name_range[1].split("-")
                resolved_name_1 = f"{resolved_name_range[0]}EP{resolved_name_episodes[0]}"
                resolved_name_2 = f"{resolved_name_range[0]}EP{resolved_name_episodes[1]}"
                if resolved_name_1 in resolved_names_archive or resolved_name_2 in resolved_names_archive:
                    logger.warning(f"Video ID: {video_id}, Part of resolved name: {resolved_name} already in archive.")
                else:
                    logger.info(f"Video ID: {video_id}, Resolved name: {resolved_name} is being added to the archive.")
                    archive_checked_videos[video_id] = video_title
                    if resolved_name_1 not in resolved_names_archive:
                        new_resolved_names.append(resolved_name_1 + "\n")
                    new_resolved_names.append(resolved_name_2 + "\n")
            else:
                logger.info(f"Video ID: {video_id}, Resolved name: {resolved_name} is being added to the archive.")
                archive_checked_videos[video_id] = video_title
                new_resolved_names.append(resolved_name + "\n")
        if new_resolved_names:
            logger.info(f"Archive updated with new names. Names: {new_resolved_names}")
            with open(self.resolved_names_file, 'a', encoding="utf-8") as text_file:
                text_file.writelines(new_resolved_names)
        return archive_checked_videos

    def get_all_channel_uploads(self, youtube_channel_ids: list) -> dict:
        """
        Get recent updates from all the channel ids.
        """
        logger.info(f"..........Checking channel(s) for recent video uploads "
                    f"in the last {self.default_duration}..........")
        all_recent_uploads = {}
        for channel_id in youtube_channel_ids:
            uploads = self.get_channel_recent_video_uploads(channel_id)
            all_recent_uploads.update(uploads)
        return all_recent_uploads

    def check_matches(self, matched_videos: dict) -> None:
        """
        Run matched videos through checks and add videos that passed to playlist.
        """
        if matched_videos:
            quality_checked_videos = self.quality_check_videos(matched_videos)
            archive_checked_videos = self.archive_check(quality_checked_videos)
            self.add_video_to_playlist(archive_checked_videos)
        else:
            logger.warning("No video matches!")

    def match_to_youtube_videos(self, youtube_channel_ids: list, anime_names: list) -> None:
        """
        This function matches the names in the list to recently uploaded YouTube videos
        from the channels and adds them to the playlist.
        """
        start = time.perf_counter()
        all_recent_uploads = self.get_all_channel_uploads(youtube_channel_ids)
        if not all_recent_uploads:
            logger.info("No recent video uploads!")
            return
        logger.info("..........Checking for video matches..........")
        matched_videos = {}
        for anime_name in anime_names:
            for video_id, video_title in all_recent_uploads.items():
                if anime_name in video_title:  # Match found.
                    resolved_name = self.ch_name_gen.generate_title(video_title, anime_name)
                    logger.info(f"Anime name: {anime_name} matches Video ID: {video_id}, Video Title: {video_title}")
                    # Prevent matching video with same name from different channels.
                    if resolved_name not in list(matched_videos.values()):
                        logger.info(f"Video ID: {video_id}, Resolved name: {resolved_name} added to matches.")
                        matched_videos[video_id] = resolved_name
                    else:
                        logger.warning(f"Video ID: {video_id}, "
                                       f"Resolved name: {resolved_name} already exists in matches, will not be added.")
        self.check_matches(matched_videos)
        end = time.perf_counter()
        logger.info(f"Time matching recent uploads and adding to playlist took: {round(end - start)}s")
