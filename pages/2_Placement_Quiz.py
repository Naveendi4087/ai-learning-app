import streamlit as st
from modules import db, helpers, psychometrics, curriculum
import numpy as np
# *** Import the component classes for direct method calling in 0.17.3 ***
from catsim.selection import MaxInfoSelector 
from catsim.estimation import NumericalSearchEstimator 


helpers.set_page_styling()

st.set_page_config(page_title="Placement Quiz", page_icon="🧠", layout="centered")

if 'user_id' not in st.session_state or 'selected_subject' not in st.session_state:
    st.page_link("pages/0_Login.py", label="Go to Login", icon="🔑")
    st.stop()

subject = st.session_state['selected_subject']
user_id = st.session_state['user_id']
progress = db.get_or_create_progress(user_id, subject)

def get_ability_level(theta):
    """Maps IRT Theta score (ability) to a human-readable proficiency level."""
    if theta < -1.0:
        return "Absolute Beginner"
    elif theta < 0.0:
        return "Beginner"
    elif theta < 1.0:
        return "Intermediate"
    else:
        return "Proficient"


# Check if quiz is already completed
if progress['irt_theta_initial'] is not None:
    st.title(f"{subject} Placement Quiz")
    st.info("You have already completed the placement quiz.")
    
    # Display level based on existing score
    final_theta = progress['irt_theta_initial']
    level = get_ability_level(final_theta)
    
    # MODIFICATION 1: Remove Theta from st.metric delta
    st.metric("Your Starting Knowledge Level", level) 
    
    if st.button("Continue Your Learning Path", type="primary"):
        st.switch_page("pages/3_Learning_Path.py")
    st.stop()

st.title(f"{subject} Placement Quiz")
st.write("This adaptive quiz will precisely measure your starting knowledge. It adapts to your skill level, so don't worry if questions seem to get harder or easier.")

# --- CAT SIMULATOR INITIALIZATION ---
if 'cat_simulator' not in st.session_state:
    with st.spinner("Loading calibrated question bank..."):
        item_bank, item_map = psychometrics.get_irt_question_bank(subject, 'placement')
        
        if item_bank is None or len(item_bank) == 0:
            st.error("No question bank found. Cannot start quiz.")
            st.stop()

        TEST_LENGTH = 10 # Number of items in the placement quiz
        
        if len(item_bank) < TEST_LENGTH:
            st.error(f"Not enough items in bank ({len(item_bank)}) to run a {TEST_LENGTH}-item test.")
            st.stop()

        st.session_state.cat_simulator = psychometrics.initialize_cat_simulator(item_bank, TEST_LENGTH)
        st.session_state.cat_item_map = item_map
        st.session_state.cat_item_bank = item_bank
        
        st.session_state.cat_administered_items = []
        st.session_state.cat_responses = [] 
        st.session_state.cat_current_theta = 0.0
        st.session_state.cat_current_item_index = None

# --- RUN THE TEST ---
simulator = st.session_state.cat_simulator
item_map = st.session_state.cat_item_map
item_bank = st.session_state.cat_item_bank 

q_num = len(st.session_state.cat_administered_items) + 1
# Use max_itens for catsim 0.17.3
TEST_LENGTH = simulator.stopper.max_itens 

test_is_complete = q_num > TEST_LENGTH

if not test_is_complete:
    st.header(f"Question {q_num} of {TEST_LENGTH}")
    
    # 1. Select the next item (if we don't have one)
    if st.session_state.cat_current_item_index is None:
        theta_estimate = st.session_state.cat_current_theta
        
        administered_indices = [idx for idx, r in st.session_state.cat_administered_items]
        
        #
        # *** Use KEYWORD ARGUMENTS for independence check to pass ***
        #
        next_item_sim_index = MaxInfoSelector.select(
            simulator.selector, # The 'self' instance
            items=item_bank,
            administered_items=administered_indices, # Pass indices
            est_theta=theta_estimate
        )
        st.session_state.cat_current_item_index = next_item_sim_index
    
    # 2. Display the item
    item_sim_index = st.session_state.cat_current_item_index
    item_data = item_map[item_sim_index]
    
    #st.markdown(f"**Topic ID:** {item_data['topic_id']}") 
    st.markdown(item_data['question_text'])
    
    options = item_data['options']
    
    with st.form(key=f"cat_q_{item_sim_index}"):
        user_choice_idx = st.radio(
            "Select your answer:",
            options=options,
            index=None,
            format_func=lambda x: x, 
            label_visibility="collapsed"
        )
        submitted = st.form_submit_button("Submit Answer")

    if submitted:
        if user_choice_idx is None:
            st.warning("Please select an answer.")
        else:
            # 3. Process the response
            response_idx = options.index(user_choice_idx)
            is_correct = (response_idx == item_data['correct_option_index'])
            
            # Store for simulator
            st.session_state.cat_administered_items.append((item_sim_index, is_correct))
            st.session_state.cat_responses.append(is_correct)
            
            # Extract administered indices AND responses
            administered_indices = [idx for idx, r in st.session_state.cat_administered_items]
            responses = [r for idx, r in st.session_state.cat_administered_items]

            #
            # *** Call estimate directly on the class, passing the instance as 'self' ***
            #
            theta_estimate = NumericalSearchEstimator.estimate(
                simulator.estimator, # The 'self' instance
                items=item_bank, 
                administered_items=administered_indices, 
                response_vector=responses,
                est_theta=st.session_state.cat_current_theta # Pass current estimate for reference
            )
            st.session_state.cat_current_theta = float(theta_estimate)
            
            # Log to DB
            psychometrics.log_cat_response(
                user_id, 
                item_data['id'], 
                'placement', 
                response_idx, 
                bool(is_correct), 
                float(theta_estimate)
            )
            
            # Clear for next question
            st.session_state.cat_current_item_index = None
            st.rerun()

else:
    # --- TEST IS COMPLETE ---
    st.success("🎉 Quiz Complete! Your knowledge profile is built.")
    
    final_theta = st.session_state.cat_current_theta
    level = get_ability_level(final_theta) # Get level for final display
    
    # *** Display proficiency level***
    st.metric("Your Starting Knowledge Level", level)
    
    with st.spinner("Creating your personalized Student Brain"):
        # The "Psychometric Hand-off"
        initial_prob_knows = psychometrics.map_theta_to_bkt_prior(final_theta)
        
        # 1. Seed the BKT model
        db.seed_bkt_model_from_irt(user_id, subject, initial_prob_knows)
        
        # 2. Update the progress record
        db.update_progress(user_id, subject, irt_theta_initial=final_theta, status='learning')
        
        # 3. Find the starting topic
        path = curriculum.get_full_learning_path(subject)
        if path:
            st.session_state.current_topic_id = path[0]['id']
            
    st.info(f"We've analyzed your results and set your initial knowledge profile. You are assessed as **{level}** with a starting mastery probability of {initial_prob_knows*100:.0f}%.")
    st.page_link("pages/3_Learning_Path.py", label="Start Your Learning Path!")
    
    # Clean up session state
    keys_to_delete = [k for k in st.session_state if k.startswith('cat_')]
    for k in keys_to_delete:
        del st.session_state[k]