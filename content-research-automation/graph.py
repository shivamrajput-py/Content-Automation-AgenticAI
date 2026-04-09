from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ..common.clients import ApifyClient, GoogleSheetsRepository
from ..common.llm import build_chat_model
from ..common.settings import CommonSettings
from ..common.utils import (
    analyze_instagram_reels,
    as_list,
    dedupe_preserve_order,
    parse_competitors,
    rank_instagram_reels,
    select_recent_best_reels,
    slugify,
    summarize_linkedin_posts,
    summarize_tweets,
    utc_now_iso,
    write_json_artifact,
)
from .prompts import QUALITY_REVIEW_PROMPT, SEARCH_PLANNER_PROMPT, SYNTHESIS_PROMPT
from .schemas import ContentResearchInput, QualityReview, ResearchSynthesis, SearchPlan

logger = logging.getLogger(__name__)


class ContentResearchState(TypedDict, total=False):
    request: dict[str, Any]
    run_id: str
    revision_count: int
    search_plan: dict[str, Any]
    instagram_research: dict[str, Any]
    twitter_research: dict[str, Any]
    linkedin_research: dict[str, Any]
    synthesis: dict[str, Any]
    quality_review: dict[str, Any]
    artifact_path: str
    warnings: list[str]


def build_graph(settings: CommonSettings):
    llm = build_chat_model(settings)
    planner = llm.with_structured_output(SearchPlan)
    strategist = llm.with_structured_output(ResearchSynthesis)
    reviewer = llm.with_structured_output(QualityReview)
    apify = ApifyClient(settings)
    sheets = GoogleSheetsRepository(settings)

    def prepare_input(state: ContentResearchState) -> ContentResearchState:
        request = ContentResearchInput.model_validate(state["request"])
        run_id = state.get("run_id") or slugify(f"{request.niche}-{utc_now_iso()}")
        return {
            "request": request.model_dump(mode="json", by_alias=True),
            "run_id": run_id,
            "revision_count": state.get("revision_count", 0),
            "warnings": state.get("warnings", []),
        }

    def build_search_plan(state: ContentResearchState) -> ContentResearchState:
        request = ContentResearchInput.model_validate(state["request"])
        if request.search_terms:
            normalized = dedupe_preserve_order(request.search_terms)
            search_plan = SearchPlan(
                hashtags=[term.replace(" ", "") for term in normalized[:5]],
                search_queries=normalized[:5],
                rationale=["Provided directly in the workflow input."],
            )
        else:
            search_plan = planner.invoke(
                SEARCH_PLANNER_PROMPT.format(
                    creator_niche=request.creator_niche,
                    niche=request.niche,
                    location=request.location,
                    language_of_text=request.language_of_text,
                )
            )
            if request.is_specific_niche and request.niche not in search_plan.search_queries:
                search_plan.search_queries.insert(0, request.niche)
            search_plan.hashtags = dedupe_preserve_order(
                [tag.replace("#", "").replace(" ", "") for tag in search_plan.hashtags]
            )[:5]
            search_plan.search_queries = dedupe_preserve_order(search_plan.search_queries)[:5]

        return {"search_plan": search_plan.model_dump(mode="json")}

    def collect_instagram_research(state: ContentResearchState) -> ContentResearchState:
        request = ContentResearchInput.model_validate(state["request"])
        search_plan = SearchPlan.model_validate(state["search_plan"])

        raw_reels = apify.scrape_instagram_hashtags(
            search_plan.hashtags,
            limit=request.no_of_reels_to_scrape,
            result_type=request.result_type,
        )
        ranked = rank_instagram_reels(raw_reels)
        filtered = [
            reel
            for reel in ranked
            if reel.get("likesCount", 0) >= request.min_likes_reel_filter
            and reel.get("age_hours", 0) <= request.reels_till_filter * 24
        ]
        recent = select_recent_best_reels(filtered, limit=5)

        transcripts: list[dict[str, Any]] = []
        for reel in recent[:3]:
            if not reel.get("url"):
                continue
            try:
                transcript_items = apify.extract_instagram_transcript(reel["url"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Transcript extraction failed for %s: %s", reel.get("url"), exc)
                continue
            transcript = transcript_items[0] if transcript_items else {}
            transcripts.append(
                {
                    "url": reel.get("url"),
                    "caption": reel.get("caption"),
                    "transcript": transcript.get("transcript") or transcript.get("summary"),
                }
            )

        return {
            "instagram_research": {
                "search_terms": search_plan.hashtags,
                "top_reels": filtered[:10],
                "recent_best_reels": recent,
                "recent_transcripts": transcripts,
                "analysis": analyze_instagram_reels(filtered),
            }
        }

    def collect_twitter_research(state: ContentResearchState) -> ContentResearchState:
        request = ContentResearchInput.model_validate(state["request"])
        search_plan = SearchPlan.model_validate(state["search_plan"])
        tweets: list[dict[str, Any]] = []
        for query in search_plan.search_queries[:3]:
            tweets.extend(apify.scrape_twitter(query, max_posts=max(10, request.no_of_reels_to_scrape // 2)))
        return {
            "twitter_research": {
                "queries": search_plan.search_queries[:3],
                "summary": summarize_tweets(tweets),
                "tweets": tweets[:25],
            }
        }

    def collect_linkedin_research(state: ContentResearchState) -> ContentResearchState:
        search_plan = SearchPlan.model_validate(state["search_plan"])
        posts: list[dict[str, Any]] = []
        for query in search_plan.search_queries[:3]:
            posts.extend(apify.scrape_linkedin(query, limit=5))
        return {
            "linkedin_research": {
                "queries": search_plan.search_queries[:3],
                "summary": summarize_linkedin_posts(posts),
                "posts": posts[:15],
            }
        }

    def synthesize_research(state: ContentResearchState) -> ContentResearchState:
        request = ContentResearchInput.model_validate(state["request"])
        research_payload = {
            "request": request.model_dump(mode="json", by_alias=True),
            "search_plan": state["search_plan"],
            "instagram_research": state["instagram_research"],
            "twitter_research": state["twitter_research"],
            "linkedin_research": state["linkedin_research"],
            "competitors": parse_competitors(request.competitor_list_usernames),
            "revision_feedback": state.get("quality_review", {}).get("feedback"),
        }
        synthesis = strategist.invoke(
            SYNTHESIS_PROMPT.format(research_payload=json.dumps(research_payload, indent=2))
        )
        return {"synthesis": synthesis.model_dump(mode="json")}

    def review_synthesis(state: ContentResearchState) -> ContentResearchState:
        review = reviewer.invoke(
            QUALITY_REVIEW_PROMPT.format(
                brief=json.dumps(state["synthesis"], indent=2),
            )
        )
        return {"quality_review": review.model_dump(mode="json")}

    def route_review(state: ContentResearchState) -> str:
        review = QualityReview.model_validate(state["quality_review"])
        if review.approved or state.get("revision_count", 0) >= 1:
            return "persist_artifact"
        return "synthesize_research"

    def increment_revision(state: ContentResearchState) -> ContentResearchState:
        return {"revision_count": state.get("revision_count", 0) + 1}

    def persist_artifact(state: ContentResearchState) -> ContentResearchState:
        request = ContentResearchInput.model_validate(state["request"])
        payload = {
            "run_id": state["run_id"],
            "generated_at": utc_now_iso(),
            "request": request.model_dump(mode="json", by_alias=True),
            "search_plan": state["search_plan"],
            "instagram_research": state["instagram_research"],
            "twitter_research": state["twitter_research"],
            "linkedin_research": state["linkedin_research"],
            "synthesis": state["synthesis"],
        }
        artifact_path = write_json_artifact(
            settings.artifact_root / "content_research",
            state["run_id"],
            payload,
        )

        warnings = list(state.get("warnings", []))
        if request.persist_to_sheet and settings.google_sheet_id:
            try:
                sheets.append_record(
                    settings.google_sheet_id,
                    "gid=0",
                    {
                        "Date": utc_now_iso(),
                        "niche ": request.creator_niche,
                        "Script Title": ", ".join(as_list(state["synthesis"].get("recommended_topics"))[:2]),
                        "Status": "done",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Google Sheets persistence failed: {exc}")

        return {"artifact_path": str(artifact_path), "warnings": warnings}

    builder = StateGraph(ContentResearchState)
    builder.add_node("prepare_input", prepare_input)
    builder.add_node("build_search_plan", build_search_plan)
    builder.add_node("collect_instagram_research", collect_instagram_research)
    builder.add_node("collect_twitter_research", collect_twitter_research)
    builder.add_node("collect_linkedin_research", collect_linkedin_research)
    builder.add_node("synthesize_research", synthesize_research)
    builder.add_node("review_synthesis", review_synthesis)
    builder.add_node("increment_revision", increment_revision)
    builder.add_node("persist_artifact", persist_artifact)

    builder.add_edge(START, "prepare_input")
    builder.add_edge("prepare_input", "build_search_plan")
    builder.add_edge("build_search_plan", "collect_instagram_research")
    builder.add_edge("collect_instagram_research", "collect_twitter_research")
    builder.add_edge("collect_twitter_research", "collect_linkedin_research")
    builder.add_edge("collect_linkedin_research", "synthesize_research")
    builder.add_edge("synthesize_research", "review_synthesis")
    builder.add_conditional_edges(
        "review_synthesis",
        route_review,
        {
            "persist_artifact": "persist_artifact",
            "synthesize_research": "increment_revision",
        },
    )
    builder.add_edge("increment_revision", "synthesize_research")
    builder.add_edge("persist_artifact", END)

    return builder.compile(checkpointer=MemorySaver())
