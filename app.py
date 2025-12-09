import streamlit as st
import pandas as pd
import json
import requests
from datetime import datetime
import re
import time
import ast

# -----------------------------------------------------------------------------
# 1. SYSTEM CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="TheHelloMedia | Research OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# 2. DESIGN SYSTEM (CSS)
# -----------------------------------------------------------------------------
def apply_styling():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

    :root {
        --bg-dark: #0e1117;
        --bg-card: #161b22;
        --border-glass: 1px solid rgba(255, 255, 255, 0.1);
        --accent-core: #7c3aed;
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
    }

    .stApp { background-color: var(--bg-dark); font-family: 'Inter', sans-serif; }

    /* Glass Panel */
    .glass-panel {
        background: var(--bg-card);
        border: var(--border-glass);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
        position: relative;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        height: 100%;
    }
    .glass-panel:hover {
        border-color: rgba(124, 58, 237, 0.5);
        transform: translateY(-2px);
    }

    /* REEL SPECIFIC (9:16 Aspect) */
    .reel-thumbnail-container {
        position: relative;
        width: 100%;
        aspect-ratio: 9/16; 
        background: #000;
        overflow: hidden;
        border-radius: 8px;
    }
    
    .reel-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        opacity: 0.9;
        transition: opacity 0.3s;
    }
    .reel-img:hover { opacity: 1; }

    /* Overlays */
    .overlay-top-left { position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.7); padding: 2px 8px; border-radius: 4px; color: white; font-weight: bold; font-size: 0.8rem; z-index: 2; }
    .overlay-top-right { position: absolute; top: 10px; right: 10px; z-index: 2; }
    .overlay-bottom { position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(to top, rgba(0,0,0,0.9), transparent); padding: 30px 10px 10px; z-index: 2; }

    /* Badges */
    .stat-badge {
        display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 99px;
        font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: white;
    }
    
    .badge-viral { background: #ec4899; box-shadow: 0 0 10px rgba(236, 72, 153, 0.4); }
    .badge-trend { background: #f59e0b; }
    .badge-norm { background: #10b981; }
    .badge-blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.2); }

    /* Script Blocks */
    .script-block { border-left: 2px solid #333; padding-left: 1rem; margin-bottom: 1rem; }
    .script-block.hook { border-color: #ef4444; }
    .script-block.body { border-color: #3b82f6; }
    .script-block.cta { border-color: #10b981; }
    .block-label { font-size: 0.7rem; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 0.25rem; font-weight: 700; }

    /* Streamlit Overrides */
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input, .stTextArea textarea {
        background-color: #1f2937 !important;
        border: 1px solid #374151 !important;
        color: white !important;
        border-radius: 8px;
    }
    div[data-testid="stDialog"] { background-color: #1e293b; border: 1px solid #334155; }
    div[data-testid="stMetricValue"] { color: #f8fafc; font-family: 'JetBrains Mono', monospace; }
    </style>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. DATA ENGINE
# -----------------------------------------------------------------------------
SHEET_ID = "1OTuusBq6CSawKz6nHHsZvJ1275AffW8seICMopMuN6s"

SHEET_MAPPING = {
    "Summary": "ResearchSummary",
    "Reels": "TopPerformingReels",
    "Scripts": "Top3ReelsIdeas",
    "Tweets_Top": "XTopTweets",
    "Tweets_Latest": "XLatestTweets",
    "Competitors": "CompetitorData"
}

@st.cache_data(ttl=60)
def fetch_data(key):
    try:
        sheet_name = SHEET_MAPPING.get(key, key)
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        
        numeric_cols = ['velocity_score', 'videoPlayCount', 'likesCount', 'commentsCount', 'reshareCount', 'views', 'Score', 'Likes', 'Retweets', 'Replies', 'age_hours']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        return df
    except Exception as e:
        return None

def get_safe(row, potential_cols, default=""):
    for col in potential_cols:
        if col in row and pd.notna(row[col]):
            return row[col]
    return default

def format_k(num):
    try:
        n = float(num)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000: return f"{n/1_000:.1f}K"
        return str(int(n))
    except:
        return "0"

def clean_json_text(text):
    if not isinstance(text, str): return str(text)
    if text.startswith('[') and text.endswith(']'):
        try:
            return ", ".join(ast.literal_eval(text))
        except:
            return text
    return text

def parse_summary_points(text):
    if not isinstance(text, str): return {}
    sections = {}
    pattern = r"(\d+\.\s+[A-Z\s]+:)(.*?)(?=\d+\.\s+[A-Z\s]+:|$)"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        for title, content in matches:
            clean_title = title.strip().rstrip(':')
            sections[clean_title] = content.strip()
    else:
        sections["Analysis"] = text
    return sections

def escape_fstring(text):
    if not isinstance(text, str): return text
    return text.replace("{", "{{").replace("}", "}}")

# -----------------------------------------------------------------------------
# 4. WORKFLOW TRIGGER (N8N)
# -----------------------------------------------------------------------------
def load_credentials():
    try:
        with open('security.json', 'r') as f: return json.load(f)
    except: return {"users": {"admin": "admin123"}, "n8n_api_url": ""}

def trigger_workflow(params):
    creds = load_credentials()
    url = creds.get('n8n_api_url', '')
    if not url: return False, "N8N API URL not found in security.json"
    
    try:
        # --- CRITICAL FIX: Wrap in 'body' object to match N8N expectations ---
        payload = {
            "body": {
                **params,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Fire request with short timeout (we don't wait for completion)
        try:
            requests.post(url, json=payload, timeout=2, headers={'Content-Type': 'application/json'})
        except requests.exceptions.Timeout:
            pass # This is EXPECTED for long scraping jobs
            
        return True, "Workflow initiated successfully"
    except Exception as e:
        return True, f"Triggered with warning: {str(e)}"

# -----------------------------------------------------------------------------
# 5. COMPONENT RENDERERS
# -----------------------------------------------------------------------------

# --- CODE 1: REEL DIALOG & CARD (With Analyze Button & 9:16) ---
@st.dialog("📽️ Reel Analysis")
def show_reel_details(row):
    """Modal for detailed reel analysis"""
    caption = get_safe(row, ['caption', 'title'], 'No Caption')
    img_url = get_safe(row, ['displayUrl', 'thumbnail'], '')
    url = get_safe(row, ['url', 'permalink'], '#')
    
    # Metrics
    views = get_safe(row, ['views', 'videoPlayCount', 'igPlayCount'], 0)
    likes = get_safe(row, ['likesCount', 'likes'], 0)
    comments = get_safe(row, ['commentsCount', 'comments'], 0)
    shares = get_safe(row, ['reshareCount', 'shares'], 0)
    age = get_safe(row, ['age_hours'], 0)
    velocity = get_safe(row, ['velocity_score'], 0)

    # Top Level Stats
    c1, c2, c3 = st.columns(3)
    c1.metric("Viral Velocity", f"{float(velocity):.1f}")
    c2.metric("Age", f"{float(age):.1f} hrs")
    c3.metric("Views", format_k(views))

    st.divider()

    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.image(img_url, use_container_width=True)
        st.link_button("↗ Open in Instagram", url, use_container_width=True)
    
    with col2:
        st.markdown("#### 📊 Engagement")
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Likes", format_k(likes))
        sc2.metric("Comments", format_k(comments))
        sc3.metric("Shares", format_k(shares))
        
        st.markdown("#### 📝 Full Caption")
        st.caption(clean_json_text(caption))
        
        st.markdown("#### # Hashtags")
        tags = clean_json_text(get_safe(row, ['hashtags'], ''))
        st.info(tags)

def render_reel_card(row, rank):
    """Card with 9:16 Thumbnail and Analyze Button"""
    img_url = get_safe(row, ['displayUrl', 'thumbnail'], '')
    caption = clean_json_text(get_safe(row, ['caption', 'title'], 'No Caption'))
    views = format_k(get_safe(row, ['views', 'videoPlayCount'], 0))
    velocity = float(get_safe(row, ['velocity_score'], 0))
    
    badge_class = "badge-norm"
    if velocity > 10: badge_class = "badge-viral"
    elif velocity > 5: badge_class = "badge-trend"

    html = f"""
<div class="glass-panel" style="padding:0; height: 100%;">
    <div class="reel-thumbnail-container">
        <img src="{img_url}" class="reel-img" onerror="this.src='https://via.placeholder.com/400x711?text=No+Image'">
        <div class="overlay-top-left">#{rank}</div>
        <div class="overlay-top-right">
            <span class="stat-badge {badge_class}">⚡ {velocity:.1f}</span>
        </div>
        <div class="overlay-bottom">
           <div style="color: white; font-weight: 600; font-size: 0.9rem;">▶ {views}</div>
        </div>
    </div>
    <div style="padding: 1rem; flex-grow: 1;">
        <div style="height: 3em; overflow: hidden; color: #cbd5e1; font-size: 0.85rem; margin-bottom: 0.5rem; line-height: 1.5;">
            {escape_fstring(caption[:100])}...
        </div>
    </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)
    
    b1, b2 = st.columns([1, 1])
    if b1.button("🔍 Analyze", key=f"btn_an_{rank}", use_container_width=True):
        show_reel_details(row)
    url = get_safe(row, ['url', 'permalink'], '#')
    b2.link_button("↗ Open", url, use_container_width=True)


# --- CODE 2: SCRIPT CARD (With HTML Fixes) ---
def render_script_card(row, idx):
    title = get_safe(row, ['script_title', 'title'], 'Untitled Script')
    topic = get_safe(row, ['topic_title', 'topic'], 'General')
    score = get_safe(row, ['viral_potential_score', 'score'], 0)
    duration = get_safe(row, ['estimated_duration'], '30s')
    audience = get_safe(row, ['target_audience'], 'General')
    
    hook = get_safe(row, ['script_hook'], '')
    buildup = get_safe(row, ['script_buildup'], '')
    value = get_safe(row, ['script_value'], '')
    cta = get_safe(row, ['script_cta'], '')
    why_works = get_safe(row, ['why_this_works'], '')
    strategy = get_safe(row, ['content_gap_addressed'], 'N/A')

    with st.container():
        html = f"""
<div class="glass-panel">
    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
        <div>
            <span class="stat-badge badge-blue" style="margin-bottom: 0.5rem;">#{idx} {escape_fstring(topic)}</span>
            <h3 style="margin: 0.5rem 0 0 0;">{escape_fstring(title)}</h3>
        </div>
        <div style="text-align: right;">
            <div style="font-family: 'JetBrains Mono'; font-size: 1.5rem; font-weight: 700; color: #a78bfa;">{score}/100</div>
            <div style="font-size: 0.7rem; color: #94a3b8; text-transform: uppercase;">Viral Score</div>
        </div>
    </div>
    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
        <div style="background: rgba(255,255,255,0.03); padding: 0.5rem; border-radius: 6px;">
            <div class="block-label">Duration</div>
            <div style="color: white;">{duration}</div>
        </div>
        <div style="background: rgba(255,255,255,0.03); padding: 0.5rem; border-radius: 6px;">
            <div class="block-label">Audience</div>
            <div style="color: white; font-size: 0.85rem;">{escape_fstring(audience)}</div>
        </div>
        <div style="background: rgba(255,255,255,0.03); padding: 0.5rem; border-radius: 6px;">
            <div class="block-label">Strategy</div>
            <div style="color: white; font-size: 0.85rem;">{escape_fstring(strategy[:50])}...</div>
        </div>
    </div>
</div>
"""
        st.markdown(html, unsafe_allow_html=True)
        
        with st.expander("📜 View Full Script & Structure", expanded=(idx==1)):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("#### Script Flow")
                if hook:
                    st.markdown(f'<div class="script-block hook"><div class="block-label">The Hook</div><div style="white-space: pre-wrap;">{escape_fstring(hook)}</div></div>', unsafe_allow_html=True)
                if buildup or value:
                    st.markdown(f'<div class="script-block body"><div class="block-label">The Value</div><div style="white-space: pre-wrap;">{escape_fstring(buildup)}<br>{escape_fstring(value)}</div></div>', unsafe_allow_html=True)
                if cta:
                    st.markdown(f'<div class="script-block cta"><div class="block-label">CTA</div><div style="white-space: pre-wrap;">{escape_fstring(cta)}</div></div>', unsafe_allow_html=True)
                
                full_text = get_safe(row, ['full_text', 'script_full_text'], '')
                if not hook and full_text:
                    st.code(full_text, language="markdown")
            with c2:
                st.markdown("#### 🧠 Why It Works")
                st.info(why_works)
                st.markdown("#### # Hashtags")
                st.caption(get_safe(row, ['hashtags_all', 'hashtags'], ''))

# --- CODE 2: TWEET CARD (Merged Styling) ---
def render_tweet_card(row, is_viral=False):
    author = get_safe(row, ['Author', 'ownerUsername'])
    text = get_safe(row, ['Tweet', 'full_text'])
    score = get_safe(row, ['Score', 'velocity_score'], None)
    date = get_safe(row, ['Posted_Ago', 'Date'], '')
    
    likes = format_k(get_safe(row, ['Likes', 'likes'], 0))
    views = format_k(get_safe(row, ['Views', 'views'], 0))
    replies = format_k(get_safe(row, ['Replies', 'replies'], 0))
    
    header_html = ""
    if is_viral and score:
        header_html = f'<span style="background: #7c3aed; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem;">🔥 Score: {float(score):.1f}</span>'
    else:
        header_html = f'<span style="color: #94a3b8; font-size: 0.75rem;">🕒 {date}</span>'

    with st.container():
        html = f"""
<div class="glass-panel" style="padding: 1rem;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
        <span style="font-weight: 700; color: white;">{author}</span>
        {header_html}
    </div>
    <div style="color: #cbd5e1; font-size: 0.9rem; margin-bottom: 1rem; line-height: 1.5;">
        {escape_fstring(text)}
    </div>
</div>
"""
        st.markdown(html, unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.caption(f"👁️ {views}")
        m2.caption(f"❤️ {likes}")
        m3.caption(f"💬 {replies}")
        st.markdown("---")

# -----------------------------------------------------------------------------
# 6. MAIN APPLICATION
# -----------------------------------------------------------------------------

def main():
    apply_styling()
    
    # ------------------ AUTHENTICATION ------------------
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            st.markdown("<br><br><br>", unsafe_allow_html=True)
            st.markdown("## 🔐 Research OS Login")
            with st.form("login"):
                u = st.text_input("ID")
                p = st.text_input("Key", type="password")
                if st.form_submit_button("Access Terminal"):
                    if u == "admin" and p == "admin123":
                        st.session_state.authenticated = True
                        st.rerun()
        return

    # ------------------ SIDEBAR (Code 1 - Detailed Form) ------------------
    with st.sidebar:
        st.title("⚡ TheHelloMedia")
        view = st.radio("Menu", ["Dashboard", "Content Lab", "Insta Intelligence", "X Pulse", "Competitors"], label_visibility="collapsed")
        
        st.divider()
        with st.expander("🛠️ New Research Config", expanded=False):
            with st.form("research_config"):
                st.markdown("### 🎯 Parameters")
                niche = st.text_input("Main Niche", value="Virat Kohli Cricket")
                is_specific = st.checkbox("Is Specific Niche?", value=True)
                creator_niche = st.text_input("Creator Niche (Sub-niche)", value="Cricket Analysis")
                
                c1, c2 = st.columns(2)
                with c1:
                    lang_script = st.selectbox("Script Lang", ["Hinglish", "English", "Hindi"], index=0)
                    style = st.selectbox("Writing Style", ["Storytelling", "Analytical", "Hype", "Educational"], index=0)
                with c2:
                    lang_text = st.selectbox("Text Lang", ["English", "Hindi"], index=0)
                    location = st.text_input("Location", value="India")
                
                st.markdown("### 🔍 Filters")
                count = st.number_input("Reels to Scrape (Total)", min_value=10, max_value=100, value=30)
                reels_filter = st.number_input("Reels Till Filter (Days)", min_value=1, max_value=365, value=30, help="How many reels to check back")
                min_likes = st.number_input("Min Likes Filter", min_value=0, value=0)
                competitors = st.text_area("Competitor Usernames (comma separated)", placeholder="espncricinfo, icc, bcci")
                res_type = "Instagram"

                if st.form_submit_button("🚀 Launch Research Agents"):
                    params = {
                        "is_specific_niche": is_specific,
                        "creator_niche": creator_niche,
                        "niche": niche,
                        "language_of_script": lang_script,
                        "language_of_text": lang_text,
                        "writing_style": style,
                        "location": location,
                        "noOfReelsToScrape": count,
                        "type": res_type,
                        "reelsTill_Filter": reels_filter,
                        "minLikesReel_Filter": min_likes,
                        "competitorListUsernames": competitors
                    }
                    with st.spinner("Transmitting coordinates to N8N..."):
                        success, msg = trigger_workflow(params)
                        if success: st.success(f"Deployed! {msg}")
                        else: st.error(f"Error: {msg}")

        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    # ------------------ DASHBOARD (Code 2 - Parsed UI) ------------------
    if view == "Dashboard":
        st.title("🚀 Research Command Center")
        summ = fetch_data("Summary")
        reels = fetch_data("Reels")
        
        # High Level Metrics
        if reels is not None:
            c1, c2, c3 = st.columns(3)
            max_vel = reels['velocity_score'].max() if 'velocity_score' in reels else 0
            c1.metric("Highest Velocity", f"{max_vel:.1f}", delta="Viral Peak")
            c2.metric("Reels Analyzed", len(reels))
            if summ is not None and not summ.empty:
                last_run = get_safe(summ.iloc[0], ['generatedAt'], 'Unknown')[:16]
                c3.metric("Last Sync", last_run)

        # Parsed Executive Summary
        if summ is not None and not summ.empty:
            raw_text = get_safe(summ.iloc[0], ['instagram_summary_research'], '')
            sections = parse_summary_points(raw_text)
            
            sc1, sc2 = st.columns(2)
            items = list(sections.items())
            half = len(items) // 2
            
            with sc1:
                for title, content in items[:half]:
                    st.markdown(f'<div class="glass-panel"><h4 style="color: #a78bfa; margin-top:0;">{title}</h4><p style="font-size: 0.9rem; color: #cbd5e1;">{escape_fstring(content)}</p></div>', unsafe_allow_html=True)
            with sc2:
                for title, content in items[half:]:
                    st.markdown(f'<div class="glass-panel"><h4 style="color: #34d399; margin-top:0;">{title}</h4><p style="font-size: 0.9rem; color: #cbd5e1;">{escape_fstring(content)}</p></div>', unsafe_allow_html=True)
            
            schedule = get_safe(summ.iloc[0], ['posting_schedule'], '')
            if schedule:
                st.markdown(f'<div class="glass-panel" style="border-left: 4px solid #f59e0b;"><h4 style="color: #fbbf24; margin-top:0;">📅 Strategic Posting Schedule</h4><p style="font-size: 0.9rem; margin-bottom: 0;">{escape_fstring(schedule)}</p></div>', unsafe_allow_html=True)

    # ------------------ INSTA INTELLIGENCE (Code 1 - UI) ------------------
    elif view == "Insta Intelligence":
        st.title("📸 Instagram Intelligence")
        df = fetch_data("Reels")
        if df is not None:
            c1, c2 = st.columns([3, 1])
            with c1: q = st.text_input("🔍 Filter Content", placeholder="Keywords...")
            with c2: sort = st.selectbox("Sort By", ["Viral Velocity", "Most Viewed", "Most Liked", "Recent"])
            
            if sort == "Viral Velocity": df = df.sort_values('velocity_score', ascending=False)
            elif sort == "Most Viewed": df = df.sort_values('videoPlayCount', ascending=False)
            elif sort == "Most Liked": df = df.sort_values('likesCount', ascending=False)
            elif sort == "Recent": df = df.sort_values('age_hours', ascending=True)

            if q: df = df[df['caption'].astype(str).str.contains(q, case=False, na=False)]

            st.markdown("<br>", unsafe_allow_html=True)
            cols = st.columns(4)
            for i, row in df.iterrows():
                with cols[i % 4]: render_reel_card(row, i+1)
        else: st.error("No Instagram Data Found")

    # ------------------ CONTENT LAB (Code 2 - UI) ------------------
    elif view == "Content Lab":
        st.title("🤖 AI Script Lab")
        scripts = fetch_data("Scripts")
        if scripts is not None:
            for i, row in scripts.iterrows():
                render_script_card(row, i+1)

    # ------------------ X PULSE (Code 2 - UI) ------------------
    elif view == "X Pulse":
        st.title("🐦 Twitter / X Pulse")
        t1, t2 = st.tabs(["🔥 Viral Hits", "⏱️ Fresh Feed"])
        with t1:
            df = fetch_data("Tweets_Top")
            if df is not None:
                for _, row in df.iterrows(): render_tweet_card(row, is_viral=True)
        with t2:
            df = fetch_data("Tweets_Latest")
            if df is not None:
                for _, row in df.iterrows(): render_tweet_card(row, is_viral=False)

    # ------------------ COMPETITORS (Code 1 - UI) ------------------
    elif view == "Competitors":
        st.title("⚔️ Competitor Recon")
        df = fetch_data("Competitors")
        if df is not None:
            if 'ownerUsername' in df.columns:
                stats = df.groupby('ownerUsername').agg({'velocity_score': 'mean'}).reset_index().sort_values('velocity_score', ascending=False)
                c1, c2, c3 = st.columns(3)
                for i, row in stats.head(3).iterrows():
                    with [c1, c2, c3][i]:
                        st.markdown(f'<div class="glass-panel" style="text-align: center; border-top: 4px solid #7c3aed;"><h3 style="margin-bottom: 0;">@{row["ownerUsername"]}</h3><div style="font-size: 2rem; font-weight: 700; color: #10b981;">{row["velocity_score"]:.1f}</div><div style="font-size: 0.8rem; text-transform: uppercase; color: #64748b;">Avg Velocity</div></div>', unsafe_allow_html=True)
            
            st.markdown("### 🕵️ Recent Activities")
            cols = st.columns(4)
            for i, row in df.iterrows():
                with cols[i % 4]: render_reel_card(row, f"C-{i+1}")

if __name__ == "__main__":
    main()
