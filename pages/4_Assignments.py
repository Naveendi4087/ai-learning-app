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
st.title(f"🏆 Final Assessment for {subject}")

progress = db.get_or_create_progress(user_id, subject)

if progress['status'] == 'completed':
    st.success(f"You have already mastered the {subject} module!")
    st.metric(label="Your Final Ability Score (Theta)", value=f"{progress['irt_theta_final']:.3f}")
    st.metric(label="Learning Gain (Theta)", value=f"{(progress['irt_theta_final'] - progress['irt_theta_initial']):.3f}")
    st.page_link("pages/5_Profile.py", label="View Your Profile", icon="👤")
    st.stop()

if progress['irt_theta_final'] is not None and progress['status'] == 'learning':
    st.warning(f"Your previous final score was {progress['irt_theta_final']:.3f}. Review the lessons and try again when you're ready.")
    if st.button("Try a New Assessment", type="primary"):
        db.update_progress(user_id, subject, status='assessing')
        st.rerun()
    st.page_link("pages/3_Learning_Path.py", label="Go to Review Mode", icon="📚")
    st.stop()

if progress['status'] != 'assessing':
    st.info("You must complete the learning path before taking the final assessment.")
    st.page_link("pages/3_Learning_Path.py", label="Back to Learning Path")
    st.stop()

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
    st.header(f"Question {q_num} of {TEST_LENGTH}")
    
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
    
    st.markdown(f"**Topic:** {item_data['topic_id']}") 
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
            db.update_bkt_model(user_id, subject, item_data['topic_id'], is_correct)
            
            st.session_state.cat_current_item_index_final = None
            st.rerun()
else:
    # --- TEST IS COMPLETE ---
    st.success("🎉 Final Assessment Complete!")
    
    final_theta = st.session_state.cat_current_theta_final
    initial_theta = progress['irt_theta_initial'] or 0.0
    learning_gain = final_theta - initial_theta
    
    st.metric("Your Final Ability Estimate (Theta)", f"{final_theta:.3f}")
    st.metric("Your Initial Ability Estimate (Theta)", f"{initial_theta:.3f}")
    st.metric("Total Learning Gain", f"{learning_gain:+.3f}")
    
    # --- Gap Analysis 2.0 ---
    PASSING_THRESHOLD_THETA = 1.0
    
    if final_theta >= PASSING_THRESHOLD_THETA and learning_gain > 0:
        st.success("### Congratulations! You passed and demonstrated significant learning.")
        st.balloons()
        db.update_progress(user_id, subject, irt_theta_final=final_theta, status='completed')
        st.page_link("pages/5_Profile.py", label="View Your Profile")
    else:
        st.error(f"### Your final ability score is {final_theta:.3f}. You need more practice.")
        db.update_progress(user_id, subject, irt_theta_final=final_theta, status='learning')
        
        with st.spinner("Analyzing your results and generating feedback..."):
            summary = db.get_student_model_summary(user_id, subject)
            if isinstance(summary, list):
                weak_topics = sorted([s for s in summary if s['prob_knows'] < 0.7], key=lambda x: x['prob_knows'])
                
                if weak_topics:
                    st.warning("AI Tutor Feedback: What to Focus On")
                    st.write("Our analysis shows you should focus on the following topics:")
                    for t in weak_topics:
                        st.markdown(f"- **{t['topic_name']}** (Current Mastery: {t['prob_knows']*100:.0f}%)")
                else:
                    st.info("Your mastery profile looks strong, but you haven't yet reached the passing threshold. Keep reviewing!")

        st.page_link("pages/3_Learning_Path.py", label="Go to Review Mode", icon="📚")
    
    # Clean up session state
    keys_to_delete = [k for k in st.session_state if k.startswith('cat_')]
    for k in keys_to_delete:
        del st.session_state[k]