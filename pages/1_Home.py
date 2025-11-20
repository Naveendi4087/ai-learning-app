import streamlit as st
from modules import db, helpers

helpers.load_css("assets/style.css")
helpers.set_page_styling()
helpers.hide_sidebar()

st.set_page_config(page_title="Home", page_icon="🏠", layout="centered")

# --- CSS STYLING ---
st.markdown("""
<style>
    /* 1. SUBJECT CARDS (Secondary Buttons) */
    div.stButton > button[kind="secondary"] {
        width: 100%;
        height: 120px;
        border: 1px solid #e6e6e6;
        border-radius: 16px;
        background-color: #f8f9fa; /* Simple light background */
        color: #2c3e50;
        font-size: 1.3rem;
        font-weight: 600;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
        transition: all 0.2s ease-in-out;
    }
    
    /* Hover Effect for Cards */
    div.stButton > button[kind="secondary"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
        background-color: #e8f0fe; /* Slight blue tint on hover */
        border-color: #d2e3fc;
        color: #1967d2;
    }
    
    /* 2. LOGOUT BUTTON (Primary Button - Resetting styles) */
    /* We style this to look 'pale' and simple, removing the card look */
    div.stButton > button[kind="primary"] {
        width: auto;
        height: auto;
        background-color: transparent;
        color: #666;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 8px 24px;
        font-size: 0.9rem;
        font-weight: 500;
        box-shadow: none;
    }
    
    div.stButton > button[kind="primary"]:hover {
        background-color: #f1f1f1;
        color: #333;
        border-color: #ccc;
        transform: none;
        box-shadow: none;
    }
</style>
""", unsafe_allow_html=True)

if 'user_id' not in st.session_state:
    st.page_link("pages/0_Login.py", label="Go to Login", icon="🔑")
    st.stop()

st.title(f"Welcome, {st.session_state.get('username', 'Student')}!")
st.subheader("Select a subject to begin your learning journey.")

# --- DYNAMIC SUBJECT LOADING ---
try:
    available_subjects = db.get_available_subjects()
    if not available_subjects:
        st.warning("No subjects are currently available. Please contact an administrator.")
        st.stop()
except Exception as e:
    st.error(f"Error loading subjects from database: {e}")
    st.stop()

st.markdown("###") 

cols = st.columns(3) 
col_index = 0

for subject in available_subjects:
    with cols[col_index % 3]:
        if st.button(subject, use_container_width=True, key=f"subject_{subject}"):
            st.session_state['selected_subject'] = subject
            
            if 'revise_mode' in st.session_state:
                del st.session_state['revise_mode']
                
            progress = db.get_or_create_progress(st.session_state['user_id'], subject)
            if progress['irt_theta_initial'] is None:
                st.switch_page("pages/2_Placement_Quiz.py")
            else:
                st.switch_page("pages/3_Learning_Path.py")
    col_index += 1

st.markdown("---")

if st.button("Logout", type="primary"):
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()