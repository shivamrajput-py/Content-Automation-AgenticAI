import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import time
import os

# Page configuration
st.set_page_config(
    page_title="TheHelloMedia - Instagram Research",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load credentials
def load_credentials():
    try:
        with open('security.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"users": {"admin": "admin123", "demo": "demo123"}}

def authenticate(username, password):
    credentials = load_credentials()
    users = credentials.get('users', {})
    return username in users and users[username] == password

# Google Sheets Configuration
SHEET_ID = "1OTuusBq6CSawKz6nHHsZvJ1275AffW8seICMopMuN6s"

# Data fetching functions
def fetch_sheet_data(worksheet_name):
    """
    Fetch data from public Google Sheet using CSV export
    """
    try:
        # Construct the public CSV export URL
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={worksheet_name}"

        # Read the CSV data
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Error fetching sheet '{worksheet_name}': {str(e)}")
        return None

def get_column_value(row, possible_names, default=None):
    """
    Try to get value from row using multiple possible column names
    """
    for name in possible_names if isinstance(possible_names, list) else [possible_names]:
        if name in row and pd.notna(row[name]):
            return row[name]
    return default

def format_number(num):
    try:
        num = float(num) if pd.notna(num) else 0
        if num >= 1000000:
            return f"{num/1000000:.1f}M"
        elif num >= 1000:
            return f"{num/1000:.1f}K"
        else:
            return str(int(num))
    except:
        return "0"

def calculate_engagement_rate(likes, views):
    try:
        likes = float(likes) if pd.notna(likes) else 0
        views = float(views) if pd.notna(views) else 0
        if views > 0:
            return (likes / views) * 100
        return 0
    except:
        return 0

# Call N8N Workflow
def call_n8n_workflow(niche, language_script, language_text, writing_style, location, reels_count):
    try:
        config = load_credentials()
        n8n_api_url = config.get('n8n_api_url', '')
        
        if not n8n_api_url:
            return True, "Demo mode - using local data"
        
        payload = {
            "is_specific_niche": True,
            "creator_niche": niche,
            "niche": niche,
            "type": "Instagram",
            "language_of_script": language_script,
            "language_of_text": language_text,
            "writing_style": writing_style,
            "location": location,
            "noOfReelsToScrape": reels_count,
            "userInstaUrl": "",
            "userYtUrl": "",
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(
            n8n_api_url, 
            json=payload, 
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        return True, "Workflow triggered successfully"
            
    except requests.exceptions.Timeout:
        return True, "Workflow triggered (processing in background)"
    except Exception as e:
        return False, str(e)

# Check if data is ready
def check_data_ready(initial_timestamp):
    """
    Check if new data is available by comparing generatedAt timestamp
    """
    try:
        summary_df = fetch_sheet_data("ResearchSummary")
        if summary_df is not None and not summary_df.empty:
            # Check if generatedAt column exists
            if 'generatedAt' in summary_df.columns:
                current_timestamp = summary_df['generatedAt'].iloc[0]

                # If initial_timestamp is None, store current and wait for change
                if initial_timestamp is None:
                    return False, current_timestamp

                # Compare timestamps
                if pd.notna(current_timestamp) and str(current_timestamp) != str(initial_timestamp):
                    return True, current_timestamp
            else:
                st.warning("generatedAt column not found in ResearchSummary sheet")
        return False, initial_timestamp
    except Exception as e:
        st.error(f"Error checking data ready: {str(e)}")
        return False, initial_timestamp

# Apply CSS styling
def apply_styling():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --bg-primary: #0a0a0a;
        --bg-secondary: #1a1a1a;
        --bg-card: #212121;
        --border: #2a2a2a;
        --text-primary: #ffffff;
        --text-secondary: #b0b0b0;
        --text-muted: #707070;
        --accent: #E1306C;
        --accent-hover: #c91f5c;
    }

    .stApp {
        background: var(--bg-primary);
        font-family: 'Inter', sans-serif;
    }

    /* Hide default Streamlit elements */
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }

    /* Main header */
    .main-header {
        background: var(--bg-secondary);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        border: 1px solid var(--border);
    }

    /* Reel Card - Clean Design */
    .reel-card {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1.5rem;
        display: flex;
        gap: 1.5rem;
        transition: border-color 0.2s;
    }

    .reel-card:hover {
        border-color: #404040;
    }

    .reel-image {
        width: 120px;
        height: 120px;
        border-radius: 8px;
        object-fit: cover;
        flex-shrink: 0;
        background: var(--bg-card);
    }

    .reel-content {
        flex: 1;
        min-width: 0;
    }

    .reel-rank {
        display: inline-block;
        background: var(--bg-card);
        color: var(--text-secondary);
        padding: 0.25rem 0.75rem;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }

    .reel-caption {
        color: var(--text-primary);
        font-size: 0.95rem;
        line-height: 1.5;
        margin: 0.5rem 0;
    }

    .reel-stats {
        display: flex;
        gap: 1.5rem;
        margin-top: 0.75rem;
        flex-wrap: wrap;
    }

    .stat-item {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        color: var(--text-muted);
        font-size: 0.85rem;
    }

    .stat-value {
        color: var(--text-secondary);
        font-weight: 500;
    }

    /* Script Card - Clean Design */
    .script-card {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }

    .script-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 1rem;
    }

    .script-title-text {
        color: var(--text-primary);
        font-size: 1.1rem;
        font-weight: 600;
        margin: 0.25rem 0;
    }

    .script-score {
        background: var(--bg-card);
        color: var(--text-secondary);
        padding: 0.35rem 0.85rem;
        border-radius: 6px;
        font-size: 0.85rem;
        white-space: nowrap;
    }

    .script-meta {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 0.75rem;
        margin: 1rem 0;
    }

    .meta-item {
        color: var(--text-muted);
        font-size: 0.85rem;
    }

    .meta-label {
        font-weight: 500;
        color: var(--text-secondary);
        margin-right: 0.35rem;
    }

    .script-text {
        background: var(--bg-card);
        padding: 1rem;
        border-radius: 8px;
        color: var(--text-primary);
        font-size: 1.05rem;
        line-height: 1.7;
        font-weight: 600;
        margin: 1rem 0;
    }

    /* Summary Section */
    .summary-box {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }

    .summary-title {
        color: var(--text-primary);
        font-size: 1.05rem;
        font-weight: 600;
        margin-bottom: 0.75rem;
    }

    .summary-content {
        color: var(--text-secondary);
        font-size: 0.95rem;
        line-height: 1.7;
    }

    /* Buttons */
    .stButton > button {
        background: var(--bg-card) !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 500 !important;
        transition: all 0.2s !important;
    }

    .stButton > button:hover {
        background: var(--bg-secondary) !important;
        border-color: #404040 !important;
        color: var(--text-primary) !important;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text-secondary) !important;
        font-size: 0.9rem !important;
    }

    .streamlit-expanderHeader:hover {
        border-color: #404040 !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid var(--border);
    }

    .stTabs [data-baseweb="tab"] {
        color: var(--text-muted);
        border-bottom: 2px solid transparent;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        color: var(--text-primary) !important;
        border-bottom-color: var(--accent) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Main app
def main():
    apply_styling()
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # Login page
    if not st.session_state.authenticated:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.markdown("<h1 style='text-align: center; color: #E1306C;'>TheHelloMedia</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #a8a8a8;'>Instagram Research Platform</p>", unsafe_allow_html=True)
            
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            
            if st.button("🔓 Sign In", use_container_width=True):
                if authenticate(username, password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.success("✅ Welcome!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")
    
    # Main dashboard
    else:
        # Header
        st.markdown(f"""
            <div class='main-header'>
                <h2 style='margin:0; color: white;'>📸 Instagram Research Dashboard</h2>
                <p style='margin:0; color: #a8a8a8;'>User: {st.session_state.username}</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Logout button
        col1, col2 = st.columns([10, 1])
        with col2:
            if st.button("Logout"):
                st.session_state.clear()
                st.rerun()
        
        # Research inputs
        with st.container():
            st.markdown("### 🎯 Research Configuration")
            col1, col2 = st.columns(2)
            
            with col1:
                niche = st.text_input("Content Niche", placeholder="e.g., Fitness, Beauty, Tech...")
                language_script = st.text_input("Script Language", value="Hinglish", placeholder="e.g., Hinglish, English, Hindi")
                writing_style = st.text_input("Writing Style", value="Let AI Decide", placeholder="e.g., Let AI Decide, Professional, Casual")

            with col2:
                language_text = st.text_input("Text Language", value="English", placeholder="e.g., English, Hindi, Hinglish")
                location = st.text_input("Target Location", value="India")
                reels_count = st.slider("Reels to Analyze", 10, 50, 25, 5)
            
            # Start research button
            if st.button("🚀 Start Research", use_container_width=True):
                if not niche:
                    st.error("Please enter a content niche")
                else:
                    # Get initial timestamp before triggering workflow
                    summary_df = fetch_sheet_data("ResearchSummary")
                    initial_timestamp = None
                    if summary_df is not None and not summary_df.empty and 'generatedAt' in summary_df.columns:
                        initial_timestamp = summary_df['generatedAt'].iloc[0]

                    st.session_state.research_params = {
                        'niche': niche,
                        'initial_timestamp': initial_timestamp,
                        'start_time': datetime.now()
                    }
                    
                    with st.spinner("Initiating research..."):
                        success, message = call_n8n_workflow(niche, language_script, language_text, writing_style, location, reels_count)
                        if success:
                            st.session_state.checking_data = True
                            st.success("✅ Research workflow started!")
                            st.info("🔄 Polling for updates every 10 seconds. Please wait...")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to start workflow: {message}")
        
        # Check for updates with polling
        if 'checking_data' in st.session_state and st.session_state.checking_data:
            params = st.session_state.research_params
            elapsed = datetime.now() - params['start_time']
            elapsed_seconds = int(elapsed.total_seconds())

            # Check if data is ready
            data_ready, new_timestamp = check_data_ready(params['initial_timestamp'])

            if data_ready:
                st.session_state.checking_data = False
                st.session_state.show_results = True
                st.success(f"✅ Research complete! New data generated at: {new_timestamp}")
                time.sleep(1)
                st.rerun()
            else:
                # Continue polling if within timeout
                if elapsed_seconds < 600:  # 10 minutes timeout
                    # Compact progress indicator
                    st.markdown("---")
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.info(f"⏳ Research in progress... Time elapsed: {elapsed_seconds // 60}m {elapsed_seconds % 60}s")
                    with col2:
                        if st.button("⏸️ Stop", use_container_width=True):
                            st.session_state.checking_data = False
                            st.session_state.show_results = True
                            st.rerun()

                    progress_bar = st.progress(min(elapsed_seconds / 600, 1.0))

                    # Wait and rerun
                    time.sleep(10)
                    st.rerun()
                else:
                    st.session_state.checking_data = False
                    st.session_state.show_results = True
                    st.warning("⚠️ Research is taking longer than expected. Showing current data.")
        
        # Refresh button
        if 'research_params' in st.session_state:
            st.markdown("---")
            if st.button("🔄 Refresh Results"):
                st.rerun()
        
        # Display results
        if 'show_results' in st.session_state or 'research_params' in st.session_state:
            # Load data from Google Sheets
            summary_df = fetch_sheet_data("ResearchSummary")
            reels_df = fetch_sheet_data("TopPerformingReels")
            scripts_df = fetch_sheet_data("Top3ReelsIdeas")
            
            # Tabs - Default to Script Ideas
            tab1, tab2, tab3, tab4 = st.tabs(["✨ Script Ideas", "🎬 Top Reels", "📊 Summary", "📈 Raw Data"])

            # Script Ideas Tab (First/Default)
            with tab1:
                if scripts_df is not None and not scripts_df.empty:
                    for idx, row in scripts_df.iterrows():
                        # Get data
                        rank = get_column_value(row, ['rank', 'Rank'], idx + 1)
                        script_title = get_column_value(row, ['script_title', 'Script Title', 'title'], 'Untitled')
                        topic_title = get_column_value(row, ['topic_title', 'Topic Title', 'topic'], script_title)
                        viral_score = get_column_value(row, ['viral_potential_score', 'Viral Potential Score'], None)
                        audience = get_column_value(row, ['target_audience', 'Target Audience'], 'N/A')
                        trigger = get_column_value(row, ['emotional_trigger', 'Emotional Trigger'], 'N/A')
                        duration = get_column_value(row, ['estimated_duration', 'Duration'], 'N/A')
                        full_text = get_column_value(row, ['full_text', 'Full Text', 'script_full_text'], '')

                        # Card container
                        st.markdown('<div class="script-card">', unsafe_allow_html=True)

                        # Header with title and score
                        col_title, col_score = st.columns([4, 1])
                        with col_title:
                            st.markdown(f'<div class="script-title-text">#{rank} · {script_title}</div>', unsafe_allow_html=True)
                        with col_score:
                            if viral_score:
                                st.markdown(f'<div class="script-score">Score: {viral_score}/100</div>', unsafe_allow_html=True)

                        # Meta information
                        st.markdown(f'''
                            <div class="script-meta">
                                <div class="meta-item"><span class="meta-label">Duration:</span>{duration}</div>
                                <div class="meta-item"><span class="meta-label">Audience:</span>{str(audience)[:60]}</div>
                                <div class="meta-item"><span class="meta-label">Trigger:</span>{str(trigger)[:60]}</div>
                            </div>
                        ''', unsafe_allow_html=True)

                        # Script preview (bold and larger - full text)
                        if full_text:
                            st.markdown(f'<div class="script-text">{full_text}</div>', unsafe_allow_html=True)

                        # View Details button
                        with st.expander("📄 View Complete Details"):
                            # Topic and titles
                            st.markdown("### Script Information")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Topic:** {topic_title}")
                                st.write(f"**Script Title:** {script_title}")
                                if viral_score:
                                    st.write(f"**Viral Potential Score:** {viral_score}/100")
                            with col2:
                                st.write(f"**Duration:** {duration}")
                                st.write(f"**Target Audience:** {audience}")
                                st.write(f"**Emotional Trigger:** {trigger}")

                            # Full script
                            if full_text:
                                st.markdown("### Full Script")
                                st.markdown(f'<div class="script-text">{full_text}</div>', unsafe_allow_html=True)

                            # Script components
                            hook = get_column_value(row, ['script_hook', 'Hook'], None)
                            buildup = get_column_value(row, ['script_buildup', 'Buildup'], None)
                            value = get_column_value(row, ['script_value', 'Value'], None)
                            cta = get_column_value(row, ['script_cta', 'CTA'], None)

                            if any([hook, buildup, value, cta]):
                                st.markdown("### Script Structure")
                                col1, col2 = st.columns(2)
                                with col1:
                                    if hook:
                                        st.markdown(f"**🎣 Hook:**\n\n{hook}")
                                    if buildup:
                                        st.markdown(f"**📈 Buildup:**\n\n{buildup}")
                                with col2:
                                    if value:
                                        st.markdown(f"**💎 Value:**\n\n{value}")
                                    if cta:
                                        st.markdown(f"**🎯 CTA:**\n\n{cta}")

                            # Additional details
                            gap = get_column_value(row, ['content_gap_addressed', 'Content Gap'], None)
                            why_works = get_column_value(row, ['why_this_works', 'Why This Works'], None)

                            if gap or why_works:
                                st.markdown("### Strategy Insights")
                                if gap:
                                    st.markdown(f"**Content Gap Addressed:**\n\n{gap}")
                                if why_works:
                                    st.markdown(f"**Why This Works:**\n\n{why_works}")

                            # Caption
                            caption_full = get_column_value(row, ['caption_full', 'Caption'], None)
                            if caption_full:
                                st.markdown("### Caption")
                                st.markdown(f'<div style="color: var(--text-secondary); font-size: 0.9rem; line-height: 1.6; white-space: pre-wrap;">{caption_full}</div>', unsafe_allow_html=True)

                            # Hashtags
                            hashtags_all = get_column_value(row, ['hashtags_all', 'Hashtags All'], None)
                            hashtags_primary = get_column_value(row, ['hashtags_primary', 'Primary Hashtags'], None)
                            hashtags_secondary = get_column_value(row, ['hashtags_secondary', 'Secondary Hashtags'], None)
                            hashtags_niche = get_column_value(row, ['hashtags_niche_specific', 'Niche Hashtags'], None)
                            hashtags_trending = get_column_value(row, ['hashtags_trending', 'Trending Hashtags'], None)

                            if any([hashtags_all, hashtags_primary, hashtags_secondary, hashtags_niche, hashtags_trending]):
                                st.markdown("### Hashtags")
                                if hashtags_primary:
                                    st.markdown(f"**Primary:** {hashtags_primary}")
                                if hashtags_secondary:
                                    st.markdown(f"**Secondary:** {hashtags_secondary}")
                                if hashtags_niche:
                                    st.markdown(f"**Niche Specific:** {hashtags_niche}")
                                if hashtags_trending:
                                    st.markdown(f"**Trending:** {hashtags_trending}")
                                if hashtags_all:
                                    st.markdown(f"**All Hashtags:** {hashtags_all}")

                        st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.info("✨ No script ideas available yet. Data will appear here once the workflow completes.")


            # Top Reels Tab
            with tab2:
                if scripts_df is not None and not scripts_df.empty:
                    for idx, row in scripts_df.iterrows():
                        # Get data
                        rank = get_column_value(row, ['rank', 'Rank'], idx + 1)
                        caption = get_column_value(row, ['caption', 'Caption', 'title', 'Title'], '')
                        display_url = get_column_value(row, ['displayUrl', 'DisplayUrl', 'thumbnail', 'image'], '')
                        views = get_column_value(row, ['views', 'Views', 'videoPlayCount', 'viewCount'], 0)
                        likes = get_column_value(row, ['likesCount', 'likes', 'Likes', 'likeCount'], 0)
                        comments = get_column_value(row, ['comments', 'Comments', 'commentCount', 'commentsCount'], 0)
                        shares = get_column_value(row, ['reshareCount', 'shares', 'Shares', 'shareCount'], 0)
                        engagement = get_column_value(row, ['engagement_rate', 'engagementRate', 'Engagement Rate'], None)
                        if engagement is None:
                            engagement = calculate_engagement_rate(likes, views)

                        # Display card
                        col_img, col_content = st.columns([1, 5])

                        with col_img:
                            if display_url:
                                st.markdown(f'<img src="{display_url}" class="reel-image" />', unsafe_allow_html=True)

                        with col_content:
                            st.markdown(f'<span class="reel-rank">#{rank}</span>', unsafe_allow_html=True)

                            caption_preview = str(caption)[:150] + "..." if len(str(caption)) > 150 else str(caption)
                            st.markdown(f'<div class="reel-caption">{caption_preview}</div>', unsafe_allow_html=True)

                            # Stats in one line
                            st.markdown(f'''
                                <div class="reel-stats">
                                    <div class="stat-item">👁️ <span class="stat-value">{format_number(views)}</span></div>
                                    <div class="stat-item">❤️ <span class="stat-value">{format_number(likes)}</span></div>
                                    <div class="stat-item">💬 <span class="stat-value">{format_number(comments)}</span></div>
                                    <div class="stat-item">🔄 <span class="stat-value">{format_number(shares)}</span></div>
                                    <div class="stat-item">📊 <span class="stat-value">{float(engagement):.2f}%</span></div>
                                </div>
                            ''', unsafe_allow_html=True)

                            # Full Info Button
                            with st.expander("📋 Full Details"):
                                col1, col2 = st.columns(2)

                                with col1:
                                    st.markdown("**Performance Metrics:**")
                                    st.write(f"• **Views:** {format_number(views)}")
                                    st.write(f"• **Likes:** {format_number(likes)}")
                                    st.write(f"• **Comments:** {format_number(comments)}")
                                    st.write(f"• **Shares:** {format_number(shares)}")
                                    st.write(f"• **Engagement Rate:** {float(engagement):.2f}%")

                                    performance_index = get_column_value(row, ['performance_index', 'Performance Index', 'score'], None)
                                    if performance_index:
                                        st.write(f"• **Performance Index:** {performance_index}")

                                with col2:
                                    st.markdown("**Content Details:**")
                                    username = get_column_value(row, ['ownerUsername', 'username', 'creator', 'Creator'], None)
                                    if username:
                                        st.write(f"• **Creator:** @{username}")

                                    timestamp = get_column_value(row, ['timestamp', 'Timestamp', 'date', 'Date'], None)
                                    if timestamp:
                                        st.write(f"• **Posted:** {str(timestamp)[:19]}")

                                    url = get_column_value(row, ['url', 'URL', 'link', 'Link'], None)
                                    if url:
                                        st.markdown(f"• **Link:** [{url}]({url})")

                                # Full caption
                                if caption:
                                    st.markdown("**Full Caption:**")
                                    st.text_area("", caption, height=150, disabled=True, key=f"caption_{idx}", label_visibility="collapsed")

                                # Hashtags
                                hashtags = get_column_value(row, ['hashtags', 'Hashtags', 'tags'], None)
                                if hashtags:
                                    st.markdown("**Hashtags:**")
                                    if isinstance(hashtags, str):
                                        # Parse if it's a string representation of a list
                                        import re
                                        tags = re.findall(r'\w+', str(hashtags))
                                        hashtags_formatted = " ".join([f"#{tag}" for tag in tags if tag])
                                        st.markdown(f'<div style="color: #b0b0b0; font-size: 0.85rem;">{hashtags_formatted}</div>', unsafe_allow_html=True)

                        st.markdown("<br>", unsafe_allow_html=True)
                else:
                    st.info("📊 No reel data available yet. Data will appear here once the workflow completes.")
            
            # Summary Tab
            with tab3:
                if summary_df is not None and not summary_df.empty:
                    # Generated timestamp
                    generated_at = get_column_value(summary_df.iloc[0], ['generatedAt', 'Generated At', 'timestamp'], 'N/A')
                    st.markdown(f'<div class="summary-box"><div class="summary-content">Generated: {str(generated_at)[:19]}</div></div>', unsafe_allow_html=True)

                    # Niche Summary
                    niche_summary = get_column_value(summary_df.iloc[0], ['niche_summary', 'Niche Summary', 'summary'], None)
                    if niche_summary:
                        st.markdown(f'''
                            <div class="summary-box">
                                <div class="summary-title">Niche Analysis</div>
                                <div class="summary-content">{niche_summary}</div>
                            </div>
                        ''', unsafe_allow_html=True)

                    # Posting Schedule and Content Calendar
                    col1, col2 = st.columns(2)

                    with col1:
                        posting_schedule = get_column_value(summary_df.iloc[0], ['posting_schedule', 'Posting Schedule', 'schedule'], None)
                        if posting_schedule:
                            st.markdown(f'''
                                <div class="summary-box">
                                    <div class="summary-title">📅 Posting Schedule</div>
                                    <div class="summary-content">{posting_schedule}</div>
                                </div>
                            ''', unsafe_allow_html=True)

                    with col2:
                        content_calendar = get_column_value(summary_df.iloc[0], ['content_calendar', 'Content Calendar', 'calendar'], None)
                        if content_calendar:
                            st.markdown(f'''
                                <div class="summary-box">
                                    <div class="summary-title">📆 Content Calendar</div>
                                    <div class="summary-content">{content_calendar}</div>
                                </div>
                            ''', unsafe_allow_html=True)

                    # Additional summary fields if available
                    for col in summary_df.columns:
                        if col not in ['generatedAt', 'niche_summary', 'posting_schedule', 'content_calendar']:
                            value = get_column_value(summary_df.iloc[0], [col], None)
                            if value and str(value).strip() and str(value) != 'nan':
                                st.markdown(f'''
                                    <div class="summary-box">
                                        <div class="summary-title">{col.replace('_', ' ').title()}</div>
                                        <div class="summary-content">{value}</div>
                                    </div>
                                ''', unsafe_allow_html=True)
                else:
                    st.info("📊 No summary data available yet. Data will appear here once the workflow completes.")

            # Raw Data Tab
            with tab4:
                st.markdown("### 📊 Complete Datasets")
                
                if summary_df is not None:
                    st.markdown("**Research Summary**")
                    st.dataframe(summary_df)
                
                col1, col2 = st.columns(2)
                with col1:
                    if reels_df is not None:
                        st.markdown("**Top Performing Reels**")
                        st.dataframe(reels_df)
                
                with col2:
                    if scripts_df is not None:
                        st.markdown("**AI Script Ideas**")
                        st.dataframe(scripts_df)

if __name__ == "__main__":
    main()
