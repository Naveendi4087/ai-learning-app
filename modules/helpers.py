import streamlit as st
import re
import json

def set_page_styling():
    """
    Injects CSS to hide the first two sidebar pages (app and Login)
    and applies any other global styles.
    """
    # Define the CSS to hide the pages
    hide_pages_css = """
    <style>
    /* Hide the main 'app' page link */
    [data-testid="stSidebarNav"] li:nth-child(1) {
        display: none !important;
    }
    /* Hide the 'Login' page link */
    [data-testid="stSidebarNav"] li:nth-child(2) {
        display: none !important;
    }
    </style>
    """
    st.markdown(hide_pages_css, unsafe_allow_html=True)

def hide_sidebar():
    """Hides the default Streamlit sidebar."""
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {
                display: none;
            }
        </style>
    """, unsafe_allow_html=True)

def load_css(file_path):
    """Loads a CSS file into the Streamlit app."""
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def extract_json_from_string(text):
    """
    Finds and extracts the first valid JSON object from a string.
    Handles cases where JSON is embedded in markdown code blocks.
    """
    # Regex to find content between ```json and ``` or just { and }
    # Suppressing S5857 because the suggested fix ([^}]*) breaks parsing of nested JSON objects.
    match = re.search(r'```json\s*(\{.*?\})\s*```|(\{.*?\})', text, re.DOTALL) # noqa: S5857
    if match:
        # Prioritize the first capturing group if it exists (for ```json), else use the second
        json_str = match.group(1) if match.group(1) else match.group(2)
        return json_str
    return text     

def parse_llm_json_content(llm_response, content_type='object'):
    """
    Finds and extracts a JSON object or array from a string.
    Returns the parsed JSON dictionary/list, or None on failure.
    """
    if content_type == 'array':
        regex = r'\[.*?\]'
    else: # content_type == 'object'
        regex = r'\{.*?\}'
        
    match = re.search(regex, llm_response, re.DOTALL) 
    
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None

def get_ability_level(theta):
    """
    Maps IRT Theta score (ability) to a human-readable proficiency level.
    Used for personalizing LLM prompts.
    """
    if theta is None:
        return "Absolute Beginner" # Default fallback
        
    if theta < -1.0:
        return "Absolute Beginner"
    elif theta < 0.0:
        return "Beginner"
    elif theta < 1.0:
        return "Intermediate"
    else:
        return "Proficient"
    
def apply_modern_sidebar_css():
    st.markdown("""
    <style>
        /* 1. Target all buttons inside the sidebar */
        [data-testid="stSidebar"] div.stButton > button {
            width: 100%;                /* Full width */
            text-align: left !important; /* Force left alignment */
            justify-content: flex-start !important; /* Flexbox alignment to start */
            padding-left: 15px !important;
            border: 1px solid #f0f2f6;  /* Very subtle border */
            background-color: transparent; /* Transparent background */
            color: #31333F;             /* Dark grey text */
            border-radius: 8px;         /* Rounded corners */
            transition: all 0.2s ease-in-out; /* Smooth hover animation */
        }

        /* 2. Hover Effect for all buttons */
        [data-testid="stSidebar"] div.stButton > button:hover {
            background-color: #f0f2f6;  /* Light grey on hover */
            border-color: #dce0e6;
            transform: translateX(5px); /* Slight move to right on hover */
        }

        /* 3. Styling the 'Active' Button (The Red one in your image) */
        /* We target the button that has the 'primary' type */
        [data-testid="stSidebar"] div.stButton > button[kind="primary"] {
            background-color: #E8F0FE !important; /* Light Blue background (Change to match your brand) */
            color: #1967D2 !important;            /* Dark Blue text */
            border: 1px solid #1967D2 !important;
            font-weight: 600;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); /* Subtle shadow */
        }
        
        /* 4. Remove the default red border if Streamlit forces it */
        [data-testid="stSidebar"] div.stButton > button[kind="primary"]:focus {
            outline: none;
            box-shadow: none;
        }
    </style>
    """, unsafe_allow_html=True) 