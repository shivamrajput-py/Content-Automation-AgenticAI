from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ..common.clients import (
    ApifyClient,
    ElevenLabsClient,
    GoogleSheetsRepository,
    HeyGenClient,
    InstagramGraphClient,
    QuickReelClient,
    TemporaryUploadClient,
)
from ..common.llm import build_chat_model
from ..common.settings import CommonSettings, MissingConfigurationError
from ..common.utils import (
    analyze_instagram_reels,
    dedupe_preserve_order,
    poll_until,
    rank_instagram_reels,
    select_recent_best_reels,
    summarize_tweets,
    utc_now_iso,
    write_json_artifact,
)
from .prompts import REVIEW_PROMPT, SEARCH_PROMPT, STRATEGY_PROMPT, WRITER_PROMPT
from .schemas import InstagramAutomationInput, InstagramScriptPackage, InstagramStrategy, QualityReview, SearchPlan

logger = logging.getLogger(__name__)


class InstagramAutomationState(TypedDict, total=False):
    request: dict[str, Any]
    run_id: str
    revision_count: int
    search_plan: dict[str, Any]
    market_research: dict[str, Any]
    creator_context: dict[str, Any]
    history: list[dict[str, Any]]
    strategy: dict[str, Any]
    script_package: dict[str, Any]
    quality_review: dict[str, Any]
    audio_url: str
    base_video_url: str
    processed_video_url: str
    final_video_url: str
    publish_result: dict[str, Any]
    artifact_path: str
    warnings: list[str]


def build_graph(settings: CommonSettings):
    llm = build_chat_model(settings)
    planner = llm.with_structured_output(SearchPlan)
    strategist = llm.with_structured_output(InstagramStrategy)
    writer = llm.with_structured_output(InstagramScriptPackage)
    reviewer = llm.with_structured_output(QualityReview)

    apify = ApifyClient(settings)
    uploader = TemporaryUploadClient(settings)
    tts = ElevenLabsClient(settings)
    heygen = HeyGenClient(settings)
    quickreel = QuickReelClient(settings)
    sheets = GoogleSheetsRepository(settings)

    def prepare_input(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        return {
            "request": request.model_dump(mode="json", by_alias=True),
            "run_id": state.get("run_id") or f"instagram-{request.niche.lower().replace(' ', '-')}",
            "revision_count": state.get("revision_count", 0),
            "warnings": state.get("warnings", []),
        }

    def build_search_plan(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        plan = planner.invoke(
            SEARCH_PROMPT.format(
                creator_niche=request.creator_niche,
                niche=request.niche,
                location=request.location,
            )
        )
        if request.is_specific_niche and request.niche.replace(" ", "") not in plan.hashtags:
            plan.hashtags.insert(0, request.niche.replace(" ", ""))
        plan.hashtags = dedupe_preserve_order([tag.replace("#", "").replace(" ", "") for tag in plan.hashtags])[:5]
        return {"search_plan": plan.model_dump(mode="json")}

    def collect_market_research(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        search_plan = SearchPlan.model_validate(state["search_plan"])

        reels = apify.scrape_instagram_hashtags(
            search_plan.hashtags,
            limit=request.reels_per_hashtag,
            result_type=request.insta_scrape_type,
        )
        ranked_reels = rank_instagram_reels(reels)
        recent_reels = select_recent_best_reels(ranked_reels, limit=5)
        transcripts: list[dict[str, Any]] = []
        for reel in recent_reels[:3]:
            if not reel.get("url"):
                continue
            transcript_items = apify.extract_instagram_transcript(reel["url"])
            transcript = transcript_items[0] if transcript_items else {}
            transcripts.append(
                {
                    "url": reel.get("url"),
                    "caption": reel.get("caption"),
                    "transcript": transcript.get("transcript") or transcript.get("summary"),
                }
            )

        tweets: list[dict[str, Any]] = []
        for hashtag in search_plan.hashtags[:3]:
            tweets.extend(apify.scrape_twitter(hashtag, max_posts=10))

        return {
            "market_research": {
                "hashtags": search_plan.hashtags,
                "instagram": {
                    "top_reels": ranked_reels[:10],
                    "recent_reels": recent_reels,
                    "recent_transcripts": transcripts,
                    "analysis": analyze_instagram_reels(ranked_reels),
                },
                "twitter": summarize_tweets(tweets),
            }
        }

    def collect_creator_context(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        context: dict[str, Any] = {"profile_url": request.instagram_profile_url}
        if not request.instagram_profile_url:
            return {"creator_context": context}

        creator_reels = apify.scrape_instagram_profile(
            request.instagram_profile_url,
            limit=10,
            result_type=request.insta_scrape_type,
        )
        ranked_creator_reels = rank_instagram_reels(creator_reels)
        best = ranked_creator_reels[:1]
        if best and best[0].get("url"):
            transcript_items = apify.extract_instagram_transcript(best[0]["url"])
            transcript = transcript_items[0] if transcript_items else {}
            context.update(
                {
                    "best_reel": best[0],
                    "best_reel_transcript": transcript.get("transcript") or transcript.get("summary"),
                }
            )
        return {"creator_context": context}

    def load_history(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        history: list[dict[str, Any]] = []
        warnings = list(state.get("warnings", []))
        if settings.google_sheet_id and request.persist_to_sheet:
            try:
                history = sheets.read_records(settings.google_sheet_id, request.history_sheet_ref)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"History sheet read failed: {exc}")
        return {"history": history[-20:], "warnings": warnings}

    def draft_strategy(state: InstagramAutomationState) -> InstagramAutomationState:
        strategy = strategist.invoke(
            STRATEGY_PROMPT.format(
                market_research=json.dumps(state["market_research"], indent=2),
                creator_context=json.dumps(state["creator_context"], indent=2),
                history=json.dumps(state.get("history", []), indent=2),
                review_feedback=state.get("quality_review", {}).get("feedback", "None"),
            )
        )
        return {"strategy": strategy.model_dump(mode="json")}

    def write_script(state: InstagramAutomationState) -> InstagramAutomationState:
        script = writer.invoke(
            WRITER_PROMPT.format(
                strategy=json.dumps(state["strategy"], indent=2),
                review_feedback=state.get("quality_review", {}).get("feedback", "None"),
            )
        )
        return {"script_package": script.model_dump(mode="json")}

    def review_script(state: InstagramAutomationState) -> InstagramAutomationState:
        review = reviewer.invoke(REVIEW_PROMPT.format(draft=json.dumps(state["script_package"], indent=2)))
        return {"quality_review": review.model_dump(mode="json")}

    def route_review(state: InstagramAutomationState) -> str:
        review = QualityReview.model_validate(state["quality_review"])
        if review.approved or state.get("revision_count", 0) >= 1:
            return "generate_audio"
        return "increment_revision"

    def increment_revision(state: InstagramAutomationState) -> InstagramAutomationState:
        return {"revision_count": state.get("revision_count", 0) + 1}

    def generate_audio(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        script = InstagramScriptPackage.model_validate(state["script_package"])
        audio_bytes = tts.synthesize(script.full_text, request.voice_id)
        audio_url = uploader.upload_bytes(f"{state['run_id']}.mp3", audio_bytes)
        return {"audio_url": audio_url}

    def generate_avatar_video(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        video_id = heygen.generate_avatar_video(state["audio_url"], request.avatar_id)
        status = poll_until(
            lambda: heygen.get_video_status(video_id),
            is_complete=lambda payload: payload.get("data", {}).get("status") == "completed",
            interval_seconds=settings.poll_interval_seconds,
            attempts=settings.max_poll_attempts,
        )
        video_url = status.get("data", {}).get("video_url") or status.get("data", {}).get("data")
        if not video_url:
            raise RuntimeError(f"HeyGen video generation did not complete successfully: {status}")
        return {"base_video_url": video_url}

    def route_video_processing(state: InstagramAutomationState) -> str:
        request = InstagramAutomationInput.model_validate(state["request"])
        return "process_with_ai_edit" if request.enable_ai_edit else "process_with_subtitles"

    def process_with_ai_edit(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        project_id = quickreel.edit_with_ai(video_url=state["base_video_url"], language=request.language_of_script)
        status = poll_until(
            lambda: quickreel.get_project(project_id),
            is_complete=lambda payload: payload.get("data", {}).get("status") == "completed",
            interval_seconds=settings.poll_interval_seconds,
            attempts=settings.max_poll_attempts,
        )
        final_url = status.get("data", {}).get("outputs", [{}])[0].get("videoUrl")
        if not final_url:
            raise RuntimeError(f"QuickReel AI edit did not return a video URL: {status}")
        return {"processed_video_url": final_url}

    def process_with_subtitles(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        project_id = quickreel.create_subtitles(
            video_url=state["base_video_url"],
            language=request.language_of_script,
            template=request.subtitle_template,
            font_size=request.subtitle_font_size,
            add_bgm=request.enable_bgm,
            remove_filler_words=request.remove_filler_words,
            remove_silence_parts=request.remove_silence_parts,
        )
        status = poll_until(
            lambda: quickreel.get_project(project_id),
            is_complete=lambda payload: payload.get("data", {}).get("status") == "completed",
            interval_seconds=settings.poll_interval_seconds,
            attempts=settings.max_poll_attempts,
        )
        subtitled_url = status.get("data", {}).get("outputs", [{}])[0].get("videoUrl")
        if not subtitled_url:
            raise RuntimeError(f"QuickReel subtitles did not return a video URL: {status}")
        return {"processed_video_url": subtitled_url}

    def route_broll(state: InstagramAutomationState) -> str:
        request = InstagramAutomationInput.model_validate(state["request"])
        if request.enable_ai_edit or not request.enable_broll:
            return "rehost_final_video"
        return "add_broll"

    def add_broll(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        project_id = quickreel.create_broll(
            video_url=state["processed_video_url"],
            language=request.language_of_script,
        )
        status = poll_until(
            lambda: quickreel.get_project(project_id),
            is_complete=lambda payload: payload.get("data", {}).get("status") == "completed",
            interval_seconds=settings.poll_interval_seconds,
            attempts=settings.max_poll_attempts,
        )
        final_url = status.get("data", {}).get("outputs", [{}])[0].get("videoUrl")
        if not final_url:
            raise RuntimeError(f"QuickReel B-roll did not return a video URL: {status}")
        return {"processed_video_url": final_url}

    def rehost_final_video(state: InstagramAutomationState) -> InstagramAutomationState:
        warnings = list(state.get("warnings", []))
        final_url = state["processed_video_url"]
        try:
            final_url = uploader.upload_from_url(final_url, f"{state['run_id']}.mp4")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Video re-host failed, using original URL instead: {exc}")
        return {"final_video_url": final_url, "warnings": warnings}

    def publish_instagram(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        result: dict[str, Any] = {"dry_run": request.dry_run, "instagram": None}
        warnings = list(state.get("warnings", []))
        if request.dry_run or not request.publish_to_instagram:
            return {"publish_result": result}

        account_id = request.instagram_account_id or settings.instagram_business_account_id
        if not account_id:
            warnings.append("Instagram publish skipped because no business account id is configured.")
            return {"publish_result": result, "warnings": warnings}

        try:
            instagram = InstagramGraphClient(settings)
            script = InstagramScriptPackage.model_validate(state["script_package"])
            caption = f"{script.caption_text}\n\n{' '.join(script.primary_hashtags)}"
            container_id = instagram.create_reel_container(account_id, video_url=state["final_video_url"], caption=caption)
            result["instagram"] = instagram.publish_media(account_id, container_id)
        except (MissingConfigurationError, Exception) as exc:  # noqa: BLE001
            warnings.append(f"Instagram publish failed: {exc}")
        return {"publish_result": result, "warnings": warnings}

    def persist_artifact(state: InstagramAutomationState) -> InstagramAutomationState:
        request = InstagramAutomationInput.model_validate(state["request"])
        payload = {
            "generated_at": utc_now_iso(),
            "request": request.model_dump(mode="json", by_alias=True),
            "search_plan": state["search_plan"],
            "market_research": state["market_research"],
            "creator_context": state["creator_context"],
            "strategy": state["strategy"],
            "script_package": state["script_package"],
            "audio_url": state["audio_url"],
            "base_video_url": state["base_video_url"],
            "final_video_url": state["final_video_url"],
            "publish_result": state.get("publish_result"),
            "warnings": state.get("warnings", []),
        }
        artifact_path = write_json_artifact(
            settings.artifact_root / "instagram_reels",
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
                        "Script Title": state["script_package"]["script_title"],
                        "Status": "done",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Sheet persistence failed: {exc}")

        return {"artifact_path": str(artifact_path), "warnings": warnings}

    builder = StateGraph(InstagramAutomationState)
    builder.add_node("prepare_input", prepare_input)
    builder.add_node("build_search_plan", build_search_plan)
    builder.add_node("collect_market_research", collect_market_research)
    builder.add_node("collect_creator_context", collect_creator_context)
    builder.add_node("load_history", load_history)
    builder.add_node("draft_strategy", draft_strategy)
    builder.add_node("write_script", write_script)
    builder.add_node("review_script", review_script)
    builder.add_node("increment_revision", increment_revision)
    builder.add_node("generate_audio", generate_audio)
    builder.add_node("generate_avatar_video", generate_avatar_video)
    builder.add_node("process_with_ai_edit", process_with_ai_edit)
    builder.add_node("process_with_subtitles", process_with_subtitles)
    builder.add_node("add_broll", add_broll)
    builder.add_node("rehost_final_video", rehost_final_video)
    builder.add_node("publish_instagram", publish_instagram)
    builder.add_node("persist_artifact", persist_artifact)

    builder.add_edge(START, "prepare_input")
    builder.add_edge("prepare_input", "build_search_plan")
    builder.add_edge("build_search_plan", "collect_market_research")
    builder.add_edge("collect_market_research", "collect_creator_context")
    builder.add_edge("collect_creator_context", "load_history")
    builder.add_edge("load_history", "draft_strategy")
    builder.add_edge("draft_strategy", "write_script")
    builder.add_edge("write_script", "review_script")
    builder.add_conditional_edges(
        "review_script",
        route_review,
        {
            "generate_audio": "generate_audio",
            "increment_revision": "increment_revision",
        },
    )
    builder.add_edge("increment_revision", "write_script")
    builder.add_edge("generate_audio", "generate_avatar_video")
    builder.add_conditional_edges(
        "generate_avatar_video",
        route_video_processing,
        {
            "process_with_ai_edit": "process_with_ai_edit",
            "process_with_subtitles": "process_with_subtitles",
        },
    )
    builder.add_conditional_edges(
        "process_with_ai_edit",
        route_broll,
        {
            "rehost_final_video": "rehost_final_video",
            "add_broll": "add_broll",
        },
    )
    builder.add_conditional_edges(
        "process_with_subtitles",
        route_broll,
        {
            "rehost_final_video": "rehost_final_video",
            "add_broll": "add_broll",
        },
    )
    builder.add_edge("add_broll", "rehost_final_video")
    builder.add_edge("rehost_final_video", "publish_instagram")
    builder.add_edge("publish_instagram", "persist_artifact")
    builder.add_edge("persist_artifact", END)

    return builder.compile(checkpointer=MemorySaver())
