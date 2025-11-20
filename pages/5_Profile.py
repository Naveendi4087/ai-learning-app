import streamlit as st
import json
from modules import db, helpers, curriculum
import pandas as pd
import plotly.graph_objects as go

helpers.set_page_styling()
st.set_page_config(page_title="My Profile", page_icon="👤", layout="wide")

st.markdown("""
<style>
    /* --- 1. CARD STYLING --- */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
        background-color: #ffffff;
        border-radius: 16px;
        padding: 25px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        border: 1px solid #f0f2f5;
    }

    /* --- 2. CUSTOM TABS (Clean Pill Style - NO GRAY LINE) --- */
    /* Hide the default bottom border line */
    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }
    /* Hide the sliding highlight line */
    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }
    /* Gap between buttons */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    /* Tab Button Style */
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 20px;
        padding: 0 20px;
        background-color: white;
        border: 1px solid #e0e0e0;
        color: #5f6368;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    /* Active Tab Style */
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #e8f0fe !important;
        color: #1967d2 !important;
        border-color: #1967d2 !important;
    }

    /* --- 3. BADGES & STATS --- */
    .status-badge {
        background-color: #e6f4ea;
        color: #137333;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        border: 1px solid #ceead6;
    }
    .status-badge.completed {
        background-color: #e8f0fe;
        color: #1967d2;
        border-color: #d2e3fc;
    }

    .stat-box {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        border: 1px solid #eff2f5;
        min-height: 100px; /* Ensure consistent height */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .stat-value {
        font-size: 1.4rem; /* Slightly smaller to fit "Absolute Beginner" */
        font-weight: 800;
        color: #202124;
        line-height: 1.2;
    }
    .stat-label {
        font-size: 0.8rem;
        color: #5f6368;
        font-weight: 600;
        text-transform: uppercase;
        margin-top: 5px;
    }

    /* --- 4. COURSE TITLE --- */
    .course-title {
        font-size: 1.6rem;
        font-weight: 800;
        color: #1a73e8;
        margin: 0;
    }
    
    /* --- 5. FOOTER SPACING --- */
    .card-spacer {
        height: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- Helpers ---
def get_ability_level(theta):
    if theta is None: return "Not Taken"
    if theta < -1.0: return "Absolute Beginner"
    elif theta < 0.0: return "Beginner"
    elif theta < 1.0: return "Intermediate"
    else: return "Proficient"

def get_mastery_color(prob_knows):
    if prob_knows < 0.4: return '#ea4335' 
    elif prob_knows < 0.7: return '#fbbc04' 
    elif prob_knows < 0.95: return '#4285f4' 
    else: return '#34a853' 

# --- Custom HTML Progress Bar ---
def render_custom_progress_bar(percent):
    bar_color = "#1a73e8" if percent < 1.0 else "#34a853"
    width_pct = int(percent * 100)
    
    html = f"""
    <div style="margin-top: 5px; margin-bottom: 15px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
            <span style="font-weight:600; color:#3c4043; font-size:0.9rem;">Overall Progress</span>
            <span style="font-weight:700; color:{bar_color}; font-size:0.9rem;">{width_pct}%</span>
        </div>
        <div style="width: 100%; background-color: #f1f3f4; border-radius: 10px; height: 12px;">
            <div style="width: {width_pct}%; background-color: {bar_color}; height: 12px; border-radius: 10px; transition: width 0.5s ease-in-out;"></div>
        </div>
    </div>
    """
    return html

if 'user_id' not in st.session_state:
    st.page_link("pages/0_Login.py", label="Go to Login", icon="🔑")
    st.stop()

# --- HEADER ---
initial = st.session_state.get('username', 'S')[0].upper()
st.markdown(f"""
<div style="display: flex; align-items: center; gap: 20px; margin-bottom: 30px; padding: 10px;">
    <div style="
        background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%);
        color: white;
        width: 70px;
        height: 70px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        font-weight: bold;
        box-shadow: 0 4px 10px rgba(26, 115, 232, 0.3);
    ">
        {initial}
    </div>
    <div>
        <h1 style="margin:0; font-size: 2.2rem; color: #202124;">{st.session_state.get('username', 'Student')}'s Dashboard</h1>
        <p style="margin:0; color: #5f6368; font-size: 1rem;">Track your mastery, continue learning, and analyze your growth.</p>
    </div>
</div>
""", unsafe_allow_html=True)

all_progress = db.get_all_user_progress(st.session_state['user_id'])
all_subjects = db.get_available_subjects()
user_subjects = [p['subject'] for p in all_progress]

active_courses = []
not_started_courses = []

for p in all_progress:
    if p['irt_theta_initial'] is not None:
        active_courses.append(p)

for sub in all_subjects:
    if sub not in user_subjects:
        not_started_courses.append(sub)
    else:
        p = next((x for x in all_progress if x['subject'] == sub), None)
        if p and p['irt_theta_initial'] is None:
             not_started_courses.append(sub)

# --- TABS ---
tab1, tab2 = st.tabs(["🔥 Active Courses", "📚 Course Catalog"])

with tab1:
    if not active_courses:
        st.info("You haven't started any courses yet. Check the Catalog!")
    
    for p in active_courses:
        subject = p['subject']
        
        # --- MAIN CARD CONTAINER ---
        with st.container(border=True):
            
            # 1. Header Row
            head_c1, head_c2, head_c3 = st.columns([0.6, 4, 1.5])
            with head_c1:
                st.markdown("<div style='font-size:36px;'>📘</div>", unsafe_allow_html=True)
            with head_c2:
                st.markdown(f"<div style='padding-top:5px;' class='course-title'>{subject}</div>", unsafe_allow_html=True)
            with head_c3:
                status_class = "completed" if p['status'] == 'completed' else ""
                status_text = "COMPLETED" if p['status'] == 'completed' else "IN PROGRESS"
                st.markdown(f"<div style='text-align:right;'><span class='status-badge {status_class}'>{status_text}</span></div>", unsafe_allow_html=True)

            st.markdown("<div class='card-spacer'></div>", unsafe_allow_html=True)

            # 2. Metrics
            path = curriculum.get_full_learning_path(subject)
            total_topics = len(path)
            mastery_data = db.get_student_model_summary(st.session_state['user_id'], subject)
            topics_mastered = 0
            if isinstance(mastery_data, list):
                 topics_mastered = sum(1 for m in mastery_data if m.get('prob_knows', 0) > 0.95)
            
            progress_percent = topics_mastered / total_topics if total_topics > 0 else 0
            theta = p['irt_theta_initial']
            theta_final = p['irt_theta_final']
            
            # 3. Stat Boxes
            st.markdown(f"""
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">
                <div class="stat-box">
                    <div class="stat-value">{topics_mastered}/{total_topics}</div>
                    <div class="stat-label">Topics Mastered</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{get_ability_level(theta)}</div>
                    <div class="stat-label">Starting Level</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" style="color: #188038;">{get_ability_level(theta_final) if theta_final else 'Learning'}</div>
                    <div class="stat-label">Current Ability</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 4. Progress Bar
            st.markdown(render_custom_progress_bar(progress_percent), unsafe_allow_html=True)

            st.markdown("<div class='card-spacer'></div>", unsafe_allow_html=True)

            # 5. Action Footer
            foot_c1, foot_c2 = st.columns([4, 1])
            
            with foot_c1:
                with st.expander("📊 View Topic Details"):
                    if isinstance(mastery_data, list):
                        df = pd.DataFrame(mastery_data)
                        if 'prob_knows' in df.columns:
                            df['prob_knows_percent'] = (df['prob_knows'] * 100).round(0)
                            df['color'] = df['prob_knows'].apply(get_mastery_color)
                            
                            fig = go.Figure(go.Bar(
                                x=df['prob_knows'],
                                y=df['topic_name'],
                                orientation='h',
                                marker_color=df['color'],
                                text=df['prob_knows_percent'].astype(str) + '%',
                                textposition='auto',
                                marker_cornerradius=5
                            ))
                            fig.update_layout(
                                margin=dict(l=0, r=0, t=0, b=0),
                                height=300,
                                xaxis=dict(showgrid=False, showticklabels=False),
                                yaxis=dict(showgrid=False),
                                plot_bgcolor='rgba(0,0,0,0)',
                                paper_bgcolor='rgba(0,0,0,0)'
                            )
                            st.plotly_chart(fig, use_container_width=True)
            
            with foot_c2:
                 if p['status'] == 'completed':
                     st.button("Review Course", key=f"rev_{subject}", use_container_width=True)
                 else:
                     st.button("Continue Learning 🚀", key=f"cont_{subject}", type="primary", use_container_width=True, on_click=lambda s=subject: st.session_state.update(selected_subject=s) or st.switch_page("pages/3_Learning_Path.py"))

with tab2:
    st.subheader("Available Courses")
    if not_started_courses:
        cols = st.columns(3)
        for i, sub in enumerate(not_started_courses):
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"### 🚀 {sub}")
                    st.caption("Start your journey in this subject.")
                    st.markdown("---")
                    if st.button(f"Start {sub}", key=f"start_{sub}", use_container_width=True):
                        st.session_state['selected_subject'] = sub
                        db.get_or_create_progress(st.session_state['user_id'], sub)
                        st.switch_page("pages/2_Placement_Quiz.py")
    else:
        st.success("🎉 You have started all available courses!")