import html
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Content Automation OS",
    page_icon="??",
    layout="wide",
    initial_sidebar_state="expanded",
)

CONFIG_PATH = Path("dashboard_config.json")
SHEET_MAPPING = {
    "Summary": "ResearchSummary",
    "Reels": "TopPerformingReels",
    "Scripts": "Top3ReelsIdeas",
    "Tweets_Top": "XTopTweets",
    "Tweets_Latest": "XLatestTweets",
    "Competitors": "CompetitorData",
}


def apply_styling() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');

        :root {
            --bg-dark: #08131a;
            --bg-card: rgba(12, 24, 32, 0.84);
            --border-glass: 1px solid rgba(148, 163, 184, 0.18);
            --accent-core: #ff6b2c;
            --accent-soft: #14b8a6;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(20, 184, 166, 0.12), transparent 28%),
                radial-gradient(circle at top right, rgba(255, 107, 44, 0.14), transparent 26%),
                linear-gradient(180deg, #08131a 0%, #0d1821 100%);
            font-family: 'Manrope', sans-serif;
        }

        .glass-panel {
            background: var(--bg-card);
            border: var(--border-glass);
            border-radius: 14px;
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
            backdrop-filter: blur(18px);
            box-shadow: 0 18px 50px rgba(0, 0, 0, 0.18);
        }

        .section-title {
            margin: 0 0 0.4rem 0;
            color: var(--text-primary);
            font-weight: 700;
        }

        .section-copy {
            margin: 0;
            color: var(--text-secondary);
            line-height: 1.55;
        }

        .stButton > button, .stLinkButton a {
            border-radius: 999px !important;
            border: 1px solid rgba(255, 107, 44, 0.35) !important;
            background: linear-gradient(135deg, rgba(255, 107, 44, 0.18), rgba(20, 184, 166, 0.18)) !important;
            color: #f8fafc !important;
        }

        .metric-card {
            padding: 0.85rem 1rem;
            border-radius: 12px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(148, 163, 184, 0.12);
        }

        .mono {
            font-family: 'Space Mono', monospace;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_dashboard_config() -> dict:
    config = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            config = {}

    users = config.get("users", {})
    users_env = os.getenv("DASHBOARD_USERS_JSON", "").strip()
    if users_env:
        try:
            users = json.loads(users_env)
        except json.JSONDecodeError:
            users = {}

    auth_env = os.getenv("DASHBOARD_AUTH_ENABLED", "").strip().lower()
    if auth_env:
        auth_enabled = auth_env in {"1", "true", "yes", "on"}
    else:
        auth_enabled = bool(users)

    return {
        "users": users,
        "auth_enabled": auth_enabled,
        "agent_api_url": os.getenv("AGENT_API_URL", "").strip() or config.get("agent_api_url", ""),
        "google_sheet_id": os.getenv("RESEARCH_SHEET_ID", "").strip() or config.get("google_sheet_id", ""),
    }


APP_CONFIG = load_dashboard_config()


def escape_text(value: object) -> str:
    return html.escape(str(value or ""))


def format_k(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if number >= 1_000:
        return f"{number / 1_000:.1f}K"
    return str(int(number))


def get_sheet_csv_url(sheet_name: str) -> str | None:
    sheet_id = APP_CONFIG.get("google_sheet_id", "")
    if not sheet_id:
        return None
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"


@st.cache_data(ttl=0)
def fetch_summary_timestamp() -> str | None:
    url = get_sheet_csv_url("ResearchSummary")
    if not url:
        return None
    try:
        df = pd.read_csv(url)
        if not df.empty and "generatedAt" in df.columns:
            return str(df["generatedAt"].iloc[0])
    except Exception:
        return None
    return None


@st.cache_data(ttl=60)
def fetch_data(key: str) -> pd.DataFrame | None:
    sheet_name = SHEET_MAPPING.get(key, key)
    url = get_sheet_csv_url(sheet_name)
    if not url:
        return None
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        numeric_cols = [
            "velocity_score",
            "videoPlayCount",
            "likesCount",
            "commentsCount",
            "reshareCount",
            "views",
            "Score",
            "Likes",
            "Retweets",
            "Replies",
            "age_hours",
            "videoViewCount",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df
    except Exception:
        return None


def authenticate_user(username: str, password: str) -> bool:
    users = APP_CONFIG.get("users", {})
    return bool(username in users and users[username] == password)


def trigger_workflow(params: dict) -> tuple[bool, str]:
    url = APP_CONFIG.get("agent_api_url", "")
    if not url:
        return False, "AGENT_API_URL is not configured."

    payload = {**params, "timestamp": pd.Timestamp.utcnow().isoformat()}
    try:
        requests.post(url, json=payload, timeout=5, headers={"Content-Type": "application/json"})
        return True, "Workflow initiated successfully."
    except requests.exceptions.Timeout:
        return True, "Workflow initiated successfully."
    except Exception as exc:
        return False, f"Trigger failed: {exc}"


def render_panel(title: str, body: str) -> None:
    st.markdown(
        f'<div class="glass-panel"><h4 class="section-title">{escape_text(title)}</h4><p class="section-copy">{escape_text(body)}</p></div>',
        unsafe_allow_html=True,
    )


def render_reel_grid(df: pd.DataFrame) -> None:
    cols = st.columns(4)
    for index, (_, row) in enumerate(df.iterrows()):
        with cols[index % 4]:
            caption = escape_text(row.get("caption") or row.get("title") or "No caption")
            thumb = escape_text(row.get("displayUrl") or row.get("thumbnail") or "")
            views = format_k(row.get("views") or row.get("videoPlayCount") or row.get("videoViewCount") or 0)
            velocity = float(row.get("velocity_score", 0) or 0)
            url = row.get("url") or row.get("permalink") or "#"
            st.markdown(
                f"""
                <div class="glass-panel" style="padding:0; overflow:hidden;">
                    <div style="aspect-ratio:9/16; background:#020617;">
                        <img src="{thumb}" style="width:100%;height:100%;object-fit:cover;" />
                    </div>
                    <div style="padding:1rem;">
                        <div class="mono" style="font-size:0.78rem;color:#5eead4;">Velocity {velocity:.1f}</div>
                        <div style="margin-top:0.35rem;color:#f8fafc;font-weight:600;">Views {views}</div>
                        <div style="margin-top:0.55rem;color:#cbd5e1;font-size:0.9rem;line-height:1.45;max-height:4.2rem;overflow:hidden;">{caption}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.link_button("Open", url, use_container_width=True)


def render_posts(df: pd.DataFrame, text_col: str, author_col: str, meta_cols: list[str]) -> None:
    for _, row in df.iterrows():
        meta = " | ".join(str(row.get(col, "")) for col in meta_cols if row.get(col, "") != "")
        st.markdown(
            f'<div class="glass-panel"><h4 class="section-title">{escape_text(row.get(author_col, "Unknown"))}</h4><p class="section-copy">{escape_text(row.get(text_col, ""))}</p><p class="section-copy" style="margin-top:0.6rem;font-size:0.82rem;">{escape_text(meta)}</p></div>',
            unsafe_allow_html=True,
        )


def render_scripts(df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        title = row.get("script_title") or row.get("title") or "Untitled"
        topic = row.get("topic_title") or row.get("topic") or "General"
        full_text = row.get("full_text") or row.get("script_full_text") or ""
        caption = row.get("caption_full") or row.get("caption") or ""
        st.markdown(
            f"""
            <div class="glass-panel">
                <div class="mono" style="color:#5eead4;font-size:0.78rem;">{escape_text(topic)}</div>
                <h3 class="section-title" style="margin-top:0.35rem;">{escape_text(title)}</h3>
                <p class="section-copy">{escape_text(full_text)}</p>
                <p class="section-copy" style="margin-top:0.85rem;"><strong>Caption:</strong> {escape_text(caption)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_dashboard() -> None:
    st.title("Research Command Center")
    summary_df = fetch_data("Summary")
    reels_df = fetch_data("Reels")

    if APP_CONFIG.get("google_sheet_id", "") == "":
        st.info("Set RESEARCH_SHEET_ID or dashboard_config.json to load dashboard data.")
        return

    if reels_df is not None and not reels_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Highest Velocity", f"{float(reels_df.get('velocity_score', pd.Series([0])).max()):.1f}")
        c2.metric("Reels Analyzed", len(reels_df))
        last_sync = "Unknown"
        if summary_df is not None and not summary_df.empty and "generatedAt" in summary_df.columns:
            last_sync = str(summary_df.iloc[0]["generatedAt"])[:16]
        c3.metric("Last Sync", last_sync)

    if summary_df is None or summary_df.empty:
        st.warning("No summary data is currently available.")
        return

    for column in ["instagram_summary_research", "posting_schedule"]:
        if column in summary_df.columns and str(summary_df.iloc[0].get(column, "")).strip():
            render_panel(column.replace("_", " ").title(), str(summary_df.iloc[0][column]))


def render_sidebar() -> str:
    with st.sidebar:
        st.title("Content Automation OS")
        view = st.radio("View", ["Dashboard", "Content Lab", "Insta Intelligence", "X Pulse", "Competitors"], label_visibility="collapsed")
        st.divider()
        with st.expander("Run Research", expanded=False):
            with st.form("research_config"):
                niche = st.text_input("Main Niche", value="Virat Kohli Cricket")
                creator_niche = st.text_input("Creator Positioning", value=niche)
                is_specific = st.toggle("Treat niche as highly specific", value=True)
                c1, c2 = st.columns(2)
                with c1:
                    language_of_script = st.text_input("Script Language", value="Hinglish")
                    writing_style = st.text_input("Writing Style", value="Let AI decide")
                with c2:
                    language_of_text = st.text_input("Text Language", value="English")
                    location = st.text_input("Location", value="India")
                count = st.slider("Reels to Scrape", min_value=10, max_value=500, value=30, step=5)
                reels_filter = st.number_input("Reels Till Filter (Days)", min_value=1, max_value=365, value=30)
                min_likes = st.number_input("Minimum Likes", min_value=0, value=0)
                competitors = st.text_area("Competitor Usernames", placeholder="espncricinfo icc bcci")
                if st.form_submit_button("Launch Research"):
                    with st.spinner("Sending request to the agent backend..."):
                        success, message = trigger_workflow(
                            {
                                "is_specific_niche": is_specific,
                                "creator_niche": creator_niche,
                                "niche": niche,
                                "language_of_script": language_of_script,
                                "language_of_text": language_of_text,
                                "writing_style": writing_style,
                                "location": location,
                                "noOfReelsToScrape": count,
                                "type": "Instagram",
                                "reelsTill_Filter": reels_filter,
                                "minLikesReel_Filter": min_likes,
                                "competitorListUsernames": competitors,
                            }
                        )
                        if success:
                            st.session_state.polling = True
                            st.rerun()
                        st.info(message) if success else st.error(message)
        if st.button("Refresh Data"):
            st.cache_data.clear()
            st.rerun()
    return view


def require_auth() -> bool:
    if not APP_CONFIG.get("auth_enabled", False):
        return True

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("## Research OS Login")
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Access"):
                if authenticate_user(username, password):
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    return False


def handle_polling() -> bool:
    if not st.session_state.get("polling"):
        return False

    if "poll_start" not in st.session_state:
        st.session_state.poll_start = time.time()
        st.session_state.initial_ts = fetch_summary_timestamp()

    elapsed = int(time.time() - st.session_state.poll_start)
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            f'<div class="glass-panel"><h3 class="section-title">Agents are processing the request</h3><p class="section-copy">Elapsed time: <span class="mono">{elapsed}s</span></p></div>',
            unsafe_allow_html=True,
        )
        current_ts = fetch_summary_timestamp()
        if current_ts and current_ts != st.session_state.initial_ts:
            st.session_state.polling = False
            st.success("New data is available.")
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()
        if elapsed > 300:
            st.session_state.polling = False
            st.error("Research timed out. Check the agent backend.")
        else:
            time.sleep(15)
            st.rerun()
    return True


def main() -> None:
    apply_styling()
    if not require_auth():
        return
    if handle_polling():
        return

    view = render_sidebar()
    if view == "Dashboard":
        render_dashboard()
    elif view == "Content Lab":
        st.title("AI Script Lab")
        df = fetch_data("Scripts")
        if df is None or df.empty:
            st.info("No script data is available.")
        else:
            render_scripts(df)
    elif view == "Insta Intelligence":
        st.title("Instagram Intelligence")
        df = fetch_data("Reels")
        if df is None or df.empty:
            st.info("No Instagram reel data is available.")
        else:
            q = st.text_input("Filter Content", placeholder="Keywords")
            if q and "caption" in df.columns:
                df = df[df["caption"].astype(str).str.contains(q, case=False, na=False)]
            render_reel_grid(df)
    elif view == "X Pulse":
        st.title("X Pulse")
        tab1, tab2 = st.tabs(["Top Posts", "Latest Posts"])
        with tab1:
            df = fetch_data("Tweets_Top")
            if df is None or df.empty:
                st.info("No top post data is available.")
            else:
                render_posts(df, text_col="Tweet", author_col="Author", meta_cols=["Score", "Views", "Likes"])
        with tab2:
            df = fetch_data("Tweets_Latest")
            if df is None or df.empty:
                st.info("No latest post data is available.")
            else:
                render_posts(df, text_col="Tweet", author_col="Author", meta_cols=["Date", "Views", "Replies"])
    elif view == "Competitors":
        st.title("Competitor Recon")
        df = fetch_data("Competitors")
        if df is None or df.empty:
            st.info("No competitor data is available.")
        else:
            if "ownerUsername" in df.columns and "velocity_score" in df.columns:
                stats = df.groupby("ownerUsername").agg({"velocity_score": "mean"}).reset_index().sort_values("velocity_score", ascending=False)
                top = st.columns(3)
                for idx, (_, row) in enumerate(stats.head(3).iterrows()):
                    with top[idx]:
                        st.markdown(
                            f'<div class="glass-panel"><div class="mono">@{escape_text(row["ownerUsername"])}</div><h3 class="section-title">{float(row["velocity_score"]):.1f}</h3><p class="section-copy">Average velocity</p></div>',
                            unsafe_allow_html=True,
                        )
            render_reel_grid(df)


if __name__ == "__main__":
    main()

