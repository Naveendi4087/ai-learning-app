import streamlit as st
from modules import db, helpers, psychometrics, curriculum
import numpy as np
# *** Import the component classes for direct method calling in 0.17.3 ***
from catsim.selection import MaxInfoSelector 
from catsim.estimation import NumericalSearchEstimator 

helpers.set_page_styling()

st.set_page_config(page_title="Final Assessment", page_icon="🏆", layout="centered")

if 'user_id' not in st.session_state or 'selected_subject' not in st.session_state:
    st.page_link("pages/0_Login.py", label="Go to Login", icon="🔑")
    st.stop()

subject = st.session_state['selected_subject']
user_id = st.session_state['user_id']
st.title(f"Final Assessment for {subject}")

# --- PROGRESS & ATTEMPT CHECK ---
progress = db.get_or_create_progress(user_id, subject)
attempt_num = progress.get('final_assessment_attempts', 0) + 1 # Use .get for robustness

if progress['status'] == 'completed':
    st.success(f"You have already mastered the {subject} module!")
    
    # User-friendly score display (NEW CONVEYANCE)
    final_level = helpers.get_ability_level(progress['irt_theta_final'])
    initial_level = helpers.get_ability_level(progress['irt_theta_initial'])
    
    st.metric(label="Your Final Proficiency Level", value=f"{final_level}")
    st.markdown(f"**Learning Gain:** You improved from a **{initial_level}** to a **{final_level}** proficiency level. Keep up the great work!")

    if st.button("View Your Profile", type="secondary"):
        st.switch_page("pages/5_Profile.py")
    st.stop()

# Get mastery status for locking retries
all_bkt_data = db.get_all_bkt_models_for_subject(user_id, subject)
all_mastered = all(model['prob_knows'] >= 0.95 for model in all_bkt_data)

if progress['irt_theta_final'] is not None and progress['status'] == 'learning':
    # User previously failed and is in 'learning' status
    final_level = helpers.get_ability_level(progress['irt_theta_final'])
    st.warning(f"Your previous attempt ({attempt_num - 1}) resulted in a **{final_level}** level. You need to re-achieve **full mastery** (95% P(Knows) on ALL topics) before attempting the exam again.")
    
    if all_mastered:
        st.success("✅ **Great job!** All required topics are mastered again. You are ready for the next attempt.")
        if st.button(f"Start Assessment Attempt {attempt_num}", type="primary"):
            # Reset final theta and update status/attempts for the new test
            db.update_progress(user_id, subject, irt_theta_final=None, status='assessing')
            st.rerun()
    else:
        st.error("❌ **Action Required:** Some topics have fallen below the 95% mastery threshold. Please return to the Learning Path to review.")
    
    st.page_link("pages/3_Learning_Path.py", label="Go to Review Mode", icon="📚")
    st.stop()

if progress['status'] != 'assessing':
    st.info("You must complete the initial learning path before taking the final assessment.")
    st.page_link("pages/3_Learning_Path.py", label="Back to Learning Path")
    st.stop()

# Display the current attempt number for the active assessment state
if 'cat_simulator_final' not in st.session_state:
    st.session_state.current_attempt = attempt_num
st.subheader(f"Attempt: {st.session_state.current_attempt}")

# --- CAT SIMULATOR INITIALIZATION ---
if 'cat_simulator_final' not in st.session_state:
    with st.spinner("Loading calibrated final exam..."):
        item_bank, item_map = psychometrics.get_irt_question_bank(subject, 'final')
        
        if item_bank is None or len(item_bank) < 20:
            st.error("No final exam bank found or not enough items. Cannot start assessment.")
            st.stop()
            
        TEST_LENGTH = 20 

        st.session_state.cat_simulator_final = psychometrics.initialize_cat_simulator(item_bank, TEST_LENGTH)
        st.session_state.cat_item_map_final = item_map
        st.session_state.cat_item_bank_final = item_bank
        
        # Initialize lists
        st.session_state.cat_administered_items_final = []
        st.session_state.cat_responses_final = []
        
        # Initialize theta based on initial score
        initial_theta = progress['irt_theta_initial'] or 0.0
        st.session_state.cat_current_theta_final = initial_theta
        
        st.session_state.cat_current_item_index_final = None

# --- RUN THE TEST ---
simulator = st.session_state.cat_simulator_final
item_map = st.session_state.cat_item_map_final
item_bank = st.session_state.cat_item_bank_final

q_num = len(st.session_state.cat_administered_items_final) + 1
# Use max_itens for catsim 0.17.3
TEST_LENGTH = simulator.stopper.max_itens 

test_is_complete = q_num > TEST_LENGTH

if not test_is_complete:
    st.header(f"Attempt {st.session_state.current_attempt}: Question {q_num} of {TEST_LENGTH}")
    
    # 1. Select the next item
    if st.session_state.cat_current_item_index_final is None:
        theta_estimate = st.session_state.cat_current_theta_final
        
        administered_indices = [idx for idx, r in st.session_state.cat_administered_items_final]
        
        #
        # Use KEYWORD ARGUMENTS for independence check to pass
        #
        next_item_sim_index = MaxInfoSelector.select(
            simulator.selector, # The 'self' instance
            items=item_bank,
            administered_items=administered_indices, 
            est_theta=theta_estimate
        )
        st.session_state.cat_current_item_index_final = next_item_sim_index
    
    # 2. Display the item
    item_sim_index = st.session_state.cat_current_item_index_final
    item_data = item_map[item_sim_index]
    
    #st.markdown(f"**Topic:** {item_data['topic_id']}") 
    st.markdown(item_data['question_text'])
    
    options = item_data['options']
    
    with st.form(key=f"cat_final_q_{item_sim_index}"):
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
            
            st.session_state.cat_administered_items_final.append((item_sim_index, is_correct))
            st.session_state.cat_responses_final.append(is_correct)
            
            # Extract administered indices AND responses
            administered_indices = [idx for idx, r in st.session_state.cat_administered_items_final]
            responses = [r for idx, r in st.session_state.cat_administered_items_final]
            
            #
            # Use KEYWORD ARGUMENTS for independence check to pass
            # NumericalSearchEstimator.estimate(self, items, administered_items, response_vector, est_theta, **kwargs)
            #
            theta_estimate = NumericalSearchEstimator.estimate(
                simulator.estimator, # The 'self' instance
                items=item_bank,
                administered_items=administered_indices,
                response_vector=responses,
                est_theta=st.session_state.cat_current_theta_final
            )
            st.session_state.cat_current_theta_final = float(theta_estimate)
            
            # Log to DB
            psychometrics.log_cat_response(
                user_id, 
                item_data['id'], 
                'final', 
                response_idx, 
                bool(is_correct), 
                float(theta_estimate)
            )
            
            # --- NEW: BKT Update for Final Exam ---
            # This is key for the remediation analysis!
            db.update_bkt_model(user_id, subject, item_data['topic_id'], is_correct)
            
            st.session_state.cat_current_item_index_final = None
            st.rerun()
else:
    # --- TEST IS COMPLETE ---
    st.success("🎉 Final Assessment Complete!")
    
    final_theta = st.session_state.cat_current_theta_final
    initial_theta = progress['irt_theta_initial'] or 0.0
    
    # User-friendly score interpretation (NEW CONVEYANCE)
    final_level = helpers.get_ability_level(final_theta)
    initial_level = helpers.get_ability_level(initial_theta)
    
    st.metric("Your Final Proficiency Level", f"{final_level}")
    st.markdown(f"**Learning Gain:** You successfully improved from the **{initial_level}** level to the **{final_level}** level during this module.")

    
    # --- Gap Analysis 2.0 ---
    PASSING_THRESHOLD_THETA = 1.0
    
    # Increment the attempt count for the next time (Crucial update)
    new_attempts = progress.get('final_assessment_attempts', 0) + 1 # Use .get for robustness

    if final_theta >= PASSING_THRESHOLD_THETA:
        st.success("### Congratulations! You passed the final assessment and demonstrated the required mastery.")
        st.balloons()
        db.update_progress(user_id, subject, irt_theta_final=final_theta, status='completed', final_assessment_attempts=new_attempts)
        st.page_link("pages/5_Profile.py", label="View Your Profile")
    else:
        st.error(f"### Assessment Failed (Attempt {new_attempts}). Your score places you at the {final_level} level.")
        st.warning(f"You need to reach the Intermediate Level or higher to pass.")
        
        # Set status back to 'learning' so the user is forced to re-master topics
        db.update_progress(user_id, subject, irt_theta_final=final_theta, status='learning', final_assessment_attempts=new_attempts)
        
        with st.spinner("Analyzing your results and generating remediation feedback..."):
            summary = db.get_student_model_summary(user_id, subject)
            if isinstance(summary, list):
                # Find topics where mastery (prob_knows) dropped significantly or is low
                weak_topics = sorted([s for s in summary if s['prob_knows'] < 0.7], key=lambda x: x['prob_knows'])
                
                if weak_topics:
                    st.warning("AI Tutor Feedback: What to Focus On")
                    st.write("Your mastery profile decreased in the following areas due to the assessment results. You must re-master these topics:")
                    for t in weak_topics:
                        st.markdown(f"- **{t['topic_name']}** (Current Mastery: {t['prob_knows']*100:.0f}%)")
                else:
                    st.info("Your individual topic mastery profile remains strong, but your overall ability score was too low. Review the entire curriculum before your next attempt.")

        st.page_link("pages/3_Learning_Path.py", label="Go to Review Mode", icon="📚")
    
    # Clean up session state
    keys_to_delete = [k for k in st.session_state if k.startswith('cat_')]
    for k in keys_to_delete:
        del st.session_state[k]