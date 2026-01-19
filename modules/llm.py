import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1", 
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

def extract_json_object(text):
    """Helper to extract JSON from LLM response."""
    if not text: return None
    match = re.search(r'\{.*?\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None

def ask_ai(prompt, language="text"):
    """
    Standard generation function.
    """
    system_message = f"You are an expert tutor for the {language.capitalize()} programming language. Provide clear, concise, and accurate information."

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=600,
            temperature=0.5,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error connecting to AI: {str(e)}"

def agent_analyze_error(topic, question, wrong_answer, correct_answer, student_level):
    """
    AGENTIC REASONING FUNCTION.
    Analyzes specific mistakes.
    """
    system_message = "You are a Senior AI Pedagogical Agent. Your goal is to diagnose student misconceptions accurately."
    
    prompt = f"""
    Context:
    - Subject: {topic}
    - Student Level: {student_level}
    
    SPECIFIC DATA:
    - Question asked: "{question}"
    - The Student Answered: "{wrong_answer}"
    - The Correct Answer is: "{correct_answer}"

    TASK:
    1. Compare the Student Answer to the Correct Answer.
    2. Identify WHY they are different (Logic error? Syntax? Guessing?).
    3. Select the ONE best remediation strategy:
       - 'Analogy': For abstract concepts.
       - 'Step_by_Step': For logic/math errors.
       - 'Code_Comparison': For syntax errors.
       - 'Simple_Explanation': For facts/definitions.

    OUTPUT JSON ONLY:
    {{
        "diagnosis": "A short sentence explaining the specific mistake.",
        "strategy": "The_Selected_Strategy"
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3, # Low temp for precision
        )
        return extract_json_object(response.choices[0].message.content)
    except Exception:
        return {"strategy": "Simple_Explanation", "diagnosis": "Let's review the core concept."}