import streamlit as st
import psycopg2
import os
import json
import hashlib
from psycopg2.extras import DictCursor
import numpy as np

# --- BKT Model Parameters (Research-Backed) ---
# These are your model's "assumptions" about learning.
P_TRANSIT = 0.15  # Probability of learning (transitioning) after an activity
P_GUESS = 0.20    # Probability of guessing a correct answer
P_SLIP = 0.10     # Probability of making a mistake even if you know it

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        # Use os.environ.get for flexibility (local.env or Streamlit Secrets)
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            # Access the secret key, not the whole object
            db_url = st.secrets["DATABASE_URL"]
            
        conn = psycopg2.connect(db_url)
        conn.cursor_factory = DictCursor
        return conn
    except Exception as e:
        st.error(f"Error connecting to database. Make sure your DATABASE_URL is set. Error: {e}")
        st.stop()

def create_tables(conn): # <--- Accepts 'conn'
    """Creates the necessary tables if they don't exist."""
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS progress (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            subject TEXT NOT NULL,
            
            -- OLD level (e.g., "beginner") is replaced by IRT score
            -- NEW: Store the IRT "theta" (ability) score
            irt_theta_initial REAL,
            irt_theta_final REAL,
            
            topic_index INTEGER DEFAULT 0, -- This is now legacy, BKT is primary
            status TEXT DEFAULT 'learning', -- learning, assessing, completed
            assignment_score INTEGER,

            final_assessment_attempts INTEGER DEFAULT 0,    
            
            UNIQUE(user_id, subject)
        )
    ''')

    # ---
    # --- SECTION 2: CURRICULUM & PEDAGOGY (REFACTOR)
    # ---
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_units (
            id SERIAL PRIMARY KEY,
            ku_code TEXT UNIQUE NOT NULL, -- e.g., "SDF-Fundamentals"
            ku_name TEXT NOT NULL,
            description TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            id SERIAL PRIMARY KEY,
            subject TEXT NOT NULL,        -- e.g., "C"
            ku_id INTEGER REFERENCES knowledge_units(id),
            topic_name TEXT NOT NULL,
            topic_order INTEGER, -- Used to order the path
            UNIQUE(subject, topic_name)
        )
    ''')
    
    # --- Create ENUM types *only if* they don't exist
    cur.execute("SELECT 1 FROM pg_type WHERE typname = 'bloom_level'")
    if cur.fetchone() is None:
        cur.execute('''
            CREATE TYPE bloom_level AS ENUM (
                'Explain',    -- (Bloom: Remember/Understand)
                'Apply',      -- (Bloom: Understand/Apply)
                'Evaluate',   -- (Bloom: Analyze/Evaluate)
                'Develop'     -- (Bloom: Create)
            )
        ''')
        
    cur.execute("SELECT 1 FROM pg_type WHERE typname = 'intention_type'")
    if cur.fetchone() is None:
        cur.execute('''
            CREATE TYPE intention_type AS ENUM (
                'Lesson',               -- Main teaching content
                'Worked_Example',       -- A fully solved problem
                'Socratic_Question',    -- A guided question
                'Hint_L1',              -- A vague hint
                'Hint_L2',              -- A specific hint
                'Quiz_Question_Apply',  -- An "Apply" level MCQ
                'Quiz_Question_Eval',   -- An "Evaluate" level MCQ
                'Code_Challenge',       -- A problem statement
                'Simple_Explanation'    -- A simpler explanation
            )
        ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS pedagogical_content (
            id SERIAL PRIMARY KEY,
            topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
            bloom_level bloom_level NOT NULL,
            intention_type intention_type NOT NULL,
            content TEXT NOT NULL, -- This is the Markdown, code, or JSON
            author_notes TEXT,
            UNIQUE(topic_id, bloom_level, intention_type)
        )
    ''')

    # ---
    # --- SECTION 3: PSYCHOMETRICS (IRT/CAT)
    # ---
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS question_bank (
            id SERIAL PRIMARY KEY,
            topic_id INTEGER REFERENCES topics(id),
            question_text TEXT NOT NULL,
            options JSONB NOT NULL, -- e.g., ["A", "B", "C"]
            correct_option_index INTEGER NOT NULL, -- e.g., 0 for "A"
            irt_difficulty_b REAL NOT NULL DEFAULT 0.0,
            irt_discrimination_a REAL NOT NULL DEFAULT 1.0,
            irt_guessing_c REAL NOT NULL DEFAULT 0.25,
            
            -- Track which test this question is for
            test_type TEXT DEFAULT 'placement' -- 'placement' or 'final'
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS student_cat_responses (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            question_id INTEGER REFERENCES question_bank(id),
            test_type TEXT NOT NULL, -- 'placement' or 'final'
            response_index INTEGER,
            is_correct BOOLEAN,
            theta_estimate_after REAL, -- Store ability estimate after each answer
            timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ---
    # --- SECTION 4: STUDENT "BRAIN" (BKT) 
    # ---
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bkt_model (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            subject TEXT NOT NULL,
            
            -- This now links to the new topics table
            topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
            
            prob_knows REAL DEFAULT 0.0,
            misconceptions TEXT, -- Stored as JSON array string
            last_assessed TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, subject, topic_id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS learning_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            subject TEXT NOT NULL,
            topic_id INTEGER REFERENCES topics(id),
            event_type TEXT NOT NULL, 
            details TEXT,
            timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    cur.close()

# --- User & Progress Functions ---

def add_user_to_db(username, hashed_password):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            'INSERT INTO users (username, hashed_password) VALUES (%s, %s)',
            (username, hashed_password)
        )
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        return False
    finally:
        cur.close()
        conn.close()

def get_user_from_db(username):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = cur.fetchone() 
    cur.close()
    conn.close()
    return user

def get_or_create_progress(user_id, subject):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'SELECT * FROM progress WHERE user_id = %s AND subject = %s',
        (user_id, subject)
    )
    progress = cur.fetchone()
    if not progress:
        cur.execute(
            'INSERT INTO progress (user_id, subject) VALUES (%s, %s) RETURNING *',
            (user_id, subject)
        )
        progress = cur.fetchone()
        conn.commit()
    cur.close()
    conn.close()
    return progress

def update_progress(user_id, subject, irt_theta_initial=None, irt_theta_final=None, status=None, score=None, final_assessment_attempts=None):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Initialize lists
    query_parts = []
    params = []
    
    if irt_theta_initial is not None:
        query_parts.append("irt_theta_initial = %s")
        params.append(irt_theta_initial)
    if irt_theta_final is not None:
        query_parts.append("irt_theta_final = %s")
        params.append(irt_theta_final)
    if status is not None:
        query_parts.append("status = %s")
        params.append(status)
    if score is not None:
        query_parts.append("assignment_score = %s")
        params.append(score)
    if final_assessment_attempts is not None: 
        query_parts.append("final_assessment_attempts = %s")
        params.append(final_assessment_attempts)
        
    if not query_parts:
        return

    params.extend([user_id, subject])
    
    cur.execute(
        f'UPDATE progress SET {", ".join(query_parts)} WHERE user_id = %s AND subject = %s',
        tuple(params)
    )
    
    conn.commit()
    cur.close()
    conn.close()

def get_all_user_progress(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM progress WHERE user_id = %s', (user_id,))
    progress_records = cur.fetchall()
    cur.close()
    conn.close()
    return progress_records

# --- BKT "BRAIN" FUNCTIONS ---

def get_or_create_bkt_model(cur, user_id, subject, topic_id):
    """
    Gets or creates a BKT model entry.
    Note: Now uses topic_id instead of topic_name.
    """
    cur.execute(
        'SELECT * FROM bkt_model WHERE user_id = %s AND subject = %s AND topic_id = %s',
        (user_id, subject, topic_id)
    )
    model = cur.fetchone()
    
    if not model:
        cur.execute(
            'INSERT INTO bkt_model (user_id, subject, topic_id, prob_knows) VALUES (%s, %s, %s, %s) RETURNING *',
            (user_id, subject, topic_id, 0.0) # Start with 0% knowledge
        )
        model = cur.fetchone()
        cur.connection.commit() # Commit within the transaction
    return model

def update_bkt_model(user_id, subject, topic_id, is_correct, new_misconception=None):
    """Updates the BKT model based on a quiz answer."""
    conn = get_db_connection()
    cur = conn.cursor()
    model = get_or_create_bkt_model(cur, user_id, subject, topic_id)
    
    prob_knows_prior = model['prob_knows']
    
    if is_correct:
        # Student got it RIGHT
        prob_knows_if_learned = (prob_knows_prior * (1 - P_SLIP)) / (prob_knows_prior * (1 - P_SLIP) + (1 - prob_knows_prior) * P_GUESS)
    else:
        # Student got it WRONG
        prob_knows_if_learned = (prob_knows_prior * P_SLIP) / (prob_knows_prior * P_SLIP + (1 - prob_knows_prior) * (1 - P_GUESS))
    
    # This is the final, updated probability
    new_prob_knows = prob_knows_if_learned

    # Update misconceptions
    misconceptions = json.loads(model['misconceptions']) if model['misconceptions'] else []
    if new_misconception and new_misconception not in misconceptions:
        misconceptions.append(new_misconception)
    
    cur.execute(
        'UPDATE bkt_model SET prob_knows = %s, misconceptions = %s, last_assessed = CURRENT_TIMESTAMP WHERE id = %s',
        (new_prob_knows, json.dumps(misconceptions), model['id'])
    )
    conn.commit()
    cur.close()
    conn.close()

def apply_learning(user_id, subject, topic_id):
    """Applies the "learning" probability (P_TRANSIT) after an activity."""
    conn = get_db_connection()
    cur = conn.cursor()
    model = get_or_create_bkt_model(cur, user_id, subject, topic_id)
    
    prob_knows_prior = model['prob_knows']
    
    # P(Knows_New) = P(Knows_Old) + P(Not_Knows_Old) * P(Learns_Now)
    new_prob_knows = prob_knows_prior + (1 - prob_knows_prior) * P_TRANSIT
    
    cur.execute(
        'UPDATE bkt_model SET prob_knows = %s, last_assessed = CURRENT_TIMESTAMP WHERE id = %s',
        (new_prob_knows, model['id'])
    )
    conn.commit()
    cur.close()
    conn.close()

def get_bkt_model(user_id, subject, topic_id):
    """Gets a single BKT model record."""
    conn = get_db_connection()
    cur = conn.cursor()
    model = get_or_create_bkt_model(cur, user_id, subject, topic_id)
    cur.close()
    conn.close()
    return model

def get_student_model_summary(user_id, subject):
    """Gets the full knowledge profile for the agent."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # LEFT JOIN to include all topics
    # regardless of whether a BKT record exists yet.
    cur.execute(
        '''
        SELECT 
            t.topic_name, 
            b.prob_knows, 
            b.misconceptions 
        FROM topics t
        LEFT JOIN bkt_model b ON t.id = b.topic_id AND b.user_id = %s
        WHERE t.subject = %s
        ORDER BY t.topic_order
        ''',
        (user_id, subject)
    )
    model_records = cur.fetchall()
    cur.close()
    conn.close()
    
    if not model_records:
        return "No topics found for this subject."
        
    # Process the results to handle NULL prob_knows
    results = []
    for m in model_records:
        if m['prob_knows'] is None:
            results.append({
                'topic_name': m['topic_name'],
                'prob_knows': 0.0, # Default to 0
                'misconceptions': None
            })
        else:
            results.append(dict(m)) # Convert from DictRow
            
    return results

def seed_bkt_model_from_irt(user_id, subject, initial_prob):
    """
    Sets the initial P(Knows) for all topics for a user/subject.
    This "seeds the brain" from the IRT placement test.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all topic IDs for this subject
    cur.execute("SELECT id FROM topics WHERE subject = %s", (subject,))
    topic_rows = cur.fetchall()
    
    if not topic_rows:
        st.warning(f"No topics found for subject {subject} to seed BKT model.")
        return
        
    initial_prob_float = float(initial_prob)
    
    for row in topic_rows:
        topic_id = row['id']
        # Use get_or_create to insert/ignore
        model = get_or_create_bkt_model(cur, user_id, subject, topic_id)
        
        # Update the model with the new P(Prior)
        cur.execute(
            "UPDATE bkt_model SET prob_knows = %s WHERE id = %s",
            (initial_prob_float, model['id'])
        )
    
    conn.commit()
    cur.close()
    conn.close()

def log_learning_event(user_id, subject, topic_id, event_type, details=""):
    """Logs a specific learning interaction."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO learning_log (user_id, subject, topic_id, event_type, details) VALUES (%s, %s, %s, %s, %s)',
        (user_id, subject, topic_id, event_type, details)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_available_subjects():
    """
    Queries the database for a distinct list of all available subjects
    based on the topics loaded.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'SELECT DISTINCT subject FROM topics ORDER BY subject'
    )
    subjects = [row['subject'] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return subjects

# ---BKT Caching Function ---

@st.cache_data(ttl=60, show_spinner=False)
def get_bkt_model_cached(user_id, subject, topic_id):
    """
    Gets a single BKT model record, optimized with Streamlit caching 
    to speed up sidebar rendering.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    # Using get_or_create_bkt_model ensures a record exists for the topic
    model = get_or_create_bkt_model(cur, user_id, subject, topic_id) 
    cur.close()
    conn.close()
    return model

@st.cache_data(ttl=60, show_spinner=False)
def get_all_bkt_models_for_subject(user_id, subject):
    """
    Gets the *entire* BKT model profile for a user/subject
    in a single query.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 
            t.id AS topic_id, 
            t.topic_name, 
            b.prob_knows,
            b.misconceptions
        FROM topics t
        LEFT JOIN bkt_model b ON t.id = b.topic_id AND b.user_id = %s
        WHERE t.subject = %s
        ORDER BY t.topic_order
        """,
        (user_id, subject)
    )
    models = cur.fetchall()
    cur.close()
    conn.close()
    
    # Ensure a default record for any topics not yet in bkt_model
    results = []
    for m in models:
        if m['prob_knows'] is None:
            # This topic exists, but the user has no BKT record for it yet.
            # We'll just return the 0.0 probability
            results.append({
                'topic_id': m['topic_id'],
                'topic_name': m['topic_name'],
                'prob_knows': 0.0, 
                'misconceptions': None
            })
        else:
            # User has a valid BKT record
            results.append(dict(m)) # convert from DictRow to regular dict
            
    return results