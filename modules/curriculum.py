import streamlit as st
from. import db
import json

@st.cache_data(ttl=3600, show_spinner=False)
def get_full_learning_path(subject):
    """
    Gets the ordered list of all topics for a subject.
    """
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.id, t.topic_name, ku.ku_code
        FROM topics t
        JOIN knowledge_units ku ON t.ku_id = ku.id
        WHERE t.subject = %s
        ORDER BY t.topic_order
        """,
        (subject,)
    )
    topics = cur.fetchall()
    cur.close()
    conn.close()
    return topics

@st.cache_data(ttl=600, show_spinner=False)
def get_pedagogical_content(topic_id, bloom_level, intention_type):
    """
    Retrieves a specific piece of pedagogical content from the BDI
    agent's "Intention Library".
    """
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT content, id FROM pedagogical_content
        WHERE topic_id = %s
        AND bloom_level = %s
        AND intention_type = %s
        """,
        (topic_id, bloom_level, intention_type)
    )
    content = cur.fetchone()
    cur.close()
    conn.close()
    
    if not content:
        st.error("We couldn't find the specific learning material for this section right now.")
        return {"content": "Error: Content not found.", "id": None}
        
    # Check if content is JSON (for quizzes)
    try:
        data = json.loads(content['content'])
        # If it's JSON, return the parsed data
        return {"content": data, "id": content['id']}
    except json.JSONDecodeError:
        # If not JSON, it's Markdown/text
        return {"content": content['content'], "id": content['id']}

@st.cache_data(ttl=600, show_spinner=False)
def get_remedial_options(topic_id, failed_bloom_level):
    """
    Finds available BDI intentions for a failed quiz.
    """
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT intention_type, id FROM pedagogical_content
        WHERE topic_id = %s
        AND bloom_level = %s
        AND intention_type IN (
            'Simple_Explanation', 
            'Worked_Example', 
            'Socratic_Question',
            'Hint_L1',
            'Hint_L2'
        )
        """,
        (topic_id, failed_bloom_level)
    )
    options = cur.fetchall()
    cur.close()
    conn.close()
    return options

def get_next_topic(subject, current_topic_id):
    """
    Gets the next topic in the learning path.
    """
    path = get_full_learning_path(subject)
    path_ids = [t['id'] for t in path]
    
    try:
        current_index = path_ids.index(current_topic_id)
        if current_index + 1 < len(path_ids):
            return path[current_index + 1] # Return the next topic record
        else:
            return None # End of path
    except ValueError:
        return None # Topic not in path?