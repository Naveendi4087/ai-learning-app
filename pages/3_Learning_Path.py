import streamlit as st
from modules import llm, db, helpers, curriculum
import json
import re

def extract_json_object(text):
    """Finds and extracts the first JSON object from a string."""
    if not text: 
        return None
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

learning_path = curriculum.get_full_learning_path(subject)
if not learning_path:
    st.error(f"Curriculum path for {subject} not found.")
    st.stop()
    
topics = {t['id']: t for t in learning_path}
topic_ids = [t['id'] for t in learning_path]

progress_data = db.get_or_create_progress(user_id, subject)
failed_assignment = progress_data.get('assignment_score') is not None and progress_data.get('status') == 'learning'
revise_mode_flag = st.session_state.get('revise_mode', False)
review_mode = failed_assignment or revise_mode_flag

if review_mode:
    st.info("📖 You are in **Review Mode**. All lessons are unlocked.")
else:
    st.title(f"🚀 Your {subject.capitalize()} Learning Path")

first_unmastered_id = topic_ids[0]
all_bkt_data = db.get_all_bkt_models_for_subject(user_id, subject)
bkt_model_map = {model['topic_id']: model for model in all_bkt_data}

for t_id in topic_ids:
    model = bkt_model_map.get(t_id, {'prob_knows': 0.0})
    if model['prob_knows'] < 0.95:
        first_unmastered_id = t_id
        break
else:
    first_unmastered_id = topic_ids[-1]

progress_index = topic_ids.index(first_unmastered_id)

if 'viewing_topic_id' not in st.session_state:
    st.session_state.viewing_topic_id = first_unmastered_id

viewing_id = st.session_state.viewing_topic_id
current_topic = topics[viewing_id]
current_topic_name = current_topic['topic_name']
current_viewing_index = topic_ids.index(viewing_id)

st.sidebar.header("Course Outline")

for topic_record in learning_path:
    t_id = topic_record['id']
    t_name = topic_record['topic_name']
    
    btn_type = "secondary"
    model = bkt_model_map.get(t_id, {'prob_knows': 0.0}) 
    prob_knows = model['prob_knows']
    topic_record_index = topic_ids.index(t_id)
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
        for key in list(st.session_state.keys()):
            if key.startswith('bdi_'):
                del st.session_state[key]
        st.rerun()

def get_state_key(key_name):
    return f"bdi_{viewing_id}_{key_name}"

BDI_STATE = get_state_key('bdi_state')
AGENT_PLAN_KEY = get_state_key('agent_plan') 
LAST_QUIZ_DATA = get_state_key('last_quiz_data') 
CODING_CHALLENGE_KEY = get_state_key('coding_challenge_text')
CODING_FEEDBACK_KEY = get_state_key('coding_feedback')

current_model = bkt_model_map.get(viewing_id, {'prob_knows': 0.0})
is_topic_mastered = current_model['prob_knows'] > 0.95

if BDI_STATE not in st.session_state:
    if is_topic_mastered:
        st.session_state[BDI_STATE] = 'initial_lesson'
    elif current_model['prob_knows'] > 0.70: 
        st.session_state[BDI_STATE] = 'skip_lesson_prompt'
    else:
        st.session_state[BDI_STATE] = 'initial_lesson'

topic_state = st.session_state[BDI_STATE]

st.header(f"{current_topic_name}")
st.caption(f"Knowledge Unit: {current_topic['ku_code']}")

# =====================================================
# STATE 0: SKIP LESSON (Proactive Agent)
# =====================================================
if topic_state == 'skip_lesson_prompt':
    st.info("🧠 **Agent Analysis:** Our records show you likely know this topic!")
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

# =====================================================
# STATE 1: INITIAL LESSON (Personalized Content)
# =====================================================
elif topic_state == 'initial_lesson':
    content_key = get_state_key("lesson")
    
    if content_key not in st.session_state:
        st.session_state[content_key] = None
        with st.spinner("Personalizing lesson content based on your skill level..."):
            current_theta = progress_data['irt_theta_initial']
            user_level = helpers.get_ability_level(current_theta)
            
            base_content = curriculum.get_pedagogical_content(viewing_id, 'Explain', 'Lesson')
            base_text = base_content.get('content') if base_content else None
            
            is_valid_content = base_text and len(str(base_text)) > 20 and "error" not in str(base_text).lower()
            
            if is_valid_content:
                llm_prompt = f"""
                You are an expert tutor for {subject}.
                Target Student Level: {user_level}.
                
                BASE CONTENT: "{base_text}"

                INSTRUCTIONS:
                Rewrite the Base Content to match the student's level.
                - Absolute Beginner: Use analogies, simple English.
                - Proficient: concise, technical, focus on efficiency.
                - Ensure FACTS remain identical to the Base Content.
                """
            else:
                llm_prompt = f"""
                You are an expert tutor for {subject}.
                Target Student Level: {user_level}.
                Topic: {current_topic_name}
                
                INSTRUCTIONS:
                Write a comprehensive lesson on this topic.
                - Provide clear explanations.
                - Include code examples.
                - Adapt the complexity to the student's level.
                """
            
            llm_content = llm.ask_ai(llm_prompt, language=subject)
            
            if llm_content:
                st.session_state[content_key] = llm_content
            else:
                st.session_state[content_key] = base_text if is_valid_content else "Content unavailable. Please try refreshing."
                
            if not review_mode and not is_topic_mastered:
                db.apply_learning(user_id, subject, viewing_id)
    
    st.markdown(st.session_state[content_key])

    if is_topic_mastered:
        st.info("🎓 **Topic Mastered** (Review Mode)")
        next_topic_index = current_viewing_index + 1
        if next_topic_index < len(topic_ids):
            next_tid = topic_ids[next_topic_index]
            if st.button("Go to Next Topic ➡️", type="primary"):
                st.session_state.viewing_topic_id = next_tid
                for key in list(st.session_state.keys()):
                    if key.startswith('bdi_'):
                        del st.session_state[key]
                st.rerun()
        else:
             st.success("Module Completed! Check the Assignments page.")
    else:
        st.markdown("---")
        if st.button("I'm ready, let's check my understanding", type="primary"):
            st.session_state[BDI_STATE] = 'understanding_quiz'
            st.rerun()

# =====================================================
# STATE 2: AGENTIC REMEDIATION (The "Smart" Part)
# =====================================================
elif topic_state == 'failed_quiz':
    
    # 1. Retrieve Context
    quiz_context = st.session_state.get(LAST_QUIZ_DATA, {})
    
    # 2. TRIGGER AGENT ANALYSIS (If not done yet)
    if AGENT_PLAN_KEY not in st.session_state:
        with st.spinner("🤖 Agent is analyzing your error pattern..."):
            current_theta = progress_data['irt_theta_initial']
            user_level = helpers.get_ability_level(current_theta)
            
            # Call the new reasoning function in llm.py
            analysis = llm.agent_analyze_error(
                topic=current_topic_name,
                question=quiz_context.get('question', ''),
                wrong_answer=quiz_context.get('selected', ''),
                correct_answer=quiz_context.get('correct', ''),
                student_level=user_level
            )
            if analysis is None:
                analysis = {"diagnosis": "General review needed.", "strategy": "Simple Explanation"}
                
            st.session_state[AGENT_PLAN_KEY] = analysis
    
    agent_plan = st.session_state[AGENT_PLAN_KEY]
    
    # 3. Display Agent Reasoning (The "Transparent" AI)
    with st.container(border=True):
        st.markdown("### 🤖 AI Tutor Diagnosis")
        st.info(f"**Diagnosis:** {agent_plan.get('diagnosis', 'Analysis complete.')}")
        st.markdown(f"**Selected Strategy:** `{agent_plan.get('strategy', 'Review')}`")

    # 4. Generate Remedial Content based on Plan
    remedial_content_key = get_state_key("remedial_content")
    if remedial_content_key not in st.session_state:
        with st.spinner("Generating targeted remediation..."):
            strategy = agent_plan.get('strategy', 'Simple Explanation')
            
            remedial_prompt = f"""
            The student failed a question on {current_topic_name}.
            
            DIAGNOSIS: {agent_plan.get('diagnosis')}
            STRATEGY: {strategy}
            
            Task: Provide a short explanation or example using ONLY the '{strategy}' method. 
            Keep it strictly relevant to the diagnosis.
            """
            
            content = llm.ask_ai(remedial_prompt, language=subject)
            st.session_state[remedial_content_key] = content
            
            # Apply partial learning credit for remediation
            if not review_mode and not is_topic_mastered:
                 db.apply_learning(user_id, subject, viewing_id)

    st.markdown("### Remediation Lesson")
    st.markdown(st.session_state.get(remedial_content_key, "Content generating..."))

    st.markdown("---")
    if st.button("I understand now. Try Quiz Again", type="primary"):
        # Reset Logic
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith(f"bdi_{viewing_id}_")]
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
        st.session_state[BDI_STATE] = 'understanding_quiz'
        st.rerun()

# =====================================================
# STATE 3: UNDERSTANDING QUIZ (Agent-Validated & Memory-Aware)
# =====================================================
elif topic_state == 'understanding_quiz':
    st.markdown("---")
    st.subheader("🌟 Check Your Understanding")
    
    content_key = get_state_key("quiz")
    
    if content_key not in st.session_state:
        with st.spinner("Agent is retrieving your learning history and formulating a question..."):
            
            # 1. Fetch Lesson Content
            lesson_db = curriculum.get_pedagogical_content(viewing_id, 'Explain', 'Lesson')
            lesson_text = lesson_db.get('content')
            if not lesson_text or "Error" in str(lesson_text):
                lesson_text = f"Topic: {current_topic_name}"

            # 2. THE AGENTIC BRAIN: Fetch Past Misconceptions from DB
            bkt_record = db.get_bkt_model(user_id, subject, viewing_id)
            past_misconceptions = []
            if bkt_record and bkt_record['misconceptions']:
                try:
                    past_misconceptions = json.loads(bkt_record['misconceptions'])
                except:
                    past_misconceptions = []

            # 3. Construct the Adaptive Prompt
            memory_context = ""
            if past_misconceptions:
                memory_context = f"""
                ATTENTION: This student has previously struggled with these concepts: {", ".join(past_misconceptions)}.
                GENERATE A QUESTION THAT SPECIFICALLY TESTS THESE WEAKNESSES to verify they have fixed their understanding.
                """
            else:
                memory_context = "Generate a standard application-level question."

            llm_prompt = f"""
            Generate a multiple-choice question for {subject}: {current_topic_name}.
            
            CONTEXT: {lesson_text}
            
            AGENT MEMORY:
            {memory_context}
            
            Return JSON:
            {{"question": "...", "options": ["A", "B", "C", "D"], "correct_answer": "...", "explanation": "..."}}
            """
            
            quiz_data = extract_json_object(llm.ask_ai(llm_prompt, language=subject))
            
            # Fallback
            if not quiz_data or 'options' not in quiz_data:
                fallback = curriculum.get_pedagogical_content(viewing_id, 'Apply', 'Quiz_Question_Apply')
                quiz_data = fallback.get('content')
            
            st.session_state[content_key] = quiz_data

    quiz_data = st.session_state.get(content_key)
    
    # Final check for valid quiz data
    if not quiz_data or not isinstance(quiz_data, dict) or 'question' not in quiz_data:
         st.error("Quiz generation error. Reloading...")
         if content_key in st.session_state: del st.session_state[content_key]
         if st.button("Retry"): st.rerun()
         st.stop()

    question = quiz_data.get('question')
    options = quiz_data.get('options')
    correct_answer = quiz_data.get('correct_answer')
    
    radio_key = get_state_key("quiz_radio")
    user_choice = st.radio(question, options, index=None, key=radio_key)
    
    if st.button("Submit Answer"):
        if not user_choice:
            st.warning("Please select an option.")
        else:
            is_correct = (user_choice == correct_answer)
            
            # Only update BKT if not already mastered
            if not is_topic_mastered:
                db.update_bkt_model(user_id, subject, viewing_id, is_correct)
            
            if is_correct:
                st.balloons()
                st.success("✅ Correct! Proceeding to Coding Challenge...")
                db.log_learning_event(user_id, subject, viewing_id, "quiz_pass")
                st.session_state[BDI_STATE] = 'coding_challenge'
                st.rerun()
            else:
                # *** AGENTIC TRIGGER: MEMORY STORAGE ***
                misconception_text = quiz_data.get('explanation', 'General misunderstanding')
                
                if not is_topic_mastered:
                    try:
                        db.update_bkt_model(user_id, subject, viewing_id, False, new_misconception=misconception_text)
                    except TypeError:
                        db.update_bkt_model(user_id, subject, viewing_id, False)

                st.session_state[LAST_QUIZ_DATA] = {
                    "question": question,
                    "selected": user_choice,
                    "correct": correct_answer,
                    "explanation": quiz_data.get('explanation')
                }
                
                st.session_state[BDI_STATE] = 'failed_quiz'
                
                if AGENT_PLAN_KEY in st.session_state: del st.session_state[AGENT_PLAN_KEY]
                if get_state_key("remedial_content") in st.session_state: del st.session_state[get_state_key("remedial_content")]
                
                db.log_learning_event(user_id, subject, viewing_id, "quiz_fail", details=misconception_text)
                st.rerun()

# ==========================================
# STATE 4: CODING CHALLENGE (Context-Aware)
# ==========================================
elif topic_state == 'coding_challenge':
    st.markdown("---")
    st.subheader("💻 Practical Coding Challenge")
    st.info("Prove your mastery by writing code. The AI will grade your logic.")

    # 1. Generate the Challenge
    if CODING_CHALLENGE_KEY not in st.session_state:
        with st.spinner("Generating a challenge based on your current knowledge..."):
            current_theta = progress_data['irt_theta_initial']
            user_level = helpers.get_ability_level(current_theta)
            
            #RETRIEVE LESSON CONTEXT TO DEFINE SCOPE ---
            lesson_content_key = get_state_key("lesson")
            lesson_context = st.session_state.get(lesson_content_key, "")
            
            # Fallback if text is missing
            if not lesson_context or len(lesson_context) < 50:
                lesson_db = curriculum.get_pedagogical_content(viewing_id, 'Explain', 'Lesson')
                lesson_context = lesson_db.get('content', f"Topic: {current_topic_name}")

            # --- SCOPE GUARD PROMPT ---
            prompt = f"""
            Act as a Computer Science Examiner.
            Create a coding problem for {subject} on the topic '{current_topic_name}'.
            Target Difficulty: {user_level}.
            
            LESSON CONTEXT (The student just learned this):
            ------------------------------------------------
            {lesson_context[:1000]}... (truncated to save tokens)
            ------------------------------------------------
            
            STRICT RULES:
            1. **SCOPE GUARD**: The problem must be solvable using ONLY the concepts taught in the LESSON CONTEXT above.
               - Example: If the lesson only mentions 'printf', do NOT ask for 'scanf' (Input) or 'if/else'.
               - Example: If the lesson is about 'Variables', do not ask for 'Loops'.
            2. Describe the problem scenario clearly.
            3. Show an Example Output.
            4. 🛑 **NEGATIVE CONSTRAINT**: DO NOT WRITE THE SOLUTION CODE.
            5. The output must be the PROBLEM STATEMENT ONLY in Markdown.
            """
            challenge_text = llm.ask_ai(prompt, language=subject)
            st.session_state[CODING_CHALLENGE_KEY] = challenge_text

    st.markdown(st.session_state[CODING_CHALLENGE_KEY])

    # 2. Check Previous Status (To Lock UI)
    feedback_state = st.session_state.get(CODING_FEEDBACK_KEY)
    
    is_already_solved = False
    if feedback_state and feedback_state.get('is_correct'):
        is_already_solved = True

    # 3. User Input Area
    default_code = ""
    if subject == 'C':
        default_code = "#include <stdio.h>\n\nint main() {\n    // Write your code here\n    return 0;\n}"
    elif subject == 'Python':
        default_code = "# Write your python code here\n"

    # UI LOCK: Disable text area if solved
    user_code = st.text_area(
        "Your Solution:", 
        value=default_code, 
        height=250, 
        key="code_area",
        disabled=is_already_solved 
    )

    # 4. Action Buttons
    if not is_already_solved:
        if st.button("Submit Solution", type="primary"):
            if user_code.strip() == default_code.strip():
                st.warning("⚠️ You left the placeholder text. Please write your solution.")
            elif len(user_code) < 15:
                st.warning("⚠️ That doesn't look like enough code. Please write a full solution.")
            else:
                with st.spinner("Agent is reviewing your code..."):
                    # We also pass the lesson context to the grader so it doesn't grade too harshly
                    lesson_content_key = get_state_key("lesson")
                    lesson_context = st.session_state.get(lesson_content_key, "")

                    grade_prompt = f"""
                    You are a Context-Aware Code Evaluator.
                    
                    CONTEXT (What was taught):
                    {lesson_context[:500]}... (truncated)

                    THE CHALLENGE: "{st.session_state[CODING_CHALLENGE_KEY]}"
                    THE STUDENT'S SOLUTION: {user_code}
                    
                    STRICT GRADING RULES:
                    1. **PLACEHOLDER CHECK**: If code is empty/comments only, return is_correct: false.
                    2. **SYNTAX CHECK**: Is it valid {subject} code?
                    3. **LOGIC CHECK**: Does it solve the problem?
                    
                    Return JSON: {{"is_correct": true/false, "feedback": "Specific feedback..."}}
                    """
                    resp = llm.ask_ai(grade_prompt, language=subject)
                    extracted_data = extract_json_object(resp)
                    
                    if extracted_data is None:
                        extracted_data = {"is_correct": False, "feedback": "Error processing code."}
                    
                    st.session_state[CODING_FEEDBACK_KEY] = extracted_data
                    st.rerun() 

    # 5. Feedback & Navigation Display
    if feedback_state:
        if feedback_state.get('is_correct'):
            if not is_already_solved:
                st.balloons()
            
            st.success(f"MASTERY ACHIEVED! {feedback_state.get('feedback', 'Good job!')}")
            
            if st.button("Continue to Next Topic", type="primary"):
                if not is_topic_mastered:
                    db.update_bkt_model(user_id, subject, viewing_id, True)
                
                next_topic = curriculum.get_next_topic(subject, viewing_id)
                if next_topic:
                    st.session_state.viewing_topic_id = next_topic['id']
                else:
                    st.success("Course Complete! Go to Assignments.")
                
                keys_to_clear = [k for k in st.session_state.keys() if k.startswith('bdi_')]
                for k in keys_to_clear: del st.session_state[k]
                st.rerun()
        else:
            msg = feedback_state.get('feedback', 'An unknown error occurred.')
            st.error(f"Try Again: {msg}")

# --- Chat (Agentic Persona) ---
st.markdown("---")
st.header("💬 AI Tutor Chat")
if user_prompt := st.chat_input("Ask me anything about this topic..."):
    with st.chat_message("user"): st.write(user_prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            context_prompt = f"""
            You are a personalized tutor agent.
            Current Topic: {current_topic_name}.
            Student Level: {helpers.get_ability_level(progress_data['irt_theta_initial'])}.
            Question: {user_prompt}
            """
            response = llm.ask_ai(context_prompt, language=subject)
            st.write(response)