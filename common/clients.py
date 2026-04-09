from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import gspread
import httpx
from openai import OpenAI
from requests_oauthlib import OAuth1Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .settings import CommonSettings, MissingConfigurationError


class ApifyClient:
    def __init__(self, settings: CommonSettings) -> None:
        if not settings.apify_api_token:
            raise MissingConfigurationError("APIFY_API_TOKEN is required for Apify scraping.")
        self._settings = settings
        self._client = httpx.Client(timeout=settings.request_timeout_seconds)

    @retry(
        reraise=True,
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
    )
    def run_actor_sync(self, actor_slug: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        response = self._client.post(
            f"https://api.apify.com/v2/acts/{actor_slug}/run-sync-get-dataset-items",
            params={"token": self._settings.apify_api_token},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else [data]

    def scrape_instagram_hashtags(self, hashtags: list[str], limit: int, result_type: str) -> list[dict[str, Any]]:
        return self.run_actor_sync(
            "apify~instagram-hashtag-scraper",
            {
                "hashtags": hashtags,
                "resultsLimit": limit,
                "resultsType": result_type,
            },
        )

    def scrape_instagram_profile(self, profile_url: str, limit: int, result_type: str) -> list[dict[str, Any]]:
        return self.run_actor_sync(
            "apify~instagram-scraper",
            {
                "addParentData": False,
                "directUrls": [profile_url],
                "enhanceUserSearchWithFacebookPage": False,
                "isUserReelFeedURL": False,
                "isUserTaggedFeedURL": False,
                "resultsLimit": limit,
                "resultsType": result_type,
            },
        )

    def extract_instagram_transcript(self, instagram_url: str) -> list[dict[str, Any]]:
        return self.run_actor_sync(
            "sian.agency~instagram-ai-transcript-extractor",
            {"fastProcessing": False, "instagramUrl": instagram_url},
        )

    def scrape_twitter(self, query: str, max_posts: int) -> list[dict[str, Any]]:
        return self.run_actor_sync(
            "danek~twitter-scraper-ppr",
            {"query": query, "max_posts": max_posts},
        )

    def scrape_linkedin(self, keyword: str, limit: int) -> list[dict[str, Any]]:
        return self.run_actor_sync(
            "apimaestro~linkedin-posts-search-scraper-no-cookies",
            {
                "date_filter": "past-week",
                "keyword": keyword,
                "limit": limit,
                "sort_type": "relevance",
            },
        )


class GoogleSheetsRepository:
    def __init__(self, settings: CommonSettings) -> None:
        self._settings = settings

    def _client(self):
        if not self._settings.google_service_account_json:
            raise MissingConfigurationError("GOOGLE_SERVICE_ACCOUNT_JSON is required for Google Sheets access.")

        raw = self._settings.google_service_account_json
        credentials_info = json.loads(raw) if raw.strip().startswith("{") else json.loads(Path(raw).read_text(encoding="utf-8"))
        return gspread.service_account_from_dict(credentials_info)

    def _worksheet(self, spreadsheet_id: str, worksheet_ref: str):
        spreadsheet = self._client().open_by_key(spreadsheet_id)
        if worksheet_ref.startswith("gid="):
            return spreadsheet.get_worksheet_by_id(int(worksheet_ref.split("=", 1)[1]))
        if worksheet_ref.isdigit():
            return spreadsheet.get_worksheet_by_id(int(worksheet_ref))
        return spreadsheet.worksheet(worksheet_ref)

    def read_records(self, spreadsheet_id: str, worksheet_ref: str) -> list[dict[str, Any]]:
        return self._worksheet(spreadsheet_id, worksheet_ref).get_all_records()

    def append_record(self, spreadsheet_id: str, worksheet_ref: str, record: dict[str, Any]) -> None:
        worksheet = self._worksheet(spreadsheet_id, worksheet_ref)
        header = worksheet.row_values(1)
        if not header:
            worksheet.append_row(list(record.keys()))
            header = list(record.keys())
        worksheet.append_row([record.get(column, "") for column in header], value_input_option="USER_ENTERED")


class OpenRouterImageClient:
    def __init__(self, settings: CommonSettings) -> None:
        if not settings.openrouter_api_key:
            raise MissingConfigurationError("OPENROUTER_API_KEY is required for image generation.")
        self._client = OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)
        self._settings = settings

    def generate_image_bytes(self, prompt: str) -> bytes:
        response = self._client.chat.completions.create(
            model=self._settings.openrouter_image_model,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        )
        images = response.choices[0].message.images or []
        if not images:
            raise RuntimeError("OpenRouter did not return an image.")
        image_url = images[0].image_url.url
        encoded = image_url.replace("data:image/png;base64,", "")
        return base64.b64decode(encoded)


class TemporaryUploadClient:
    def __init__(self, settings: CommonSettings) -> None:
        self._client = httpx.Client(timeout=settings.request_timeout_seconds)

    def upload_bytes(self, filename: str, payload: bytes, *, retention_hours: int = 72) -> str:
        response = self._client.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            files={"fileToUpload": (filename, payload)},
            data={"reqtype": "fileupload", "time": f"{retention_hours}h"},
        )
        response.raise_for_status()
        return response.text.strip()

    def upload_from_url(self, source_url: str, filename: str) -> str:
        binary = self._client.get(source_url)
        binary.raise_for_status()
        return self.upload_bytes(filename, binary.content)


class ElevenLabsClient:
    def __init__(self, settings: CommonSettings) -> None:
        if not settings.elevenlabs_api_key:
            raise MissingConfigurationError("ELEVENLABS_API_KEY is required for TTS.")
        self._settings = settings
        self._client = httpx.Client(timeout=settings.request_timeout_seconds)

    def synthesize(self, text: str, voice_id: str, *, speed: float = 1.15) -> bytes:
        response = self._client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": self._settings.elevenlabs_api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.9,
                    "style": 0.2,
                    "use_speaker_boost": True,
                    "speed": speed,
                },
            },
        )
        response.raise_for_status()
        return response.content


class HeyGenClient:
    def __init__(self, settings: CommonSettings) -> None:
        if not settings.heygen_api_key:
            raise MissingConfigurationError("HEYGEN_API_KEY is required for avatar video generation.")
        self._settings = settings
        self._client = httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={
                "X-Api-Key": settings.heygen_api_key,
                "Content-Type": "application/json",
            },
        )

    def generate_avatar_video(self, audio_url: str, avatar_id: str) -> str:
        response = self._client.post(
            "https://api.heygen.com/v2/video/generate",
            json={
                "video_inputs": [
                    {
                        "character": {
                            "type": "avatar",
                            "avatar_id": avatar_id,
                            "avatar_style": "normal",
                        },
                        "voice": {"type": "audio", "audio_url": audio_url},
                    }
                ],
                "dimension": {"width": 1080, "height": 1920},
            },
        )
        response.raise_for_status()
        return response.json()["data"]["video_id"]

    def get_video_status(self, video_id: str) -> dict[str, Any]:
        response = self._client.get(
            "https://api.heygen.com/v1/video_status.get",
            params={"video_id": video_id},
        )
        response.raise_for_status()
        return response.json()


class QuickReelClient:
    def __init__(self, settings: CommonSettings) -> None:
        if not settings.quickreel_api_key:
            raise MissingConfigurationError("QUICKREEL_API_KEY is required for video finishing.")
        self._client = httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={"x-api-key": settings.quickreel_api_key, "Content-Type": "application/json"},
        )

    def create_subtitles(
        self,
        *,
        video_url: str,
        language: str,
        template: str,
        font_size: int,
        add_bgm: bool,
        remove_filler_words: bool,
        remove_silence_parts: bool,
    ) -> str:
        response = self._client.post(
            "https://mango.quickreel.io/api/v2/subtitles",
            json={
                "videoUrl": video_url,
                "language": language,
                "subtitleStyles": {
                    "template": template,
                    "position": "bottom-center",
                    "fontSize": font_size,
                },
                "additionalFeatures": {
                    "removeFillerWords": remove_filler_words,
                    "removeSilenceParts": remove_silence_parts,
                    "addBgm": add_bgm,
                },
            },
        )
        response.raise_for_status()
        return response.json()["data"]["projectId"]

    def edit_with_ai(self, *, video_url: str, language: str) -> str:
        response = self._client.post(
            "https://mango.quickreel.io/api/v2/edit",
            json={
                "videoUrl": video_url,
                "language": language,
                "template": "vivid",
                "brollFrequency": "medium",
                "additionalFeatures": {
                    "addBgm": True,
                    "removeFillerWords": False,
                    "removeSilenceParts": False,
                },
                "additionalSettings": {
                    "soundEffectsVolume": 0.5,
                    "applySpearkerDetection": True,
                },
            },
        )
        response.raise_for_status()
        return response.json()["data"]["projectId"]

    def create_broll(self, *, video_url: str, language: str) -> str:
        response = self._client.post(
            "https://mango.quickreel.io/api/v2/brolls",
            json={"videoUrl": video_url, "language": language},
        )
        response.raise_for_status()
        return response.json()["data"]["projectId"]

    def get_project(self, project_id: str) -> dict[str, Any]:
        response = self._client.get(f"https://mango.quickreel.io/api/v2/projects/{project_id}")
        response.raise_for_status()
        return response.json()


class InstagramGraphClient:
    def __init__(self, settings: CommonSettings) -> None:
        if not settings.facebook_access_token:
            raise MissingConfigurationError("FACEBOOK_ACCESS_TOKEN is required for Instagram publishing.")
        self._settings = settings
        self._client = httpx.Client(timeout=settings.request_timeout_seconds)

    def create_reel_container(self, account_id: str, *, video_url: str, caption: str) -> str:
        response = self._client.post(
            f"https://graph.facebook.com/v23.0/{account_id}/media",
            params={
                "access_token": self._settings.facebook_access_token,
                "video_url": video_url,
                "caption": caption,
                "media_type": "REELS",
            },
        )
        response.raise_for_status()
        return response.json()["id"]

    def publish_media(self, account_id: str, creation_id: str) -> dict[str, Any]:
        response = self._client.post(
            f"https://graph.facebook.com/v23.0/{account_id}/media_publish",
            params={
                "access_token": self._settings.facebook_access_token,
                "creation_id": creation_id,
            },
        )
        response.raise_for_status()
        return response.json()


class TwitterPublisher:
    def __init__(self, settings: CommonSettings) -> None:
        required = [
            settings.twitter_consumer_key,
            settings.twitter_consumer_secret,
            settings.twitter_access_token,
            settings.twitter_access_token_secret,
        ]
        if any(value is None for value in required):
            raise MissingConfigurationError("Twitter OAuth 1.0a user credentials are required for posting.")
        self._session = OAuth1Session(
            settings.twitter_consumer_key,
            client_secret=settings.twitter_consumer_secret,
            resource_owner_key=settings.twitter_access_token,
            resource_owner_secret=settings.twitter_access_token_secret,
        )

    def publish(self, text: str) -> dict[str, Any]:
        response = self._session.post("https://api.twitter.com/2/tweets", json={"text": text})
        response.raise_for_status()
        return response.json()


class LinkedInPublisher:
    def __init__(self, settings: CommonSettings) -> None:
        if not settings.linkedin_access_token or not settings.linkedin_author_urn:
            raise MissingConfigurationError("LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are required for LinkedIn publishing.")
        self._settings = settings
        self._client = httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={
                "Authorization": f"Bearer {settings.linkedin_access_token}",
                "LinkedIn-Version": "202502",
                "X-Restli-Protocol-Version": "2.0.0",
            },
        )

    def _register_upload(self) -> dict[str, Any]:
        response = self._client.post(
            "https://api.linkedin.com/rest/images?action=initializeUpload",
            json={"initializeUploadRequest": {"owner": self._settings.linkedin_author_urn}},
        )
        response.raise_for_status()
        return response.json()["value"]

    def _upload_image(self, upload_url: str, image_bytes: bytes) -> None:
        response = self._client.put(upload_url, content=image_bytes, headers={"Content-Type": "image/png"})
        response.raise_for_status()

    def publish_with_image(self, *, text: str, image_bytes: bytes, alt_text: str) -> dict[str, Any]:
        upload = self._register_upload()
        self._upload_image(upload["uploadUrl"], image_bytes)
        response = self._client.post(
            "https://api.linkedin.com/rest/posts",
            json={
                "author": self._settings.linkedin_author_urn,
                "commentary": text,
                "visibility": "PUBLIC",
                "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                "content": {
                    "media": {
                        "id": upload["image"],
                        "title": "AI-generated LinkedIn image",
                        "altText": alt_text,
                    }
                },
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            },
        )
        response.raise_for_status()
        return response.json()
