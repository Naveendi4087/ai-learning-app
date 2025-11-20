import streamlit as st
from . import db
import numpy as np
from catsim.simulation import Simulator
from catsim.initialization import FixedPointInitializer
from catsim.selection import MaxInfoSelector
from catsim.estimation import NumericalSearchEstimator 
from catsim.stopping import MaxItemStopper

@st.cache_data(ttl=3600)
def get_irt_question_bank(subject, test_type='placement'):
    """
    Loads the IRT question bank from the database.
    """
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, topic_id, irt_difficulty_b, irt_discrimination_a, irt_guessing_c,
               question_text, options, correct_option_index
        FROM question_bank
        WHERE topic_id IN (SELECT id FROM topics WHERE subject = %s)
        AND test_type = %s
        """,
        (subject, test_type)
    )
    questions = cur.fetchall()
    cur.close()
    conn.close()
    
    if not questions:
        return None, None
        
    # Original format intention: [discrimination (a), difficulty (b), guessing (c)] (3PL)
    item_bank_3pl = []
    item_map = {} # maps simulator index to db record
    
    for i, q in enumerate(questions):
        disc = q['irt_discrimination_a'] if q['irt_discrimination_a'] is not None else 1.0
        diff = q['irt_difficulty_b'] if q['irt_difficulty_b'] is not None else 0.0
        guess = q['irt_guessing_c'] if q['irt_guessing_c'] is not None else 0.25
        
        item_bank_3pl.append([disc, diff, guess]) 
        item_map[i] = q 
        
    # *** FIX FOR CATSIM 0.17.3 INDEXERROR ***
    # The old catsim library internally assumes 4 parameters (4PL) for validation.
    # We must append a 4th column (upper asymptote, d=1.0) to avoid the IndexError.
    
    item_bank_3pl_np = np.array(item_bank_3pl)
    
    # Create an array of 1.0s for the 4th parameter (d)
    d_param = np.ones((item_bank_3pl_np.shape[0], 1))
    
    # Concatenate the 3PL parameters with the new d parameter
    item_bank = np.concatenate((item_bank_3pl_np, d_param), axis=1)
    
    # This item_bank now has the required (N x 4) shape: [a, b, c, d]
    return item_bank, item_map

def initialize_cat_simulator(item_bank, test_length=20):
    """
    Initializes a catsim Simulator object.
    
    *** MODIFIED FOR CATSIM 0.17.3: REMOVED ALL 'model' KWARGS ***
    """
    if item_bank is None or len(item_bank) == 0:
        return None
        
    # 1. Initializer: Start all students at theta = 0 (average)
    initializer = FixedPointInitializer(0)
    
    # 2. Selector: Initialize without 'model'
    selector = MaxInfoSelector()
    
    # 3. Estimator: Initialize without 'model'
    estimator = NumericalSearchEstimator()
    
    # 4. Stopper: Stop after a fixed number of questions
    stopper = MaxItemStopper(test_length) 
    
    # 5. Create the simulator (no 'model' keyword allowed)
    simulator = Simulator(
        item_bank,              
        1,                      
        initializer,            
        selector,               
        estimator,              
        stopper                 
    )
    
    return simulator

def map_theta_to_bkt_prior(theta):
    """
    Converts an IRT theta score (ability) into a BKT P(Prior) probability.
    """
    prob = 1 / (1 + np.exp(-theta))
    return np.clip(prob, 0.01, 0.99)

def log_cat_response(user_id, q_id, test_type, response_idx, is_correct, theta_after):
    """
    Logs the student's response to a CAT question.
    """
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO student_cat_responses 
        (user_id, question_id, test_type, response_index, is_correct, theta_estimate_after)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (user_id, q_id, test_type, response_idx, is_correct, theta_after)
    )
    conn.commit()
    cur.close()
    conn.close()