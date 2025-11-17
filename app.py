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

# Data fetching functions
def fetch_sheet_data(sheet_name, worksheet_name):
    try:
        if worksheet_name == "ResearchSummary":
            df = pd.read_csv('/mnt/user-data/uploads/InstaResearchData_-_ResearchSummary.csv')
        elif worksheet_name == "TopPerformingReels":
            df = pd.read_csv('/mnt/user-data/uploads/InstaResearchData_-_TopPerformingReels__4_.csv')
        elif worksheet_name == "Top3ReelsIdeas":
            df = pd.read_csv('/mnt/user-data/uploads/InstaResearchData_-_Top3ReelsIdeas__3_.csv')
        else:
            return None
        return df
    except Exception as e:
        return None

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
    try:
        summary_df = fetch_sheet_data("InstaResearchData", "ResearchSummary")
        if summary_df is not None and not summary_df.empty:
            current_timestamp = summary_df['generatedAt'].iloc[0]
            if pd.notna(current_timestamp) and str(current_timestamp) != str(initial_timestamp):
                return True, current_timestamp
        return False, initial_timestamp
    except:
        return False, initial_timestamp

# Apply CSS styling
def apply_styling():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    :root {
        --bg-primary: #0a0a0a;
        --bg-secondary: #141414;
        --bg-card: #1f1f1f;
        --border: #2a2a2a;
        --text-primary: #ffffff;
        --text-secondary: #a8a8a8;
        --accent: #E1306C;
        --success: #4ade80;
    }
    
    .stApp { 
        background: var(--bg-primary); 
        font-family: 'Inter', sans-serif;
    }
    
    /* Hide default Streamlit elements */
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
    
    /* Custom elements */
    .main-header {
        background: var(--bg-secondary);
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        border: 1px solid var(--border);
    }
    
    .reel-card {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: all 0.2s;
    }
    
    .reel-card:hover {
        border-color: var(--accent);
        transform: translateY(-2px);
    }
    
    .metric-box {
        background: var(--bg-primary);
        padding: 0.75rem;
        border-radius: 8px;
        text-align: center;
    }
    
    .script-card {
        background: linear-gradient(135deg, var(--bg-secondary), var(--bg-card));
        border-left: 4px solid var(--accent);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
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
                language_script = st.selectbox("Script Language", ["Hinglish", "English", "Hindi"])
                writing_style = st.selectbox("Writing Style", ["Let AI Decide", "Professional", "Casual"])
            
            with col2:
                language_text = st.selectbox("Text Language", ["English", "Hindi", "Hinglish"])
                location = st.text_input("Target Location", value="India")
                reels_count = st.slider("Reels to Analyze", 10, 50, 25, 5)
            
            # Start research button
            if st.button("🚀 Start Research", use_container_width=True):
                if not niche:
                    st.error("Please enter a content niche")
                else:
                    # Get initial timestamp
                    summary_df = fetch_sheet_data("InstaResearchData", "ResearchSummary")
                    initial_timestamp = summary_df['generatedAt'].iloc[0] if summary_df is not None and not summary_df.empty else None
                    
                    st.session_state.research_params = {
                        'niche': niche,
                        'initial_timestamp': initial_timestamp,
                        'start_time': datetime.now()
                    }
                    
                    with st.spinner("Initiating research..."):
                        success, message = call_n8n_workflow(niche, language_script, language_text, writing_style, location, reels_count)
                        if success:
                            st.session_state.checking_data = True
                            st.success("Research workflow started!")
                            st.info("Checking for results every 30 seconds...")
                            time.sleep(2)
                            st.rerun()
        
        # Check for updates
        if 'checking_data' in st.session_state and st.session_state.checking_data:
            params = st.session_state.research_params
            
            with st.spinner("⏳ Checking for results..."):
                data_ready, new_timestamp = check_data_ready(params['initial_timestamp'])
                
                if data_ready:
                    st.session_state.checking_data = False
                    st.session_state.show_results = True
                    st.success("✅ Research complete!")
                    time.sleep(1)
                    st.rerun()
                else:
                    elapsed = datetime.now() - params['start_time']
                    if elapsed.total_seconds() < 600:
                        time.sleep(30)
                        st.rerun()
                    else:
                        st.session_state.checking_data = False
                        st.warning("Research is taking longer than expected. Please refresh manually.")
        
        # Refresh button
        if 'research_params' in st.session_state:
            st.markdown("---")
            if st.button("🔄 Refresh Results"):
                st.rerun()
        
        # Display results
        if 'show_results' in st.session_state or 'research_params' in st.session_state:
            # Load data
            summary_df = fetch_sheet_data("InstaResearchData", "ResearchSummary")
            reels_df = fetch_sheet_data("InstaResearchData", "TopPerformingReels")
            scripts_df = fetch_sheet_data("InstaResearchData", "Top3ReelsIdeas")
            
            # Tabs
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Summary", "🎬 Top Reels", "✨ Script Ideas", "📈 Raw Data"])
            
            # Summary Tab
            with tab1:
                if summary_df is not None and not summary_df.empty:
                    st.markdown(f"**Generated:** {summary_df['generatedAt'].iloc[0]}")
                    
                    if 'niche_summary' in summary_df.columns:
                        st.markdown("### Niche Analysis")
                        st.info(summary_df['niche_summary'].iloc[0])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if 'posting_schedule' in summary_df.columns:
                            st.markdown("**📅 Posting Schedule**")
                            st.success(summary_df['posting_schedule'].iloc[0])
                    
                    with col2:
                        if 'content_calendar' in summary_df.columns:
                            st.markdown("**📆 Content Calendar**")
                            st.warning(summary_df['content_calendar'].iloc[0])
            
            # Top Reels Tab
            with tab2:
                if reels_df is not None and not reels_df.empty:
                    for idx, row in reels_df.head(10).iterrows():
                        with st.container():
                            st.markdown(f"<div class='reel-card'>", unsafe_allow_html=True)
                            
                            # Rank and caption
                            rank = row['rank'] if 'rank' in row else idx + 1
                            st.markdown(f"### #{rank} - Top Performing Reel")
                            
                            caption = str(row['caption'])[:200] + "..." if len(str(row['caption'])) > 200 else row['caption']
                            st.write(caption)
                            
                            # Metrics
                            col1, col2, col3, col4, col5 = st.columns(5)
                            
                            with col1:
                                views = row.get('views', row.get('videoPlayCount', 0))
                                st.metric("Views", format_number(views))
                            
                            with col2:
                                likes = row.get('likesCount', 0)
                                st.metric("Likes", format_number(likes))
                            
                            with col3:
                                comments = row.get('comments', 0)
                                st.metric("Comments", format_number(comments))
                            
                            with col4:
                                shares = row.get('reshareCount', 0)
                                st.metric("Shares", format_number(shares))
                            
                            with col5:
                                engagement = row.get('engagement_rate', calculate_engagement_rate(likes, views))
                                st.metric("Engagement", f"{float(engagement):.2f}%")
                            
                            # Link and user
                            if 'url' in row and pd.notna(row['url']):
                                st.markdown(f"[View Reel]({row['url']})")
                            
                            if 'ownerUsername' in row and pd.notna(row['ownerUsername']):
                                st.caption(f"@{row['ownerUsername']}")
                            
                            st.markdown("</div>", unsafe_allow_html=True)
            
            # Script Ideas Tab
            with tab3:
                if scripts_df is not None and not scripts_df.empty:
                    for idx, row in scripts_df.iterrows():
                        with st.container():
                            st.markdown("<div class='script-card'>", unsafe_allow_html=True)
                            
                            rank = row['rank'] if 'rank' in row else idx + 1
                            st.markdown(f"### 💡 Idea #{rank}: {row.get('script_title', 'Untitled')}")
                            
                            if 'viral_potential_score' in row:
                                st.success(f"Viral Potential: {row['viral_potential_score']}/100")
                            
                            # Meta info
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.markdown(f"**Duration:** {row.get('estimated_duration', 'N/A')}")
                            with col2:
                                st.markdown(f"**Audience:** {str(row.get('target_audience', 'N/A'))[:50]}...")
                            with col3:
                                st.markdown(f"**Trigger:** {str(row.get('emotional_trigger', 'N/A'))[:50]}...")
                            
                            # Script preview
                            if 'full_text' in row and pd.notna(row['full_text']):
                                with st.expander("View Full Script"):
                                    st.text_area("", row['full_text'], height=200, disabled=True)
                            
                            # Script components
                            with st.expander("Script Structure"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    if 'script_hook' in row:
                                        st.info(f"**Hook:** {row['script_hook']}")
                                    if 'script_buildup' in row:
                                        st.info(f"**Buildup:** {row['script_buildup']}")
                                with col2:
                                    if 'script_value' in row:
                                        st.success(f"**Value:** {row['script_value']}")
                                    if 'script_cta' in row:
                                        st.warning(f"**CTA:** {row['script_cta']}")
                            
                            st.markdown("</div>", unsafe_allow_html=True)
            
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