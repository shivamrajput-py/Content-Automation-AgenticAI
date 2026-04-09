from __future__ import annotations

import base64
import json
import logging
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ..common.clients import (
    ApifyClient,
    GoogleSheetsRepository,
    LinkedInPublisher,
    OpenRouterImageClient,
    TemporaryUploadClient,
    TwitterPublisher,
)
from ..common.llm import build_chat_model
from ..common.settings import CommonSettings, MissingConfigurationError
from ..common.utils import dedupe_preserve_order, summarize_linkedin_posts, summarize_tweets, utc_now_iso, write_json_artifact
from .prompts import IMAGE_PROMPT, REVIEW_PROMPT, SEARCH_PROMPT, STRATEGY_PROMPT, WRITER_PROMPT
from .schemas import ContentStrategy, ImagePromptPackage, QualityReview, SocialAutopostInput, SocialPostPackage, SocialSearchPlan

logger = logging.getLogger(__name__)


class SocialAutopostState(TypedDict, total=False):
    request: dict[str, Any]
    run_id: str
    revision_count: int
    search_plan: dict[str, Any]
    research: dict[str, Any]
    history: list[dict[str, Any]]
    strategy: dict[str, Any]
    posts: dict[str, Any]
    quality_review: dict[str, Any]
    image_prompt: dict[str, Any]
    image_b64: str
    image_preview_url: str
    publish_result: dict[str, Any]
    artifact_path: str
    warnings: list[str]


def build_graph(settings: CommonSettings):
    llm = build_chat_model(settings)
    planner = llm.with_structured_output(SocialSearchPlan)
    strategist = llm.with_structured_output(ContentStrategy)
    writer = llm.with_structured_output(SocialPostPackage)
    reviewer = llm.with_structured_output(QualityReview)
    image_prompt_builder = llm.with_structured_output(ImagePromptPackage)

    apify = ApifyClient(settings)
    sheets = GoogleSheetsRepository(settings)
    image_client = OpenRouterImageClient(settings)
    uploader = TemporaryUploadClient(settings)

    def prepare_input(state: SocialAutopostState) -> SocialAutopostState:
        request = SocialAutopostInput.model_validate(state["request"])
        return {
            "request": request.model_dump(mode="json"),
            "run_id": state.get("run_id") or f"social-{request.niche.lower().replace(' ', '-')}",
            "revision_count": state.get("revision_count", 0),
            "warnings": state.get("warnings", []),
        }

    def build_search_plan(state: SocialAutopostState) -> SocialAutopostState:
        request = SocialAutopostInput.model_validate(state["request"])
        if request.searches:
            plan = SocialSearchPlan(searches=dedupe_preserve_order(request.searches), rationale=["Provided in workflow input."])
        else:
            plan = planner.invoke(
                SEARCH_PROMPT.format(
                    creator_niche=request.creator_niche,
                    niche=request.niche,
                    location=request.location,
                )
            )
            plan.searches = dedupe_preserve_order(plan.searches)[:5]
        return {"search_plan": plan.model_dump(mode="json")}

    def collect_research(state: SocialAutopostState) -> SocialAutopostState:
        search_plan = SocialSearchPlan.model_validate(state["search_plan"])
        tweets: list[dict[str, Any]] = []
        linkedin_posts: list[dict[str, Any]] = []

        for query in search_plan.searches[:3]:
            tweets.extend(apify.scrape_twitter(query, max_posts=10))
            linkedin_posts.extend(apify.scrape_linkedin(query, limit=5))

        research = {
            "twitter": {
                "queries": search_plan.searches[:3],
                "summary": summarize_tweets(tweets),
                "examples": tweets[:20],
            },
            "linkedin": {
                "queries": search_plan.searches[:3],
                "summary": summarize_linkedin_posts(linkedin_posts),
                "examples": linkedin_posts[:12],
            },
        }
        return {"research": research}

    def load_history(state: SocialAutopostState) -> SocialAutopostState:
        request = SocialAutopostInput.model_validate(state["request"])
        history: list[dict[str, Any]] = []
        warnings = list(state.get("warnings", []))
        if settings.google_sheet_id and request.persist_to_sheet:
            try:
                history = sheets.read_records(settings.google_sheet_id, request.history_sheet_ref)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"History sheet read failed: {exc}")
        return {"history": history[-20:], "warnings": warnings}

    def draft_strategy(state: SocialAutopostState) -> SocialAutopostState:
        strategy = strategist.invoke(
            STRATEGY_PROMPT.format(
                research=json.dumps(state["research"], indent=2),
                history=json.dumps(state.get("history", []), indent=2),
                review_feedback=state.get("quality_review", {}).get("feedback", "None"),
            )
        )
        return {"strategy": strategy.model_dump(mode="json")}

    def write_posts(state: SocialAutopostState) -> SocialAutopostState:
        posts = writer.invoke(
            WRITER_PROMPT.format(
                strategy=json.dumps(state["strategy"], indent=2),
                review_feedback=state.get("quality_review", {}).get("feedback", "None"),
            )
        )
        return {"posts": posts.model_dump(mode="json")}

    def review_posts(state: SocialAutopostState) -> SocialAutopostState:
        review = reviewer.invoke(REVIEW_PROMPT.format(draft=json.dumps(state["posts"], indent=2)))
        return {"quality_review": review.model_dump(mode="json")}

    def route_review(state: SocialAutopostState) -> str:
        review = QualityReview.model_validate(state["quality_review"])
        if review.approved or state.get("revision_count", 0) >= 1:
            return "generate_image_prompt"
        return "increment_revision"

    def increment_revision(state: SocialAutopostState) -> SocialAutopostState:
        return {"revision_count": state.get("revision_count", 0) + 1}

    def generate_image_prompt(state: SocialAutopostState) -> SocialAutopostState:
        image_prompt = image_prompt_builder.invoke(
            IMAGE_PROMPT.format(
                linkedin_post=state["posts"]["linkedin_post"]["post_text"],
                strategy=json.dumps(state["strategy"], indent=2),
            )
        )
        return {"image_prompt": image_prompt.model_dump(mode="json")}

    def generate_image_asset(state: SocialAutopostState) -> SocialAutopostState:
        image_bytes = image_client.generate_image_bytes(state["image_prompt"]["image_prompt"])
        preview_url = uploader.upload_bytes("linkedin_post.png", image_bytes)
        return {
            "image_b64": base64.b64encode(image_bytes).decode("utf-8"),
            "image_preview_url": preview_url,
        }

    def publish_posts(state: SocialAutopostState) -> SocialAutopostState:
        request = SocialAutopostInput.model_validate(state["request"])
        result: dict[str, Any] = {"dry_run": request.dry_run, "twitter": None, "linkedin": None}
        warnings = list(state.get("warnings", []))

        if request.dry_run:
            return {"publish_result": result}

        if request.publish_to_twitter:
            try:
                twitter = TwitterPublisher(settings)
                result["twitter"] = twitter.publish(state["posts"]["twitter_post"]["post_text"])
            except (MissingConfigurationError, Exception) as exc:  # noqa: BLE001
                warnings.append(f"Twitter publish failed: {exc}")

        if request.publish_to_linkedin:
            try:
                linkedin = LinkedInPublisher(settings)
                result["linkedin"] = linkedin.publish_with_image(
                    text=state["posts"]["linkedin_post"]["post_text"],
                    image_bytes=base64.b64decode(state["image_b64"]),
                    alt_text=state["image_prompt"]["alt_text"],
                )
            except (MissingConfigurationError, Exception) as exc:  # noqa: BLE001
                warnings.append(f"LinkedIn publish failed: {exc}")

        return {"publish_result": result, "warnings": warnings}

    def persist_artifact(state: SocialAutopostState) -> SocialAutopostState:
        request = SocialAutopostInput.model_validate(state["request"])
        payload = {
            "generated_at": utc_now_iso(),
            "request": request.model_dump(mode="json"),
            "search_plan": state["search_plan"],
            "research": state["research"],
            "strategy": state["strategy"],
            "posts": state["posts"],
            "image_prompt": state["image_prompt"],
            "image_preview_url": state["image_preview_url"],
            "publish_result": state.get("publish_result"),
            "warnings": state.get("warnings", []),
        }
        artifact_path = write_json_artifact(
            settings.artifact_root / "social_autopost",
            state["run_id"],
            payload,
        )

        warnings = list(state.get("warnings", []))
        if request.persist_to_sheet and settings.google_sheet_id:
            try:
                sheets.append_record(
                    settings.google_sheet_id,
                    request.history_sheet_ref,
                    {
                        "Date": utc_now_iso(),
                        "niche ": request.creator_niche,
                        "Script Title": state["posts"]["topic_title"],
                        "Status": "done",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Sheet persistence failed: {exc}")

        return {"artifact_path": str(artifact_path), "warnings": warnings}

    builder = StateGraph(SocialAutopostState)
    builder.add_node("prepare_input", prepare_input)
    builder.add_node("build_search_plan", build_search_plan)
    builder.add_node("collect_research", collect_research)
    builder.add_node("load_history", load_history)
    builder.add_node("draft_strategy", draft_strategy)
    builder.add_node("write_posts", write_posts)
    builder.add_node("review_posts", review_posts)
    builder.add_node("increment_revision", increment_revision)
    builder.add_node("generate_image_prompt", generate_image_prompt)
    builder.add_node("generate_image_asset", generate_image_asset)
    builder.add_node("publish_posts", publish_posts)
    builder.add_node("persist_artifact", persist_artifact)

    builder.add_edge(START, "prepare_input")
    builder.add_edge("prepare_input", "build_search_plan")
    builder.add_edge("build_search_plan", "collect_research")
    builder.add_edge("collect_research", "load_history")
    builder.add_edge("load_history", "draft_strategy")
    builder.add_edge("draft_strategy", "write_posts")
    builder.add_edge("write_posts", "review_posts")
    builder.add_conditional_edges(
        "review_posts",
        route_review,
        {
            "generate_image_prompt": "generate_image_prompt",
            "increment_revision": "increment_revision",
        },
    )
    builder.add_edge("increment_revision", "write_posts")
    builder.add_edge("generate_image_prompt", "generate_image_asset")
    builder.add_edge("generate_image_asset", "publish_posts")
    builder.add_edge("publish_posts", "persist_artifact")
    builder.add_edge("persist_artifact", END)

    return builder.compile(checkpointer=MemorySaver())
