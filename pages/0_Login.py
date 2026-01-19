import streamlit as st
from modules import auth, db, helpers
from dotenv import load_dotenv

load_dotenv()

helpers.set_page_styling()
helpers.hide_sidebar()


def load_page_css():
    # Custom CSS with responsive background and theme support
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Base styling */
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main app background with animated gradient - LIGHTER COLORS */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #a8c0ff 0%, #c2e9fb 50%, #fbc2eb 100%);
        background-size: 200% 200%;
        animation: gradientShift 15s ease infinite;
    }
    
    /* Dark theme background */
    [data-theme="dark"] [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        background-size: 200% 200%;
        animation: gradientShift 15s ease infinite;
    }
    
    /* Subtle pattern overlay */
    [data-testid="stAppViewContainer"]::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-image: 
            radial-gradient(circle at 20% 50%, rgba(255, 255, 255, 0.3) 0%, transparent 50%),
            radial-gradient(circle at 80% 80%, rgba(255, 255, 255, 0.3) 0%, transparent 50%),
            linear-gradient(to bottom right, rgba(255, 255, 255, 0.1), transparent);
        pointer-events: none;
    }
    
    /* Gradient animation */
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Content container styling */
    [data-testid="stAppViewContainer"] > div:first-child {
        background: transparent;
    }
    
    /* Form cards with glassmorphism */
    [data-testid="stForm"] {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    [data-theme="dark"] [data-testid="stForm"] {
        background: rgba(30, 30, 30, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    
    /* Text styling for better readability - DARKER TEXT FOR LIGHT THEME */
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] ul {
        color: rgba(30, 30, 60, 0.95);
        text-shadow: 0 1px 2px rgba(255, 255, 255, 0.5);
    }
    
    /* Dark theme text */
    [data-theme="dark"] [data-testid="stMarkdownContainer"] h1,
    [data-theme="dark"] [data-testid="stMarkdownContainer"] p,
    [data-theme="dark"] [data-testid="stMarkdownContainer"] ul {
        color: rgba(255, 255, 255, 0.95);
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    /* Title styling */
    [data-testid="stMarkdownContainer"] h1 {
        font-weight: 700;
        font-size: 2.5rem;
        line-height: 1.2;
        margin-bottom: 1.5rem;
    }
    
    /* Button styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* Input field styling */
    [data-testid="stTextInput"] > div > div > input {
        border-radius: 8px;
    }
    
    /* Remove default padding for full-height effect */
    .block-container {
        padding-top: 3rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Responsive adjustments */
    @media (max-width: 768px) {
        [data-testid="stMarkdownContainer"] h1 {
            font-size: 2rem;
        }
        
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)


load_page_css()

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="AI Learning Agent",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- DATABASE & REDIRECT ---
conn = db.get_db_connection()
db.create_tables(conn)
conn.close()

if "user_id" in st.session_state:
    st.switch_page("pages/1_Home.py")

# --- STATE INITIALIZATION ---
if "form_view" not in st.session_state:
    st.session_state.form_view = "login"

# --- LAYOUT & CONTENT ---
left_col, right_col = st.columns([1.2, 1], gap="large")

# --- Left Column (Branding & Information) ---
with left_col:
    st.markdown(
        "<h1 style='font-weight: 700;'>Adaptive Learning Platform</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size: 1.1rem; opacity: 0.95;'>Master programming with an AI tutor that adapts to your learning style. Get personalized guidance, practice with real coding challenges, and track your progress as you develop your skills.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='opacity: 0.3; border-color: rgba(30,30,60,0.3);'>", unsafe_allow_html=True)
    st.markdown(
        """
        <ul style='font-size: 1.05rem; opacity: 0.95; list-style-type: none; padding-left: 0;'>
            <li style='margin-bottom: 0.8rem;'>✓ Personalized Learning Paths</li>
            <li style='margin-bottom: 0.8rem;'>✓ Interactive AI-Powered Coding Tutor</li>
            <li style='margin-bottom: 0.8rem;'>✓ Hands-On Programming Assignments</li>
            <li style='margin-bottom: 0.8rem;'>✓ Real-Time Progress Analytics</li>
        </ul>
        """,
        unsafe_allow_html=True,
    )

# --- Right Column (Login/Signup Card) ---
with right_col:
    # --- LOGIN VIEW ---
    if st.session_state.form_view == "login":
        st.title("Welcome Back")

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input(
                "Password", type="password", placeholder="Enter your password"
            )
            submitted = st.form_submit_button("Login")

            if submitted:
                user_id = auth.check_user(username, password)
                if user_id:
                    st.session_state["user_id"] = user_id
                    st.session_state["username"] = username
                    st.success("Logged in successfully! Redirecting...")
                    import time

                    time.sleep(1)
                    st.switch_page("pages/1_Home.py")
                else:
                    st.error("Invalid username or password.")

        # Use 3 columns for alignment: [spacer, text, button]
        _, col_text, col_btn = st.columns([1, 2, 1.1])
        with col_text:
            st.markdown(
                "<p style='text-align: right; margin-top: 10px; opacity: 0.8; color: rgba(30,30,60,0.9);'>Don't have an account?</p>",
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("Sign Up", key="switch-to-signup", type="secondary"):
                st.session_state.form_view = "signup"
                st.rerun()

    # --- SIGNUP VIEW ---
    else:
        st.title("Create Your Account")

        with st.form("signup_form"):
            new_username = st.text_input(
                "Choose a Username", placeholder="Create a unique username"
            )
            new_password = st.text_input(
                "Choose a Password",
                type="password",
                placeholder="Create a strong password",
            )
            submitted = st.form_submit_button("Sign Up")

            if submitted:
                if not new_username or not new_password:
                    st.error("Please fill out all fields.")
                else:
                    if auth.add_user(new_username, new_password):
                        st.success("Account created! Please log in.")
                        st.session_state.form_view = "login"
                        st.rerun()
                    else:
                        st.error("This username is already taken.")

        # Use 3 columns for alignment: [spacer, text, button]
        _, col_text, col_btn = st.columns([1, 2, 1.1])
        with col_text:
            st.markdown(
                "<p style='text-align: right; margin-top: 10px; opacity: 0.8; color: rgba(30,30,60,0.9);'>Already have an account?</p>",
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("Login", key="switch-to-login", type="secondary"):
                st.session_state.form_view = "login"
                st.rerun()