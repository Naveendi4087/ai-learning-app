import streamlit as st
from modules import llm, db, helpers, curriculum
import json
import re

def extract_json_object(text):
    """Finds and extracts the first JSON object from a string."""
    match = re.search(r'\{.*?\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None

helpers.set_page_styling()

st.set_page_config(page_title="Learning Path", page_icon="📚", layout="wide")

helpers.apply_modern_sidebar_css()

if 'user_id' not in st.session_state or 'selected_subject' not in st.session_state:
    st.page_link("pages/0_Login.py", label="Go to Login", icon="🔑")
    st.stop()

subject = st.session_state['selected_subject']
user_id = st.session_state['user_id']

# --- Load Curriculum Path (Cached in curriculum module) ---
learning_path = curriculum.get_full_learning_path(subject)
if not learning_path:
    st.error(f"Curriculum path for {subject} not found.")
    st.stop()
    
topics = {t['id']: t for t in learning_path}
topic_ids = [t['id'] for t in learning_path]

# --- Get Progress & Mode ---
progress_data = db.get_or_create_progress(user_id, subject)
failed_assignment = progress_data['assignment_score'] is not None and progress_data['status'] == 'learning'
revise_mode_flag = st.session_state.get('revise_mode', False)
review_mode = failed_assignment or revise_mode_flag

if review_mode:
    st.info("📖 You are in **Review Mode**. All lessons are unlocked.")
else:
    st.title(f"🚀 Your {subject.capitalize()} Learning Path")

# --- CALCULATE PROGRESS FRONTIER (Fix for Sidebar Locking) ---
# We need to know the furthest topic the user has reached to handle locking correctly.
first_unmastered_id = topic_ids[0]
all_bkt_data = db.get_all_bkt_models_for_subject(user_id, subject)
bkt_model_map = {model['topic_id']: model for model in all_bkt_data}

for t_id in topic_ids:
    model = bkt_model_map.get(t_id, {'prob_knows': 0.0})
    if model['prob_knows'] < 0.95:
        first_unmastered_id = t_id
        break
else:
    # If loop completes without break, all are mastered. Set to last topic.
    first_unmastered_id = topic_ids[-1]

progress_index = topic_ids.index(first_unmastered_id)

# --- Set Initial Viewing Topic ---
if 'viewing_topic_id' not in st.session_state:
    st.session_state.viewing_topic_id = first_unmastered_id

viewing_id = st.session_state.viewing_topic_id
current_topic = topics[viewing_id]
current_topic_name = current_topic['topic_name']
current_viewing_index = topic_ids.index(viewing_id)

# --- Sidebar Navigation (FIXED FOR PERFORMANCE) ---
st.sidebar.header("Course Outline")

# --- ICON LEGEND ---
with st.sidebar.expander("ℹ️ Icon Legend", expanded=False):
    st.markdown("""
- 🔒 : **Locked** (Complete previous topic first)
- 📖 : **Unlocked** (Ready to learn)
- ▶️ : **Current** (You are here)
- ✅ : **Fully Mastered** (Score > 95%)
""")
# -----------------------

for topic_record in learning_path:
    t_id = topic_record['id']
    t_name = topic_record['topic_name']
    
    btn_type = "secondary"
    
    # Instant lookup
    model = bkt_model_map.get(t_id, {'prob_knows': 0.0}) 
    prob_knows = model['prob_knows']
    
    topic_record_index = topic_ids.index(t_id)
    
    # Locking Logic uses progress_index
    is_unlocked = review_mode or topic_record_index <= progress_index
    
    icon = "🔒"
    if prob_knows > 0.95:
        icon = "✅"
    elif is_unlocked:
        icon = "📖"
        
    if t_id == viewing_id:
        icon = "▶️"
        btn_type = "primary"

    if st.sidebar.button(f"{icon} {t_name}", key=f"topic_{t_id}", disabled=not is_unlocked, type=btn_type):
        st.session_state.viewing_topic_id = t_id
        # Clear all state for the new topic
        for key in list(st.session_state.keys()):
            if key.startswith('agent_') or key.startswith('bdi_'):
                del st.session_state[key]
        st.rerun()

if failed_assignment:
    st.sidebar.markdown("---")
    if st.sidebar.button("Ready to Retake Assignment", type="primary"):
        db.update_progress(user_id, subject, status='assessing')
        st.switch_page("pages/4_Assignments.py")

# --- BDI AGENT STATE MACHINE ---
def get_state_key(key_name):
    return f"bdi_{viewing_id}_{key_name}"

# --- DEFINING KEYS ---
BDI_STATE = get_state_key('bdi_state')
REMEDIATION_VIEW = get_state_key('remediation_view')
LAST_FAILED_LEVEL = get_state_key('last_failed_level')
LAST_QUIZ_CHOICE = get_state_key('last_quiz_choice')
LAST_QUIZ_EXPLANATION = get_state_key('last_quiz_explanation')
CODING_CHALLENGE_KEY = get_state_key('coding_challenge_text')
CODING_FEEDBACK_KEY = get_state_key('coding_feedback')

# Get current topic model
current_model = bkt_model_map.get(viewing_id, {'prob_knows': 0.0})
is_topic_mastered = current_model['prob_knows'] > 0.95

if BDI_STATE not in st.session_state:
    
    # 1. If Mastered (>0.95), FORCE LESSON VIEW (Review Mode)
    if is_topic_mastered:
        st.session_state[BDI_STATE] = 'initial_lesson'
        
    # 2. If High Competence (0.70 - 0.95), offer the skip prompt.
    elif current_model['prob_knows'] > 0.70: 
        st.session_state[BDI_STATE] = 'skip_lesson_prompt'
        
    # 3. Otherwise, standard lesson flow.
    else:
        st.session_state[BDI_STATE] = 'initial_lesson'

topic_state = st.session_state[BDI_STATE]

st.header(f"{current_topic_name}")
st.caption(f"Knowledge Unit: {current_topic['ku_code']}")

# --- State 0: Skip Lesson Prompt (Proactive Agent) ---
if topic_state == 'skip_lesson_prompt':
    st.info("🧠 **Agent Analysis:** Our records show you likely know this topic!")
    st.write("You can skip the lesson and go straight to the quiz, or review the material first.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Review Lesson Anyway"):
            st.session_state[BDI_STATE] = 'initial_lesson'
            st.rerun()
    with col2:
        if st.button("Skip to Understanding Quiz", type="primary"):
            lesson_content_key = get_state_key("lesson")
            if lesson_content_key in st.session_state:
                del st.session_state[lesson_content_key]
            st.session_state[BDI_STATE] = 'understanding_quiz'
            st.rerun()

# -----------------------------------------------------
# --- State 1: Initial Lesson (PERSONALIZED CONTENT) ---
# -----------------------------------------------------
elif topic_state == 'initial_lesson':
    content_key = get_state_key("lesson")
    
    if content_key not in st.session_state:
        st.session_state[content_key] = None # Initialize content to None
        
        with st.spinner("Personalizing lesson content based on your skill level..."):
            
            # 1. Get User Proficiency Level
            current_theta = progress_data['irt_theta_initial']
            user_level = helpers.get_ability_level(current_theta)
            
            # 2. Construct the Adaptive Prompt
            llm_prompt = f"""
            You are an expert computer science tutor.
            Create a lesson for the subject: '{subject}'
            Topic: '{current_topic_name}'
            
            TARGET STUDENT LEVEL: {user_level} (Theta: {current_theta})
            
            INSTRUCTIONS FOR ADAPTATION:
            - If 'Absolute Beginner' or 'Beginner': Use real-world analogies (e.g., cooking, traffic) to explain concepts. Keep code examples extremely simple. Avoid complex jargon.
            - If 'Intermediate': Focus on standard practices, syntax nuances, and efficiency.
            - If 'Proficient': Focus on memory management, edge cases, optimization, and under-the-hood mechanics.
            
            FORMAT:
            - Return the content in clear Markdown.
            - Include one code example relevant to the level.
            """
            
            # 3. Generate Content via LLM
            llm_content = llm.ask_ai(llm_prompt, language=subject)
            
            # 4. Check LLM Content
            if llm_content and len(llm_content) > 100:
                st.session_state[content_key] = llm_content
                if not is_topic_mastered:
                    st.success(f"✨ Content adapted for **{user_level}** level.")
            else:
                # 5. DB FALLBACK
                st.warning("⚠️ LLM generation delay. Loading standard curriculum.")
                lesson = curriculum.get_pedagogical_content(viewing_id, 'Explain', 'Lesson')
                st.session_state[content_key] = lesson['content']
                
            # --- Apply BKT Learning (P_TRANSIT) ---
            # *** Strictly disable calculation in Review Mode or if Mastered ***
            if not review_mode and not is_topic_mastered:
                db.apply_learning(user_id, subject, viewing_id)
    
    st.markdown(st.session_state[content_key])

    # --- VISUAL CUE & NAVIGATION LOGIC ---
    if is_topic_mastered:
        # REVIEW MODE VIEW
        st.info("🎓 **Topic Mastered:** You are viewing this lesson in **Review Mode**.")
        st.markdown("---")
        
        next_topic_index = current_viewing_index + 1
        if next_topic_index < len(topic_ids):
            next_tid = topic_ids[next_topic_index]
            next_tname = topics[next_tid]['topic_name']
            if st.button(f"Go to Next Topic: {next_tname} ➡️", type="primary"):
                st.session_state.viewing_topic_id = next_tid
                # Clear state
                for key in list(st.session_state.keys()):
                    if key.startswith('agent_') or key.startswith('bdi_'):
                        del st.session_state[key]
                st.rerun()
        else:
            # Check for Global Mastery to display the correct message
            all_mastered = all(model['prob_knows'] >= 0.95 for model in all_bkt_data)
            if all_mastered:
                st.success("You have completed **ALL** modules and achieved mastery!")
                st.page_link("pages/4_Assignments.py", label="Go to Final Assessment", icon="🏆")
            else:
                st.info("You have reached the end of the modules, but must return to unmastered topics to proceed.")
            
    else:
        # STANDARD LEARNING VIEW
        st.markdown("---")
        if st.button("I'm ready, let's check my understanding", type="primary"):
            
            # Clear Lesson content key on transition to Quiz
            if content_key in st.session_state:
                del st.session_state[content_key]
                
            st.session_state[BDI_STATE] = 'understanding_quiz'
            st.rerun()

# -----------------------------------------------------
# --- State 2: Remediation Hub (HYBRID CONTENT) ---
# -----------------------------------------------------
elif topic_state == 'failed_quiz':
    st.error("### Not quite... but that's okay! Let's review.")
    
    last_choice = st.session_state.get(LAST_QUIZ_CHOICE)
    last_explanation = st.session_state.get(LAST_QUIZ_EXPLANATION, "a key concept")
    
    if last_choice:
        st.warning(f"You answered: **{last_choice}**")
    
    st.info("🧠 **AI Tutor's Analysis**")
    st.markdown(f"It looks like you're struggling with the concept of: **{last_explanation}**")
    st.markdown("Let's try a different approach to clear this up.")
    
    failed_level = st.session_state.get(LAST_FAILED_LEVEL, 'Apply') 
    
    st.markdown("---")
    st.subheader("How would you like to review this?")

    remedial_options = curriculum.get_remedial_options(viewing_id, failed_level)
    
    llm_remedial_intentions = [
        {'intention_type': 'Worked_Example'},
        {'intention_type': 'Simple_Explanation'}
    ]
    
    existing_types = {opt['intention_type'] for opt in remedial_options}
    for opt in llm_remedial_intentions:
        if opt['intention_type'] not in existing_types:
            opt['id'] = 9999 + len(remedial_options) 
            remedial_options.append(opt)

    if not remedial_options:
        st.warning("No specific remedial content found for this. Please review the lesson.")
        st.session_state[BDI_STATE] = 'initial_lesson'
        st.rerun()
        
    cols = st.columns(len(remedial_options))
    for i, option in enumerate(remedial_options):
        intention_name = option['intention_type'].replace('_', ' ')
        with cols[i]:
            if st.button(intention_name, key=f"remedial_{option['id']}", use_container_width=True):
                db.log_learning_event(user_id, subject, viewing_id, "remedial_choice", option['intention_type'])
                st.session_state[REMEDIATION_VIEW] = option['intention_type']
                st.rerun()

    st.markdown("---")
    current_remedial_view = st.session_state.get(REMEDIATION_VIEW)
    
    if current_remedial_view:
        content_key = get_state_key(f"remedial_{current_remedial_view}") 
        
        with st.container(border=True):
            st.subheader(f"Re-Teaching: {current_remedial_view.replace('_', ' ')}")
            
            content_source = "DB"
            
            if content_key not in st.session_state:
                db_content = curriculum.get_pedagogical_content(viewing_id, failed_level, current_remedial_view)
                
                if db_content['id'] is not None:
                    st.session_state[content_key] = db_content['content']
                else:
                    content_source = "LLM"
                    with st.spinner(f"Generating a personalized {current_remedial_view.replace('_', ' ')}..."):
                        
                        current_theta = progress_data['irt_theta_initial']
                        user_level = helpers.get_ability_level(current_theta)

                        llm_prompt = f"""
                        The user is studying '{current_topic_name}' in {subject}.
                        TARGET LEVEL: {user_level} (Theta: {current_theta}).

                        SITUATION:
                        They just failed a quiz question. The specific concept they are confused about is:
                        **"{last_explanation}"**
                        
                        TASK:
                        Provide a **'{current_remedial_view.replace('_', ' ')}'** that *specifically* addresses this confusion.
                        
                        ADAPTATION INSTRUCTIONS:
                        - If {user_level} is 'Absolute Beginner' or 'Beginner': Use simple language and analogies.
                        - If {user_level} is 'Intermediate' or 'Proficient': Be precise and technical.

                        Return the content as Markdown.
                        """
                        
                        llm_content = llm.ask_ai(llm_prompt, language=subject)
                        st.session_state[content_key] = llm_content
            
            st.markdown(st.session_state[content_key])
            if content_source == "LLM":
                st.caption(f"✨ Remediation adapted for **{helpers.get_ability_level(progress_data['irt_theta_initial'])}** level.")
            
            if not review_mode and not is_topic_mastered:
                db.apply_learning(user_id, subject, viewing_id)

    st.markdown("---")
    if st.button("✅ I'm ready to try the quiz again", type="primary", use_container_width=True):
        bdi_state_key = BDI_STATE 
        
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith(f"bdi_{viewing_id}_") and k != bdi_state_key]
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
        
        st.session_state[bdi_state_key] = 'understanding_quiz'
        st.rerun()

# -----------------------------------------------------
# --- State 3: Understanding Quiz (HYBRID CONTENT) ---
# -----------------------------------------------------
elif topic_state == 'understanding_quiz':
    st.markdown("---")
    st.subheader("🌟 Check Your Understanding")
    
    content_key = get_state_key("quiz")
    lesson_content_key = get_state_key("lesson")
    
    if content_key not in st.session_state:
        quiz_data = None
        
        lesson_text = st.session_state.get(lesson_content_key, "")
        if not lesson_text:
            lesson_db_check = curriculum.get_pedagogical_content(viewing_id, 'Explain', 'Lesson')
            lesson_text = lesson_db_check['content'] if isinstance(lesson_db_check['content'], str) else "General Topic"

        with st.spinner("Loading quiz..."):
            llm_prompt = f"""
            Based **STRICTLY** on the following lesson text for '{current_topic_name}', generate one multiple-choice question for {subject}.
            The Bloom's level should be 'Apply'. Ensure the question is answerable ONLY from the provided text.

            --- LESSON CONTENT ---
            {lesson_text}
            ---

            Return ONLY a valid JSON object:
            {{"question": "...", "options": ["A", "B", "C", "D"], "correct_answer": "...", "explanation": "A brief explanation of WHY this is the correct answer and what concept it tests."}}
            """
            # NEW CODE SNIPPET (replace lines 408-422)

            llm_response = llm.ask_ai(llm_prompt, language=subject)
            quiz_data = extract_json_object(llm_response)

            # --- Start Validation and Fallback ---
            is_valid_llm_quiz = False
            if quiz_data and isinstance(quiz_data, dict):
                options_list = quiz_data.get('options', [])
                is_valid_llm_quiz = (
                    'question' in quiz_data and
                    len(options_list) == 4 and
                    all(isinstance(opt, str) and len(opt.strip()) > 0 for opt in options_list) and
                    quiz_data.get('correct_answer') in options_list and
                    'explanation' in quiz_data and len(quiz_data.get('explanation', '')) > 5
                )

            if is_valid_llm_quiz:
                st.session_state[content_key] = quiz_data
                st.info("✨ Unique quiz generated by the AI.")
            else:
                st.warning("⚠️ LLM quiz generation failed or malformed. Falling back to static quiz.")
                quiz_db = curriculum.get_pedagogical_content(viewing_id, 'Apply', 'Quiz_Question_Apply')

                if isinstance(quiz_db['content'], dict) and 'explanation' in quiz_db['content']:
                    st.session_state[content_key] = quiz_db['content']
                    # IMPORTANT: Since we used the fallback, update quiz_data for subsequent access
                    quiz_data = st.session_state[content_key] 
                else:
                    st.error("❌ Pre-authored quiz content missing or corrupted in database.")
                    # Final safety net assignment
                    quiz_data = {
                        "question": "Content Error: Quiz data unavailable.",
                        "options": ["A", "B", "C", "D"],
                        "correct_answer": "D",
                        "explanation": "Default topic concept"
                    }
                    st.session_state[content_key] = quiz_data
    quiz_data = st.session_state.get(content_key)

    if not quiz_data or 'question' not in quiz_data or 'explanation' not in quiz_data:
        st.error("Critical Error: Quiz data is malformed. Please go back and review the lesson.")
        if st.button("Go to Lesson"):
            st.session_state[BDI_STATE] = 'initial_lesson'
            st.rerun()
        st.stop()

    question = quiz_data.get('question')
    options = quiz_data.get('options')
    correct_answer = quiz_data.get('correct_answer')
    explanation = quiz_data.get('explanation')
    
    radio_key = get_state_key("quiz_radio")
    user_choice = st.radio(question, options, index=None, key=radio_key)
    
    if st.button("Submit Answer"):
        is_correct = (user_choice == correct_answer)
        
        # *** Do not update BKT if reviewed ***
        if not is_topic_mastered:
            db.update_bkt_model(user_id, subject, viewing_id, is_correct)
        
        if is_correct:
            st.balloons()
            st.success("✅ Theory Verified! Proceeding to Coding Challenge...")
            db.log_learning_event(user_id, subject, viewing_id, "quiz_pass")
            
            # --- TRANSITION TO CODING CHALLENGE ---
            st.session_state[BDI_STATE] = 'coding_challenge'
            st.rerun()
        else:
            st.session_state[BDI_STATE] = 'failed_quiz'
            st.session_state[LAST_FAILED_LEVEL] = 'Apply'

            error_details = {
                "selected_option": user_choice,
                "correct_option": correct_answer,
                "question_text": question,
                "explanation_shown": explanation
            }
            import json
            log_payload = json.dumps(error_details)
            
            st.session_state[LAST_QUIZ_CHOICE] = user_choice
            st.session_state[LAST_QUIZ_EXPLANATION] = explanation

            db.log_learning_event(user_id, subject, viewing_id, "quiz_fail", log_payload)
            
            if REMEDIATION_VIEW in st.session_state:
                del st.session_state[REMEDIATION_VIEW]
            if content_key in st.session_state:
                del st.session_state[content_key]
                
            st.rerun()

# ==========================================
# STATE 4: CODING CHALLENGE (Practical Check)
# ==========================================
elif topic_state == 'coding_challenge':
    st.markdown("---")
    st.subheader("💻 Practical Coding Challenge")
    st.info("Prove your mastery by writing code. The AI will grade your logic.")

    # 1. Generate the Challenge
    if CODING_CHALLENGE_KEY not in st.session_state:
        with st.spinner("Generating a challenge for you..."):
            current_theta = progress_data['irt_theta_initial']
            user_level = helpers.get_ability_level(current_theta)
            
            prompt = f"""
            Generate a coding problem for {subject} on the topic '{current_topic_name}'.
            TARGET LEVEL: {user_level}.
            
            REQUIREMENTS:
            - The problem must test the core concept of {current_topic_name}.
            - If {user_level} is 'Absolute Beginner' or 'Beginner': Keep it simple (e.g., print statement or simple math).
            - If {user_level} is 'Intermediate' or 'Proficient': Include edge cases or specific constraints.
            
            OUTPUT FORMAT:
            Return ONLY the problem description in Markdown. Do not give the solution.
            """
            challenge_text = llm.ask_ai(prompt, language=subject)
            st.session_state[CODING_CHALLENGE_KEY] = challenge_text

    st.markdown(st.session_state[CODING_CHALLENGE_KEY])

    # 2. User Input Area
    default_code = ""
    if subject == 'C':
        default_code = "#include <stdio.h>\n\nint main() {\n    // Write your code here\n    return 0;\n}"
    elif subject == 'Python':
        default_code = "# Write your python code here\n"

    user_code = st.text_area("Your Solution:", value=default_code, height=250, key="code_area")

    if st.button("Submit Solution 🚀", type="primary"):
        if len(user_code) < 10:
            st.warning("Please write some code first!")
        else:
            with st.spinner("AI Tutor is reviewing your code..."):
                # 3. Grading Logic
                grade_prompt = f"""
                Topic: {current_topic_name} ({subject})
                Problem: {st.session_state[CODING_CHALLENGE_KEY]}
                
                Student Solution:
                ```
                {user_code}
                ```
                
                Evaluate this solution.
                1. Is it syntactically correct?
                2. Does it solve the problem?
                
                Return a JSON object:
                {{
                    "is_correct": true/false,
                    "feedback": "Detailed feedback on what is right or wrong...",
                    "security_warning": "null or warning message if code is unsafe"
                }}
                """
                grade_resp = llm.ask_ai(grade_prompt, language=subject)
                grade_data = extract_json_object(grade_resp)
                
                if not grade_data:
                    grade_data = {"is_correct": False, "feedback": "Error analyzing code. Please try again."}

                st.session_state[CODING_FEEDBACK_KEY] = grade_data

    # 4. Display Feedback & Handle Progression
    if CODING_FEEDBACK_KEY in st.session_state:
        feedback = st.session_state[CODING_FEEDBACK_KEY]
        
        if feedback['is_correct']:
            # *** DISPLAY SUCCESS FEEDBACK IMMEDIATELY ***
            st.balloons() 
            st.success("🎉 **Topic Mastery Achieved!**") 
            st.write(f"**Feedback:** {feedback['feedback']}")
            st.info("You have demonstrated mastery of this topic. Click 'Continue' to move on.")
            
        # --- NAVIGATION BUTTON ---
        if st.button("Continue to Next Topic ➡️", type="primary"):
            
            # --- MASTERY MOMENT: Update BKT before checking global mastery ---
            if not is_topic_mastered:
                db.update_bkt_model(user_id, subject, viewing_id, True) 
                db.log_learning_event(user_id, subject, viewing_id, "coding_pass", json.dumps({"code": user_code}))
            
            next_topic = curriculum.get_next_topic(subject, viewing_id)
            
            if next_topic:
                # Case A: Not the last topic, continue sequentially
                st.session_state.viewing_topic_id = next_topic['id']
                
            else:
                # Case B: Last topic in the sequence. Check Global Mastery.
                
                # --- GLOBAL MASTERY CHECK ---
                # Get the latest BKT models (Crucial: Use fresh data after the current topic update)
                all_bkt_data_after_update = db.get_all_bkt_models_for_subject(user_id, subject)
                all_mastered = all(model['prob_knows'] >= 0.95 for model in all_bkt_data_after_update)
                
                if all_mastered:
                    # Global Mastery achieved -> Go to Assignment
                    st.balloons()
                    st.success("You have completed **ALL** required modules! Ready for the Final Assessment.")
                    db.update_progress(user_id, subject, status='assessing')
                    st.page_link("pages/4_Assignments.py", label="Start Final Assessment")
                    st.stop() # Ensure immediate redirection
                else:
                    # Global Mastery NOT achieved -> Redirect to the first unmastered topic
                    st.warning("You have completed the required topics sequentially, but still need to review previous modules to meet the mastery threshold (95%).")
                    
                    # Recreate the map from the fresh data (needed for the next step)
                    fresh_bkt_map = {model['topic_id']: model for model in all_bkt_data_after_update}
                    
                    # Find the first unmastered topic ID
                    first_unmastered_id = topic_ids[0]
                    for t_id in topic_ids:
                        model = fresh_bkt_map.get(t_id, {'prob_knows': 0.0})
                        if model['prob_knows'] < 0.95:
                            first_unmastered_id = t_id
                            break
                            
                    st.session_state.viewing_topic_id = first_unmastered_id
                    
            # --- RERUN / CLEAR STATE (applies to both sequential and remedial transition) ---
            keys_to_clear = [k for k in st.session_state.keys() if k.startswith(f"bdi_{viewing_id}_")]
            for k in keys_to_clear:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()
        else:
            # --- INCORRECT SUBMISSION FEEDBACK ---
            st.error("Not quite right yet.")
            st.write(f"**Feedback:** {feedback['feedback']}")
            st.info("Read the feedback, edit your code above, and submit again!")
            db.log_learning_event(user_id, subject, viewing_id, "coding_fail", json.dumps({"feedback": feedback['feedback']}))

# --- AI Tutor Chat (Always at the bottom) ---
st.markdown("---")
st.header("💬 AI Tutor Chat")
st.write(f"Ask any question about **{current_topic_name}** or general {subject} concepts.")

# Initialize chat history if it doesn't exist
if 'chat_history' not in st.session_state: 
    st.session_state.chat_history = []

# Initialize a tracker for the current chat topic
if 'chat_active_topic_id' not in st.session_state:
    st.session_state.chat_active_topic_id = viewing_id

# CHECK: Did the user switch topics?
if st.session_state.chat_active_topic_id != viewing_id:
    # Yes, they switched. Clear the history!
    st.session_state.chat_history = []
    # Update the tracker to the new topic
    st.session_state.chat_active_topic_id = viewing_id
# -----------------------------------------

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]): st.markdown(message["content"])

if user_prompt := st.chat_input(f"Ask me about {subject}..."):
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"): st.markdown(user_prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            db.log_learning_event(user_id, subject, viewing_id, "chat_query", user_prompt)
            
            chat_prompt = f"The user is currently studying the topic '{current_topic_name}'. Answer their question: \"{user_prompt}\""
            ai_response = llm.ask_ai(chat_prompt, language=subject)
            st.markdown(ai_response)
    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})