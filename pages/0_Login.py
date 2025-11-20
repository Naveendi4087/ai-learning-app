import streamlit as st
from modules import auth, db, helpers
from dotenv import load_dotenv 

load_dotenv() 

helpers.set_page_styling()
helpers.hide_sidebar()

def load_page_css():
    with open("assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_page_css()

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Welcome - AI Learning Agent", page_icon="🤖", layout="wide", initial_sidebar_state="collapsed")

# --- DATABASE & REDIRECT ---
conn = db.get_db_connection()
db.create_tables(conn) 
conn.close() 

if 'user_id' in st.session_state:
    st.switch_page("pages/1_Home.py")

# --- STATE INITIALIZATION ---
if 'form_view' not in st.session_state:
    st.session_state.form_view = 'login'

# --- LAYOUT & CONTENT ---
left_col, right_col = st.columns([1.2, 1], gap="large")

# --- Left Column (Branding & Information) ---
with left_col:
    st.markdown(
        "<h1 style='color: #222; font-weight: 700;'>Personal AI Learning Assistant</h1>", 
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='color: #333; font-size: 1.1rem;'>Unlock your potential with a learning experience tailored just for you. Our intelligent assistant adapts to your skill level, guides you through complex topics, and helps you master any subject.</p>",
        unsafe_allow_html=True
    )
    st.markdown("<hr style='border-color: #333;'>", unsafe_allow_html=True)
    st.markdown(
        """
        <ul style='color: #333; font-size: 1.1rem; list-style-type: "✅ "; padding-left: 20px;'>
            <li>Personalized Learning Paths</li>
            <li>Interactive AI-Powered Tutor</li>
            <li>Comprehensive Assignments & Feedback</li>
            <li>Track and Visualize Your Progress</li>
        </ul>
        """,
        unsafe_allow_html=True
    )

# --- Right Column (Login/Signup Card) ---
with right_col:
    # --- LOGIN VIEW ---
    if st.session_state.form_view == 'login':
        st.title("Welcome Back! 👋")
        
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Login")

            if submitted:
                user_id = auth.check_user(username, password)
                if user_id:
                    st.session_state['user_id'] = user_id
                    st.session_state['username'] = username
                    st.success("Logged in successfully! Redirecting...")
                    import time
                    time.sleep(1)
                    st.switch_page("pages/1_Home.py")
                else:
                    st.error("Invalid username or password.")
        
        # Use 3 columns for alignment: [spacer, text, button]
        _, col_text, col_btn = st.columns([1, 2, 1.1])
        with col_text:
            st.markdown("<p style='text-align: right; margin-top: 10px;'>Don't have an account?</p>", unsafe_allow_html=True)
        with col_btn:
            if st.button("🚀 Sign Up", key="switch-to-signup", type="secondary"):
                st.session_state.form_view = 'signup'
                st.rerun()

    # --- SIGNUP VIEW ---
    else:
        st.title("Create Your Account 🚀")

        with st.form("signup_form"):
            new_username = st.text_input("Choose a Username", placeholder="Create a unique username")
            new_password = st.text_input("Choose a Password", type="password", placeholder="Create a strong password")
            submitted = st.form_submit_button("Sign Up")

            if submitted:
                if not new_username or not new_password:
                    st.error("Please fill out all fields.")
                else:
                    if auth.add_user(new_username, new_password):
                        st.success("Account created! Please log in.")
                        st.session_state.form_view = 'login'
                        st.rerun()
                    else:
                        st.error("This username is already taken.")

        # Use 3 columns for alignment: [spacer, text, button]
        _, col_text, col_btn = st.columns([1, 2, 1.1])
        with col_text:
            st.markdown("<p style='text-align: right; margin-top: 10px;'>Already have an account?</p>", unsafe_allow_html=True)
        with col_btn:
            if st.button("👋 Login", key="switch-to-login", type="secondary"):
                st.session_state.form_view = 'login'
                st.rerun()