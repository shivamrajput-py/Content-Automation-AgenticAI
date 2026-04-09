from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InstagramAutomationInput(BaseModel):
    creator_niche: str
    niche: str
    is_specific_niche: bool = False
    language_of_script: str = "Hinglish"
    language_of_text: str = "English"
    writing_style: str = "direct, insightful, engaging"
    location: str = "India"
    instagram_profile_url: str | None = None
    reels_per_hashtag: int = 25
    insta_scrape_type: str = "reels"
    enable_ai_edit: bool = Field(default=False, alias="enableaiedit")
    enable_broll: bool = True
    enable_bgm: bool = True
    remove_filler_words: bool = False
    remove_silence_parts: bool = False
    subtitle_template: str = "spotlight"
    subtitle_font_size: int = 48
    avatar_id: str = "13661b81f91a4e7fa458c6e0b4a8b00c"
    voice_id: str = "8OPtOKmpfhvnN2wLH7oo"
    publish_to_instagram: bool = False
    instagram_account_id: str | None = None
    dry_run: bool = True
    persist_to_sheet: bool = True
    history_sheet_ref: str = "gid=0"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class SearchPlan(BaseModel):
    hashtags: list[str]
    rationale: list[str]


class InstagramStrategy(BaseModel):
    topic: str
    target_audience: str
    why_this_works: str
    content_gap_addressed: str
    emotional_trigger: str
    supporting_points: list[str]


class ScriptSegment(BaseModel):
    start_seconds: int
    end_seconds: int
    purpose: str
    visual_direction: str


class InstagramScriptPackage(BaseModel):
    script_title: str
    topic_title: str
    estimated_duration: str
    hook: str
    buildup: str
    payoff: str
    cta: str
    full_text: str
    caption_text: str
    primary_hashtags: list[str]
    secondary_hashtags: list[str]
    broll_segments: list[ScriptSegment]


class QualityReview(BaseModel):
    approved: bool
    feedback: str
