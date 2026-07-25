from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ContentResearchInput(BaseModel):
    creator_niche: str
    niche: str
    is_specific_niche: bool = False
    language_of_script: str = "Hinglish"
    language_of_text: str = "English"
    writing_style: str = "direct, clear, insightful"
    location: str = "India"
    no_of_reels_to_scrape: int = Field(default=25, alias="noOfReelsToScrape")
    reels_till_filter: int = Field(default=30, alias="reelsTill_Filter")
    min_likes_reel_filter: int = Field(default=0, alias="minLikesReel_Filter")
    competitor_list_usernames: list[str] | str | None = Field(default=None, alias="competitorListUsernames")
    instagram_profile_url: str | None = None
    result_type: str = Field(default="reels", alias="type")
    search_terms: list[str] | None = None
    persist_to_sheet: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class SearchPlan(BaseModel):
    hashtags: list[str]
    search_queries: list[str]
    rationale: list[str]


class ResearchSynthesis(BaseModel):
    executive_summary: str
    posting_schedule: str
    instagram_findings: list[str]
    twitter_findings: list[str]
    linkedin_findings: list[str]
    content_recommendations: list[str]
    recommended_topics: list[str]
    risks_to_avoid: list[str]


class QualityReview(BaseModel):
    approved: bool
    feedback: str
