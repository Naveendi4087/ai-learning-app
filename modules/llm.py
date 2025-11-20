import openai
import os
from dotenv import load_dotenv

load_dotenv()

client = openai.OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=os.getenv("OPENROUTER_API_KEY"),
)

def ask_ai(prompt, language="text"):
    """
    Sends a prompt to the LLM and gets a response.
    The 'language' parameter here is just for the system message, not for code generation.
    """
    system_message = f"You are an expert tutor for the {language.capitalize()} programming language. Provide clear, concise, and accurate information. If JSON is requested, provide only valid JSON."

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=400,
        temperature=0.5,
    )
    
    return response.choices[0].message.content