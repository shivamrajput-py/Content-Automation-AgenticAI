from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SocialAutopostInput(BaseModel):
    creator_niche: str
    niche: str
    searches: list[str] | None = None
    language_of_text: str = "English"
    writing_style: str = "insightful, clear, shareable"
    location: str = "India"
    dry_run: bool = True
    publish_to_twitter: bool = False
    publish_to_linkedin: bool = False
    persist_to_sheet: bool = True
    history_sheet_ref: str = "gid=0"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SocialSearchPlan(BaseModel):
    searches: list[str]
    rationale: list[str]


class ContentStrategy(BaseModel):
    core_angle: str
    audience_problem: str
    supporting_points: list[str]
    linkedin_hook: str
    twitter_hook: str
    differentiation: str
    avoid_topics: list[str]


class PlatformPost(BaseModel):
    post_text: str
    hashtags: list[str]
    hashtags_string: str
    hook_line: str


class SocialPostPackage(BaseModel):
    linkedin_post: PlatformPost
    twitter_post: PlatformPost
    topic_title: str
    rationale: str


class ImagePromptPackage(BaseModel):
    image_prompt: str
    alt_text: str


class QualityReview(BaseModel):
    approved: bool
    feedback: str
